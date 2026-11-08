"""Inbound classification, the pre-turn gate, and the continuation hand-off.

This module is the *adapter* half of the grading gate (``PREBUILD_SPEC.md`` §8, ``AUDIT.md`` R2):

* :func:`classify_inbound` decides whether a chat message is an answer, a clarification, a hint
  request, a skip/override, or ordinary conversation. Ambiguity resolves to ``clarification`` —
  never to a failed answer — because a learner who asks a question must not lose a retry.
* :func:`pre_turn` runs inside ``pre_llm_call``: it resolves the session binding by its *stored*
  id, submits a real ``attempt.submit`` through the same dispatcher the UI uses, and only after
  the transition is committed returns the teaching context. Any grading failure returns a local
  ``needs_retry`` block, so no inference runs against ungraded state.
* :func:`continuation_prompt` renders the public verdict/next action for **Continue lesson**. It
  never contains the reference answer, the rubric's answer key, or any grading model output that
  was not already committed to the attempt row.
* :func:`record_assistant_snapshot` is the post-turn observer. It carries the pre-turn revision
  and turn nonce as a compare-and-swap fence: a late callback from an abandoned turn cannot write
  into a newer revision.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from . import api, db, evidence, prompts, segments

# ── classification ──────────────────────────────────────────────────────────

#: The five inbound kinds the product promises plus ordinary conversation.
INBOUND_KINDS: tuple[str, ...] = (
    "answer",
    "clarification",
    "hint",
    "skip",
    "override",
    "chat",
)

#: Explicit pane controls are deterministic; free text goes through the bounded patterns below.
EXPLICIT_CONTROLS: dict[str, str] = {
    "submit_answer": "answer",
    "clarify": "clarification",
    "hint": "hint",
    "show_answer": "hint",
    "skip": "skip",
    "override": "override",
    "chat": "chat",
}

_HINT = re.compile(
    r"\b(hint|clue|nudge|point me|give me a (small )?(hint|clue|start)|"
    r"help me get started|what'?s the first step)\b",
    re.IGNORECASE,
)
_SHOW_ANSWER = re.compile(
    r"\b(show (me )?(the )?answer|just tell me|give me the answer|reveal|"
    r"what'?s the (correct )?answer|tell me the answer)\b",
    re.IGNORECASE,
)
_SKIP = re.compile(r"\b(skip( this)?|pass( on this)?|next (one|question)|move on)\b", re.IGNORECASE)
_OVERRIDE = re.compile(
    r"\b(override|i'?ll come back|mark it (done|complete)|i know this already|"
    r"unlock|let me through)\b",
    re.IGNORECASE,
)
_CLARIFY = re.compile(
    r"(\?|^\s*(what|why|how|which|who|when|where|does|do|is|are|can|could|should|would)\b|"
    r"\b(i (do not|don'?t) understand|confus(ed|ing)|not sure what|rephrase|"
    r"clarify|explain (the|this) (question|task|prompt|word)|what do you mean|"
    r"repeat (that|the question)|again please|in (romaji|english|japanese))\b)",
    re.IGNORECASE,
)
_CHAT = re.compile(
    r"^\s*(hi|hello|hey|thanks|thank you|ok(ay)?|good (morning|evening)|"
    r"how are you|nice|got it|bye)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Classification:
    """What the learner meant, and what that is allowed to do to the evidence map."""

    kind: str
    #: ``True`` when the message asked for the answer itself, not just a nudge.
    shows_answer: bool = False
    #: Deterministic controls and unambiguous phrases are ``certain``; the rest is ``bounded``.
    confidence: str = "bounded"
    reason: str = ""
    #: Only an ``answer`` classification may create an attempt.
    creates_attempt: bool = field(default=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "shows_answer": self.shows_answer,
            "confidence": self.confidence,
            "creates_attempt": self.creates_attempt,
        }


def classify_inbound(
    text: str | None,
    *,
    open_check: bool = True,
    explicit: str | None = None,
) -> Classification:
    """Classify one inbound chat message before any attempt exists.

    Ordering is deliberate: an explicit control wins, then answer-request/hint (they change the
    evidence class of the *next* answer), then skip/override, then clarification, then chat.
    Anything left over inside an open check is an answer. With no open check there is nothing to
    grade, so the message is conversation.
    """
    if explicit is not None:
        kind = EXPLICIT_CONTROLS.get(str(explicit))
        if kind is None:
            raise ValueError(f"unknown explicit control {explicit!r}")
        return Classification(
            kind=kind,
            shows_answer=explicit == "show_answer",
            confidence="certain",
            reason=f"explicit control {explicit}",
            creates_attempt=kind == "answer" and open_check,
        )

    body = (text or "").strip()
    if not body:
        return Classification("clarification", confidence="certain", reason="empty message")

    if not open_check:
        # No open check: nothing to attempt. A skip/override still means something to the lesson
        # flow, so keep those; everything else is conversation.
        if _SKIP.search(body):
            return Classification("skip", confidence="bounded", reason="skip phrase")
        if _OVERRIDE.search(body):
            return Classification("override", confidence="bounded", reason="override phrase")
        return Classification("chat", confidence="bounded", reason="no open check")

    if _SHOW_ANSWER.search(body):
        return Classification("hint", shows_answer=True, reason="answer request")
    if _HINT.search(body):
        return Classification("hint", reason="hint request")
    if _SKIP.search(body):
        return Classification("skip", reason="skip phrase")
    if _OVERRIDE.search(body):
        return Classification("override", reason="override phrase")
    if _CLARIFY.search(body):
        return Classification("clarification", reason="question form")
    if _CHAT.search(body):
        return Classification("chat", reason="greeting/meta")
    return Classification("answer", reason="free text inside an open check", creates_attempt=True)


# ── gate plumbing ───────────────────────────────────────────────────────────


def turn_nonce(session_id: str, user_message: str, *, revision: int) -> str:
    """A per-turn nonce. Stable for the same message at the same revision, never for a re-answer."""
    digest = hashlib.sha256(f"{session_id}\x00{revision}\x00{user_message}".encode("utf-8")).hexdigest()
    return f"n_{digest[:32]}"


def idempotency_key(session_id: str, nonce: str) -> str:
    """Key shaped for ``cb.rpc`` (``^[A-Za-z0-9][A-Za-z0-9_.:-]*$``, 8..192 chars)."""
    digest = hashlib.sha256(f"{session_id}\x00{nonce}".encode("utf-8")).hexdigest()
    return f"turn.{digest[:48]}"


def _safe_operation_id(value: str) -> str:
    """``cb.rpc`` allows ``^[A-Za-z0-9][A-Za-z0-9_-]*$`` — a method name with dots is not one."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", str(value))
    cleaned = cleaned.lstrip("-_")[:120]
    return cleaned or "hook-operation"


