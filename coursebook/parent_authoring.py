"""Authored parent course → ``cb.pack`` document, content hash and handout PDF.

One builder shared by the three v6 commands that must agree about *exactly which bytes were
approved*:

* ``parent.blueprint.read`` serves the tab text and reports ``content_hash``;
* ``parent.final.approve`` binds that hash;
* ``parent.export`` recomputes it and refuses when it no longer matches the active approval.

If the three ever disagreed, a parent could approve one page and export another. So the text
composition, the digest and the manifest are produced here once and imported by
:mod:`coursebook.domain` and :mod:`coursebook.pack_flow`.

Rules this module keeps:

* **Answers never reach a learner file.** ``answer_guide`` is a separate role; the learner page
  and narration text are checked against the check's reference answer before a digest exists.
* **Only declared material is written.** Every file is composed from ``gen_lessons.page_json``,
  the plan objective and the check row. Notebook entries, attempts, reflections, transcripts and
  provider settings have no path into this module.
* **No fabrication.** A missing reference answer, a lesson parked for review, or an objective
  with no section stops the export with a typed refusal instead of a plausible-looking file.
* **Narration is a tab, not a pack file.** ``cb.pack`` requires ``audio/*`` MIME for the
  ``narration`` role (``packs._role_mime_mismatch``); an authored course has a narration
  *script*, not audio, so the script rides in the narration tab and in the parent guide, and the
  pack never claims an audio file it does not have.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from . import lesson_document
from . import packs

#: The roles an authored parent pack may declare. All four exist in ``cb.pack``'s role enum.
EXPORT_ROLES: tuple[str, ...] = ("parent_guide", "learner_page", "answer_guide", "narration")

#: Roles that carry a text file in an authored pack. ``narration`` is audio-only in ``cb.pack``.
TEXT_ROLES: tuple[str, ...] = ("parent_guide", "learner_page", "answer_guide")

#: Page text served in one blueprint tab entry before it is marked truncated.
MAX_BLUEPRINT_CHARS = 20000

#: Roles whose text must never contain a check's reference answer.
LEARNER_ROLES: frozenset[str] = frozenset({"learner_page", "narration"})

#: The licence an authored course is packaged under. An authored export is a local copy, never a
#: publication and never a redistribution grant, so the rights statement is fixed with the licence.
AUTHORED_LICENSE: dict[str, str] = {"id": "all-rights-reserved", "redistribution": "local_only"}

#: The one learner-page state a page may be exported from. ``generation`` writes ``validated`` only
#: after its independent validator passed; anything else (missing row, ``draft``,
#: ``needs_review``) is content a validator has not cleared.
VALIDATED_LESSON_STATE = "validated"


class AuthoredExportBlocked(RuntimeError):
    """The authored course cannot be exported right now, with the reason the studio renders."""

    def __init__(self, reason: str, message: str, problems: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.reason = reason
        self.problems = [str(problem) for problem in problems]


# ── small helpers ───────────────────────────────────────────────────────────


def _load(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def sha256_text(text: str) -> str:
    return packs.file_sha256(text.encode("utf-8"))


def text_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def slug(value: str, fallback: str) -> str:
    """ASCII-safe, deterministic pack-internal name component."""
    lowered = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return lowered[:40] or fallback


def _normalized(text: str) -> str:
    return " ".join(str(text).casefold().split())


def _bullet(items: Iterable[Any]) -> list[str]:
    lines: list[str] = []
    for item in items:
        text = " ".join(str(item or "").split())
        if text:
            lines.append(f"- {text}")
    return lines


# ── rows ────────────────────────────────────────────────────────────────────


def current_plan(connection, course_id: str) -> Any:
    """The plan the studio is looking at: approved first, else newest version."""
    return connection.execute(
        "SELECT * FROM plans WHERE course_id = ?"
        " ORDER BY (state = 'approved') DESC, version DESC LIMIT 1",
        (course_id,),
    ).fetchone()


def plan_hash(connection, plan) -> str:
    """The kernel's plan digest. One implementation, shared with :mod:`coursebook.domain`.

    ``domain._plan_hash`` delegates here so the hash a parent approves (``plan.approve``), the
    hash ``parent.blueprint.read`` reports and the hash inside ``content_hash`` can never drift.

    R4 legacy invariance is structural, not a special case: the ``units`` key is added only when
    at least one ``plan_units`` row exists, and an objective's ``unit`` key only when its
    ``unit_id`` is non-NULL. A plan stored before migration 0007 therefore hashes exactly the
    payload it hashed under v6 — byte for byte, so every stored ``plan_content_hash`` keeps
    binding. A unit retitle or a prerequisite change *does* change the hash, because it changes
    what the learner approved.
    """
    objective_columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(objectives)").fetchall()
    }
    has_unit_column = "unit_id" in objective_columns
    select = "SELECT id, ordinal, title, evidence_target, evidence_criteria_json, version"
    if has_unit_column:
        select += ", unit_id"
    objectives = connection.execute(
        select + " FROM objectives WHERE plan_id = ? ORDER BY ordinal",
        (plan["id"],),
    ).fetchall()
    payload = {
        "course_id": plan["course_id"],
        "version": plan["version"],
        "schedule": _load(plan["schedule_json"], {}),
        "objectives": [
            _objective_hash_entry(row, has_unit_column) for row in objectives
        ],
    }
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    units = []
    if "plan_units" in tables:
        units = connection.execute(
            "SELECT id, ordinal, title, goal, prereq_unit_ordinals_json, target_lessons"
            " FROM plan_units WHERE plan_id = ? ORDER BY ordinal",
            (plan["id"],),
        ).fetchall()
    if units:
        payload["units"] = [
            {
                "id": row["id"],
                "ordinal": row["ordinal"],
                "title": row["title"],
                "goal": row["goal"],
                "prereq_unit_ordinals": _load(row["prereq_unit_ordinals_json"], []),
                "target_lessons": row["target_lessons"],
            }
            for row in units
        ]
    return "sha256:" + hashlib.sha256(packs.canonical_json_bytes(payload)).hexdigest()


def _objective_hash_entry(row, has_unit_column: bool) -> dict[str, Any]:
    """One objective's hash entry. ``unit`` exists only for a unit-scoped (post-0007) row."""
    entry = {
        "id": row["id"],
        "ordinal": row["ordinal"],
        "title": row["title"],
        "evidence_target": row["evidence_target"],
        "evidence_criteria": _load(row["evidence_criteria_json"], []),
        "version": row["version"],
    }
    if has_unit_column and row["unit_id"] is not None:
        entry["unit"] = row["unit_id"]
    return entry


