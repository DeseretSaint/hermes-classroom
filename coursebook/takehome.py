"""Take-home packs over an existing Game or Textbook lesson (GM-005).

A take-home pack is a **rendered print artifact**, not a course, not a ``cb.pack`` and not a
``course.export``. This module is the one backend path ``takehome.*`` uses:

* :func:`sources` reads one learner course's objectives, section and validated lesson version;
* :func:`preview` composes the exact pages of the source lesson and persists nothing;
* :func:`create` writes a ``takehome_packs`` row bound to ``source_course_id``,
  ``source_objective_id``, ``source_lesson_version`` and ``content_hash``;
* :func:`approve` freezes ``approval_hash`` over the exact previewed pages;
* :func:`export` renders those bound bytes to selectable-text PDF through the artifact store,
  never re-reading the live lesson;
* :func:`read` returns the stored pack with the learner page and the answer guide as separate
  page objects.

Rules this module keeps:

* **The source course is read-only.** No command here writes ``courses``, ``plans``,
  ``objectives``, ``gen_lessons``, ``checks``, ``attempts`` or ``evidence``. The tests snapshot
  those tables across a full preview/create/approve/export cycle.
* **The learner page never carries the answer guide.** The learner page is composed from the
  lesson's teaching blocks only; the reference answer, accepted answers and rubric live in a
  separate ``answer_guide`` page object. A defence-in-depth scan refuses a pack whose learner
  narrative announces a reference answer.
* **Bound bytes, not a regenerated lesson.** Export renders ``content_json`` stored at create
  time, so an edit to the source after binding cannot silently change the printed pack.
* **No private rows.** Attempts, notebook entries, tutor turns, observations and engagement are
  never read here; ``takehome.read`` returns only the pack.
* **Named errors.** A missing course, objective or lesson version is ``NOT_FOUND``; a
  parent-only authoring course, an unvalidated lesson, an unapproved export, a stale approval
  and AI art used as a procedure are ``POLICY_VIOLATION`` with a discriminating
  ``details.reason``.
* **Print output is selectable text and audience-gated.** Export uses
  :func:`coursebook.artifacts.make_pdf` — the same low-ink PDF template the authored export uses —
  with explicit page breaks. Markdown heading markers are converted to typographic headings, never
  printed literally. A learner-audience copy prints only the cover, learner page and captioned
  plates; the parent guide and the parent-only answer guide are printed only for a parent pack.
  No image of text, no colour-only meaning.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Mapping, Sequence

from . import artifacts, db, gm_contract, lesson_document
from . import parent_authoring as authoring
from .api import RpcError

#: Lesson states a pack may render. ``needs_review`` is an authored edit no one approved, and a
#: pack is a printed artifact a parent may hand to a learner, so it is refused.
SERVED_LESSON_STATES = ("validated", "model_assessed", "parent_approved")

#: The print profile every exported pack declares. Letter is the PDF template's native size;
#: A4 proofing is the same fixed template at 595 x 842 (see the GM-005 audit proof script).
PRINT_PROFILE: dict[str, Any] = {
    "paper": "letter",
    "width_pt": 612,
    "height_pt": 792,
    "margin_pt": 56,
    "selectable_text": True,
    "low_ink": True,
    "page_breaks": True,
    "color_only_answers": False,
    "learner_answer_key": False,
}

#: The separator line printed at the top of the parent-only answer guide page.
ANSWER_GUIDE_RULE = "Answer guide - parent only"

#: Roles a world plate may carry in a printed pack. A world plate is captioned orientation.
PLATE_ROLES = ("cover", "section", "lesson_scene")

#: Media roles that can serve as an instructional diagram. Anything else is orientation art.
DIAGRAM_ROLES = ("schematic", "sourced_technical")

#: The frozen contract's page ceiling for ``takehome.preview``/``takehome.create``. Four pages
#: are always the composed base (cover, parent guide, learner page, answer guide); the rest is a
#: shared budget for captioned plates and diagrams, so a full world kit can never overflow the
#: response schema and become an INTERNAL_ERROR.
MAX_PACK_PAGES = 12
BASE_PAGE_ROLES = ("cover", "parent_guide", "learner_page", "answer_guide")
PLATE_BUDGET = MAX_PACK_PAGES - len(BASE_PAGE_ROLES)


# ── small helpers ───────────────────────────────────────────────────────────


def _now() -> str:
    return db.utcnow()


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
    error = RpcError.of("STALE_REVISION", message, current_revision=current)
    error.error["current_revision"] = current
    return error


def _idempotent_lookup(connection, key: str | None, method: str, payload_hash: str):
    """Replay the persisted result for the same key + payload; refuse a different payload."""
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


# ── source lesson resolution ────────────────────────────────────────────────


def _course(connection, course_id: str):
    course = _row(connection, "SELECT * FROM courses WHERE id = ?", (course_id,))
    if course is None or str(course["status"]) == "deleted":
        raise _not_found("course", course_id)
    return course


def _current_plan(connection, course_id: str):
    plan = _row(
        connection,
        "SELECT * FROM plans WHERE course_id = ?"
        " ORDER BY (state = 'approved') DESC, version DESC LIMIT 1",
        (course_id,),
    )
    if plan is None:
        raise _not_found("plan for course", course_id)
    return plan


def _plan_hash(connection, plan) -> str:
    return authoring.generation_plan_hash(connection, str(plan["id"]), str(plan["plan_hash"] or ""))


def _section_for_objective(connection, plan_id: str, objective) -> Any:
    """The generated section that owns *objective*, by its authored objective references.

    ``gen_plan_sections.objective_refs_json`` is the authored mapping; the plan ordinal is the
    fallback so a single-objective unit still resolves. Nothing is guessed from a title.
    """
    ordinal = int(objective["ordinal"])
    sections = connection.execute(
        "SELECT * FROM gen_plan_sections WHERE plan_id = ? ORDER BY ordinal", (plan_id,)
    ).fetchall()
    for section in sections:
        refs = _load(section["objective_refs_json"], [])
        if isinstance(refs, list) and ordinal in [int(item) for item in refs if str(item).isdigit()]:
            return section
    for section in sections:
        if int(section["ordinal"]) == ordinal:
            return section
    return None


def _lesson_for_section(connection, section_id: str, plan_hash: str) -> Any:
    return _row(
        connection,
        "SELECT * FROM gen_lessons WHERE section_id = ? AND plan_hash = ?"
        " ORDER BY version DESC, rowid DESC LIMIT 1",
        (section_id, plan_hash),
    )


def _section_check(connection, lesson_id: str) -> Any:
    return _row(
        connection,
        "SELECT c.* FROM checks c JOIN gen_lesson_checks g ON g.check_id = c.id"
        " WHERE g.lesson_id = ? ORDER BY c.version DESC LIMIT 1",
        (lesson_id,),
    )


def lesson_version(lesson) -> str:
    """The stable source version a pack binds: the immutable ``gen_lessons`` row id + version."""
    return f"{lesson['id']}:v{int(lesson['version'])}"


def source_content(connection, course_id: str, objective_id: str, version: str) -> dict[str, Any]:
    """Resolve the exact source lesson and the content hash a pack binds to.

    The hash covers the teaching page, the section's authored intent/context and the check row
    (stimulus, rubric and reference answer), so an approval is fenced to the exact content the
    parent reviewed — including the answer guide — without rewriting any row.
    """
    course = _course(connection, course_id)
    if str(course["recipe"] or "") == "parent":
        raise _policy(
            "parent_only_course",
            "a parent-authored lesson plan is not shared as a learner source for a take-home pack.",
            course_id=course_id,
        )
    plan = _current_plan(connection, course_id)
    objective = _row(
        connection,
        "SELECT * FROM objectives WHERE id = ? AND plan_id = ?",
        (objective_id, str(plan["id"])),
    )
    if objective is None:
        raise _not_found("objective", objective_id)
    section = _section_for_objective(connection, str(plan["id"]), objective)
    if section is None:
        raise _policy(
            "objective_has_no_section",
            "this objective has no generated section to print.",
            objective_id=objective_id,
        )
    lesson = _lesson_for_section(connection, str(section["id"]), _plan_hash(connection, plan))
    if lesson is None:
        raise _not_found("lesson for objective", objective_id)
    if lesson_version(lesson) != str(version):
        raise _not_found("source lesson version", str(version))
    if str(lesson["state"]) not in SERVED_LESSON_STATES:
        raise _policy(
            "lesson_not_validated",
            "the source lesson is not validated; a take-home pack prints only validated text.",
            state=str(lesson["state"]),
        )
    page = _load(lesson["page_json"], None)
    if not isinstance(page, dict) or not page:
        raise _policy(
            "lesson_page_missing",
            "the source lesson has no printable page.",
            lesson_id=str(lesson["id"]),
        )
    check = _section_check(connection, str(lesson["id"]))
    bundle = {
        "section": section,
        "objective": objective,
        "lesson": lesson,
        "page": page,
        "check": check,
        "plan": plan,
        "course": course,
    }
    bundle["content_hash"] = _labelled_hash(
        {
            "source_course_id": str(course["id"]),
            "source_objective_id": str(objective["id"]),
            "source_lesson_version": lesson_version(lesson),
            "section": {
                "id": str(section["id"]),
                "title": str(section["title"]),
                "lesson_intent": section["lesson_intent"],
                "context_needs": _load(section["context_needs_json"], []),
            },
            "objective": {
                "title": str(objective["title"]),
                "evidence_target": str(objective["evidence_target"]),
                "evidence_criteria": _load(objective["evidence_criteria_json"], []),
            },
            "page": page,
            "check": None if check is None else {
                "id": str(check["id"]),
                "version": int(check["version"]),
                "evidence_target": str(check["evidence_target"]),
                "stimulus": _load(check["stimulus_json"], {}),
                "rubric": _load(check["rubric_json"], {}),
                "reference": _load(check["reference_json"], {}),
                "audit_state": str(check["audit_state"]),
            },
        }
    )
    return bundle


# ── page composition ────────────────────────────────────────────────────────


def _cover_text(*, course, objective, title: str, audience: str) -> str:
    lines = [
        f"# Take-home: {title}",
        "",
        "A lesson pack prepared from a Coursebook lesson.",
        "",
        f"Course: {course['title']}",
        f"Lesson: {title}",
        f"Objective: {objective['title']}",
        f"Target: {objective['evidence_target']}",
        f"Edition: {'learner' if audience == 'learner' else 'parent'}",
        "",
        "The source course is unchanged; this pack prints the lesson exactly as it was validated.",
    ]
    return "\n".join(lines).strip() + "\n"


def _takehome_learner_text(page: Mapping[str, Any]) -> str:
    """The learner page: one activity, one target, no answer and no grading.

    Composed from the authored teaching blocks only. The worked example keeps its prompt and
    steps — the *procedure the learner watches* — but not its answer; the answer lives in the
    separate parent-only answer guide. Steps are numbered in authored order.
    """
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
        for number, step in enumerate(worked.get("steps") or [], start=1):
            lines.append(f"{number}. {step}")
        lines.append("")
    if page.get("learner_explanation"):
        lines.extend(["## What to notice", str(page["learner_explanation"]), ""])
    check = page.get("check") or {}
    stimulus = check.get("stimulus") or {}
    if stimulus.get("prompt"):
        lines.extend(["## Your turn", str(stimulus["prompt"])])
        items = [
            str(item.get("label") or "").strip()
            for item in (stimulus.get("items") or [])
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        ]
        printed = {authoring._label_key(label) for label in items}
        for number, label in enumerate(items, start=1):
            lines.append(f"{number}. {label}")
        for choice in stimulus.get("choices") or []:
            if authoring._label_key(str(choice)) in printed:
                continue
            lines.append(f"- {choice}")
        if check.get("learner_instructions"):
            lines.extend(["", str(check["learner_instructions"])])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _takehome_answer_guide_text(*, section, objective, page, check) -> str:
    """The parent-only answer guide: the check's answer material plus the worked example answer."""
    text = authoring._answer_guide_text(section=section, objective=objective, check=check)
    lines = text.splitlines()
    body = "\n".join(lines[1:]).strip("\n")
    text = f"# {ANSWER_GUIDE_RULE}\n\n## {section['title']}\n\n{body}\n"
    worked = page.get("worked_example") or {}
    answer = " ".join(str(worked.get("answer") or "").split())
    if answer:
        text = text.rstrip() + f"\n\n## Worked example answer\n{answer}\n"
    return text


