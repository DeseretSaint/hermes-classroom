"""Bounded conversation practice: declaration validation, directive, and the session log.

A practice is a *check property*, not a lesson kind (``docs/CONVERSATION-PRACTICE.md`` §2):

* the declaration rides in ``checks.stimulus_json.practice``;
* the target expressions are answer key and live only in ``checks.reference_json``;
* the rubric is synthesized by the backend, one criterion per target plus the turn count;
* the session (``practice_sessions``) and its turns (``practice_turns``) are this module's
  only storage, and grading reads the stored **learner** turns.

Nothing here calls a provider. The tutor's opening line is authored, so starting a practice
spends nothing, and the directive carries no grading power.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from . import db

#: Frozen chat directive (§6.1). ``turn.pre_turn``'s practice branch returns this instead of the
#: normal continuation prompt; it is appended with the existing ``prompts.CHAT_CAPABILITY_RULE``.
PRACTICE_DIRECTIVE = (
    "Coursebook practice is active. Scene: {scenario}. You are {tutor_role}; the learner is "
    "{learner_role}.\n"
    "Stay in character for the whole practice. Reply in the target language at the learner's "
    "level, one short turn at a time, and ask at most one question per turn.\n"
    "This is learner turn {n} of at most {max}. {targets_line}\n"
    "Do not grade, do not score, do not say whether the learner has passed, and do not claim the "
    "practice is a success or a failure: the backend grades the transcript after End practice, and "
    "nothing you write is read by the grader.\n"
    "Do not break character to explain grammar unless the learner asks for help. When they ask, "
    "give one short scaffold, in character.\n"
    "When the learner reaches the last turn, close the scene, say the practice is complete and stop."
)

TARGETS_LINE_VISIBLE = "The learner is practising these expressions: {labels}."
TARGETS_LINE_HIDDEN = (
    "Do not list the target expressions and do not translate them: the learner was not shown them."
)

MIN_TURNS = 3
MAX_TURNS = 5
MIN_TARGETS = 2
MAX_TARGETS = 5
MAX_CLAUSES = 8
MAX_TURN_TEXT = 2000
MAX_TUTOR_TEXT = 8000

TARGET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")

SESSION_STATES = ("active", "graded", "cancelled", "abandoned")


class PracticeDeclarationError(ValueError):
    """A practice declaration (or its key) was refused. ``reason`` is the frozen contract reason."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


def normalize_label(value: str) -> str:
    """Case/space/punctuation-insensitive label comparison, matching ``validators.normalize_text``."""
    from . import validators

    return validators.normalize_text(value)


def declaration(stimulus: Any) -> dict[str, Any] | None:
    """The stored practice declaration, or ``None`` when this check is not a practice."""
    if not isinstance(stimulus, dict):
        return None
    practice = stimulus.get("practice")
    return practice if isinstance(practice, dict) else None


def _text(value: Any, minimum: int, maximum: int) -> bool:
    return isinstance(value, str) and minimum <= len(value.strip()) <= maximum


def _turn_range(practice: dict[str, Any]) -> tuple[int, int]:
    turns = practice.get("turns")
    if not isinstance(turns, dict):
        raise PracticeDeclarationError(
            "practice_turn_range", "a practice declares turns.min and turns.max as integers."
        )
    low, high = turns.get("min"), turns.get("max")
    if (
        not isinstance(low, int)
        or isinstance(low, bool)
        or not isinstance(high, int)
        or isinstance(high, bool)
        or not (MIN_TURNS <= low <= high <= MAX_TURNS)
    ):
        raise PracticeDeclarationError(
            "practice_turn_range",
            f"a practice holds between {MIN_TURNS} and {MAX_TURNS} learner turns, with min <= max.",
        )
    return low, high