def _objectives(connection, plan_id: str) -> list[Any]:
    return list(
        connection.execute(
            "SELECT * FROM objectives WHERE plan_id = ? ORDER BY ordinal", (plan_id,)
        ).fetchall()
    )


def generation_plan_hash(connection, plan_id: str, fallback: str = "") -> str:
    """The digest the generation rows were written under.

    ``generation.run_plan_job`` persists ``plans.plan_hash`` from its own document hash, which is
    a different function from the kernel's ``domain._plan_hash`` used by ``plan.approve``. Lessons
    join on the generation digest; the approved hash is the wire hash. Reading the digest here
    (instead of guessing) is what keeps a re-approved plan's lessons readable.
    """
    row = connection.execute(
        "SELECT plan_hash FROM gen_plan_documents WHERE plan_id = ? ORDER BY created_at DESC LIMIT 1",
        (str(plan_id),),
    ).fetchone()
    if row is not None and row["plan_hash"]:
        return str(row["plan_hash"])
    return fallback


def _lesson_rows(connection, plan_id: str, plan_hash: str) -> dict[str, Any]:
    """`section_id -> (section row, lesson row)` for lessons generated against this plan hash."""
    rows = connection.execute(
        "SELECT s.*, l.id AS lesson_id, l.state AS lesson_state, l.page_json AS page_json,"
        " l.parent_notes_json AS parent_notes_json"
        " FROM gen_plan_sections s"
        " LEFT JOIN gen_lessons l ON l.section_id = s.id AND l.plan_hash = ? AND l.version = 1"
        " WHERE s.plan_id = ? ORDER BY s.ordinal",
        (plan_hash, plan_id),
    ).fetchall()
    return {str(row["id"]): row for row in rows}


