"""The lesson-bound tutor backend (GM-011): bounded context, no tools, no state writes.

The right rail is a *lesson tutor*, not a general agent and not the authoring chat
(``docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md`` §7). This module is the whole backend policy:

* one thread per ``lesson_run_id`` (``tutor_threads``, UNIQUE), never a global chat or a host
  session id;
* the context envelope is built from the served lesson document, the authored glossary, the
  objective and the learner's own recent turns. It never reads ``checks.reference_json``,
  ``checks.rubric_json``, an expected response, a worked example answer or another learner;
* the model has **no tools**: the request carries a JSON answer and citation ids, and this module
  never imports a shell, browser, filesystem or authoring seam;
* citations are resolved against the blocks and course sources actually in context; an id that
  does not resolve is omitted, never rendered;
* while a check is open the final answer is withheld. The response names the existing assist
  policy so the UI can send the learner through ``lesson.assist``; this command writes no
  attempt, transition or evidence row;
* a provider failure is the named state ``provider_failure`` with no turn, never an empty or
  fabricated answer. Nothing is persisted for a failed call;
* ``mode=practice`` reuses the existing ``practice_sessions``/``practice_turns`` engine and the
  authoring the check already carries. Only learner turns reach ``conversation.grade_transcript``;
  tutor prose is never graded.

The module registers its two commands itself, exactly like ``engagement``: a build whose frozen
``cb.rpc`` lacks ``tutor.ask``/``tutor.history`` stays ``NOT_IMPLEMENTED`` instead of inventing a
method.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable, Iterable, Mapping

from . import db, generation, gm_contract, lesson_document, practice
from .contracts import method_names

#: This module exposes no tools. It is a value, not documentation: the test asserts it, and the
#: provider request is built without a tools/functions key at all.
TOOLS: tuple[str, ...] = ()

#: One bounded call. The answer is prose; citations are ids the backend resolves or drops.
CONTEXT_BLOCK_LIMIT = 40
CONTEXT_DEEP_CHARS = 1200
CONTEXT_TOTAL_CHARS = 12000
CONTEXT_TURNS = 6
CONTEXT_TURN_CHARS = 600
CONTEXT_GLOSSARY = 20
MAX_QUESTION = 2000
MAX_SELECTED = 600
MAX_ANSWER = 6000
MAX_CITATIONS = 8
MAX_HISTORY_TURNS = 200
TUTOR_PURPOSE = "coursebook.tutor.ask"
PROMPT_VERSION = "gm011-tutor-v1"
TUTOR_TIMEOUT_S = 45.0
TUTOR_MAX_TOKENS = 700

#: The one answer the tutor may give when the model tried to reveal a sealed answer.
WITHHELD_ANSWER = (
    "That would give away the answer while the check is open. Ask for a hint instead — the "
    "lesson's steps are still here to work through."
)

SYSTEM_PROMPT = """You are the Coursebook lesson tutor. You answer only about the lesson in the
context envelope. You have no tools: no shell, browser, file access, network, authoring or grading.

Rules:
- Use only the lesson blocks, the authored glossary, the objective and the learner's recent turns
  in the context. If you answer from general background, say so plainly and do not cite the lesson
  for it.
- Cite with the exact block ids and source ids from the context. Never invent an id, a quotation,
  a source or a page. An answer with no support may carry no citations.
- If check_open is true, do NOT state, spell out or paraphrase the final answer, an expected
  response or an answer key. Offer a scaffold: a question, a first step, an example of the same
  shape, or a pointer to the block that teaches it.