def validate_declaration(
    stimulus: Any,
    reference: Any,
    rubric: Any,
    *,
    evidence_target: str,
    recipe: str | None = None,
    practice_check_already: bool = False,
) -> dict[str, Any]:
    """Validate one stored practice declaration and its key. Returns the declaration.

    Every rule is a refusal with a named reason (§3.1). Both check writers call this before a row
    is inserted, so a malformed practice can never reach a learner.
    """
    practice = declaration(stimulus)
    if practice is None:
        raise PracticeDeclarationError(
            "practice_malformed_declaration", "the stimulus carries no practice declaration."
        )
    if not _text(practice.get("scenario"), 3, 300):
        raise PracticeDeclarationError(
            "practice_malformed_declaration", "a practice names a scenario of 3 to 300 characters."
        )
    if not _text(practice.get("learner_role"), 3, 120):
        raise PracticeDeclarationError(
            "practice_malformed_declaration", "a practice names the learner's role in 3 to 120 characters."
        )
    if not _text(practice.get("tutor_role"), 3, 120):
        raise PracticeDeclarationError(
            "practice_malformed_declaration", "a practice names the tutor's role in 3 to 120 characters."
        )
    if not _text(practice.get("opening"), 1, 300):
        raise PracticeDeclarationError(
            "practice_malformed_declaration", "a practice names an opening line of 1 to 300 characters."
        )
    if not isinstance(practice.get("targets_visible"), bool):
        raise PracticeDeclarationError(
            "practice_malformed_declaration", "targets_visible must be a boolean."
        )
    low, high = _turn_range(practice)

    targets = practice.get("targets")
    if not isinstance(targets, list) or not (MIN_TARGETS <= len(targets) <= MAX_TARGETS):
        raise PracticeDeclarationError(
            "practice_targets_invalid",
            f"a practice declares {MIN_TARGETS} to {MAX_TARGETS} target expressions.",
        )
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    for target in targets:
        if not isinstance(target, dict):
            raise PracticeDeclarationError("practice_targets_invalid", "each target is an object.")
        target_id = target.get("id")
        label = target.get("label")
        if not isinstance(target_id, str) or not TARGET_ID.match(target_id) or target_id in seen_ids:
            raise PracticeDeclarationError(
                "practice_targets_invalid", "target ids are unique and use the identifier alphabet."
            )
        if not isinstance(label, str) or not (1 <= len(label.strip()) <= 120):
            raise PracticeDeclarationError(
                "practice_targets_invalid", "each target label is 1 to 120 characters."
            )
        key = normalize_label(label)
        if key in seen_labels:
            raise PracticeDeclarationError(
                "practice_targets_invalid", "target labels are unique after normalisation."
            )
        seen_ids.add(target_id)
        seen_labels.add(key)

    angle = practice.get("rubric_angle")
    if evidence_target != "production":
        raise PracticeDeclarationError(
            "practice_evidence_target",
            "a conversation practice belongs to an objective with the production evidence target.",
        )
    try:
        from . import policy, rubrics, validators

        profile_ok = angle in policy.RUBRIC_PROFILES and rubrics.serves(str(angle), evidence_target)
    except Exception:  # noqa: BLE001 - an unreadable profile set is a refusal, never a pass
        profile_ok = False
    if not profile_ok:
        raise PracticeDeclarationError(
            "practice_rubric_off_profile",
            "a practice names a rubric profile that serves this objective's evidence target.",
        )
    if recipe == "parent":
        raise PracticeDeclarationError(
            "practice_not_available_for_recipe",
            "a parent-recipe course records observations, not conversation practice.",
        )
    if practice_check_already:
        raise PracticeDeclarationError(
            "practice_duplicate_in_course", "a course may declare at most one conversation practice."
        )
    stored_format = str((stimulus or {}).get("format") or "text")
    if stored_format != "text":
        raise PracticeDeclarationError(
            "practice_check_shape", "a practice is a quiz delivered as text."
        )

    reference = reference if isinstance(reference, dict) else {}
    if reference.get("kind") != "conversation":
        raise PracticeDeclarationError(
            "practice_check_shape", "a practice stores its key as a conversation reference."
        )
    declared = {target["id"] for target in targets}
    reference_targets = reference.get("targets")
    if not isinstance(reference_targets, list):
        raise PracticeDeclarationError(
            "practice_targets_invalid", "the conversation reference declares targets."
        )
    reference_ids = [str(item.get("id")) for item in reference_targets if isinstance(item, dict)]
    if sorted(reference_ids) != sorted(declared) or len(reference_ids) != len(declared):
        raise PracticeDeclarationError(
            "practice_targets_invalid",
            "every declaration target id appears exactly once in the key, and no others.",
        )
    if int(reference.get("min_turns", -1)) != low or int(reference.get("max_turns", -1)) != high:
        raise PracticeDeclarationError(
            "practice_turn_range", "the key's turn range matches the declared turns."
        )
    for item in reference_targets:
        _validate_clauses(item.get("match"))

    rubric = rubric if isinstance(rubric, dict) else {}
    if rubric.get("profile") != angle:
        raise PracticeDeclarationError(
            "practice_rubric_off_profile", "rubric.profile and rubric_angle must be the same value."
        )
    criteria = rubric.get("criteria")
    if not isinstance(criteria, list) or len(criteria) != len(targets) + 1:
        raise PracticeDeclarationError(
            "practice_targets_invalid",
            "the rubric has one criterion per target plus the turn count, synthesized by the backend.",
        )
    detectors = [str((item.get("detector") or {}).get("kind") or "") for item in criteria if isinstance(item, dict)]
    if detectors.count("target_phrase") != len(targets) or detectors.count("turn_count") != 1:
        raise PracticeDeclarationError(
            "practice_targets_invalid",
            "every criterion names a known detector: target_phrase or turn_count.",
        )
    try:
        from . import rubrics

        problems = rubrics.validate_rubric(str(angle), criteria, evidence_target)
    except Exception:  # noqa: BLE001
        problems = ["the rubric could not be validated"]
    if problems:
        raise PracticeDeclarationError("practice_targets_invalid", "; ".join(str(p) for p in problems))
    return practice