def _section_check(connection, lesson_id: str) -> Any:
    return connection.execute(
        "SELECT c.* FROM checks c JOIN gen_lesson_checks g ON g.check_id = c.id"
        " WHERE g.lesson_id = ? ORDER BY c.version DESC LIMIT 1",
        (lesson_id,),
    ).fetchone()


def _objective_for_ordinal(connection, plan_id: str, ordinal: int | None) -> Any:
    if ordinal is None:
        return None
    return connection.execute(
        "SELECT * FROM objectives WHERE plan_id = ? AND ordinal = ?", (plan_id, int(ordinal))
    ).fetchone()


# ── text composition ────────────────────────────────────────────────────────


def _label_key(value: str) -> str:
    """The read seam's label normalisation, imported rather than reimplemented.

    ``domain`` imports this module, so the import is local. Using the same function is the point:
    a choice that merely repeats a checklist item's label must not be printed a second time.
    """
    from .domain import _check_label_key

    return _check_label_key(value)


def _learner_page_text(page: Mapping[str, Any]) -> str:
    lines = [f"# {page.get('section_title') or 'Lesson'}", ""]
    for segment in page.get("segments") or []:
        heading = " ".join(str(segment.get("heading") or "").split())
        body = str(segment.get("body") or "").strip()
        if heading:
            lines.append(f"## {heading}")
        if body:
            lines.append(body)
        lines.append("")
    worked = page.get("worked_example") or {}
    if worked.get("prompt"):
        lines.extend(["## Worked example", str(worked["prompt"]), ""])
        for step in worked.get("steps") or []:
            lines.append(f"1. {step}")
        if worked.get("answer"):
            lines.extend(["", f"Answer: {worked['answer']}"])
        lines.append("")
    if page.get("learner_explanation"):
        lines.extend(["## What to notice", str(page["learner_explanation"]), ""])
    check = page.get("check") or {}
    stimulus = check.get("stimulus") or {}
    if stimulus.get("prompt"):
        lines.extend(["## Your turn", str(stimulus["prompt"])])
        # A structured checklist prints one numbered line per authored item: the parent reviews
        # exactly the steps the learner will be asked to confirm, in the authored order, and no
        # label is invented or paraphrased.
        items = [
            str(item.get("label") or "").strip()
            for item in (stimulus.get("items") or [])
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        ]
        printed = {_label_key(label) for label in items}
        for number, label in enumerate(items, start=1):
            lines.append(f"{number}. {label}")
        choices = list(stimulus.get("choices") or [])
        for choice in choices:
            # A choice that only restates an item label is the same step printed twice.
            if _label_key(str(choice)) in printed:
                continue
            lines.append(f"- {choice}")
        if check.get("learner_instructions"):
            lines.extend(["", str(check["learner_instructions"])])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _parent_guide_text(
    *,
    course: Mapping[str, Any],
    section: Mapping[str, Any],
    objective: Any,
    page: Mapping[str, Any],
    notes: Mapping[str, Any],
    context_needs: Sequence[Any],
) -> str:
    lines = [f"# Parent guide — {section['title']}", ""]
    if objective is not None:
        lines.extend(
            [
                f"Objective: {objective['title']}",
                f"Evidence target: {objective['evidence_target']}",
                "",
            ]
        )
    if course["goal"]:
        lines.extend([f"Course goal: {course['goal']}", ""])
    if section["lesson_intent"]:
        lines.extend(["## Lesson intent", str(section["lesson_intent"]), ""])
    if context_needs:
        lines.extend(["## Before you start"] + _bullet(context_needs) + [""])
    explanation = page.get("learner_explanation")
    if explanation:
        lines.extend(["## What the learner will do", str(explanation), ""])
    worked = page.get("worked_example") or {}
    if worked.get("prompt"):
        lines.extend(["## Worked example"])
        lines.append(str(worked["prompt"]))
        for step in worked.get("steps") or []:
            lines.append(f"1. {step}")
        lines.append("")
    parent_notes = notes.get("parent_notes")
    if parent_notes:
        lines.extend(["## Parent notes", str(parent_notes), ""])
    supervision = list(notes.get("supervision_notes") or [])
    if supervision:
        lines.extend(["## Supervision"] + _bullet(supervision) + [""])
    script = _narration_text(page)
    if script:
        lines.extend(["## Narration script", script, ""])
    return "\n".join(lines).strip() + "\n"