- You never grade, score, pass, fail or advance anything. The backend grades learner attempts.
- Be concise and concrete. No markdown tables, no tool calls, no authoring instructions."""

ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "citations"],
    "properties": {
        "answer": {"type": "string", "minLength": 1, "maxLength": MAX_ANSWER},
        "citations": {
            "type": "array",
            "maxItems": MAX_CITATIONS,
            "items": {"type": "string", "maxLength": 120},
        },
    },
}


def _kernel() -> Any:
    """The kernel's fence helpers, imported lazily to avoid an import cycle with ``domain``."""
    from . import domain

    return domain


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _load(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


def _text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text[:limit]


# ── context envelope ────────────────────────────────────────────────────────


def _without_worked_answer(page: Mapping[str, Any]) -> dict[str, Any]:
    """A projection of the page whose worked example keeps its prompt and steps, not its answer.

    The served page is learner-facing: its worked example may legitimately show the answer. The
    tutor's provider envelope may not carry an expected response, and generation normally writes
    the same string the open check grades. So the document projection gets the scaffold only;
    the caller keeps the sealed answer for :func:`sealed_forms`.
    """
    projected = dict(page)
    for holder in (projected, projected.get("document")):
        if not isinstance(holder, Mapping):
            continue
        example = holder.get("worked_example")
        if not isinstance(example, Mapping) or "answer" not in example:
            continue
        stripped = {key: value for key, value in example.items() if key != "answer"}
        if holder is projected:
            projected["worked_example"] = stripped
        else:
            nested = dict(projected["document"])
            nested["worked_example"] = stripped
            projected["document"] = nested
    return projected


def _lesson_document(connection, objective, lesson_run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """The served document for this run, plus the authored page when one exists.

    The authored page is preferred exactly as ``lesson.page`` prefers it; a run without one (a
    pack/composed section, a chat transcript) uses the durable ``lesson_segments`` projection.
    Answer-key material is never part of a document block, and the page's worked example answer
    is stripped before projection so it cannot reach the provider envelope.
    """
    kernel = _kernel()
    authored = kernel._authored_lesson_page(connection, objective)
    if authored is not None:
        page = dict(authored["page"])
        if authored["media"]:
            page["media"] = authored["media"]
        try:
            document = lesson_document.document_from_page(_without_worked_answer(page))
        except lesson_document.LessonDocumentError:
            document = None
        if document is not None and document.get("blocks"):
            return document, page
    rows = connection.execute(
        "SELECT * FROM lesson_segments WHERE lesson_run_id = ? ORDER BY ordinal LIMIT 500",
        (lesson_run_id,),
    ).fetchall()
    if not rows:
        # The page may have been carried to an older run of the same section (H-200). Reading the
        # newest run that actually carries teaching rows keeps the tutor on the same page the
        # learner sees instead of a blank one.
        older = connection.execute(
            "SELECT r.id FROM lesson_runs r WHERE r.enrollment_id = ? AND r.objective_id = ?"
            " AND EXISTS (SELECT 1 FROM lesson_segments s WHERE s.lesson_run_id = r.id)"
            " ORDER BY r.created_at DESC, r.rowid DESC LIMIT 1",
            (objective["enrollment_id"], objective["id"]),
        ).fetchone()
        if older is not None:
            rows = connection.execute(
                "SELECT * FROM lesson_segments WHERE lesson_run_id = ? ORDER BY ordinal LIMIT 500",
                (older["id"],),
            ).fetchall()
    document = lesson_document.document_from_segments(
        [dict(row) for row in rows],
        section_title=objective["title"],
        objective_id=objective["id"],
    )
    return document, {}


def _glossary(page: Mapping[str, Any]) -> list[dict[str, str]]:
    """Authored glossary entries the page carries, allowlisted and bounded.

    There is no glossary table in this release: an authored page may carry a ``glossary`` list of
    ``{term, gloss, reading?}``. An unknown key is dropped; an entry without both halves is not a
    glossary item and is omitted.
    """
    candidates: list[Any] = []
    raw = page.get("glossary")
    if isinstance(raw, list):
        candidates.extend(raw)
    document = page.get("document")
    if isinstance(document, Mapping) and isinstance(document.get("glossary"), list):
        candidates.extend(document["glossary"])
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in candidates:
        if not isinstance(item, Mapping):
            continue
        term = _text(item.get("term"), 120)
        gloss = _text(item.get("gloss"), 400)
        if not term or not gloss:
            continue
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        entries.append({"term": term, "gloss": gloss})
        if len(entries) >= CONTEXT_GLOSSARY:
            break
    return entries


def _blocks(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The allowlisted lesson blocks: id, role, headline, short, deep, source ids."""
    blocks: list[dict[str, Any]] = []
    for block in document.get("blocks") or []:
        if not isinstance(block, Mapping):
            continue
        block_id = _text(block.get("id"), 80)
        if not block_id:
            continue
        blocks.append(
            {
                "id": block_id,
                "role": _text(block.get("role"), 40),
                "headline": _text(block.get("headline"), 200),
                "short": _text(block.get("short"), 400) or None,
                "deep": _text(block.get("deep"), CONTEXT_DEEP_CHARS),
                "source_ids": [
                    str(value) for value in block.get("source_ids") or [] if isinstance(value, str)
                ][:8],
            }
        )
        if len(blocks) >= CONTEXT_BLOCK_LIMIT:
            break
    # One total bound, applied by dropping trailing blocks rather than cutting a sentence mid-word.
    total = 0
    kept: list[dict[str, Any]] = []
    for block in blocks:
        size = len(block["headline"]) + len(block["short"] or "") + len(block["deep"])
        if kept and total + size > CONTEXT_TOTAL_CHARS:
            break
        kept.append(block)
        total += size
    return kept


def _open_check(connection, objective_id: str):
    return connection.execute(
        "SELECT * FROM checks WHERE objective_id = ? AND state = 'open'"
        " ORDER BY version DESC LIMIT 1",
        (objective_id,),
    ).fetchone()


def _objective_attempts(connection, enrollment_id: str, objective_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS n FROM attempts a JOIN checks c ON c.id = a.check_id"
        " WHERE a.enrollment_id = ? AND c.objective_id = ? AND a.state = 'committed'",
        (enrollment_id, objective_id),
    ).fetchone()
    return int(row["n"])


def assist_view(stimulus: Any, attempt_count: int) -> dict[str, Any] | None:
    """The labelled assist policy for an open check, or ``None`` when no check is open.

    This is a *label*, never an evidence write: the UI records a hint through the existing
    ``lesson.assist`` command, which owns the layer-1 row and the revision fence. Defaulting an
    undeclared policy to ``none`` is the honest reading: no authored hint exists.
    """
    if not isinstance(stimulus, Mapping):
        return None
    policy = stimulus.get("assistance_policy")
    policy = policy if isinstance(policy, Mapping) else {}
    hint = policy.get("hint")
    hint = hint if hint in ("available", "after_attempt", "none") else "none"
    available = hint == "available" or (hint == "after_attempt" and int(attempt_count) > 0)
    return {
        "kind": "hint_request",
        "label": "Hint",
        "available": available,
        "policy": hint,
        "evidence_class": "hinted",
        "layer": 1,
    }


def _recent_learner_turns(connection, thread_id: str | None) -> list[str]:
    if not thread_id:
        return []
    rows = connection.execute(
        "SELECT text FROM tutor_turns WHERE thread_id = ? AND role = 'learner'"
        " ORDER BY ordinal DESC LIMIT ?",
        (thread_id, CONTEXT_TURNS),
    ).fetchall()
    return [_text(row["text"], CONTEXT_TURN_CHARS) for row in reversed(rows)]


def _resolved_context(connection, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate scope and build the bounded envelope. No answer key is read into it."""
    kernel = _kernel()
    enrollment = kernel._enrollment(connection, payload["enrollment_id"])
    course_id = str(payload["course_id"])
    if str(enrollment["course_id"]) != course_id:
        raise kernel.RpcError.of(
            "VALIDATION_FAILED",
            "that enrollment does not belong to this course.",
            field="enrollment_id",
            reason="enrollment_not_in_course",
        )
    plan = kernel._approved_plan(connection, course_id)
    if plan is None:
        raise kernel.RpcError.of(
            "VALIDATION_FAILED", "the course plan is not approved.", reason="plan_not_approved"
        )
    objective = kernel._objective_in_plan(connection, str(payload["objective_id"]), plan["id"])
    run = connection.execute(
        "SELECT * FROM lesson_runs WHERE id = ?", (str(payload["lesson_run_id"]),)
    ).fetchone()
    if run is None:
        raise kernel._not_found("lesson run", str(payload["lesson_run_id"]))
    if str(run["enrollment_id"]) != str(enrollment["id"]) or str(run["objective_id"]) != str(
        objective["id"]
    ):
        raise kernel.RpcError.of(
            "VALIDATION_FAILED",
            "that lesson run does not belong to this enrollment and objective.",
            field="lesson_run_id",
            reason="lesson_run_not_in_scope",
        )

    # ``_lesson_document`` expects ``enrollment_id`` on the objective projection for its H-200
    # fallback; the row does not carry it, so pass a shallow projection with the scope attached.
    scoped_objective = dict(objective)
    scoped_objective["enrollment_id"] = str(enrollment["id"])
    document, page = _lesson_document(connection, scoped_objective, str(run["id"]))
    blocks = _blocks(document)
    block_ids = [block["id"] for block in blocks]
    source_ids = [
        str(value) for value in document.get("source_ids") or [] if isinstance(value, str)
    ][:50]
    sources = {}
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        for row in connection.execute(
            f"SELECT id, title FROM sources WHERE course_id = ? AND id IN ({placeholders})",
            (course_id, *source_ids),
        ).fetchall():
            sources[str(row["id"])] = _text(row["title"], 160) or str(row["id"])

    thread = connection.execute(
        "SELECT * FROM tutor_threads WHERE lesson_run_id = ?", (str(run["id"]),)
    ).fetchone()
    asked_block = payload.get("block_id")
    selection = None
    if isinstance(asked_block, str) and asked_block in block_ids:
        selection = {
            "block_id": asked_block,
            "text": _text(payload.get("selected_text"), MAX_SELECTED) or None,
        }
    check = _open_check(connection, str(objective["id"]))
    stimulus = _load(check["stimulus_json"], {}) if check is not None else {}
    attempts = _objective_attempts(connection, str(enrollment["id"]), str(objective["id"]))
    assist = assist_view(stimulus, attempts) if check is not None else None

    context = {
        "objective": {
            "objective_id": str(objective["id"]),
            "title": _text(objective["title"], 300),
            "evidence_target": str(objective["evidence_target"]),
        },
        "section_title": _text(document.get("section_title"), 300),
        "blocks": blocks,
        "glossary": _glossary(page),
        "selection": selection,
        "recent_learner_turns": _recent_learner_turns(
            connection, str(thread["id"]) if thread is not None else None
        ),
        "check": {
            "open": check is not None,
            "prompt": _text(stimulus.get("prompt"), 800) if check is not None else None,
            "assist": assist,
        },
    }
    return {
        "enrollment": enrollment,
        "objective": objective,
        "run": run,
        "thread": thread,
        "document": document,
        "blocks": blocks,
        "sources": sources,
        "check": check,
        "stimulus": stimulus,
        "assist": assist,
        "page": page,
        "context": context,
    }


def _compact_context(resolved: Mapping[str, Any]) -> dict[str, Any]:
    """The ``tutor.history`` context projection: ids and labels, no hidden material."""
    return {
        "objective_id": str(resolved["objective"]["id"]),
        "objective_title": _text(resolved["objective"]["title"], 300),
        "block_ids": [block["id"] for block in resolved["blocks"]],
        "source_ids": list(resolved["sources"]),
        "check_open": resolved["check"] is not None,
        "glossary_terms": [
            {"term": item["term"], "gloss": item["gloss"]} for item in resolved["context"]["glossary"]
        ],
    }


# ── answer-key guard ────────────────────────────────────────────────────────


def _strings(value: Any, *, depth: int = 0) -> Iterable[str]:
    """Every answer-bearing string in a stored reference, with its key context."""
    if depth > 6:
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item, depth=depth + 1)
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in (
                "value",
                "values",
                "answers",
                "answer",
                "accepted_answers",
                "accepted_alternatives",
                "match",
                "targets",
            ):
                yield from _strings(item, depth=depth + 1)


def sealed_forms(reference: Any, page: Mapping[str, Any] | None = None) -> list[str]:
    """The normalized answer strings a tutor answer may not contain while a check is open."""
    from . import validators

    values: list[str] = list(_strings(reference))
    if isinstance(page, Mapping):
        worked = page.get("worked_example")
        if isinstance(worked, Mapping) and isinstance(worked.get("answer"), str):
            values.append(worked["answer"])
    forms: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = validators.normalize_text(value)
        # A one-character or two-digit answer would match incidental prose; the guard is about a
        # meaningful expected response, and the model still never receives the key either way.
        if len(normalized) < 4 or normalized in seen:
            continue
        seen.add(normalized)
        forms.append(normalized)
    return forms


def leaks_answer(text: str, forms: Iterable[str]) -> bool:
    from . import validators

    normalized = validators.normalize_text(text)
    return any(form in normalized for form in forms)


# ── provider call ───────────────────────────────────────────────────────────


def _request(context: Mapping[str, Any], question: str, *, mode: str, directive: str = "") -> generation.LLMRequest:
    instructions = directive or (
        "Answer the learner's question about this lesson using only the context. Cite block ids or "
        "source ids exactly; omit a citation you cannot resolve. If a check is open, scaffold, do "
        "not reveal the final answer."
    )
    return generation.LLMRequest(
        purpose=TUTOR_PURPOSE,
        prompt_version=PROMPT_VERSION,
        system_prompt=SYSTEM_PROMPT,
        instructions=instructions,
        input_text=json.dumps(
            {"mode": mode, "lesson_context": context, "question": question},
            ensure_ascii=False,
            sort_keys=True,
        )[:60000],
        schema=ANSWER_SCHEMA,
        schema_name="coursebook_tutor_answer",
        max_tokens=TUTOR_MAX_TOKENS,
        timeout_s=TUTOR_TIMEOUT_S,
        temperature=0.2,
    )


def _call(request: generation.LLMRequest) -> generation.LLMResponse:
    """One provider call. Raises :class:`ProviderUnavailable` when the host has no model."""
    try:
        llm = generation.host_llm()
    except Exception as exc:  # noqa: BLE001 - no host model is a typed unavailability
        raise ProviderUnavailable(str(exc)) from exc
    return llm(request)


class ProviderUnavailable(RuntimeError):
    """The host has no bound model; nothing was called and nothing may be fabricated."""


def _parse(response: generation.LLMResponse) -> tuple[str, list[str]] | None:
    parsed: Any = response.parsed
    if not isinstance(parsed, Mapping):
        stripped = (response.text or "").strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            # Plain prose is an answer; it just cannot carry citations.
            return _text(stripped, MAX_ANSWER), []
    if not isinstance(parsed, Mapping):
        return None
    answer = _text(parsed.get("answer"), MAX_ANSWER)
    if not answer:
        return None
    raw = parsed.get("citations")
    citations = [str(item) for item in raw if isinstance(item, str)] if isinstance(raw, list) else []
    return answer, citations


def _block_label(block: Mapping[str, Any]) -> str:
    """A citation label a reader can recognise: the headline, else the first line of the text."""
    headline = _text(block.get("headline"), 160)
    if headline and headline not in ("Lesson", "Explain", "Recap", "Example", "Practice", "Media", "Check"):
        return headline
    body = _text(block.get("short") or block.get("deep"), 160)
    return body or headline or str(block.get("id"))


def resolve_citations(
    raw: Iterable[str],
    blocks: Mapping[str, Mapping[str, Any]],
    sources: Mapping[str, str],
) -> list[dict[str, str]]:
    """Resolve model-supplied ids against the context; drop anything that does not resolve."""
    resolved: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        value = str(item or "").strip()
        kind = None
        if value.startswith("block:"):
            kind, value = "block", value[len("block:"):]
        elif value.startswith("source:"):
            kind, value = "source", value[len("source:"):]
        if kind in (None, "block") and value in blocks:
            key = ("block", value)
            if key not in seen:
                seen.add(key)
                resolved.append(
                    {"kind": "block", "id": value, "label": _block_label(blocks[value])}
                )
        elif kind in (None, "source") and value in sources:
            key = ("source", value)
            if key not in seen:
                seen.add(key)
                resolved.append({"kind": "source", "id": value, "label": sources[value] or value})
        if len(resolved) >= MAX_CITATIONS:
            break
    return resolved


# ── persistence ─────────────────────────────────────────────────────────────


def _thread_for(connection, resolved: Mapping[str, Any]) -> Any:
    thread = resolved["thread"]
    if thread is not None:
        return thread
    run = resolved["run"]
    now = db.utcnow()
    connection.execute(
        "INSERT INTO tutor_threads (id, course_id, enrollment_id, objective_id, lesson_run_id,"
        " revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 0, ?, ?)"
        " ON CONFLICT(lesson_run_id) DO NOTHING",
        (
            _new_id("thr"),
            str(resolved["enrollment"]["course_id"]),
            str(resolved["enrollment"]["id"]),
            str(resolved["objective"]["id"]),
            str(run["id"]),
            now,
            now,
        ),
    )
    return connection.execute(
        "SELECT * FROM tutor_threads WHERE lesson_run_id = ?", (str(run["id"]),)
    ).fetchone()


def _append_turn(
    connection,
    thread_id: str,
    *,
    role: str,
    text: str,
    block_id: str | None,
    selected_text: str | None,
    citations: list[dict[str, str]],
    now: str,
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT COALESCE(MAX(ordinal), 0) AS ordinal FROM tutor_turns WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    ordinal = int(row["ordinal"]) + 1
    turn_id = _new_id("ttr")
    connection.execute(
        "INSERT INTO tutor_turns (id, thread_id, ordinal, role, text, block_id, selected_text,"
        " source_refs_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            turn_id,
            thread_id,
            ordinal,
            role,
            text,
            block_id,
            selected_text,
            json.dumps(citations, sort_keys=True) if citations else None,
            now,
        ),
    )
    return {
        "id": turn_id,
        "ordinal": ordinal,
        "role": role,
        "text": text,
        "block_id": block_id,
        "selected_text": selected_text,
        "citations": citations,
        "created_at": now,
    }


def _turn_view(row: Any) -> dict[str, Any]:
    citations = _load(row["source_refs_json"], [])
    return {
        "id": str(row["id"]),
        "ordinal": int(row["ordinal"]),
        "role": str(row["role"]),
        "text": str(row["text"]),
        "block_id": row["block_id"],
        "selected_text": row["selected_text"],
        "citations": citations if isinstance(citations, list) else [],
        "created_at": str(row["created_at"]),
    }


def _result(turn: dict[str, Any] | None, thread_id: str | None, citations: list[dict[str, str]],
            assist: dict[str, Any] | None, state: str) -> dict[str, Any]:
    return {
        "turn": turn,
        "thread_id": thread_id,
        "citations": citations,
        "assist": assist,
        "state": state,
    }


def _provider_failure(thread_id: str | None = None) -> dict[str, Any]:
    return _result(None, thread_id, [], None, "provider_failure")


# ── handlers ────────────────────────────────────────────────────────────────


def ask(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``tutor.ask``: one bounded, cited answer; no tool, no learning-state write."""
    db.ensure_schema()
    kernel = _kernel()
    expected = kernel._require_revision(envelope)
    method = "tutor.ask"
    payload_hash = kernel._payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    question = _text(payload["question"], MAX_QUESTION)
    mode = str(payload.get("mode") or "ask")
    if not question:
        raise kernel.RpcError.of(
            "VALIDATION_FAILED", "ask a question about this lesson.", field="question"
        )

    with db.read() as connection:
        replay = kernel._idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        resolved = _resolved_context(connection, payload)

    if mode == gm_contract.TutorMode.PRACTICE.value:
        return _ask_practice(payload, envelope, resolved, question, expected, method, payload_hash, key)

    context = resolved["context"]
    blocks = {block["id"]: block for block in resolved["blocks"]}
    sources = resolved["sources"]
    check_open = resolved["check"] is not None
    existing_thread = str(resolved["thread"]["id"]) if resolved["thread"] is not None else None
    request = _request(context, question, mode="ask")
    try:
        response = _call(request)
    except ProviderUnavailable as exc:
        raise kernel.RpcError.of(
            "HOST_UNAVAILABLE",
            "the tutor model is not configured; nothing was answered or graded.",
            reason="tutor_unavailable",
            detail=_text(exc, 300),
        ) from exc
    except Exception:  # noqa: BLE001 - a failed provider call is a named state, never a fake answer
        return 0, _provider_failure(existing_thread)

    parsed = _parse(response)
    if parsed is None:
        return 0, _provider_failure(existing_thread)
    answer, raw_citations = parsed
    citations = resolve_citations(raw_citations, blocks, sources)

    state = "answered"
    if check_open:
        forms = sealed_forms(
            kernel._json_load(resolved["check"]["reference_json"], {}), resolved.get("page")
        )
        if leaks_answer(answer, forms):
            answer = WITHHELD_ANSWER
            citations = []
            state = "answer_withheld"

    selected = context["selection"] or {}
    with db.transaction() as connection:
        replay = kernel._idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        to_revision = kernel._bump_enrollment(connection, str(resolved["enrollment"]["id"]), expected)
        thread = _thread_for(connection, resolved)
        now = db.utcnow()
        _append_turn(
            connection,
            str(thread["id"]),
            role="learner",
            text=question,
            block_id=selected.get("block_id"),
            selected_text=selected.get("text"),
            citations=[],
            now=now,
        )
        turn = _append_turn(
            connection,
            str(thread["id"]),
            role="tutor",
            text=answer,
            block_id=None,
            selected_text=None,
            citations=citations,
            now=now,
        )
        connection.execute(
            "UPDATE tutor_threads SET revision = revision + 2, updated_at = ? WHERE id = ?",
            (now, str(thread["id"])),
        )
        result = _result(turn, str(thread["id"]), citations, resolved["assist"], state)
        kernel._remember(
            connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result
        )
    return to_revision, result


def _ask_practice(
    payload: dict[str, Any],
    envelope: dict[str, Any],
    resolved: Mapping[str, Any],
    question: str,
    expected: int,
    method: str,
    payload_hash: str,
    key: str | None,
) -> tuple[int, dict[str, Any]]:
    """Practice mode: append the learner turn and the in-character reply to the practice log.

    The session and its grader already exist; this is the rail's input surface, not a second
    conversation engine. Only ``practice_turns`` learner rows reach the grader; the tutor reply is
    mirrored into the rail thread and is never graded.
    """
    kernel = _kernel()
    run_id = str(resolved["run"]["id"])
    with db.read() as connection:
        session = practice.active_session(connection, lesson_run_id=run_id)
        if session is None:
            raise kernel.RpcError.of(
                "VALIDATION_FAILED",
                "start the practice before speaking in it.",
                reason="practice_not_active",
            )
        check = connection.execute(
            "SELECT * FROM checks WHERE id = ?", (str(session["check_id"]),)
        ).fetchone()
        if check is None:
            raise kernel.RpcError.of(
                "VALIDATION_FAILED", "the practice check is missing.", reason="practice_not_active"
            )
        declaration = practice.declaration(_load(check["stimulus_json"], {})) or {}
        learner_count = len(practice.learner_turns(practice.turns_for(connection, str(session["id"]))))
        directive = practice.directive_for(declaration, learner_count + 1)
        scene = {
            "scenario": declaration.get("scenario"),
            "learner_role": declaration.get("learner_role"),
            "tutor_role": declaration.get("tutor_role"),
            "opening": declaration.get("opening"),
        }
        context = {
            "objective": resolved["context"]["objective"],
            "glossary": resolved["context"]["glossary"],
            "practice": scene,
        }

    request = _request(context, question, mode="practice", directive=directive)
    try:
        response = _call(request)
    except ProviderUnavailable as exc:
        raise kernel.RpcError.of(
            "HOST_UNAVAILABLE",
            "the tutor model is not configured; practice is not available in this build.",
            reason="tutor_unavailable",
            detail=_text(exc, 300),
        ) from exc
    except Exception:  # noqa: BLE001
        return 0, _provider_failure(
            str(resolved["thread"]["id"]) if resolved["thread"] is not None else None
        )
    parsed = _parse(response)
    if parsed is None:
        return 0, _provider_failure(
            str(resolved["thread"]["id"]) if resolved["thread"] is not None else None
        )
    answer, raw_citations = parsed
    citations = resolve_citations(
        raw_citations,
        {block["id"]: block for block in resolved["blocks"]},
        resolved["sources"],
    )

    with db.transaction() as connection:
        replay = kernel._idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        to_revision = kernel._bump_enrollment(connection, str(resolved["enrollment"]["id"]), expected)
        session = practice.active_session(connection, lesson_run_id=run_id)
        if session is None:
            raise kernel.RpcError.of(
                "VALIDATION_FAILED",
                "the practice ended before this turn could be recorded.",
                reason="practice_not_active",
            )
        now = db.utcnow()
        nonce = practice.turn_nonce(str(session["id"]), question, int(session["revision"]))
        appended, _why = practice.append_turn(
            connection, session, speaker="learner", text=question, nonce=nonce, now=now
        )
        if not appended:
            raise kernel.RpcError.of(
                "IDEMPOTENCY_CONFLICT",
                "that practice turn was already recorded.",
                reason="practice_turn_duplicate",
            )
        practice.append_turn(
            connection, session, speaker="tutor", text=answer, nonce=None, now=now
        )
        thread = _thread_for(connection, resolved)
        _append_turn(
            connection,
            str(thread["id"]),
            role="learner",
            text=question,
            block_id=None,
            selected_text=None,
            citations=[],
            now=now,
        )
        turn = _append_turn(
            connection,
            str(thread["id"]),
            role="tutor",
            text=answer,
            block_id=None,
            selected_text=None,
            citations=citations,
            now=now,
        )
        connection.execute(
            "UPDATE tutor_threads SET revision = revision + 2, updated_at = ? WHERE id = ?",
            (now, str(thread["id"])),
        )
        result = _result(turn, str(thread["id"]), citations, None, "answered")
        kernel._remember(
            connection, key, method, payload_hash, envelope.get("operation_id", ""), to_revision, result
        )
    return to_revision, result


def history(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """``tutor.history``: the persisted thread for one lesson run. Read-only."""
    db.ensure_schema()
    with db.read() as connection:
        resolved = _resolved_context(connection, payload)
        thread = resolved["thread"]
        turns: list[dict[str, Any]] = []
        thread_id = None
        if thread is not None:
            thread_id = str(thread["id"])
            rows = connection.execute(
                "SELECT * FROM tutor_turns WHERE thread_id = ? ORDER BY ordinal LIMIT ?",
                (thread_id, MAX_HISTORY_TURNS),
            ).fetchall()
            turns = [_turn_view(row) for row in rows]
        # A read never bumps a revision.
        return 0, {
            "thread_id": thread_id,
            "turns": turns,
            "context": _compact_context(resolved),
        }


HANDLERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], tuple[int, dict[str, Any]]]] = {
    "tutor.ask": ask,
    "tutor.history": history,
}


def ensure_registered() -> tuple[str, ...]:
    available = set(method_names())
    registered: list[str] = []
    for method, handler in HANDLERS.items():
        if method in available:
            from . import api

            api.register_handler(method, handler)
            registered.append(method)
    return tuple(sorted(registered))


ensure_registered()