def _validate_clauses(clauses: Any) -> None:
    if not isinstance(clauses, list) or not (1 <= len(clauses) <= MAX_CLAUSES):
        raise PracticeDeclarationError(
            "practice_targets_invalid", "each target holds 1 to 8 match clauses."
        )
    for clause in clauses:
        if not isinstance(clause, dict):
            raise PracticeDeclarationError("practice_targets_invalid", "a clause is an object.")
        kind = clause.get("type")
        value = clause.get("value")
        if kind == "exact":
            if not isinstance(value, str) or not value.strip() or len(value) > 300:
                raise PracticeDeclarationError(
                    "practice_targets_invalid", "an exact clause is a non-empty string of at most 300 characters."
                )
        elif kind == "regex":
            if not isinstance(value, str) or not value or len(value) > 300:
                raise PracticeDeclarationError(
                    "practice_targets_invalid", "a regex clause is a pattern of at most 300 characters."
                )
            try:
                compiled = re.compile(value)
            except re.error as exc:
                raise PracticeDeclarationError(
                    "practice_targets_invalid", f"a regex clause does not compile: {exc}"
                ) from exc
            if compiled.search(""):
                raise PracticeDeclarationError(
                    "practice_targets_invalid", "a regex clause matches the empty string."
                )
        else:
            raise PracticeDeclarationError(
                "practice_targets_invalid", "a clause is either exact or regex."
            )


def synthesize_rubric(practice: dict[str, Any]) -> dict[str, Any]:
    """The backend's rubric for a practice: one target criterion each, plus the turn count."""
    low, high = _turn_range(practice)
    criteria = [
        {
            "id": str(target["id"]),
            "criterion": f"Produces the target expression {target['id']}",
            "detector": {"kind": "target_phrase", "target_id": str(target["id"])},
        }
        for target in practice["targets"]
    ]
    criteria.append(
        {
            "id": "turns",
            "criterion": f"Holds the exchange for at least {low} and at most {high} learner turns",
            "detector": {"kind": "turn_count"},
        }
    )
    return {"profile": str(practice["rubric_angle"]), "pass_rule": "all", "criteria": criteria}


