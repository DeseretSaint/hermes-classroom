"""Away-from-screen homework over an existing lesson (GM-007).

Homework is a small, honest object: **one task, one target, one context, one observable
success criterion, 3-10 minutes**. It is not a course, not a chat thread and not a second
evidence store. This module owns the whole backend path:

* :func:`create` proposes one task from the source lesson's authored ``homework`` block, after
  the policy refuses a generic card, multiple targets, surveillance and graded completion;
* :func:`read` returns the task and its append-only event trail — the view the notebook and
  Parent Studio render — together with the one-page sheet;
* :func:`complete` records ``self_reported_done`` or ``parent_reported_done`` and nothing else;
* :func:`skip` records an honest skip with no penalty.

Rules this module keeps (plan §10A.4-§10A.7):

* **One target, one context.** A proposal is refused if it names more than one target, if its
  context is not one sentence, or if its success criterion is not one observable sentence.
  ``practise for ten minutes`` is not a task and is refused as ``generic_task``.
* **Sourcing.** A task's target must carry ``source_ids`` that resolve in the proposal's source
  ledger. The demo Japanese proposals are *derived from* the reviewed L0 lesson fixture
  (``bundled/homework/japanese-l0-mealtime/fixture.json``) rather than re-typing its phrases,
  so no Japanese word, reading or register is invented here.
* **No grade, no mastery, no XP.** Completion is a report by the learner or the parent. A
  parent-reported task is not independent verification and is never written as evidence; a
  later retrieval check is a separate object.
* **Nothing private is invented or leaked.** No attempt, transition, evidence, notebook or
  engagement row is written or read here, and the sheet never carries the lesson's reference
  answer or rubric.
* **Print is local and low-ink.** :func:`sheet_html` is a one-page field card in grey values
  only; printing and downloading are local actions, never an external send.
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import db, homework_print, takehome
from .api import RpcError

ROOT = Path(__file__).resolve().parent.parent
#: The reviewed lesson fixture this demo's proposals are derived from (GM-014, read-only).
LESSON_FIXTURE = ROOT / "bundled" / "homework" / "japanese-l0-mealtime" / "fixture.json"
#: The GM-007 proposals: task copy for the reviewed lesson tasks plus one sourced cafe question.
PROPOSALS_PATH = ROOT / "bundled" / "homework" / "japanese-l0-mealtime" / "proposals.v1.json"

#: Objective evidence targets that can honestly be practised away from the screen. ``recall`` and
#: ``comprehension`` are not transfer, production or procedure, and earn no homework.
EVIDENCE_TARGETS = ("transfer", "production", "procedure")
#: A check that asks the learner to observe something real qualifies even when its objective is
#: graded as comprehension.
OBSERVATION_CHECK_KINDS = ("observation", "observation_record")

#: Task kinds the plan allows (``coursebook.gm_contract.HomeworkKind``).
TASK_KINDS = ("real_world_use", "observe", "label", "practice", "make", "teach_back")

#: Completion states. Both are reports; neither is a pass.
COMPLETION_STATES = ("self_reported_done", "parent_reported_done")

#: A task title/context/criterion that only names a duration is not a task.
GENERIC_PATTERNS = (
    r"\bpracti[cs]e\b[^.]{0,30}\b(minutes?|mins?|hour|hours)\b",
    r"\bfor (a few|five|ten|fifteen|twenty|thirty|\d+)\s*(minutes?|mins?)\b",
    r"\bstudy\b[^.]{0,30}\b(minutes?|mins?|hour|hours)\b",
    r"\bdo (some|a bit of) (practice|study|revision)\b",
    r"^\s*(practi[cs]e|study|revise)\s*\.?\s*$",
)

#: Words that turn practice into surveillance or a demand for proof.
SURVEILLANCE_PATTERNS = (
    r"\bphoto\b",
    r"\bphotograph\w*\b",
    r"\btake a picture\b",
    r"\bselfie\b",
    r"\brecord (yourself|a video|audio)\b",
    r"\bvideo (proof|record)\b",
    r"\bgeolocation\b",
    r"\bgps\b",
    r"\blocation data\b",
    r"\bshare your location\b",
)

#: Words that turn a report into a grade, a score, a mastery claim or streak pressure. The
#: patterns are deliberately narrow: "passed it on the stairs" and "point at the label" are a
#: learner acting in the world, not a verdict.
GRADE_PATTERNS = (
    r"\bgrade[ds]?\b",
    r"\bscor(e|ed|ing)\b",
    r"\bpass mark\b",
    r"\bpass(ed)? (the )?(test|check|quiz|course|level|assessment)\b",
    r"\bfail(ed|ing)? (the )?(test|check|quiz|course|level|assessment)\b",
    r"\bmarked? (as|out of)\b",
    r"\bmastery\b",
    r"\bxp\b",
    r"\bstreak(s)?\b",
    r"\bxp points?\b",
    r"\bscore points?\b",
    r"\bpenalt(y|ies)\b",
)

#: Learner-visible words the one-page sheet must never carry.
SHEET_FORBIDDEN = (
    "answer",
    "grade",
    "graded",
    "score",
    "scored",
    "xp",
    "mastery",
    "streak",
    "photo",
    "photograph",
    "geolocation",
    "parent only",
    "answer guide",
    "expected response",
    "common error",
    "reference answer",
)

_JP_RUN = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


# ── small helpers ───────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _labelled_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_dump(value).encode("utf-8")).hexdigest()


def _payload_hash(method: str, payload: Mapping[str, Any]) -> str:
    return _labelled_hash({"method": method, "payload": dict(payload)})


def _row(connection, sql: str, params: tuple = ()) -> Any:
    return connection.execute(sql, params).fetchone()


def _not_found(what: str, identifier: str) -> RpcError:
    return RpcError.of("NOT_FOUND", f"{what} {identifier} does not exist in this scope.", id=identifier)


def _policy(reason: str, message: str, **details: Any) -> RpcError:
    return RpcError.of("POLICY_VIOLATION", message, reason=reason, **details)


def _require_expected(envelope: Mapping[str, Any]) -> int:
    expected = envelope.get("expected_revision")
    if expected is None:
        raise RpcError.of(
            "VALIDATION_FAILED",
            "this command requires expected_revision in the envelope.",
            field="expected_revision",
        )
    return int(expected)


def _stale(message: str, current: int) -> RpcError:
    return RpcError.of("STALE_REVISION", message, current_revision=current)


def _idempotent_lookup(connection, key: str | None, method: str, payload_hash: str):
    if not key:
        return None
    row = _row(
        connection,
        "SELECT payload_hash, method, response_json FROM idempotency_keys WHERE key = ?",
        (key,),
    )
    if row is None:
        return None
    if row["payload_hash"] != payload_hash or row["method"] != method:
        raise RpcError.of(
            "IDEMPOTENCY_CONFLICT",
            "this idempotency key was already used with a different payload.",
            key=key,
            method=row["method"],
        )
    stored = _load(row["response_json"], {})
    return int(stored.get("revision", 0)), dict(stored.get("result") or {})


def _remember(connection, key: str | None, method: str, payload_hash: str,
              operation_id: str, revision: int, result: Mapping[str, Any]) -> None:
    if not key:
        return
    connection.execute(
        "INSERT INTO idempotency_keys (key, payload_hash, method, operation_id, response_json,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (key, payload_hash, method, operation_id,
         _dump({"revision": revision, "result": dict(result)}), _now()),
    )


def _matches(patterns: Iterable[str], text: str) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in patterns if re.search(pattern, lowered)]


def _field(row: Any, key: str, default: Any = None) -> Any:
    """One field of a sqlite3.Row or a mapping.

    ``sqlite3.Row`` answers ``in`` against its *values*, not its column names, so a membership
    test is wrong for a row. Index, and fall back on the default when the column is absent.
    """
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def _sentences(text: str) -> list[str]:
    return [part for part in _SENTENCE_BREAK.split(str(text).strip()) if part.strip()]


# ── proposal validation (the policy) ────────────────────────────────────────


def _single_target(value: Any) -> dict[str, Any]:
    """Exactly one target object. A list of two is two tasks, and a task has one target."""
    if isinstance(value, list):
        if len(value) > 1:
            raise _policy(
                "multiple_targets",
                "a homework task names one target; split this into one task per target.",
                targets=len(value),
            )
        if not value:
            raise _policy("no_target", "a homework task must name one target.")
        value = value[0]
    if not isinstance(value, Mapping) or not value:
        raise _policy("no_target", "a homework task must name one target.")
    display = str(value.get("display") or value.get("title") or "").strip()
    if not display:
        raise _policy("no_target", "the target has no display text.")
    reading = str(value.get("reading") or display).strip()
    source_ids = [str(item) for item in (value.get("source_ids") or []) if str(item).strip()]
    if not source_ids:
        raise _policy(
            "unsourced_target",
            "the target has no cited source; an unsourced phrase is not printed for a learner.",
            target=display,
        )
    target = {
        "display": display,
        "reading": reading,
        "romaji": str(value.get("romaji") or "").strip(),
        "meaning": str(value.get("meaning") or "").strip(),
        "register": str(value.get("register") or "").strip(),
        "source_ids": source_ids,
    }
    if value.get("label_ids"):
        target["label_ids"] = [str(item) for item in value["label_ids"]]
    target["kind"] = "label_set" if target.get("label_ids") else "single"
    return target


def check_proposal(proposal: Mapping[str, Any], *, context: str | None = None) -> dict[str, Any]:
    """Return the normalised proposal, or raise ``POLICY_VIOLATION`` naming the reason.

    This is the one place the homework policy lives: create, the fixture validator and the
    tests all go through it, so a refusal cannot drift between them.
    """
    if not isinstance(proposal, Mapping) or not proposal:
        raise _policy("no_homework_proposal", "this lesson carries no away-from-screen task.")
    kind = str(proposal.get("task_kind") or "").strip()
    if kind not in TASK_KINDS:
        raise _policy("unknown_task_kind", f"{kind!r} is not a homework task kind.", task_kind=kind)
    target = _single_target(proposal.get("target"))

    task_context = str(context if context is not None else proposal.get("context") or "").strip()
    if not task_context:
        raise _policy("context_missing", "a homework task names one place and time.")
    if len(_sentences(task_context)) != 1:
        raise _policy(
            "multiple_contexts",
            "a homework task names one context, in one sentence.",
            context=task_context,
        )
    if _matches(GENERIC_PATTERNS, task_context):
        raise _policy(
            "generic_task",
            "a task that only names a duration is not a homework task.",
            context=task_context,
        )

    steps = [str(step).strip() for step in (proposal.get("steps") or []) if str(step).strip()]
    if not steps:
        raise _policy("steps_missing", "a homework task needs at least one step.")
    if len(steps) > 3:
        raise _policy("too_many_steps", "a field-card task has at most three steps.", steps=len(steps))

    criterion = str(proposal.get("success_criterion") or "").strip()
    if len(criterion.split()) < 6 or len(_sentences(criterion)) != 1:
        raise _policy(
            "criterion_not_observable",
            "a homework task needs one observable success criterion.",
            success_criterion=criterion,
        )
    if _matches(GENERIC_PATTERNS, criterion):
        raise _policy("generic_task", "a duration is not a success criterion.", success_criterion=criterion)

    minutes = proposal.get("estimated_minutes")
    if not isinstance(minutes, int) or isinstance(minutes, bool):
        raise _policy("minutes_not_integer", "estimated_minutes must be an integer.")
    if not 3 <= minutes <= 10:
        raise _policy(
            "minutes_out_of_range",
            "a homework task is 3 to 10 minutes.",
            estimated_minutes=minutes,
        )

    surfaces = {
        "title": str(proposal.get("title") or ""),
        "context": task_context,
        "steps": " ".join(steps),
        "success_criterion": criterion,
        "target": target["display"],
    }
    for field, text in surfaces.items():
        if _matches(SURVEILLANCE_PATTERNS, text):
            raise _policy(
                "surveillance",
                "homework never asks for a photo, a recording, a location or proof of presence.",
                field=field,
            )
        if _matches(GRADE_PATTERNS, text):
            raise _policy(
                "graded_completion",
                "completion is reported by the learner or parent; it is never graded.",
                field=field,
            )

    title = str(proposal.get("title") or "").strip()
    if not title:
        raise _policy("title_missing", "a homework task needs a title.")
    audience = str(proposal.get("audience") or "learner").strip()
    if audience not in ("learner", "parent"):
        raise _policy("unknown_audience", "audience is learner or parent.", audience=audience)

    normalised = {
        "task_kind": kind,
        "title": title,
        "target": target,
        "context": task_context,
        "steps": steps,
        "success_criterion": criterion,
        "estimated_minutes": minutes,
        "audience": audience,
        "optional": bool(proposal.get("optional", False)),
    }
    record = [str(item).strip() for item in (proposal.get("completion_record") or [])
              if str(item).strip()]
    if len(record) > 4:
        raise _policy("completion_record_too_long",
                      "a field card records at most four ticks.", completion_record=record)
    normalised["completion_record"] = record
    if proposal.get("proposal_id"):
        normalised["proposal_id"] = str(proposal["proposal_id"])
    return normalised


def proposal_for(bundle: Mapping[str, Any], *, context: str | None = None) -> dict[str, Any]:
    """The one proposal this objective has earned, or a named refusal.

    A lesson earns homework only when its objective measures transfer, production or procedure,
    or when its check is an observation of something real. A lesson with no authored
    ``homework`` block is refused rather than given a generic card.
    """
    objective = bundle.get("objective")
    evidence_target = str(_field(objective, "evidence_target", "") or "")
    page = bundle.get("page")
    page = page if isinstance(page, Mapping) else {}
    check = page.get("check")
    check = check if isinstance(check, Mapping) else {}
    check_kind = str(check.get("kind") or "")
    if evidence_target not in EVIDENCE_TARGETS and check_kind not in OBSERVATION_CHECK_KINDS:
        raise _policy(
            "no_transfer_target",
            "this objective is not transfer, production or procedure; it earns no homework.",
            evidence_target=evidence_target,
            check_kind=check_kind,
        )
    block = page.get("homework")
    if not isinstance(block, Mapping) or not block:
        raise _policy(
            "no_homework_proposal",
            "this lesson authors no away-from-screen task.",
            objective_id=str(_field(objective, "id", "") or ""),
        )
    return check_proposal(block, context=context)


# ── demo Japanese proposals (content, not a course) ─────────────────────────


def _reviewed_fixture() -> dict[str, Any]:
    return homework_print.load_fixture(LESSON_FIXTURE)


def _label_target(reviewed: Mapping[str, Any], label_ids: Sequence[str]) -> dict[str, Any]:
    labels = homework_print.label_index(reviewed)
    chosen = [labels[label_id] for label_id in label_ids]
    source_ids: list[str] = []
    for label in chosen:
        for source_id in label["source_ids"]:
            if source_id not in source_ids:
                source_ids.append(source_id)
    return {
        "display": "・".join(label["display"] for label in chosen),
        "reading": "・".join(label["reading"] for label in chosen),
        "romaji": " / ".join(label["romaji"] for label in chosen),
        "meaning": ", ".join(label["meaning"].split(";")[0] for label in chosen),
        "register": "noun (each entry is labelled a noun by the cited dictionary)",
        "source_ids": source_ids,
        "label_ids": list(label_ids),
    }


def demo_proposals() -> dict[str, Any]:
    """The reviewed L0 lesson's tasks plus the optional sourced cafe question.

    Task copy for ``hw_premeal``, ``hw_postmeal`` and ``hw_labels`` is taken from the reviewed
    lesson fixture at load time; nothing is re-typed. Only the optional cafe task and its two
    dictionary citations live in this card's own proposals file.
    """
    reviewed = _reviewed_fixture()
    extra = json.loads(PROPOSALS_PATH.read_text(encoding="utf-8"))
    targets = homework_print.target_index(reviewed)
    proposals: list[dict[str, Any]] = []
    for task_id in extra["derived_from"]["tasks"]:
        task = homework_print.task_by_id(reviewed, task_id)
        if task["target_id"] == "tgt_household_set":
            target = _label_target(reviewed, task_set_ids(reviewed, task["target_id"]))
        else:
            source = targets[task["target_id"]]
            target = {key: source[key] for key in
                      ("display", "reading", "romaji", "meaning", "register", "source_ids")}
        proposals.append(
            {
                "proposal_id": task["task_id"],
                "task_kind": task["task_kind"],
                "audience": task["audience"],
                "optional": False,
                "title": task["title"],
                "context": task["context"],
                "steps": list(task["steps"]),
                "success_criterion": task["success_criterion"],
                "estimated_minutes": int(task["estimated_minutes"]),
                "target": target,
                "derived_from": {"fixture_task_id": task["task_id"]},
            }
        )
    extra_targets = {item["target_id"]: item for item in extra["extra_targets"]}
    records = extra.get("completion_records") or {}
    for proposal in proposals:
        if proposal["proposal_id"] in records:
            proposal["completion_record"] = list(records[proposal["proposal_id"]])
    for task in extra["extra_tasks"]:
        target = extra_targets[task["lesson_target_id"]]
        proposals.append(
            {
                **{key: task[key] for key in
                   ("proposal_id", "task_kind", "audience", "optional", "title", "context",
                    "steps", "success_criterion", "estimated_minutes")},
                "target": {key: target[key] for key in
                           ("display", "reading", "romaji", "meaning", "register", "source_ids")},
                "derived_from": {"proposals_file": PROPOSALS_PATH.name},
            }
        )
    sources: dict[str, dict[str, Any]] = {}
    for source in list(reviewed["lesson"]["sources"]) + list(extra["sources"]):
        sources[source["source_id"]] = source
    return {
        "fixture_id": extra["fixture_id"],
        "contract": extra["contract"],
        "contract_version": int(extra["contract_version"]),
        "proposals": proposals,
        "sources": sources,
        "labels": list(reviewed["lesson"]["labels"]),
        "targets": list(reviewed["lesson"]["targets"]),
        "binding": {
            "lesson_fixture": LESSON_FIXTURE.relative_to(ROOT).as_posix(),
            "lesson_hash": homework_print.lesson_hash(reviewed["lesson"]),
            "proposals_fixture": PROPOSALS_PATH.relative_to(ROOT).as_posix(),
            "proposals_hash": "sha256:" + hashlib.sha256(PROPOSALS_PATH.read_bytes()).hexdigest(),
        },
    }


def task_set_ids(reviewed: Mapping[str, Any], target_id: str) -> list[str]:
    for item in reviewed.get("target_sets") or []:
        if item["target_id"] == target_id:
            return list(item["label_ids"])
    raise KeyError(target_id)


def validate_proposals(data: Mapping[str, Any] | None = None) -> list[str]:
    """Every reason this proposal set is not printable. Empty means clean."""
    data = data or demo_proposals()
    problems: list[str] = []
    sources = data["sources"]
    seen: set[str] = set()
    for proposal in data["proposals"]:
        identifier = proposal.get("proposal_id") or "<unnamed>"
        if identifier in seen:
            problems.append(f"{identifier}: duplicate proposal id")
        seen.add(identifier)
        try:
            check_proposal(proposal)
        except RpcError as error:
            problems.append(f"{identifier}: {error.error['details']['reason']}")
            continue
        for source_id in proposal["target"]["source_ids"]:
            source = sources.get(source_id)
            if source is None:
                problems.append(f"{identifier}: source {source_id} is not in the ledger")
                continue
            if not str(source.get("url", "")).startswith("https://"):
                problems.append(f"{identifier}: source {source_id} has no https url")
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(source.get("accessed", ""))):
                problems.append(f"{identifier}: source {source_id} has no access date")
            if not str(source.get("quote", "")).strip():
                problems.append(f"{identifier}: source {source_id} has no quote")
    return problems


def demo_lesson_block(proposal_id: str) -> dict[str, Any]:
    """A ``page_json['homework']`` block for one demo proposal, in lesson-page shape."""
    for proposal in demo_proposals()["proposals"]:
        if proposal["proposal_id"] == proposal_id:
            checked = check_proposal(proposal)
            return {
                "task_kind": checked["task_kind"],
                "title": checked["title"],
                "target": checked["target"],
                "context": checked["context"],
                "steps": checked["steps"],
                "success_criterion": checked["success_criterion"],
                "estimated_minutes": checked["estimated_minutes"],
                "completion_record": checked["completion_record"],
            }
    raise KeyError(proposal_id)


def proposal_sources(target: Mapping[str, Any]) -> list[dict[str, Any]]:
    sources = demo_proposals()["sources"]
    out: list[dict[str, Any]] = []
    for source_id in target.get("source_ids") or []:
        source = sources.get(source_id)
        if source is not None:
            out.append(
                {
                    "source_id": source["source_id"],
                    "title": source["title"],
                    "url": source["url"],
                    "accessed": source["accessed"],
                }
            )
    return out


# ── the one-page field card ─────────────────────────────────────────────────


def _esc(value: Any) -> str:
    return html_module.escape(str(value), quote=True)


def _esc_jp(value: Any) -> str:
    """Escape running copy and mark every Japanese run with ``lang="ja"``."""
    text = _esc(value)
    return _JP_RUN.sub(lambda match: f'<span class="jp" lang="ja">{match.group(0)}</span>', text)


_SHEET_CSS = """
@page { size: A4; margin: 16mm 15mm 14mm; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #ffffff; color: #111111; }
body { font-family: "Source Serif 4", Georgia, "Noto Serif CJK JP", serif; font-size: 11.5pt;
       line-height: 1.45; }
.sheet { width: 180mm; min-height: 0; padding: 0; background: #ffffff; }
.eyebrow { font-family: "Inter", "Noto Sans CJK JP", sans-serif; font-size: 8pt;
           letter-spacing: 0.18em; text-transform: uppercase; color: #555555; }
h1 { font-size: 20pt; line-height: 1.15; margin: 5mm 0 1mm; font-weight: 600; }
.target { font-size: 26pt; line-height: 1.2; margin: 4mm 0 1mm; }
.reading { font-size: 13pt; color: #333333; margin: 0 0 1mm; }
.gloss { font-size: 10.5pt; color: #444444; margin: 0 0 5mm; }
.rule { border: 0; border-top: 0.6pt solid #111111; margin: 4mm 0; }
.label { font-family: "Inter", "Noto Sans CJK JP", sans-serif; font-size: 8pt;
         letter-spacing: 0.14em; text-transform: uppercase; color: #555555; margin: 4mm 0 1mm; }
p.context { font-size: 12pt; margin: 0 0 2mm; }
ol { margin: 0; padding-left: 6mm; }
ol li { margin: 0 0 2mm; }
.done-when { margin-top: 5mm; padding-top: 3mm; border-top: 0.6pt solid #111111; }
.checkline { margin-top: 6mm; font-size: 11pt; }
.checkline .box { display: inline-block; width: 4.2mm; height: 4.2mm; border: 0.7pt solid #111111;
                  margin-right: 2.5mm; vertical-align: -0.6mm; }
.minutes { font-size: 10.5pt; color: #333333; margin-top: 2mm; }
.sources { margin-top: 8mm; font-family: "Inter", "Noto Sans CJK JP", sans-serif; font-size: 7.6pt;
           color: #555555; }
.sources a { color: #333333; text-decoration: none; }
.jp { word-break: keep-all; }
footer { margin-top: 6mm; font-family: "Inter", "Noto Sans CJK JP", sans-serif; font-size: 7.6pt;
         color: #555555; }
"""


def sheet_html(task: Mapping[str, Any], *, paper: str = "A4") -> str:
    """The one-page take-home sheet for one stored or proposed task.

    One target, one action, one place, one check. No worksheet grid, no grade, no red pen and no
    streak. Every colour is a grey value, so a black-and-white printer loses nothing.
    """
    if paper not in homework_print.PAPER_SIZES:
        raise ValueError(f"unknown paper {paper!r}")
    target = task["target"]
    steps = list(task.get("steps") or [])
    if len(steps) > 3:
        raise ValueError("a field card carries at most three steps")
    sources = task.get("sources") or []
    source_line = ""
    if sources:
        first = sources[0]
        source_line = (
            f'Source: <a href="{_esc(first["url"])}">{_esc(first["title"])}</a>'
            f' (accessed {_esc(first["accessed"])})'
        )
    completion = task.get("completion") or {}
    basis = completion.get("basis")
    record = [str(item) for item in (task.get("completion_record")
                                     or target.get("completion_record") or [])]
    if record:
        boxes = " ".join(f'<span class="box"></span> {_esc_jp(item)}' for item in record)
        checkline = f"{boxes} &nbsp; Date __________"
    elif basis == "parent_reported":
        checkline = ('<span class="box"></span> A parent will record this when it is done.'
                     ' &nbsp; Date __________')
    else:
        checkline = ('<span class="box"></span> Done - I will record this myself.'
                     ' &nbsp; Date __________')
    reading = target.get("reading")
    reading_line = "" if reading in (None, "", target.get("display")) else (
        f'<p class="reading">{_esc_jp(reading)}</p>'
    )
    gloss = target.get("meaning")
    gloss_line = f'<p class="gloss">{_esc_jp(gloss)}</p>' if gloss else ""
    labels = ""
    if target.get("label_ids"):
        labels = (
            f'<p class="label">Labels on this sheet</p>'
            f'<p>{_esc_jp(target["reading"])}</p>'
        )
    body = f"""<article class="sheet" id="homework-sheet">
  <p class="eyebrow">Coursebook field card</p>
  <h1>{_esc_jp(task["title"])}</h1>
  <p class="target">{_esc_jp(target["display"])}</p>
  {reading_line}
  {gloss_line}
  <hr class="rule">
  <p class="label">Where and when</p>
  <p class="context">{_esc_jp(task["context"])}</p>
  <p class="label">Do this</p>
  <ol>
    {''.join(f'<li>{_esc_jp(step)}</li>' for step in steps)}
  </ol>
  {labels}
  <div class="done-when">
    <p class="label">Done when</p>
    <p>{_esc_jp(task["success_criterion"])}</p>
  </div>
  <p class="minutes">About {int(task["estimated_minutes"])} minutes.</p>
  <div class="checkline">
    {checkline}
  </div>
  <p class="sources">{source_line}</p>
  <footer>Printed from Coursebook. Local print or download only; nothing is sent.</footer>
</article>"""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_esc(task['title'])}</title>\n<style>{_SHEET_CSS}</style>\n</head>\n"
        f"<body>{body}</body>\n</html>\n"
    )


class _TextExtractor(HTMLParser):
    """Visible text of a rendered sheet: no head, no style, no scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):  # noqa: ANN001 - stdlib signature
        if tag in ("head", "style", "script", "title"):
            self._skip += 1

    def handle_endtag(self, tag):  # noqa: ANN001 - stdlib signature
        if tag in ("head", "style", "script", "title") and self._skip:
            self._skip -= 1

    def handle_data(self, data):  # noqa: ANN001 - stdlib signature
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def sheet_text(html_text: str) -> str:
    parser = _TextExtractor()
    parser.feed(html_text)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def sheet_is_single_page(html_text: str) -> bool:
    """Structurally one sheet: exactly one article and no forced page break."""
    return html_text.count('<article class="sheet"') == 1 and "page-break-after" not in html_text


# ── handlers ────────────────────────────────────────────────────────────────


def _task_payload(row, connection) -> dict[str, Any]:
    target = _load(row["target"], {})
    events = [
        {
            "event_id": str(event["id"]),
            "ordinal": int(event["ordinal"]),
            "kind": str(event["kind"]),
            "actor": str(event["actor"]),
            "note": event["note"],
            "created_at": str(event["created_at"]),
        }
        for event in connection.execute(
            "SELECT * FROM homework_events WHERE task_id = ? ORDER BY ordinal", (str(row["id"]),)
        ).fetchall()
    ]
    state = str(row["state"])
    basis = {
        "self_reported_done": "self_reported",
        "parent_reported_done": "parent_reported",
    }.get(state)
    note = next((event["note"] for event in reversed(events) if event["note"]), None)
    task = {
        "task_id": str(row["id"]),
        "course_id": str(row["course_id"]),
        "enrollment_id": str(row["enrollment_id"]),
        "objective_id": str(row["objective_id"]),
        "source_lesson_version": str(row["source_lesson_version"]),
        "content_hash": str(target.pop("content_hash", "")),
        "audience": str(row["audience"]),
        "task_kind": str(row["task_kind"]),
        "state": state,
        "revision": int(row["revision"]),
        "title": str(row["title"]),
        "target": target,
        "context": str(row["context"]),
        "steps": _load(row["steps_json"], []),
        "success_criterion": str(row["success_criterion"]),
        "estimated_minutes": int(row["estimated_minutes"]),
        "completion": {
            "basis": basis,
            "completed_at": str(row["completed_at"]) if row["completed_at"] else None,
            "note": note,
            # A report by the learner or the parent is not independent verification.
            "independent_verification": False,
        },
        "sources": proposal_sources(target),
        "created_at": str(row["created_at"]),
    }
    task["sheet"] = {
        "paper": "A4",
        "pages": 1,
        "html": sheet_html(task),
        "text": sheet_text(sheet_html(task)),
    }
    return {"task": task, "events": events}


def _task_row(connection, task_id: str):
    row = _row(connection, "SELECT * FROM homework_tasks WHERE id = ?", (task_id,))
    if row is None:
        raise _not_found("homework task", task_id)
    return row


def _enrollment(connection, enrollment_id: str, course_id: str):
    row = _row(connection, "SELECT * FROM enrollments WHERE id = ?", (enrollment_id,))
    if row is None or str(row["course_id"]) != str(course_id):
        raise _not_found("enrollment", enrollment_id)
    return row


def _event(connection, task_id: str, ordinal: int, kind: str, actor: str, note: str | None) -> None:
    connection.execute(
        "INSERT INTO homework_events (id, task_id, ordinal, kind, actor, note, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"hwe_{uuid.uuid4().hex}", task_id, ordinal, kind, actor, note, _now()),
    )


def create(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Propose one task from the source lesson after the policy accepts it."""
    db.ensure_schema()
    expected = _require_expected(envelope)
    method = "homework.create"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    if expected != 0:
        raise _stale("homework.create starts a new task at revision 0.", 0)
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        bundle = takehome.source_content(
            connection,
            str(payload["course_id"]),
            str(payload["objective_id"]),
            str(payload["source_lesson_version"]),
        )
        _enrollment(connection, str(payload["enrollment_id"]), str(payload["course_id"]))
        proposal = proposal_for(bundle, context=str(payload.get("context") or "") or None)
        audience = str(payload["audience"])
        if audience != proposal["audience"] and audience == "parent":
            # A parent may prepare the learner's task; the report basis is chosen at completion,
            # not here, so the audience only decides who the card is written for.
            proposal["audience"] = audience
        target = dict(proposal["target"])
        if proposal.get("completion_record"):
            target["completion_record"] = list(proposal["completion_record"])
        target["content_hash"] = str(bundle["content_hash"])

        existing = _row(
            connection,
            "SELECT * FROM homework_tasks WHERE enrollment_id = ? AND objective_id = ?"
            " AND audience = ? AND task_kind = ? AND state IN ('proposed', 'assigned')"
            " ORDER BY created_at DESC LIMIT 1",
            (str(payload["enrollment_id"]), str(payload["objective_id"]), audience,
             proposal["task_kind"]),
        )
        if existing is not None:
            result = {
                "task_id": str(existing["id"]),
                "task": _task_payload(existing, connection)["task"],
                "state": str(existing["state"]),
                "revision": int(existing["revision"]),
            }
            _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                      int(existing["revision"]), result)
            return int(existing["revision"]), result

        task_id = f"hwt_{uuid.uuid4().hex}"
        stamp = _now()
        connection.execute(
            "INSERT INTO homework_tasks (id, course_id, enrollment_id, objective_id,"
            " source_lesson_version, audience, task_kind, state, revision, title, target, context,"
            " steps_json, success_criterion, estimated_minutes, created_at, completed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 'proposed', 0, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                task_id,
                str(payload["course_id"]),
                str(payload["enrollment_id"]),
                str(payload["objective_id"]),
                str(payload["source_lesson_version"]),
                audience,
                proposal["task_kind"],
                proposal["title"],
                _dump(target),
                proposal["context"],
                _dump(proposal["steps"]),
                proposal["success_criterion"],
                int(proposal["estimated_minutes"]),
                stamp,
            ),
        )
        _event(connection, task_id, 0, "proposed", audience, None)
        row = _task_row(connection, task_id)
        result = {
            "task_id": task_id,
            "task": _task_payload(row, connection)["task"],
            "state": "proposed",
            "revision": 0,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    return 0, result


def read(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """One task and its append-only events, with the one-page sheet and its cited sources."""
    db.ensure_schema()
    with db.read() as connection:
        row = _task_row(connection, str(payload["task_id"]))
        return 0, _task_payload(row, connection)


def complete(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Record an honest report: self_reported_done or parent_reported_done. Never a pass."""
    db.ensure_schema()
    expected = _require_expected(envelope)
    method = "homework.complete"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    actor = str(payload["actor"])
    if actor not in ("learner", "parent"):
        raise RpcError.of("VALIDATION_FAILED", "actor is learner or parent.", field="actor")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        row = _task_row(connection, str(payload["task_id"]))
        state = str(row["state"])
        if state in COMPLETION_STATES:
            # A second report is the same honest state: no second event, no basis flip.
            result = {
                "task": _task_payload(row, connection)["task"],
                "state": state,
                "completed_at": str(row["completed_at"]) if row["completed_at"] else None,
            }
            _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                      int(row["revision"]), result)
            return int(row["revision"]), result
        if int(row["revision"]) != expected:
            raise _stale("the homework task changed; re-read before completing it.",
                         int(row["revision"]))
        if state in ("skipped", "expired"):
            raise _policy(
                "task_closed",
                "this task was closed without a report; it cannot be reported done now.",
                state=state,
            )
        new_state = "parent_reported_done" if actor == "parent" else "self_reported_done"
        kind = "parent_reported" if actor == "parent" else "self_reported"
        stamp = _now()
        connection.execute(
            "UPDATE homework_tasks SET state = ?, revision = revision + 1, completed_at = ?"
            " WHERE id = ?",
            (new_state, stamp, str(row["id"])),
        )
        _event(connection, str(row["id"]), int(row["revision"]) + 1, kind, actor,
               str(payload.get("note") or "") or None)
        updated = _task_row(connection, str(row["id"]))
        result = {
            "task": _task_payload(updated, connection)["task"],
            "state": new_state,
            "completed_at": stamp,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                  int(updated["revision"]), result)
    return int(updated["revision"]), result


def skip(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Record an honest skip. No penalty, no streak loss, no fabricated completion."""
    db.ensure_schema()
    expected = _require_expected(envelope)
    method = "homework.skip"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    actor = str(payload["actor"])
    if actor not in ("learner", "parent"):
        raise RpcError.of("VALIDATION_FAILED", "actor is learner or parent.", field="actor")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        row = _task_row(connection, str(payload["task_id"]))
        state = str(row["state"])
        if state == "skipped":
            result = {"task": _task_payload(row, connection)["task"], "state": "skipped"}
            _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                      int(row["revision"]), result)
            return int(row["revision"]), result
        if int(row["revision"]) != expected:
            raise _stale("the homework task changed; re-read before skipping it.",
                         int(row["revision"]))
        if state in COMPLETION_STATES:
            raise _policy(
                "already_reported",
                "this task already carries a report; skipping cannot overwrite it.",
                state=state,
            )
        connection.execute(
            "UPDATE homework_tasks SET state = 'skipped', revision = revision + 1 WHERE id = ?",
            (str(row["id"]),),
        )
        _event(connection, str(row["id"]), int(row["revision"]) + 1, "skipped", actor, None)
        updated = _task_row(connection, str(row["id"]))
        result = {"task": _task_payload(updated, connection)["task"], "state": "skipped"}
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                  int(updated["revision"]), result)
    return int(updated["revision"]), result


HANDLERS = {
    "homework.create": create,
    "homework.read": read,
    "homework.complete": complete,
    "homework.skip": skip,
}