def _envelope(method: str, payload: dict[str, Any], *, operation_id: str,
              idempotency_key: str | None = None, expected_revision: int | None = None) -> dict[str, Any]:
    return {
        "contract": api.RPC_CONTRACT,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "method": method,
        "operation_id": _safe_operation_id(operation_id),
        "idempotency_key": idempotency_key,
        "expected_revision": expected_revision,
        "payload": payload,
    }


def _binding_row(session_id: str) -> Any:
    """The live binding row for a durable stored id, read from the kernel's own table.

    The gate is backend-internal, so it reads the row it needs (``lesson_run_id``/``objective_id``
    are v2 columns) rather than depending on the RPC view's field set. Resolution is still by
    stored id only: a runtime id is never a stand-in (``AUDIT.md`` R1).
    """
    if not session_id:
        return None
    if not db.store_exists():
        # No store, no binding: an unprovisioned profile is not governed. Opening a connection
        # here would create an empty database and then fail on a missing table.
        return None
    with db.read() as connection:
        return connection.execute(
            "SELECT * FROM bindings WHERE stored_session_id = ?"
            " ORDER BY (status = 'active') DESC, revision DESC, updated_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()


def _binding_for_session(dispatch: Callable[[Any], dict[str, Any]], session_id: str) -> dict[str, Any] | None:
    """Resolve by the durable stored id only. A runtime id is never a stand-in (``AUDIT.md`` R1)."""
    row = _binding_row(session_id)
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _open_check(connection, objective_id: str) -> Any:
    return connection.execute(
        "SELECT * FROM checks WHERE objective_id = ? AND state = 'open'"
        " ORDER BY version DESC LIMIT 1",
        (objective_id,),
    ).fetchone()


def _enrollment_revision(connection, enrollment_id: str) -> int:
    row = connection.execute("SELECT revision FROM enrollments WHERE id = ?", (enrollment_id,)).fetchone()
    return int(row["revision"]) if row is not None else 0


def _record_assist(connection, *, enrollment_id: str, objective_id: str, attempt_id: str | None,
                   kind: str, evidence_class: str) -> str:
    """A hint is a durable L1 event, recorded *before* the answer it contaminates.

    One writer with ``lesson.assist`` (:func:`coursebook.evidence.record_assist`): the chat hook
    and the Desktop pane must write the same row shape for the same learner action.
    """
    return evidence.record_assist(
        connection,
        enrollment_id=enrollment_id,
        objective_id=objective_id,
        attempt_id=attempt_id,
        kind=kind,
        evidence_class=evidence_class,
    )


def _random_evidence_id() -> str:
    import uuid

    return f"evd_{uuid.uuid4().hex}"


@dataclass
class GateOutcome:
    """What ``pre_llm_call`` is allowed to return to Hermes."""

    #: ``None`` means "no Coursebook injection"; otherwise the hook return value.
    hook: dict[str, Any] | None
    #: Set when the gate observed and graded something (used by the post-turn observer).
    classification: Classification | None = None
    nonce: str | None = None
    revision: int | None = None
    verdict: str | None = None
    attempt_id: str | None = None


def pre_turn(
    session_id: str,
    user_message: str,
    *,
    dispatch: Callable[[Any], dict[str, Any]] | None = None,
    deadline_ms: int = 8000,
    explicit: str | None = None,
    now: Callable[[], float] = time.monotonic,
) -> GateOutcome:
    """The pre-turn gate: classify, then grade through ``attempt.submit`` before teaching.

    Nothing here writes when there is no active binding, no open check, or the message is
    conversation/clarification. A clarification therefore cannot consume a retry, and an
    ungraded answer cannot reach a teaching turn.
    """
    dispatch = dispatch or api.dispatch
    started = now()
    binding = _binding_for_session(dispatch, session_id)
    if binding is None or binding.get("status") != "active":
        return GateOutcome(hook=None)
    enrollment_id = binding.get("enrollment_id")
    objective_id = binding.get("objective_id")
    if not enrollment_id or not objective_id:
        # The binding is active but not attached to a section; nothing to gate.
        return GateOutcome(hook=None)

    with db.read() as connection:
        check = _open_check(connection, objective_id)
        revision = _enrollment_revision(connection, enrollment_id)
    classification = classify_inbound(user_message, open_check=check is not None, explicit=explicit)
    if not classification.creates_attempt and classification.kind not in ("hint", "skip", "override"):
        # Conversation and clarification pass through untouched: no attempt, no evidence, no retry.
        return GateOutcome(hook=None, classification=classification, revision=revision)

    nonce = turn_nonce(session_id, user_message, revision=revision)
    if classification.kind == "hint":
        with db.transaction() as connection:
            _record_assist(
                connection,
                enrollment_id=enrollment_id,
                objective_id=objective_id,
                attempt_id=None,
                kind="answer_shown" if classification.shows_answer else "hint_request",
                evidence_class="answer_shown" if classification.shows_answer else "hinted",
            )
        return GateOutcome(hook=None, classification=classification, nonce=nonce, revision=revision)

    if classification.kind in ("skip", "override"):
        if check is None:
            return GateOutcome(hook=None, classification=classification, revision=revision)
        response = dispatch(
            _envelope(
                "attempt.override",
                {
                    "enrollment_id": enrollment_id,
                    "check_id": check["id"],
                    "reason": "learner asked to move on" if classification.kind == "skip" else "learner override",
                },
                operation_id=f"hook.override.{nonce}",
                idempotency_key=idempotency_key(session_id, nonce),
                expected_revision=revision,
            )
        )
        if not response.get("ok"):
            return GateOutcome(
                hook={"action": "block", "message": _refusal_message(response)},
                classification=classification,
                nonce=nonce,
                revision=revision,
            )
        result = response["result"]
        return GateOutcome(
            hook={"context": continuation_prompt(verdict="not_yet", next_action=result.get("next_action", "complete_objective"),
                                                 evidence_class="override", objective_id=objective_id)},
            classification=classification,
            nonce=nonce,
            revision=int(response.get("revision", revision)),
            verdict="not_yet",
            attempt_id=result.get("attempt_id"),
        )

    # classification.kind == "answer"
    assert check is not None
    response = dispatch(
        _envelope(
            "attempt.submit",
            {
                "enrollment_id": enrollment_id,
                "check_id": check["id"],
                "check_version": int(check["version"]),
                "attempt_nonce": nonce,
                "answer": {"kind": "text", "text": user_message},
            },
            operation_id=f"hook.submit.{nonce}",
            idempotency_key=idempotency_key(session_id, nonce),
            expected_revision=revision,
        )
    )
    elapsed_ms = (now() - started) * 1000.0
    if not response.get("ok"):
        # A refusal (stale check/revision, unaudited check, detached binding, internal failure)
        # never advances state. Stop the turn locally instead of teaching over ungraded state.
        return GateOutcome(
            hook={"action": "block", "message": _refusal_message(response)},
            classification=classification,
            nonce=nonce,
            revision=revision,
        )
    result = response["result"]
    verdict = str(result.get("verdict"))
    if verdict == "needs_retry" or (verdict is None):
        return GateOutcome(
            hook={"action": "block", "message": _needs_retry_message()},
            classification=classification,
            nonce=nonce,
            revision=int(response.get("revision", revision)),
            verdict="needs_retry",
            attempt_id=result.get("attempt_id"),
        )
    if elapsed_ms > float(deadline_ms):
        # The grade committed, but it did not finish inside the hook budget. The durable result is
        # the truth; do not start a teaching turn on top of a late gate.
        return GateOutcome(
            hook={"action": "block", "message": _late_gate_message()},
            classification=classification,
            nonce=nonce,
            revision=int(response.get("revision", revision)),
            verdict=verdict,
            attempt_id=result.get("attempt_id"),
        )
    committed_revision = int(response.get("revision", revision))
    return GateOutcome(
        hook={
            "context": continuation_prompt(
                verdict=verdict,
                next_action=str(result.get("next_action", "continue")),
                evidence_class=str(result.get("evidence_class", "cold")),
                objective_id=objective_id,
            )
        },
        classification=classification,
        nonce=nonce,
        revision=committed_revision,
        verdict=verdict,
        attempt_id=result.get("attempt_id"),
    )


def _needs_retry_message() -> str:
    return (
        "Coursebook could not grade that answer just now, so this lesson has not advanced. "
        "The answer is saved. Try Continue lesson again in a moment — a grading outage never "
        "counts as a pass."
    )


def _late_gate_message() -> str:
    return (
        "Coursebook finished grading after this turn's time budget. Your result is saved; "
        "use Continue lesson to carry on from the committed verdict."
    )


def _refusal_message(response: dict[str, Any]) -> str:
    error = response.get("error") or {}
    code = str(error.get("code") or "INTERNAL_ERROR")
    if code in ("STALE_REVISION", "CHECK_STALE"):
        return (
            "This lesson moved on while your answer was in flight, so nothing was graded. "
            "Reload the check and answer again."
        )
    if code == "BINDING_NOT_ACTIVE":
        return "This chat is no longer bound to the lesson. Rebind it from the course pane before answering."
    if code == "POLICY_VIOLATION":
        return "This check is paused by its own audit and cannot be graded. Ask for a fresh check."
    return "Coursebook could not accept that answer, so nothing advanced. Retry from the course pane."


# ── continuation ────────────────────────────────────────────────────────────

_PUBLIC_VERDICT = {
    "pass": "correct",
    "partial": "partly right",
    "not_yet": "not yet",
    "needs_retry": "not graded yet",
    "clarification": "a question, not an answer",
}


def continuation_prompt(*, verdict: str, next_action: str, evidence_class: str = "cold",
                        objective_id: str | None = None) -> str:
    """Render the transition-specific continuation prompt.

    Contains the committed public verdict and the permitted next action only. No reference answer,
    no rubric internals, no provider text (``PREBUILD_SPEC.md`` §8).
    """
    label = _PUBLIC_VERDICT.get(verdict, "not graded")
    lines = [f"Coursebook result: {label}."]
    if verdict == "pass" and evidence_class != "cold":
        lines.append(
            "This pass does not count as independent evidence: the answer followed a hint or a "
            "shown answer. Access may move on, the evidence map stays honest."
        )
    elif verdict == "pass":
        lines.append("That counted as independent evidence for this objective.")
    elif evidence_class == "override":
        lines.append("Access was granted by an override. This is not mastery and is labelled as such.")
    action = {
        "complete_objective": "Teach the wrap-up for this objective, then move to the next section.",
        "complete_course": "Teach the course wrap-up.",
        "retry_attempt": "Give one different explanation or representation, then one fresh check. Do not repeat the same item.",
        "explain": "Answer the learner's question about the task without revealing the reference answer.",
        "select_alternative": "Offer an alternative check at the same evidence target.",
        "review_objective": "Summarise what is still unproven for this objective and offer a fresh check.",
        "await_override": "Explain the options: retry, a different explanation, or an override that grants access without evidence.",
        "retry_grading": "Do not teach yet; the answer is saved and grading must be retried.",
        "continue": "Continue the lesson.",
        "rebind_session": "Ask the learner to rebind this chat before continuing.",
    }.get(next_action, "Continue the lesson.")
    lines.append(action)
    if objective_id:
        lines.append(f"Objective: {objective_id}.")
    # Frozen chat directive (docs/ASSESSMENT-BREADTH.md §7.4). Contract-independent: it is chat
    # instruction text, never a check field.
    lines.append(prompts.CHAT_CAPABILITY_RULE)
    return " ".join(lines)


def continuation_key(attempt_id: str, *, action: str = "continue") -> str:
    """A new key per Continue action; retrying the same action never regrades or advances twice."""
    return f"continue.{attempt_id}.{action}"


# ── post-turn observer ──────────────────────────────────────────────────────


def reconcile_binding(session_id: str, *, cwd_fingerprint: str | None = None,
                      compression_tip: str | None = None) -> dict[str, Any]:
    """Bring the binding row in line with the live chat after compaction or a restart.

    * a *changed* cwd detaches governance (``AUDIT.md`` H1): the lesson is preserved, the chat is
      no longer authoritative;
    * a new compression tip is adopted so resume does not depend on the old thread shape;
    * a first-seen cwd is adopted, not treated as a change.

    The binding is resolved by stored id only, so restart resumes the exact lesson the learner
    opened rather than the most recent chat (``AUDIT.md`` R1).
    """
    if not session_id:
        return {"status": "unbound", "changed": False, "binding_id": None}
    if not db.store_exists():
        # Absent store means unbound, not failed: reconciliation is not a provisioning step.
        return {"status": "unbound", "changed": False, "binding_id": None}
    with db.transaction() as connection:
        binding = connection.execute(
            "SELECT * FROM bindings WHERE stored_session_id = ? ORDER BY revision DESC, updated_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if binding is None:
            return {"status": "unbound", "changed": False, "binding_id": None}
        status = str(binding["status"])
        updates: dict[str, Any] = {}
        if cwd_fingerprint and binding["cwd_fingerprint"]:
            if cwd_fingerprint != binding["cwd_fingerprint"] and status == "active":
                status = "detached"
                updates["status"] = status
        elif cwd_fingerprint and not binding["cwd_fingerprint"]:
            updates["cwd_fingerprint"] = cwd_fingerprint
        if compression_tip and compression_tip != binding["compression_tip"] and status == "active":
            updates["compression_tip"] = compression_tip
        if updates:
            updates["revision"] = int(binding["revision"]) + 1
            updates["updated_at"] = db.utcnow()
            assignments = ", ".join(f"{column} = ?" for column in updates)
            connection.execute(
                f"UPDATE bindings SET {assignments} WHERE id = ?",
                (*updates.values(), binding["id"]),
            )
        return {
            "status": status,
            "changed": bool(updates),
            "binding_id": binding["id"],
            "revision": int(updates.get("revision", binding["revision"])),
        }


def record_assistant_snapshot(*, session_id: str, assistant_response: str, nonce: str | None,
                             revision: int | None) -> bool:
    """Record the assistant turn as a teaching segment, fenced by revision.

    Returns ``True`` when written. A late callback (revision moved, no live nonce, unknown
    session) is discarded: it cannot rewrite a newer lesson state (``AUDIT.md`` R2).
    """
    if not session_id or not assistant_response or nonce is None or revision is None:
        return False
    with db.read() as connection:
        binding = connection.execute(
            "SELECT * FROM bindings WHERE stored_session_id = ? ORDER BY revision DESC, updated_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if binding is None or binding["status"] != "active" or not binding["lesson_run_id"]:
            return False
        enrollment = connection.execute(
            "SELECT revision FROM enrollments WHERE id = ?", (binding["enrollment_id"],)
        ).fetchone()
        if enrollment is None or int(enrollment["revision"]) != int(revision):
            # The lesson advanced since this turn started; this snapshot is late.
            return False
        ordinal_row = connection.execute(
            "SELECT COALESCE(MAX(ordinal), 0) AS ordinal FROM lesson_segments WHERE lesson_run_id = ?",
            (binding["lesson_run_id"],),
        ).fetchone()
    ordinal = int(ordinal_row["ordinal"]) + 1
    # One assistant turn is one teaching snapshot, but a segment over the cb.rpc cap made the
    # lesson page unreadable (D1). Long turns are stored as ordered pieces instead of truncated.
    pieces = segments.split_text(assistant_response[:20000])
    with db.transaction() as connection:
        current = connection.execute(
            "SELECT revision FROM enrollments WHERE id = ?", (binding["enrollment_id"],)
        ).fetchone()
        if current is None or int(current["revision"]) != int(revision):
            return False
        for piece in pieces:
            connection.execute(
                "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, artifact_id, source_id, created_at)"
                " VALUES (?, ?, ?, 'teaching', ?, NULL, NULL, ?)",
                (_random_evidence_id().replace("evd_", "seg_"), binding["lesson_run_id"], ordinal,
                 piece, db.utcnow()),
            )
            ordinal += 1
    return True


def record_snapshot_failure(*, session_id: str, nonce: str | None, detail: str,
                            attempts: int = 1) -> bool:
    """Write a durable ``hook_errors`` row for a teaching snapshot that could not be stored.

    ``post_llm_call`` is the only writer of a teaching segment (``kind='teaching'``), the durable
    record the Textbook and Guided views render. Before ``cb.db`` v10 a failed write was swallowed:
    the turn stayed in the chat transcript but vanished from the lesson page with no marker
    (H-114 F3). The hook still never gates the turn, so the loss is *recorded* here instead of
    raised — a row that ``binding.get`` reports as ``snapshot_failures`` for the run.

    Returns ``True`` when the loss was recorded. **Never raises**: it runs inside an exception
    handler, so a second failure must not escape into the host turn. ``False`` means the failure
    itself could not be persisted, which the caller logs at error level.

    It does not provision. A missing store means the pre-turn gate never ran, so there is no
    lesson to lose a snapshot from; the caller never reaches here in that case.
    """
    if not session_id or not db.store_exists():
        return False
    lesson_run_id: str | None = None
    try:
        with db.read() as connection:
            binding = connection.execute(
                "SELECT lesson_run_id FROM bindings WHERE stored_session_id = ?"
                " ORDER BY revision DESC, updated_at DESC LIMIT 1",
                (str(session_id),),
            ).fetchone()
            if binding is not None:
                lesson_run_id = binding["lesson_run_id"]
    except Exception:  # noqa: BLE001 - an unreadable binding must not lose the failure record
        lesson_run_id = None
    try:
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO hook_errors (id, kind, session_id, lesson_run_id, nonce, detail,"
                " attempts, created_at) VALUES (?, 'snapshot_write_failed', ?, ?, ?, ?, ?, ?)",
                (
                    _random_evidence_id().replace("evd_", "hke_"),
                    str(session_id),
                    lesson_run_id,
                    str(nonce) if nonce is not None else None,
                    str(detail)[:2000],
                    max(1, int(attempts)),
                    db.utcnow(),
                ),
            )
    except Exception:  # noqa: BLE001 - the observer is never the gate, even when logging fails
        return False
    return True


def snapshot_failures(*, lesson_run_id: str | None) -> dict[str, Any]:
    """Per-run count of lost teaching snapshots, for the ``binding.get`` read the pane makes.

    ``recorded`` is ``None`` — never ``0`` — when the count could not be read. A pane must be able
    to tell "no snapshot was lost" from "this build cannot say", or the diagnostics surface becomes
    the same silent falsehood this table exists to remove.
    """
    if not lesson_run_id or not db.store_exists():
        return {"recorded": None, "last_at": None}
    try:
        with db.read() as connection:
            present = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'hook_errors'"
            ).fetchone()
            if present is None:
                return {"recorded": None, "last_at": None}
            row = connection.execute(
                "SELECT COUNT(*) AS recorded, MAX(created_at) AS last_at FROM hook_errors"
                " WHERE lesson_run_id = ?",
                (str(lesson_run_id),),
            ).fetchone()
    except Exception:  # noqa: BLE001 - the pane read reports unknown rather than a false zero
        return {"recorded": None, "last_at": None}
    return {"recorded": int(row["recorded"] or 0), "last_at": row["last_at"]}