def _answer_guide_text(*, section: Mapping[str, Any], objective: Any, check: Any) -> str:
    reference = _load(check["reference_json"] if check is not None else None, {})
    rubric = _load(check["rubric_json"] if check is not None else None, {})
    lines = [f"# Answer guide — {section['title']}", ""]
    if objective is not None:
        lines.extend([f"Objective: {objective['title']}", ""])
    answer = str(reference.get("reference_answer") or "").strip()
    lines.extend(["## Reference answer", answer or "(none declared)", ""])
    accepted = [str(item) for item in reference.get("accepted_answers") or [] if str(item).strip()]
    if accepted:
        lines.extend(["## Accepted answers"] + _bullet(accepted) + [""])
    alternatives = [
        ", ".join(str(item) for item in group)
        for group in reference.get("accepted_alternatives") or []
        if group
    ]
    if alternatives:
        lines.extend(["## Accepted alternatives"] + _bullet(alternatives) + [""])
    criteria = _rubric_strings(rubric)
    if criteria:
        lines.extend(["## Rubric"] + [f"{index}. {item}" for index, item in enumerate(criteria, start=1)] + [""])
    return "\n".join(lines).strip() + "\n"


def _narration_text(page: Mapping[str, Any]) -> str:
    lines: list[str] = []
    for segment in page.get("segments") or []:
        body = " ".join(str(segment.get("body") or "").split())
        if body:
            lines.append(body)
    return "\n".join(lines)