def _takehome_parent_guide(
    *, course, section, objective, page, notes, context_needs, criteria, sources,
    content_hash, source_lesson_version
) -> str:
    """The parent guide: objective, materials, activity, success criterion, sources, parent note.

    Written for the adult, composed only from authored rows. Numbered steps are numbered; a
    missing authored parent note is said plainly instead of being filled with invented advice.
    """
    lines = [f"# Parent guide - {section['title']}", ""]
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
    materials = [" ".join(str(item or "").split()) for item in context_needs if str(item or "").strip()]
    if materials:
        lines.append("## Materials and preparation")
        lines.extend(f"- {item}" for item in materials)
        lines.append("")
    explanation = page.get("learner_explanation")
    if explanation:
        lines.extend(["## What the learner will do", str(explanation), ""])
    worked = page.get("worked_example") or {}
    if worked.get("prompt"):
        lines.extend(["## Worked example", str(worked["prompt"]), ""])
        for number, step in enumerate(worked.get("steps") or [], start=1):
            lines.append(f"{number}. {step}")
        lines.append("")
    parent_note = " ".join(str(notes.get("parent_notes") or "").split())
    lines.extend(
        ["## Parent note", parent_note or "No authored parent note for this lesson.", ""]
    )
    supervision = [
        " ".join(str(item or "").split()) for item in (notes.get("supervision_notes") or [])
        if str(item or "").strip()
    ]
    if supervision:
        lines.append("## Supervision")
        lines.extend(f"- {item}" for item in supervision)
        lines.append("")
    script: list[str] = []
    for segment in page.get("segments") or []:
        body = " ".join(str(segment.get("body") or "").split())
        if body:
            script.append(body)
    if script:
        lines.extend(["## Narration script", *script, ""])
    if criteria:
        lines.extend(["## Success criterion", criteria[0], ""])
    if sources:
        lines.append("## Sources")
        for item in sources:
            line = f"- {item['title']} ({item['support_status']})"
            if item.get("url"):
                line += f" {item['url']}"
            lines.append(line)
        lines.append("")
    lines.extend(
        [
            "## Provenance",
            f"Source lesson: {source_lesson_version}",
            f"Source content: {content_hash}",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _sources(connection, course_id: str) -> list[dict[str, Any]]:
    """The recorded source ledger, bounded to the fields a printed source list carries.

    Only rows that already exist are listed; nothing is invented, and a URL is carried only when
    the ledger recorded one.
    """
    entries: list[dict[str, Any]] = []
    for item in authoring.pack_sources(connection, course_id):
        entry = {
            "source_id": item["source_id"],
            "title": item["title"],
            "support_status": item["support_status"],
        }
        if item.get("url"):
            entry["url"] = item["url"]
        entries.append(entry)
    return entries


def _plate_caption(role: str) -> str:
    return (
        f"Orientation plate ({role}). Generated world art: captioned orientation only, "
        "not instructional or safety authority."
    )


def diagrams_from_page(page: Mapping[str, Any], *, procedure: bool) -> list[dict[str, Any]]:
    """Instructional diagrams a pack may carry, with their authority stated.

    Only a ``schematic`` (deterministic, from authored facts) or a ``sourced_technical`` figure
    (with at least one recorded source id) can be a diagram. An ``illustration`` is orientation
    art; a procedure page whose only visual is an illustration is refused rather than letting AI
    art stand in for a torque value, a sequence or a safety step.
    """
    diagrams: list[dict[str, Any]] = []
    illustrations = 0
    for item in page.get("media") or []:
        if not isinstance(item, Mapping):
            continue
        role = str(item.get("role") or "")
        if role == "illustration":
            illustrations += 1
            continue
        if role not in DIAGRAM_ROLES:
            continue
        alt = " ".join(str(item.get("text_equivalent") or "").split())
        if not alt:
            raise _policy(
                "diagram_missing_alt_text",
                "an instructional diagram has no alt text; a print pack needs a text equivalent.",
                role=role,
            )
        source_ids = [str(value) for value in (item.get("source_ids") or []) if str(value).strip()]
        if role == "sourced_technical" and not source_ids:
            raise _policy(
                "diagram_not_sourced",
                "a sourced technical figure has no recorded source id.",
                role=role,
            )
        diagrams.append(
            {
                "role": role,
                "kind": "sourced" if source_ids else "deterministic",
                "caption": " ".join(str(item.get("label") or item.get("purpose") or "").split())[:400]
                or ("Sourced technical figure" if source_ids else "Deterministic schematic"),
                "text_alt": alt[:2000],
                "source_ids": source_ids[:20],
                "artifact_id": str(item["artifact_id"]) if item.get("artifact_id") else None,
            }
        )
    if procedure and not diagrams and illustrations:
        raise _policy(
            "ai_art_as_procedure",
            "this procedure has only illustration art; a technical step needs a deterministic or "
            "sourced diagram, never an AI image as authority.",
        )
    return diagrams


def world_plates(connection, course_id: str) -> list[dict[str, Any]]:
    """Approved, textless world plates as captioned orientation — never instructional authority."""
    world = _row(
        connection,
        "SELECT * FROM course_worlds WHERE course_id = ? AND state = 'approved'"
        " ORDER BY revision DESC LIMIT 1",
        (course_id,),
    )
    if world is None:
        return []
    rows = connection.execute(
        "SELECT * FROM world_assets WHERE world_id = ? ORDER BY role, section_key",
        (str(world["id"]),),
    ).fetchall()
    plates: list[dict[str, Any]] = []
    for row in rows:
        role = str(row["role"])
        if role not in PLATE_ROLES:
            continue
        plates.append(
            {
                "role": role,
                "artifact_id": str(row["artifact_id"]),
                "caption": _plate_caption(role),
                "textless": bool(row["textless"]),
                "provenance": {
                    "world_id": str(world["id"]),
                    "style_hash": str(world["style_hash"] or ""),
                    "section_id": str(row["section_id"]) if row["section_id"] else None,
                },
            }
        )
    return plates[:12]


def compose(connection, bundle: Mapping[str, Any], *, audience: str) -> dict[str, Any]:
    """Compose the pack pages from the bound source lesson.

    Three page objects are always separate: ``parent_guide``, ``learner_page`` and
    ``answer_guide``. The learner page is composed from the teaching blocks only; it has no
    reference answer, accepted answers, rubric or grading text.
    """
    course = bundle["course"]
    section = bundle["section"]
    objective = bundle["objective"]
    page = bundle["page"]
    check = bundle["check"]
    notes = _load(bundle["lesson"]["parent_notes_json"], {})
    context_needs = _load(section["context_needs_json"], [])
    diagrams = diagrams_from_page(page, procedure=bool(page.get("procedure")))
    plates = world_plates(connection, str(course["id"]))
    # Bound the whole page set to the contract ceiling. Instructional diagrams are kept ahead
    # of orientation plates; the exported pack prints exactly the pages advertised here.
    diagrams = diagrams[:PLATE_BUDGET]
    plates = plates[: PLATE_BUDGET - len(diagrams)]
    title = section["title"]
    cover = _cover_text(
        course=course, objective=objective, title=str(title), audience=audience,
    )
    criteria = [
        " ".join(str(item or "").split())
        for item in _load(objective["evidence_criteria_json"], [])
        if str(item or "").strip()
    ]
    sources = _sources(connection, str(course["id"]))
    parent_guide = _takehome_parent_guide(
        course=course,
        section=section,
        objective=objective,
        page=page,
        notes=notes if isinstance(notes, dict) else {},
        context_needs=context_needs if isinstance(context_needs, list) else [],
        criteria=criteria,
        sources=sources,
        content_hash=str(bundle["content_hash"]),
        source_lesson_version=lesson_version(bundle["lesson"]),
    )
    learner_page = _takehome_learner_text(page)
    if criteria:
        learner_page = learner_page.rstrip() + f"\n\n## What success looks like\n{criteria[0]}\n"
    answer_guide = _takehome_answer_guide_text(
        section=section, objective=objective, page=page, check=check
    )
    _assert_learner_page_has_no_answer(learner=learner_page, answer=answer_guide, check=check)
    pages = [
        {"role": "cover", "audience": "parent", "title": str(title), "text": cover, "alt_text": None},
        {"role": "parent_guide", "audience": "parent", "title": f"Parent guide - {title}",
         "text": parent_guide, "alt_text": None},
        {"role": "learner_page", "audience": "learner", "title": str(title),
         "text": learner_page, "alt_text": None},
    ]
    for plate in plates:
        provenance = plate["provenance"]
        lines = [f"# {plate['caption']}", "", "Provenance:"]
        lines.append(f"- World: {provenance['world_id']}")
        lines.append(f"- Artifact: {plate['artifact_id']}")
        if provenance.get("style_hash"):
            lines.append(f"- Style: {provenance['style_hash']}")
        if provenance.get("section_id"):
            lines.append(f"- Section: {provenance['section_id']}")
        lines.append("- Rights: generated world art; caption and provenance recorded at approval.")
        pages.append(
            {
                "role": "plate",
                "audience": "learner",
                "title": plate["caption"],
                "text": "\n".join(lines) + "\n",
                "alt_text": plate["caption"],
            }
        )
    for diagram in diagrams:
        authority = (
            f"Sourced technical figure; source: {', '.join(diagram['source_ids'])}."
            if diagram["source_ids"]
            else "Deterministic schematic from authored facts."
        )
        lines = [f"# {diagram['caption']}", "", diagram["text_alt"], "", authority]
        pages.append(
            {
                "role": "plate",
                "audience": "learner",
                "title": diagram["caption"],
                "text": "\n".join(lines) + "\n",
                "alt_text": diagram["text_alt"],
            }
        )
    pages.append(
        {"role": "answer_guide", "audience": "parent", "title": f"{ANSWER_GUIDE_RULE} - {title}",
         "text": answer_guide, "alt_text": None}
    )
    return {
        "pages": pages,
        "sources": sources,
        "plates": plates,
        "diagrams": diagrams,
        "print_profile": dict(PRINT_PROFILE),
    }


def _assert_learner_page_has_no_answer(*, learner: str, answer: str, check) -> None:
    """Refuse a learner page that announces the reference answer or copies the answer guide.

    Defence in depth: the learner page must not contain the reference answer, accepted answers
    or rubric text. The check stimulus is allowed to contain a choice that is the answer (a
    selection check necessarily prints its options); the scan therefore reads the reference and
    rubric rows, not the stimulus.
    """
    learner_key = authoring._normalized(learner)
    if check is None:
        return
    reference = _load(check["reference_json"], {})
    rubric = _load(check["rubric_json"], {})
    secrets: list[str] = []
    answer_text = str(reference.get("reference_answer") or "").strip()
    if len(answer_text) >= 2:
        secrets.append(answer_text)
    secrets.extend(str(item) for item in reference.get("accepted_answers") or [] if str(item).strip())
    secrets.extend(authoring._rubric_strings(rubric))
    for secret in secrets:
        if len(authoring._normalized(secret)) >= 2 and authoring._normalized(secret) in learner_key:
            raise _policy(
                "answer_leak_in_learner_page",
                "the learner page announces an answer-guide string; the pack was refused.",
            )


def preview_hash(content_hash: str, audience: str, kind: str, pages: Sequence[Mapping[str, Any]]) -> str:
    return _labelled_hash(
        {
            "content_hash": content_hash,
            "audience": audience,
            "kind": kind,
            "pages": [
                {"role": page["role"], "audience": page["audience"], "title": page["title"],
                 "text": page["text"], "alt_text": page["alt_text"]}
                for page in pages
            ],
        }
    )


def approval_hash(preview: str, pages: Sequence[Mapping[str, Any]]) -> str:
    return _labelled_hash(
        {
            "preview_hash": preview,
            "pages": [
                {"role": page["role"], "audience": page["audience"], "title": page["title"],
                 "text": page["text"]}
                for page in pages
            ],
        }
    )


# ── PDF rendering ───────────────────────────────────────────────────────────


def pdf_pages(pack: Mapping[str, Any]) -> list[list[str]]:
    """The printed document, filtered to the audience the pack was created for.

    A parent copy prints the cover, the parent guide, the learner page, any captioned
    plate/diagram pages and then the separate parent-only answer guide. A learner copy prints
    the cover, the learner page and the captioned orientation/diagram pages — never the parent
    guide and never the answer guide. Each part starts on a fresh page.
    """
    pages = pack["pages"]
    audience = str(pack.get("audience") or "parent")
    if isinstance(pages, Mapping):
        ordered = list(pages.values())
    else:
        ordered = list(pages)
    if audience == "learner":
        allowed = {"cover", "learner_page", "plate"}
    else:
        allowed = {"cover", "parent_guide", "learner_page", "answer_guide", "plate"}
    sections: list[list[str]] = []
    order = {"cover": 0, "parent_guide": 1, "learner_page": 2, "plate": 3, "answer_guide": 4}
    selected = []
    for page in ordered:
        role = str(page.get("role") or "")
        if role not in allowed:
            continue
        if role == "plate" and audience == "learner" and str(page.get("audience")) != "learner":
            continue
        selected.append((order[role], page))
    for _rank, page in sorted(selected, key=lambda item: item[0]):
        sections.append(str(page["text"]).splitlines() or [""])
    return sections


def render_pdf(pack: Mapping[str, Any], *, paper: str = "letter") -> bytes:
    if paper not in ("letter", "a4"):
        raise ValueError("paper must be letter or a4")
    width, height = (612, 792) if paper == "letter" else (595, 842)
    # 12 pt Helvetica averages ~6.6 pt per character. The printable width is 500 pt on Letter
    # and 483 pt on A4, so 72 characters stay inside the margin on both and never clip.
    max_chars = 72
    sections = pdf_pages(pack)
    lines: list[str] = []
    for index, section in enumerate(sections):
        if index:
            lines.append(artifacts.PAGE_BREAK)
        lines.extend(section)
    title = f"{pack['title']} - take-home pack"
    return artifacts.make_pdf(title, lines, page_width=width, page_height=height,
                              max_chars=max_chars, headings=True)


# ── commands ────────────────────────────────────────────────────────────────


def sources(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Read-only picker over one existing learner course: objective, lesson version and hash."""
    db.ensure_schema()
    course_id = str(payload["course_id"])
    query = str(payload.get("query") or "").strip().lower()
    with db.read() as connection:
        course = _course(connection, course_id)
        if str(course["recipe"] or "") == "parent":
            raise _policy(
                "parent_only_course",
                "a parent-authored lesson plan is not shared as a learner source for a take-home pack.",
                course_id=course_id,
            )
        plan = _current_plan(connection, course_id)
        plan_hash = _plan_hash(connection, plan)
        world = _row(
            connection,
            "SELECT id FROM course_worlds WHERE course_id = ? AND state = 'approved' LIMIT 1",
            (course_id,),
        )
        has_plate = False
        if world is not None:
            has_plate = _row(
                connection,
                "SELECT 1 FROM world_assets WHERE world_id = ? LIMIT 1",
                (str(world["id"]),),
            ) is not None
        objectives = connection.execute(
            "SELECT * FROM objectives WHERE plan_id = ? ORDER BY ordinal",
            (str(plan["id"]),),
        ).fetchall()
        entries: list[dict[str, Any]] = []
        for objective in objectives:
            section = _section_for_objective(connection, str(plan["id"]), objective)
            if section is None:
                continue
            if query and query not in (
                f"{objective['title']} {section['title']}".lower()
            ):
                continue
            lesson = _lesson_for_section(connection, str(section["id"]), plan_hash)
            available = False
            blocked = None
            version = ""
            content_hash = ""
            state = "missing"
            if lesson is None:
                blocked = "no generated lesson"
            elif str(lesson["state"]) not in SERVED_LESSON_STATES:
                state = str(lesson["state"])
                blocked = f"lesson is {state}, not validated"
            else:
                version = lesson_version(lesson)
                state = str(lesson["state"])
                try:
                    content_hash = source_content(
                        connection, course_id, str(objective["id"]), version
                    )["content_hash"]
                    available = True
                except RpcError as error:
                    blocked = str(error.error.get("details", {}).get("reason") or "not printable")
            entries.append(
                {
                    "objective_id": str(objective["id"]),
                    "ordinal": int(objective["ordinal"]),
                    "title": str(objective["title"])[:300],
                    "evidence_target": str(objective["evidence_target"])[:60],
                    "section_id": str(section["id"]),
                    "section_title": str(section["title"])[:300],
                    "lesson_version": version,
                    "lesson_state": state,
                    "content_hash": content_hash,
                    "available": available,
                    "blocked_reason": blocked,
                    "has_world_plate": has_plate,
                }
            )
    return 0, {
        "course_id": course_id,
        "presentation_mode": gm_contract.read_presentation_mode(course["presentation_mode"]),
        "objectives": entries,
    }


def preview(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Render the exact pages without persisting an approval. The source is not written."""
    db.ensure_schema()
    with db.read() as connection:
        bundle = source_content(
            connection,
            str(payload["course_id"]),
            str(payload["objective_id"]),
            str(payload["source_lesson_version"]),
        )
        composed = compose(connection, bundle, audience=str(payload["audience"]))
    hashed = preview_hash(
        bundle["content_hash"], str(payload["audience"]), str(payload["kind"]), composed["pages"]
    )
    return 0, {
        "content_hash": bundle["content_hash"],
        "preview_hash": hashed,
        "pages": composed["pages"],
        "sources": composed["sources"],
    }


def create(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Bind a draft pack row to the exact source lesson version and content hash."""
    db.ensure_schema()
    expected = _require_expected(envelope)
    method = "takehome.create"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    if expected != 0:
        raise _stale("takehome.create starts a new pack at revision 0.", 0)
    pack_id = f"thp_{uuid.uuid4().hex}"
    stamp = _now()
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        bundle = source_content(
            connection,
            str(payload["course_id"]),
            str(payload["objective_id"]),
            str(payload["source_lesson_version"]),
        )
        composed = compose(connection, bundle, audience=str(payload["audience"]))
        p_hash = preview_hash(
            bundle["content_hash"], str(payload["audience"]), str(payload["kind"]), composed["pages"]
        )
        existing = _row(
            connection,
            "SELECT * FROM takehome_packs WHERE source_course_id = ? AND source_objective_id = ?"
            " AND source_lesson_version = ? AND audience = ? AND kind = ? AND state != 'superseded'"
            " ORDER BY revision DESC LIMIT 1",
            (str(payload["course_id"]), str(payload["objective_id"]),
             str(payload["source_lesson_version"]), str(payload["audience"]), str(payload["kind"])),
        )
        if existing is not None:
            # A second draft for the same source is the same artifact: return it, never duplicate
            # silently. A new revision is minted only after the previous pack was exported or a
            # parent edit changed its pages.
            result = {
                "pack_id": str(existing["id"]),
                "state": str(existing["state"]),
                "revision": int(existing["revision"]),
                "content_hash": str(existing["content_hash"]),
            }
            _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""),
                      int(existing["revision"]), result)
            return int(existing["revision"]), result
        content = {
            "title": str(payload["title"]),
            "pages": composed["pages"],
            "sources": composed["sources"],
            "plates": composed["plates"],
            "diagrams": composed["diagrams"],
            "print_profile": composed["print_profile"],
        }
        connection.execute(
            "INSERT INTO takehome_packs (id, source_course_id, source_objective_id,"
            " source_lesson_version, content_hash, audience, kind, state, revision, title,"
            " content_json, preview_hash, approval_hash, approved_at, artifact_id, exported_at,"
            " created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', 0, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?)",
            (pack_id, str(payload["course_id"]), str(payload["objective_id"]),
             str(payload["source_lesson_version"]), bundle["content_hash"], str(payload["audience"]),
             str(payload["kind"]), str(payload["title"]), _dump(content), p_hash, stamp, stamp),
        )
        result = {
            "pack_id": pack_id,
            "state": "draft",
            "revision": 0,
            "content_hash": bundle["content_hash"],
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), 0, result)
    return 0, result


def _pack_row(connection, pack_id: str):
    row = _row(connection, "SELECT * FROM takehome_packs WHERE id = ?", (pack_id,))
    if row is None:
        raise _not_found("take-home pack", pack_id)
    return row


def approve(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Freeze approval over the exact previewed pages. An edit invalidates this, not the source."""
    db.ensure_schema()
    expected = _require_expected(envelope)
    method = "takehome.approve"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        pack = _pack_row(connection, str(payload["pack_id"]))
        if int(pack["revision"]) != expected:
            raise _stale("the take-home pack changed; re-read before approving.", int(pack["revision"]))
        if str(pack["state"]) == "superseded":
            raise _policy("pack_superseded", "this pack revision was superseded.", pack_id=str(pack["id"]))
        if str(pack["preview_hash"]) != str(payload["preview_hash"]):
            raise _policy(
                "preview_hash_mismatch",
                "the pages changed since preview; preview again and approve the actual pages.",
                preview_hash=str(pack["preview_hash"]),
            )
        content = _load(pack["content_json"], {})
        pages = content.get("pages") or []
        stamp = _now()
        hashed = approval_hash(str(pack["preview_hash"]), pages)
        revision = int(pack["revision"]) + 1
        connection.execute(
            "UPDATE takehome_packs SET state = 'approved', approval_hash = ?, approved_at = ?,"
            " revision = ?, updated_at = ? WHERE id = ?",
            (hashed, stamp, revision, stamp, str(pack["id"])),
        )
        result = {
            "pack_id": str(pack["id"]),
            "state": "approved",
            "approval_hash": hashed,
            "approved_at": stamp,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result)
    return revision, result


def export(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Render the approved, bound pages to selectable-text PDF through the artifact store."""
    db.ensure_schema()
    expected = _require_expected(envelope)
    method = "takehome.export"
    payload_hash = _payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    with db.read() as connection:
        # A replay of the same key + payload returns the stored result before the revision and
        # state guards: a transport retry after a successful export is not a conflict.
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        pack_row = _pack_row(connection, str(payload["pack_id"]))
        if int(pack_row["revision"]) != expected:
            raise _stale("the take-home pack changed; re-read before exporting.", int(pack_row["revision"]))
        if str(pack_row["state"]) == "exported":
            raise _policy(
                "already_exported",
                "this pack revision is already exported; read it or create a new revision.",
                artifact_id=str(pack_row["artifact_id"]),
            )
        if str(pack_row["state"]) != "approved" or not pack_row["approval_hash"]:
            raise _policy(
                "pack_not_approved",
                "export requires an explicit approval of the previewed pages.",
                state=str(pack_row["state"]),
            )
        content = _load(pack_row["content_json"], {})
        pages = content.get("pages") or []
        if approval_hash(str(pack_row["preview_hash"]), pages) != str(pack_row["approval_hash"]):
            raise _policy(
                "approval_stale",
                "the stored pages changed after approval; approve the actual pages again.",
            )
        title = str(pack_row["title"])
        pack = {
            "title": title,
            "audience": str(pack_row["audience"]),
            "kind": str(pack_row["kind"]),
            "pages": pages,
        }
        try:
            data = render_pdf(pack)
        except Exception as exc:  # noqa: BLE001 - a failed render is a named refusal, not a blank pack
            raise RpcError.of(
                "HOST_UNAVAILABLE",
                f"the PDF renderer failed: {type(exc).__name__}",
                reason="pdf_render_failed",
            ) from exc
    store = artifacts.ArtifactStore()
    staged = store.stage(data, kind="pdf", mime="application/pdf")
    try:
        store.adopt(staged)
    except BaseException:
        store.discard(staged)
        raise
    stamp = _now()
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        pack_row = _pack_row(connection, str(payload["pack_id"]))
        if int(pack_row["revision"]) != expected:
            raise _stale("the take-home pack changed; re-read before exporting.", int(pack_row["revision"]))
        artifact = store.record(
            connection,
            course_id=None,
            staged=staged,
            provenance={
                "generator": "coursebook.takehome",
                "notes": "take-home pack PDF rendered from approved, bound pages",
                "source_ids": [str(pack_row["source_lesson_version"])],
            },
        )
        revision = int(pack_row["revision"]) + 1
        connection.execute(
            "UPDATE takehome_packs SET state = 'exported', artifact_id = ?, exported_at = ?,"
            " revision = ?, updated_at = ? WHERE id = ?",
            (str(artifact["artifact_id"]), stamp, revision, stamp, str(pack_row["id"])),
        )
        result = {
            "pack_id": str(pack_row["id"]),
            "state": "exported",
            "artifact_id": str(artifact["artifact_id"]),
            "exported_at": stamp,
        }
        _remember(connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result)
    return revision, result


def read(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Read the stored pack, its separate pages and its export state. No private rows."""
    db.ensure_schema()
    with db.read() as connection:
        pack = _pack_row(connection, str(payload["pack_id"]))
        content = _load(pack["content_json"], {})
        pages_by_role = {
            page["role"]: page for page in content.get("pages") or []
            if page.get("role") in ("parent_guide", "learner_page", "answer_guide", "cover")
        }
        missing = {"parent_guide", "learner_page", "answer_guide"} - set(pages_by_role)
        if missing:
            raise _policy(
                "pack_pages_missing",
                "the stored pack is missing a required page; it is not printable.",
                missing=sorted(missing),
            )
        pages = {
            role: {
                "role": pages_by_role[role]["role"],
                "audience": pages_by_role[role]["audience"],
                "title": pages_by_role[role]["title"],
                "text": pages_by_role[role]["text"],
            }
            for role in ("parent_guide", "learner_page", "answer_guide")
        }
        export_state = {"artifact_id": None, "exported_at": None, "mime": None, "bytes": None,
                        "content_hash": None}
        if pack["artifact_id"]:
            artifact = _row(connection, "SELECT * FROM artifacts WHERE id = ?", (str(pack["artifact_id"]),))
            if artifact is not None:
                export_state = {
                    "artifact_id": str(artifact["id"]),
                    "exported_at": pack["exported_at"],
                    "mime": str(artifact["mime"]),
                    "bytes": int(artifact["bytes"]),
                    "content_hash": artifacts.labelled_hash(artifact["content_hash"]),
                }
        result = {
            "pack": {
                "pack_id": str(pack["id"]),
                "source_course_id": str(pack["source_course_id"]),
                "source_objective_id": str(pack["source_objective_id"]),
                "source_lesson_version": str(pack["source_lesson_version"]),
                "content_hash": str(pack["content_hash"]),
                "audience": str(pack["audience"]),
                "kind": str(pack["kind"]),
                "state": str(pack["state"]),
                "revision": int(pack["revision"]),
                "title": str(pack["title"]),
                "pages": pages,
                "sources": content.get("sources") or [],
                "plates": content.get("plates") or [],
                "diagrams": content.get("diagrams") or [],
                "print_profile": content.get("print_profile") or dict(PRINT_PROFILE),
                "approval": {
                    "approval_hash": str(pack["approval_hash"]) if pack["approval_hash"] else None,
                    "approved_at": str(pack["approved_at"]) if pack["approved_at"] else None,
                },
                "export": export_state,
                "created_at": str(pack["created_at"]),
                "updated_at": str(pack["updated_at"]),
            }
        }
    return 0, result


HANDLERS = {
    "takehome.sources": sources,
    "takehome.preview": preview,
    "takehome.create": create,
    "takehome.approve": approve,
    "takehome.export": export,
    "takehome.read": read,
}