def split_targets(authored: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Split the author's one target list into the declaration labels and the sealed key."""
    declaration_targets: list[dict[str, str]] = []
    key_targets: list[dict[str, Any]] = []
    for target in authored or []:
        declaration_targets.append({"id": str(target["id"]), "label": str(target["label"])})
        key_targets.append({"id": str(target["id"]), "match": [dict(c) for c in target.get("match") or []]})
    return declaration_targets, key_targets


def visible_view(practice: dict[str, Any]) -> dict[str, Any]:
    """Project a stored declaration for ``check.get``. Labels are withheld when not shown."""
    visible = bool(practice.get("targets_visible"))
    targets = [
        {"id": str(target["id"]), **({"label": str(target["label"])} if visible else {})}
        for target in practice.get("targets") or []
    ]
    return {
        "scenario": str(practice.get("scenario") or ""),
        "learner_role": str(practice.get("learner_role") or ""),
        "tutor_role": str(practice.get("tutor_role") or ""),
        "turns": {"min": int((practice.get("turns") or {}).get("min", MIN_TURNS)),
                  "max": int((practice.get("turns") or {}).get("max", MIN_TURNS))},
        "targets": targets,
        "targets_visible": visible,
        "rubric_angle": str(practice.get("rubric_angle") or ""),
        "opening": str(practice.get("opening") or ""),
    }


def directive_for(practice: dict[str, Any], learner_turn: int) -> str:
    """The frozen in-character directive for the next learner turn."""
    labels = ", ".join(str(target["label"]) for target in practice.get("targets") or [])
    targets_line = (
        TARGETS_LINE_VISIBLE.format(labels=labels)
        if practice.get("targets_visible")
        else TARGETS_LINE_HIDDEN
    )
    return PRACTICE_DIRECTIVE.format(
        scenario=str(practice.get("scenario") or ""),
        tutor_role=str(practice.get("tutor_role") or ""),
        learner_role=str(practice.get("learner_role") or ""),
        n=learner_turn,
        max=int((practice.get("turns") or {}).get("max", MIN_TURNS)),
        targets_line=targets_line,
    )


# ── the durable session ─────────────────────────────────────────────────────


def turn_nonce(session_id: str, text: str, revision: int) -> str:
    material = f"{session_id}\x00{int(revision)}\x00{text}"
    return "ptn-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def transcript_hash(turns: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        [{"speaker": t["speaker"], "text": t["text"]} for t in turns],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_transcript(learner_turns: list[str]) -> str:
    return "\n".join(f"{index + 1}. {text}" for index, text in enumerate(learner_turns))


def active_session(connection, *, lesson_run_id: str, check_id: str | None = None):
    if check_id:
        return connection.execute(
            "SELECT * FROM practice_sessions WHERE lesson_run_id = ? AND check_id = ? AND state = 'active'"
            " ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (lesson_run_id, check_id),
        ).fetchone()
    return connection.execute(
        "SELECT * FROM practice_sessions WHERE lesson_run_id = ? AND state = 'active'"
        " ORDER BY started_at DESC, rowid DESC LIMIT 1",
        (lesson_run_id,),
    ).fetchone()


def latest_session(connection, *, enrollment_id: str, objective_id: str):
    return connection.execute(
        "SELECT * FROM practice_sessions WHERE enrollment_id = ? AND objective_id = ?"
        " ORDER BY started_at DESC, rowid DESC LIMIT 1",
        (enrollment_id, objective_id),
    ).fetchone()


def session_for_check(connection, *, enrollment_id: str, check_id: str):
    return connection.execute(
        "SELECT * FROM practice_sessions WHERE enrollment_id = ? AND check_id = ?"
        " ORDER BY started_at DESC, rowid DESC LIMIT 1",
        (enrollment_id, check_id),
    ).fetchone()


def turns_for(connection, session_id: str) -> list[dict[str, Any]]:
    return [
        {"ordinal": int(row["ordinal"]), "speaker": row["speaker"], "text": row["text"]}
        for row in connection.execute(
            "SELECT ordinal, speaker, text FROM practice_turns WHERE session_id = ? ORDER BY ordinal",
            (session_id,),
        )
    ]


def learner_turns(turns: list[dict[str, Any]]) -> list[str]:
    return [str(turn["text"]) for turn in turns if turn.get("speaker") == "learner"]


def start_session(
    connection,
    *,
    enrollment_id: str,
    objective_id: str,
    check,
    lesson_run_id: str,
    opening: str,
    now: str,
) -> Any:
    """Create one active session with the authored opening as its only turn, revision 1."""
    session_id = _new_id("prc")
    connection.execute(
        "INSERT INTO practice_sessions (id, enrollment_id, objective_id, check_id, check_version,"
        " lesson_run_id, state, attempt_id, revision, started_at, ended_at, end_reason)"
        " VALUES (?, ?, ?, ?, ?, ?, 'active', NULL, 1, ?, NULL, NULL)",
        (session_id, enrollment_id, objective_id, check["id"], int(check["version"]), lesson_run_id, now),
    )
    connection.execute(
        "INSERT INTO practice_turns (id, session_id, ordinal, speaker, text, nonce, created_at)"
        " VALUES (?, ?, 1, 'tutor', ?, NULL, ?)",
        (_new_id("ptu"), session_id, opening[:MAX_TUTOR_TEXT], now),
    )
    return connection.execute("SELECT * FROM practice_sessions WHERE id = ?", (session_id,)).fetchone()


def append_turn(connection, session, *, speaker: str, text: str, nonce: str | None, now: str) -> tuple[bool, str]:
    """Append one turn inside a write transaction. Never appends twice for one nonce."""
    if nonce is not None:
        existing = connection.execute(
            "SELECT 1 FROM practice_turns WHERE session_id = ? AND nonce = ?", (session["id"], nonce)
        ).fetchone()
        if existing is not None:
            return False, "duplicate_nonce"
    row = connection.execute(
        "SELECT COALESCE(MAX(ordinal), 0) AS ordinal FROM practice_turns WHERE session_id = ?",
        (session["id"],),
    ).fetchone()
    ordinal = int(row["ordinal"]) + 1
    limit = MAX_TURN_TEXT if speaker == "learner" else MAX_TUTOR_TEXT
    connection.execute(
        "INSERT INTO practice_turns (id, session_id, ordinal, speaker, text, nonce, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (_new_id("ptu"), session["id"], ordinal, speaker, text[:limit], nonce, now),
    )
    connection.execute(
        "UPDATE practice_sessions SET revision = revision + 1 WHERE id = ?", (session["id"],)
    )
    return True, "appended"


def end_session(connection, session_id: str, *, state: str, attempt_id: str | None,
                reason: str | None, now: str) -> None:
    connection.execute(
        "UPDATE practice_sessions SET state = ?, attempt_id = ?, ended_at = ?, end_reason = ?"
        " WHERE id = ?",
        (state, attempt_id, now, reason, session_id),
    )


def abandon_for_run(connection, lesson_run_id: str, *, reason: str, now: str) -> int:
    """Mark every active session on a run abandoned (detach, fresh run, pause)."""
    rows = connection.execute(
        "SELECT id FROM practice_sessions WHERE lesson_run_id = ? AND state = 'active'",
        (lesson_run_id,),
    ).fetchall()
    for row in rows:
        connection.execute(
            "UPDATE practice_sessions SET state = 'abandoned', ended_at = ?, end_reason = ? WHERE id = ?",
            (now, reason, row["id"]),
        )
    return len(rows)


def state_view(connection, session) -> dict[str, Any]:
    """The revision-0 read: transcript, counters, awaiting_tutor, one attempt reference."""
    turns = turns_for(connection, session["id"])
    learners = learner_turns(turns)
    practice = _practice_of(connection, session)
    maximum = int((practice.get("turns") or {}).get("max", MAX_TURNS))
    last = turns[-1] if turns else None
    return {
        "session_id": session["id"],
        "check_id": session["check_id"],
        "check_version": int(session["check_version"]),
        "state": session["state"],
        "learner_turns": len(learners),
        "remaining": max(0, maximum - len(learners)),
        "awaiting_tutor": bool(last is not None and last["speaker"] == "learner"),
        "transcript": turns,
        "attempt_id": session["attempt_id"],
        "verdict": _verdict_of(connection, session["attempt_id"]),
        "criteria": _criteria_of(connection, session["attempt_id"]),
    }


def _practice_of(connection, session) -> dict[str, Any]:
    row = connection.execute(
        "SELECT stimulus_json FROM checks WHERE id = ?", (session["check_id"],)
    ).fetchone()
    if row is None:
        return {}
    try:
        return declaration(_json_load(row["stimulus_json"], {})) or {}
    except Exception:  # noqa: BLE001 - an unreadable declaration is an empty one, never a pass
        return {}


def _verdict_of(connection, attempt_id: str | None) -> str | None:
    if not attempt_id:
        return None
    row = connection.execute("SELECT verdict FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    return str(row["verdict"]) if row is not None else None


def _criteria_of(connection, attempt_id: str | None) -> list[dict[str, Any]]:
    if not attempt_id:
        return []
    row = connection.execute("SELECT criteria_json FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        return []
    loaded = _json_load(row["criteria_json"], [])
    return loaded if isinstance(loaded, list) else []


def _json_load(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


def _new_id(prefix: str) -> str:
    import uuid

    return f"{prefix}_{uuid.uuid4().hex}"