def _rubric_strings(rubric: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for item in rubric.get("criteria") or []:
        if isinstance(item, Mapping):
            text = item.get("description") or item.get("criterion") or ""
        else:
            text = item
        text = " ".join(str(text or "").split())
        if text and text not in values:
            values.append(text)
    return values


# ── the assembled course ────────────────────────────────────────────────────


def sections(connection, course, plan) -> list[dict[str, Any]]:
    """Compose every exportable section: file text per role, plus the tab fields."""
    plan_id = str(plan["id"])
    plan_hash = generation_plan_hash(connection, plan_id, str(plan["plan_hash"] or ""))
    rows = _lesson_rows(connection, plan_id, plan_hash)
    result: list[dict[str, Any]] = []
    for section_id in sorted(rows, key=lambda key: int(rows[key]["ordinal"])):
        row = rows[section_id]
        objective_refs = _load(row["objective_refs_json"], [])
        ordinal = int(objective_refs[0]) if objective_refs else int(row["ordinal"])
        objective = _objective_for_ordinal(connection, plan_id, ordinal)
        page = _load(row["page_json"], None)
        base = {
            "section_id": section_id,
            "ordinal": int(row["ordinal"]),
            "title": str(row["title"]),
            "lesson_intent": row["lesson_intent"],
            "objective_id": str(objective["id"]) if objective is not None else str(plan_id),
            "objective_title": str(objective["title"]) if objective is not None else str(row["title"]),
            "objective": objective,
            "lesson_id": row["lesson_id"],
            "lesson_state": row["lesson_state"],
            "page": page if isinstance(page, dict) else None,
            "notes": {},
            "paths": {},
            "files": {},
        }
        if base["page"] is None:
            result.append(base)
            continue
        check = _section_check(connection, str(row["lesson_id"]))
        notes = _load(row["parent_notes_json"], {})
        base["notes"] = notes if isinstance(notes, dict) else {}
        page_dict = base["page"]
        context_needs = _load(row["context_needs_json"], [])
        base["check"] = check
        base["files"] = {
            "learner_page": _learner_page_text(page_dict),
            "parent_guide": _parent_guide_text(
                course=course,
                section=row,
                objective=objective,
                page=page_dict,
                notes=notes if isinstance(notes, dict) else {},
                context_needs=context_needs if isinstance(context_needs, list) else [],
            ),
            "answer_guide": _answer_guide_text(
                section=row, objective=objective, check=check
            ),
        }
        script = _narration_text(page_dict)
        if script:
            base["files"]["narration"] = script + "\n"
        result.append(base)
    return result


def ready_sections(composed: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Sections that carry generated, validated content. Anything else blocks the export."""
    return [section for section in composed if section.get("page") is not None]


def validated_sections(
    composed: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], list[str]]:
    """Split a composed course into ``(validated, problems)``.

    The authored-export gate (``course.export``) ships only pages a validator cleared: every
    section must have a generated page *and* a ``gen_lessons`` row in ``validated`` state. A page
    parked for review is content a model wrote, not content that passed; exporting it would hand
    a reader a lesson the harness itself refused. ``problems`` names each section by ordinal and
    observed state so the surface can show exactly which page blocks and why.
    """
    validated: list[Mapping[str, Any]] = []
    problems: list[str] = []
    for section in composed:
        label = f"section {int(section['ordinal'])} ({str(section.get('title') or 'untitled')})"
        if section.get("page") is None:
            problems.append(f"{label} has no generated page")
            continue
        state = str(section.get("lesson_state") or "")
        if state != VALIDATED_LESSON_STATE:
            problems.append(f"{label} is {state or 'not generated'}, not validated")
            continue
        validated.append(section)
    return validated, problems


def content_hash(course_id: str, plan_id: str, plan_hash: str, composed: Sequence[Mapping[str, Any]]) -> str:
    """The frozen v6 definition. Depends only on the served text, never on a file name."""
    payload = {
        "course_id": str(course_id),
        "plan_id": str(plan_id),
        "plan_hash": str(plan_hash),
        "sections": [
            {
                "objective_id": str(section["objective_id"]),
                "ordinal": int(section["ordinal"]),
                "files": {
                    role: {"sha256": sha256_text(text), "bytes": text_bytes(text)}
                    for role, text in sorted((section.get("files") or {}).items())
                },
            }
            for section in composed
            if section.get("page") is not None
        ],
    }
    return "sha256:" + hashlib.sha256(packs.canonical_json_bytes(payload)).hexdigest()


# ── blueprint tabs ──────────────────────────────────────────────────────────


def blueprint_file(role: str, title: str, text: str, objective_id: str | None, *, limit: int) -> dict[str, Any]:
    """One `blueprint_file`. Hash and size describe the full declared text; `text` may clip."""
    served = text[:limit]
    return {
        "role": role,
        "title": title[:300] or role,
        "objective_id": objective_id,
        "text": served,
        "sha256": sha256_text(text),
        "bytes": text_bytes(text),
        "source": "authored",
        "truncated": len(text) > len(served),
    }


def blueprint_tabs(composed: Sequence[Mapping[str, Any]], *, limit: int = MAX_BLUEPRINT_CHARS) -> dict[str, list[dict[str, Any]]]:
    tabs: dict[str, list[dict[str, Any]]] = {
        "parent_guide": [],
        "learner_pages": [],
        "answers": [],
        "narration": [],
    }
    for section in composed:
        if section.get("page") is None:
            continue
        files = section.get("files") or {}
        title = f"{int(section['ordinal']):02d} · {section['title']}"
        tabs["parent_guide"].append(
            blueprint_file("parent_guide", title, files.get("parent_guide", ""), section["objective_id"], limit=limit)
        )
        tabs["learner_pages"].append(
            blueprint_file("learner_page", title, files.get("learner_page", ""), section["objective_id"], limit=limit)
        )
        tabs["answers"].append(
            blueprint_file("answer_guide", title, files.get("answer_guide", ""), section["objective_id"], limit=limit)
        )
        if files.get("narration"):
            tabs["narration"].append(
                blueprint_file("narration", title, files["narration"], section["objective_id"], limit=limit)
            )
    return tabs


# ── pack document ───────────────────────────────────────────────────────────


_PACK_SOURCE_TYPES = {
    "government": "reference",
    "academic": "reference",
    "encyclopedia": "reference",
    "organization": "reference",
    "web_page": "secondary",
    "unverified": "unverified",
}


def pack_sources(connection, course_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM sources WHERE course_id = ? ORDER BY created_at", (course_id,)
    ).fetchall()
    sources: list[dict[str, Any]] = []
    for row in rows:
        entry: dict[str, Any] = {
            "source_id": str(row["id"]),
            "title": str(row["title"])[:500] or "Source",
            "source_type": _PACK_SOURCE_TYPES.get(str(row["source_type"]), "unverified"),
        }
        if row["url"]:
            entry["url"] = str(row["url"])[:1000]
        if row["published_at"]:
            entry["published_at"] = str(row["published_at"])[:40]
        if row["fetched_at"]:
            entry["fetched_at"] = str(row["fetched_at"])[:40]
        entry["support_status"] = str(row["support_status"])
        sources.append(entry)
    return sources


def _check_rubric(check: Any, objective: Any) -> list[str]:
    """Real declared assessment criteria only: the check rubric plus the plan's evidence criteria.

    Supervision notes are safety instructions, already rendered in the parent guide; they are not
    grading criteria and never enter a rubric. Nothing is invented to reach the pack's
    three-criteria floor: if the declared criteria are fewer than three,
    ``packs.validate_minima`` refuses the pack and the export reports it.
    """
    values: list[str] = []
    if check is not None:
        values.extend(_rubric_strings(_load(check["rubric_json"], {})))
    criteria = _load(objective["evidence_criteria_json"], []) if objective is not None else []
    for item in criteria:
        text = " ".join(str(item or "").split())
        if text and text not in values:
            values.append(text)
    return values


def build_pack(
    connection,
    course,
    plan,
    composed: Sequence[Mapping[str, Any]],
    *,
    pack_prefix: str = "parent",
    attribution: str | None = None,
    contributors: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Assemble a fresh ``cb.pack`` v1 document. Never copies a stored manifest.

    The identity/attribution keywords let the general authored export (``course.export``) ship a
    learner-authored course under its own ``authored-`` pack identity and wording while this one
    builder keeps a single definition of *which bytes* the course is. Defaults reproduce the
    Parent Studio pack exactly, so ``parent.export`` is unchanged.
    """
    generated: list[dict[str, Any]] = [dict(item) for item in ready_sections(composed)]
    if not generated:
        raise AuthoredExportBlocked("no_generated_content", "this course has no generated lesson content yet.")

    objectives = _objectives(connection, str(plan["id"]))
    by_id = {str(row["id"]): row for row in objectives}
    section_by_objective: dict[str, list[Mapping[str, Any]]] = {}
    for section in generated:
        section_by_objective.setdefault(str(section["objective_id"]), []).append(section)

    missing = [str(row["id"]) for row in objectives if str(row["id"]) not in section_by_objective]
    if missing:
        raise AuthoredExportBlocked(
            "no_generated_content",
            "some approved objectives have no generated section; regenerate lessons before exporting.",
            problems=[f"objective {objective_id} has no generated section" for objective_id in missing],
        )

    files: dict[str, bytes] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for section in generated:
        slug_value = slug(str(section["title"]), f"section-{int(section['ordinal']):02d}")
        paths = {
            "parent_guide": f"parent-guide/{int(section['ordinal']):02d}-{slug_value}.md",
            "learner_page": f"lessons/{int(section['ordinal']):02d}-{slug_value}.md",
            "answer_guide": f"answer-guide/{int(section['ordinal']):02d}-{slug_value}.md",
        }
        section["paths"] = paths
        for role, text in (section.get("files") or {}).items():
            if role not in TEXT_ROLES:
                continue
            data = str(text).encode("utf-8")
            files[paths[role]] = data
            metadata[paths[role]] = {"mime": "text/markdown", "role": role}

    pack_objectives: list[dict[str, Any]] = []
    for row in objectives:
        objective_id = str(row["id"])
        objective_sections = section_by_objective[objective_id]
        checks: list[dict[str, Any]] = []
        for section in objective_sections:
            check = section.get("check")
            if check is None:
                raise AuthoredExportBlocked(
                    "no_generated_content",
                    f"section {section['title']!r} has no check; lessons must validate before export.",
                )
            reference = _load(check["reference_json"], {})
            answer = str(reference.get("reference_answer") or "").strip()
            if not answer:
                raise AuthoredExportBlocked(
                    "no_generated_content",
                    f"check {check['id']} declares no reference answer.",
                )
            stimulus = _load(check["stimulus_json"], {})
            rubric = _check_rubric(check, row)
            entry: dict[str, Any] = {
                "check_id": str(check["id"]),
                "version": int(check["version"]),
                "evidence_target": str(check["evidence_target"]),
                "stimulus": str(stimulus.get("prompt") or section["title"])[:8000],
                "rubric": rubric[:40],
                "reference_answer": answer[:8000],
            }
            # Alternates are additional correct answers, never the reference answer echoed back:
            # ``packs.validate_minima`` refuses a check that lists its own reference as one.
            accepted: list[str] = []
            seen: set[str] = set()
            for item in reference.get("accepted_answers") or []:
                text = str(item).strip()
                key = _normalized(text)
                if not text or key == _normalized(answer) or key in seen:
                    continue
                seen.add(key)
                accepted.append(text)
            if accepted:
                entry["accepted_alternatives"] = accepted[:40]
            if check["locale"]:
                entry["locale"] = str(check["locale"])[:35]
            entry["audit_state"] = "passed" if str(check["audit_state"]) == "passed" else "unreviewed"
            checks.append(entry)
        criteria = [
            " ".join(str(item or "").split())
            for item in _load(row["evidence_criteria_json"], [])
            if str(item or "").strip()
        ] or [str(row["title"])]
        pack_objectives.append(
            {
                "objective_id": objective_id,
                "ordinal": int(row["ordinal"]),
                "title": str(row["title"])[:300],
                "evidence_target": str(row["evidence_target"]),
                "evidence_criteria": criteria[:20],
                "sections": [
                    {
                        "section_id": str(section["section_id"]),
                        "title": str(section["title"])[:300],
                        "path": str(section["paths"]["learner_page"]),
                    }
                    for section in objective_sections
                ],
                "checks": checks,
            }
        )

    attribution = attribution or f"{course['title']} — authored by the parent in Coursebook."
    optional: dict[str, Any] = {}
    if course["locale"]:
        optional["locale"] = str(course["locale"])
    # Only reachable when a course row somehow has an empty title; the fallback follows the
    # identity so a parent pack keeps the wording it always had.
    title_fallback = "Parent course" if pack_prefix == "parent" else "Authored course"
    manifest = packs.build_manifest(
        pack_id=_pack_id(str(course["id"]), pack_prefix),
        pack_version="1.0.0",
        title=str(course["title"])[:200] or title_fallback,
        recipe=str(course["recipe"]),
        minimum_coursebook_version="0.1.0",
        license=dict(AUTHORED_LICENSE),
        attribution=attribution,
        contributors=list(contributors)
        if contributors is not None
        else [{"name": "Parent author", "role": "author"}],
        objectives=pack_objectives,
        files=files,
        file_metadata=metadata,
        sources=pack_sources(connection, str(course["id"])) or None,
        **optional,
    )
    _assert_no_answer_leak(manifest, files, generated)
    return manifest, files


def _pack_id(course_id: str, prefix: str = "parent") -> str:
    suffix = re.sub(r"[^a-z0-9]+", "-", str(course_id).lower()).strip("-") or "course"
    return f"{prefix}-{suffix}"[:128].rstrip("-")


#: The one authored learner surface where a lesson presents the form it later checks. A
#: ``model`` segment (and the narration that reads it) teaches the target; naming the function in
#: the explain step is not presentation. Same boundary as ``generation._narrative_text``; see
#: docs/DECISION-TAUGHT-TARGET.md.
_PRESENTING_SEGMENT_KIND = "model"
_PRESENTING_MEDIA_ROLE = "narration"


def _is_presenting_segment(segment: Mapping[str, Any]) -> bool:
    return str(segment.get("kind") or "").strip().casefold() == _PRESENTING_SEGMENT_KIND


def _is_presenting_media(item: Mapping[str, Any]) -> bool:
    return str(item.get("role") or "").strip().casefold() == _PRESENTING_MEDIA_ROLE


def _learner_scan_text(page: Mapping[str, Any]) -> str:
    """The learner-page strings where an answer must not be *announced*, normalised.

    Mirrors ``generation._narrative_text`` on the fields an authored page carries: ``model``
    segments and ``narration`` media are the presenting surface and are skipped; every other
    segment, the worked example, the explanation and non-narration media are scanned. A ``model``
    segment's projected ``document`` block is skipped by its ``deep`` text, never by role, because
    the worked example is also an ``example`` block. An authored ``document`` with no model
    segment has no presenting block: all of it is scanned.
    """
    parts: list[str] = []
    presented: set[str] = set()
    for segment in page.get("segments") or []:
        if not isinstance(segment, Mapping):
            continue
        if _is_presenting_segment(segment):
            body = _normalized(str(segment.get("body") or ""))
            if body:
                presented.add(body)
            continue
        parts.extend(
            [
                str(segment.get("heading") or ""),
                str(segment.get("body") or ""),
                str(segment.get("short") or ""),
            ]
        )
    worked = page.get("worked_example") or {}
    parts.extend(
        [
            str(worked.get("prompt") or ""),
            str(worked.get("answer") or ""),
            str(worked.get("short") or ""),
        ]
    )
    parts.extend(str(step) for step in worked.get("steps") or [])
    parts.extend(
        [
            str(page.get("learner_explanation") or ""),
            str(page.get("learner_explanation_short") or ""),
        ]
    )
    for item in page.get("media") or []:
        if not isinstance(item, Mapping) or _is_presenting_media(item):
            continue
        parts.extend(
            [
                str(item.get("purpose") or ""),
                str(item.get("text_equivalent") or ""),
                str(item.get("label") or ""),
            ]
        )
    document = page.get("document")
    if isinstance(document, Mapping):
        parts.append(
            lesson_document.narrative_text(
                document,
                skip_block=lambda block: _normalized(str(block.get("deep") or "")) in presented,
                skip_media=_is_presenting_media,
            )
        )
    return _normalized("\n".join(parts))


def _assert_no_answer_leak(manifest: Mapping[str, Any], files: Mapping[str, bytes], composed: Sequence[Mapping[str, Any]]) -> None:
    """Defence in depth: no reference answer may be *announced* in learner-facing narrative.

    The rule is the one ``generation._narrative_text`` applies (docs/DECISION-TAUGHT-TARGET.md):
    a lesson has to be able to teach the item it checks, so the one authored presenting
    surface — ``kind: model`` segments and ``role: narration`` media — is exempt from the key
    scan. Every other learner surface is scanned: explain/guided/retrieval segments, the worked
    example, the explanation, non-narration media, and an authored ``document`` (which carries no
    segment kind, so none of its blocks is presenting).

    The scan reads ``page`` rather than the rendered learner page: the segment kinds live there,
    and the exported text is composed from it. The ``narration`` file is a reading of the segment
    bodies, so it is a presenting surface and is not scanned on its own; a leak in an explain or
    guided body is caught on that segment. The check's stimulus and choices stay out of the scan:
    in a selection check the correct option necessarily appears in the page.

    ``files`` is kept in the signature because the guard runs at manifest-build time; the bytes
    are derived from ``page`` and add no surface the page does not carry.
    """
    narrative_parts: list[str] = []
    for section in composed:
        page = section.get("page")
        if not isinstance(page, Mapping):
            continue
        narrative_parts.append(_learner_scan_text(page))
    narrative = _normalized("\n".join(narrative_parts))
    for objective in manifest.get("objectives") or []:
        for check in objective.get("checks") or []:
            answer = _normalized(str(check.get("reference_answer") or ""))
            if len(answer) < 2:
                continue
            if answer in narrative:
                raise AuthoredExportBlocked(
                    "answer_leak_in_learner_page",
                    "a reference answer appears in learner-facing narrative; export refused.",
                    problems=[f"check {check['check_id']} leaks its reference answer"],
                )


# ── PDF ─────────────────────────────────────────────────────────────────────


def pdf_lines(course, plan, composed: Sequence[Mapping[str, Any]]) -> tuple[str, list[str]]:
    """Low-ink handout body: title + every learner page + the answer guide, as plain lines."""
    title = f"{course['title']} — parent pack"
    lines: list[str] = [
        f"Course: {course['title']}",
        f"Plan version {plan['version']} · {plan['plan_hash']}",
        f"Minimum Coursebook version: 0.1.0",
        "",
    ]
    for section in composed:
        if section.get("page") is None:
            continue
        files = section.get("files") or {}
        lines.extend(["", f"===== Section {int(section['ordinal'])}: {section['title']} =====", ""])
        lines.extend(str(files.get("learner_page") or "").splitlines())
        lines.extend(["", "--- Answer guide (parent only) ---", ""])
        lines.extend(str(files.get("answer_guide") or "").splitlines())
    return title, lines


def pdf_bytes(course, plan, composed: Sequence[Mapping[str, Any]]) -> bytes:
    from . import artifacts

    title, lines = pdf_lines(course, plan, composed)
    return artifacts.make_pdf(title, lines)
