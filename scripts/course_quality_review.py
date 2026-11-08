#!/usr/bin/env python3
"""Bounded course-quality review packet for generated Coursebook courses.

This script is the mechanical half of ``docs/COURSE-QUALITY-RUBRIC.md`` (H-173). It reads one
generated plan, optionally one lesson and one validation record, and writes a reviewer packet:
the deterministic facts a reviewer needs, the validator's recorded verdict, and eight empty
dimension blocks. It never fills a score, never calls a model, a database or the network, and
never computes an aggregate, mastery or engagement number.

The ``check`` subcommand validates a completed record: eight dimensions exactly once, integer
scores 1 to 4, evidence of real length, a routed follow-up for every dimension below 3, a named
reviewer on the label's own line, the echoed validator verdict, and no aggregate, percentage or
mastery claim anywhere in the reviewer's own prose. A record that fails is not a review.

Usage::

    python3 scripts/course_quality_review.py packet \
        --plan tests/fixtures/generation/plan_ja.json \
        --lesson tests/fixtures/generation/lesson_ja.json \
        --validation tests/fixtures/generation/validation_reject_check.json \
        --sample-id S2 --scope short --reviewer "Reviewer Name" \
        --out docs/reviews/S2-review.md

    python3 scripts/course_quality_review.py check docs/reviews/S2-review.md

Stdlib only. No imports from ``coursebook`` so the packet cannot change generation, validation,
grading, RPC or database behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

#: The eight dimensions, in record order. Ids and titles are copied from
#: ``docs/COURSE-QUALITY-RUBRIC.md`` section 4; ``tests/test_course_quality_rubric.py`` fails if
#: the two drift.
DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("D1", "capability_objective_fit"),
    ("D2", "sequencing_prerequisite_truth"),
    ("D3", "evidence_target_fit"),
    ("D4", "example_explanation_quality"),
    ("D5", "cognitive_load_session_arc"),
    ("D6", "source_grounding_citation_honesty"),
    ("D7", "media_necessity"),
    ("D8", "learner_agency_recoverability"),
)

QUESTIONS: dict[str, str] = {
    "D1": "Does the course promise a capability, and do the objectives name observable "
    "performances rather than topics?",
    "D2": "Does each objective arrive after what it needs, and are prerequisites real rather "
    "than decorative?",
    "D3": "Does the check measure the evidence target the objective declares?",
    "D4": "Do the worked example and explanation teach this case, or restate one generic example?",
    "D5": "Can a learner finish the session, in the stated order, without a jump or an unstated "
    "prerequisite?",
    "D6": "Is each load-bearing claim traceable to a fetched source or honestly marked "
    "unverified?",
    "D7": "Does each image or audio artifact carry a job the construct requires, or is it "
    "decoration?",
    "D8": "Can the learner see, choose and recover from their own path without a hidden failure?",
}

#: Input and output bounds. A course plan the pipeline can write is far below these; a larger
#: file is refused by name rather than read.
MAX_INPUT_BYTES = 2_000_000
MAX_RECORD_BYTES = 1_000_000
MAX_OBJECTIVES = 40
MAX_UNITS = 12
MAX_SECTIONS = 64
MAX_SEGMENTS = 8
EVIDENCE_MIN_CHARS = 40

#: Patterns a completed record may not assert anywhere in the document. The rubric refuses these
#: as evidence; a record that smuggles one back in is not a valid review. These are matched against
#: the reviewer's own prose only (see :func:`_assertion_text`), so a quoted example of the checker's
#: own holes is not mistaken for an aggregate the record is claiming.
FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bmastery\b", "mastery claim"),
    (r"\bpercent_mastered\b", "percent mastered"),
    (r"\b\d+(?:\.\d+)?[ \t]*%", "percentage"),
    (
        r"\b(?:aggregate|overall|total|average|mean|composite)\b[ _-]*"
        r"(?:score|quality|rating|grade|percentage|mastery)\b",
        "aggregate or overall score",
    ),
    (r"\bleaderboard\b", "leaderboard"),
    (r"\bquality badge\b", "quality badge"),
    (r"\bpublic badge\b", "public badge"),
)

#: The disclaimer names the refused concepts; it is removed before the forbidden scan.
DISCLAIMER = (
    "This record is not a mastery score, an engagement metric, a badge or a leaderboard. "
    "The eight 1-4 verdicts below are reviewer judgments about course design; they are never "
    "summed, averaged or shown to a learner. The validator's structural pass remains the gate "
    "(`docs/COURSE-QUALITY-RUBRIC.md`)."
)

#: Quoted spans are evidence the reviewer is quoting, not a claim they are making. This is how the
#: H-173d records name the checker's own "Aggregate score: 24 out of 32" hole without failing it.
QUOTED_SPAN_RE = re.compile(r"`[^`]{0,200}`|\"[^\"]{0,200}\"|“[^”]{0,200}”", re.DOTALL)
#: A record may say mastery is not recorded; that is the refusal vocabulary, not a mastery claim.
NEGATED_MASTERY_RE = re.compile(
    r"\b(?:not|no|never)\s+(?:a\s+|an\s+)?mastery\b|\bmastery\s+(?:is|was|remains)\s+not\b",
    re.IGNORECASE,
)

#: A forbidden claim that is the whole line is still forbidden when it is wrapped in quotation
#: marks: quoting an aggregate does not turn the record's own headline number into a citation.
STANDALONE_FORBIDDEN_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?[`\"“]?"
    r"(?:(?:aggregate|overall|total|average|mean|composite)\b[^\n]{0,40}"
    r"\b(?:score|quality|rating|grade|percentage|mastery)\b"
    r"|\d+(?:\.\d+)?[ \t]*%"
    r"|mastery\b)",
    re.IGNORECASE | re.MULTILINE,
)

FOLLOW_UP_RE = re.compile(r"^(t_[0-9a-f]{6,}|H-\d+[A-Za-z]?)$")
#: A header value is a single line: ``\s*`` would span the newline and capture the next header.
REVIEWER_RE = re.compile(r"^Reviewer:[ \t]*(\S.*)$", re.MULTILINE)
VERDICT_RE = re.compile(r"^Validator verdict:[ \t]*(\S.*)$", re.MULTILINE)
SAMPLE_RE = re.compile(r"^Sample:[ \t]*(\S.*)$", re.MULTILINE)
SCOPE_RE = re.compile(r"^Scope:[ \t]*(\S.*)$", re.MULTILINE)
#: A captured reviewer value that is really the next header line is not a name.
HEADER_PREFIX_RE = re.compile(
    r"^(?:sample|scope|validator verdict|reviewer|score|evidence|follow-up|question)\s*:", re.I
)
HEADING_RE = re.compile(r"^### (D[1-8]) ([a-z_]+)\s*$", re.MULTILINE)
SCORE_RE = re.compile(r"^Score:[ \t]*(\S.*)$", re.MULTILINE)
EVIDENCE_RE = re.compile(r"^Evidence:[ \t]*(.*)$", re.MULTILINE)
FOLLOW_RE = re.compile(r"^Follow-up:[ \t]*(\S.*)$", re.MULTILINE)


class PacketError(Exception):
    """A named refusal. The message says what failed and what to supply instead."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    """Read one bounded JSON object, or refuse by name."""
    if not path.exists():
        raise PacketError(f"{label}: no file at {path}")
    if not path.is_file():
        raise PacketError(f"{label}: {path} is not a file")
    size = path.stat().st_size
    if size > MAX_INPUT_BYTES:
        raise PacketError(
            f"{label}: {path} is {size} bytes, over the {MAX_INPUT_BYTES}-byte packet cap"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PacketError(f"{label}: {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PacketError(f"{label}: {path} must contain a JSON object, not {type(data).__name__}")
    return data


def _bounded_list(value: Any, label: str, cap: int) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PacketError(f"{label} must be a list, not {type(value).__name__}")
    if len(value) > cap:
        raise PacketError(f"{label} has {len(value)} items, over the {cap}-item packet cap")
    return value


def _text(value: Any, cap: int = 400) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if len(text) > cap:
        return text[: cap - 3].rstrip() + "..."
    return text


def _number(value: Any) -> Any:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _media_cell(media_need: Any) -> str:
    if not isinstance(media_need, dict):
        return "not declared"
    parts: list[str] = []
    for key in ("image", "audio"):
        entry = media_need.get(key)
        if isinstance(entry, dict):
            level = entry.get("level") or "none"
            role = entry.get("role") or "none"
            parts.append(f"{key}={level}/{role}")
    construct = media_need.get("construct")
    if isinstance(construct, str) and construct.strip():
        parts.append(f"construct={_text(construct, 120)}")
    return ", ".join(parts) if parts else "not declared"


def _plan_facts(plan: dict[str, Any]) -> list[str]:
    schema = plan.get("plan_schema")
    schema = schema if isinstance(schema, str) and schema else "coursebook.plan.v1 (no plan_schema)"
    scope = plan.get("scope")
    scope = scope if isinstance(scope, str) and scope else "not declared (v1 document)"
    objectives = _bounded_list(plan.get("objectives"), "plan.objectives", MAX_OBJECTIVES)
    units = _bounded_list(plan.get("units"), "plan.units", MAX_UNITS)
    sections = _bounded_list(plan.get("sections"), "plan.sections", MAX_SECTIONS)
    check_plan = _bounded_list(plan.get("check_plan"), "plan.check_plan", MAX_OBJECTIVES)

    lines: list[str] = []
    lines.append(f"- Plan schema: {schema}")
    lines.append(f"- Scope: {scope}")
    lines.append(f"- Title: {_text(plan.get('title'), 200) or 'MISSING'}")
    lines.append(f"- Learner outcome: {_text(plan.get('learner_outcome'), 600) or 'MISSING'}")
    lines.append(f"- Delivery: {_text(plan.get('delivery'), 80) or 'MISSING'}")

    estimate_value = plan.get("time_estimate")
    estimate: dict[str, Any] = estimate_value if isinstance(estimate_value, dict) else {}
    sessions = _number(estimate.get("sessions_per_week"))
    weeks = _number(estimate.get("weeks"))
    minutes = _number(estimate.get("minutes_per_session"))
    capacity = sessions * weeks if sessions is not None and weeks is not None else None
    basis = _text(estimate.get("basis"), 60) or "not declared"
    lines.append(
        "- Time estimate: "
        f"sessions_per_week={sessions if sessions is not None else 'MISSING'}, "
        f"weeks={weeks if weeks is not None else 'MISSING'}, "
        f"minutes_per_session={minutes if minutes is not None else 'MISSING'}, "
        f"basis={basis}"
    )
    lines.append(
        f"- Session capacity: {capacity if capacity is not None else 'unknown'} session(s) "
        f"available for {len(sections)} authored section(s) and "
        f"{len(units)} declared unit(s)"
    )

    support_counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    unsourced = 0
    lines.append(f"- Objectives ({len(objectives)}):")
    for index, objective in enumerate(objectives, start=1):
        if not isinstance(objective, dict):
            lines.append(f"  {index}. MALFORMED objective entry ({type(objective).__name__})")
            continue
        support = _text(objective.get("support"), 40) or "MISSING"
        target = _text(objective.get("evidence_target"), 40) or "MISSING"
        support_counts[support] = support_counts.get(support, 0) + 1
        target_counts[target] = target_counts.get(target, 0) + 1
        criteria = _bounded_list(objective.get("evidence_criteria"), "objective.evidence_criteria", 6)
        unit_ref = objective.get("unit_ref", "-")
        source_ids = _bounded_list(objective.get("source_ids"), "objective.source_ids", 8)
        if not source_ids:
            unsourced += 1
        lines.append(
            f"  {index}. [unit {unit_ref}] {_text(objective.get('title'), 200) or 'MISSING'} "
            f"(target={target}, support={support}, criteria={len(criteria)}, "
            f"source_ids={len(source_ids)})"
        )
    lines.append(
        f"- Objective support: {dict(sorted(support_counts.items())) or 'none'}; "
        f"targets: {dict(sorted(target_counts.items())) or 'none'}; "
        f"objectives with no source_ids: {unsourced}/{len(objectives)}"
    )

    if units:
        lines.append(f"- Units ({len(units)}):")
        lines.append("- Unit prerequisite edges and target lessons:")
        for unit in units:
            if not isinstance(unit, dict):
                lines.append("  - MALFORMED unit entry")
                continue
            prereqs = _bounded_list(unit.get("prereq_unit_ordinals"), "unit.prereq", 11)
            lines.append(
                f"  - unit {unit.get('ordinal', '?')}: {_text(unit.get('title'), 160) or 'MISSING'} "
                f"(prereqs={prereqs or 'none'}, target_lessons={unit.get('target_lessons', '?')})"
            )
        target_sum = 0
        for unit in units:
            if isinstance(unit, dict):
                value = _number(unit.get("target_lessons"))
                if value is not None:
                    target_sum += int(value)
        lines.append(
            f"- Unit target_lessons sum: {target_sum} against "
            f"{capacity if capacity is not None else 'unknown'} available session(s)"
        )
        if not sections:
            lines.append("- Sections: none in the plan document (a v2 plan authors unit sections separately)")
    else:
        lines.append("- Units: none (v1 document: one implicit unit)")

    if sections:
        lines.append(f"- Sections ({len(sections)}):")
        for section in sections:
            if not isinstance(section, dict):
                lines.append("  - MALFORMED section entry")
                continue
            refs = _bounded_list(section.get("objective_refs"), "section.objective_refs", 6)
            lines.append(
                f"  - section {section.get('ordinal', '?')}: "
                f"{_text(section.get('title'), 160) or 'MISSING'} "
                f"(objective_refs={refs or 'none'}, media_need: {_media_cell(section.get('media_need'))})"
            )
            intent = _text(section.get("lesson_intent"), 300)
            if intent:
                lines.append(f"    lesson_intent: {intent}")

    lines.append(f"- Check plan entries: {len(check_plan)}")
    for entry in check_plan:
        if not isinstance(entry, dict):
            continue
        lines.append(
            f"  - objective {entry.get('objective_ref', '?')}: kind={entry.get('kind', 'MISSING')}, "
            f"target={entry.get('evidence_target', 'MISSING')}"
            + (f", notes={_text(entry.get('notes'), 200)}" if entry.get("notes") else "")
        )

    exclusions = _bounded_list(plan.get("exclusions"), "plan.exclusions", 10)
    if exclusions:
        lines.append("- Exclusions:")
        for exclusion in exclusions:
            lines.append(f"  - {_text(exclusion, 300)}")

    source_ids = _bounded_list(plan.get("source_ids"), "plan.source_ids", 12)
    lines.append(f"- Plan source_ids: {source_ids or 'none'}")
    return lines


def _lesson_facts(lesson: dict[str, Any]) -> list[str]:
    lines: list[str] = [f"- Section title: {_text(lesson.get('section_title'), 200) or 'MISSING'}"]
    segments = _bounded_list(lesson.get("segments"), "lesson.segments", MAX_SEGMENTS)
    lines.append(f"- Segments: {len(segments)}")
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            lines.append(f"  {index}. MALFORMED segment")
            continue
        lines.append(
            f"  {index}. kind={segment.get('kind', 'MISSING')}, "
            f"heading={_text(segment.get('heading'), 160) or 'MISSING'}"
        )

    example_value = lesson.get("worked_example")
    example: dict[str, Any] = example_value if isinstance(example_value, dict) else {}
    steps = _bounded_list(example.get("steps"), "lesson.worked_example.steps", 8)
    lines.append(
        f"- Worked example: prompt={_text(example.get('prompt'), 300) or 'MISSING'}; "
        f"steps={len(steps)}"
    )
    if steps:
        for index, step in enumerate(steps, start=1):
            lines.append(f"    step {index}: {_text(step, 200)}")
    lines.append("- Worked example answer present: " + ("yes (not reproduced here)" if example.get("answer") else "MISSING"))

    explanation = _text(lesson.get("learner_explanation"), 500)
    lines.append(f"- Learner explanation: {explanation or 'MISSING'}")

    check_value = lesson.get("check")
    check: dict[str, Any] = check_value if isinstance(check_value, dict) else {}
    stimulus_value = check.get("stimulus")
    stimulus: dict[str, Any] = stimulus_value if isinstance(stimulus_value, dict) else {}
    answers = _bounded_list(check.get("accepted_answers"), "check.accepted_answers", 8)
    alternatives = _bounded_list(check.get("accepted_alternatives"), "check.accepted_alternatives", 8)
    rubric = _bounded_list(check.get("rubric"), "check.rubric", 12)
    items = _bounded_list(stimulus.get("items"), "check.stimulus.items", 24)
    assistance_value = check.get("assistance_policy")
    assistance: dict[str, Any] = assistance_value if isinstance(assistance_value, dict) else {}
    scaffolds = check.get("scaffolds")
    lines.append(
        "- Check: "
        f"kind={check.get('kind', 'MISSING')}, "
        f"format={stimulus.get('format', 'MISSING')}, "
        f"target={check.get('evidence_target', 'MISSING')}, "
        f"accepted_answers={len(answers)}, accepted_alternatives={len(alternatives)}, "
        f"rubric_criteria={len(rubric)}, stimulus_items={len(items)}"
    )
    rubric_criteria = [
        _text(entry.get("criterion"), 120)
        for entry in rubric
        if isinstance(entry, dict) and entry.get("criterion")
    ]
    if rubric_criteria:
        lines.append(f"- Rubric criteria: {rubric_criteria}")
    lines.append(
        "- Assistance policy: "
        f"hint={_text(assistance.get('hint'), 80) or 'not declared'}, "
        f"answer_marks_evidence_class={_text(assistance.get('answer_marks_evidence_class'), 80) or 'not declared'}"
    )
    if isinstance(scaffolds, dict):
        enabled = sorted(key for key, value in scaffolds.items() if value)
        lines.append(f"- Scaffolds enabled: {enabled or 'none'}")
    elif isinstance(scaffolds, list):
        lines.append(f"- Scaffolds enabled: {scaffolds or 'none'}")
    else:
        lines.append("- Scaffolds enabled: not declared")
    lines.append(
        "- Reference answer present: " + ("yes (not reproduced here)" if check.get("reference_answer") else "MISSING")
    )

    sources = _bounded_list(lesson.get("sources"), "lesson.sources", 12)
    media = _bounded_list(lesson.get("media"), "lesson.media", 12)
    lines.append(f"- Lesson sources: {sources or 'none'}")
    lines.append(f"- Lesson media artifacts: {len(media)}")
    lines.append(
        "- Parent notes: "
        + (_text(lesson.get("parent_notes"), 300) if lesson.get("parent_notes") else "none")
    )
    supervision = _bounded_list(lesson.get("supervision_notes"), "lesson.supervision_notes", 8)
    if supervision:
        lines.append("- Supervision notes:")
        for note in supervision:
            lines.append(f"  - {_text(note, 200)}")
    else:
        lines.append("- Supervision notes: none")
    return lines


def _validation_facts(validation: dict[str, Any]) -> list[str]:
    verdict = _text(validation.get("verdict"), 40) or "MISSING"
    criteria = _bounded_list(validation.get("criteria"), "validation.criteria", 20)
    lines = [f"- Recorded verdict: {verdict}"]
    if criteria:
        lines.append("- Recorded criteria:")
        for entry in criteria:
            if not isinstance(entry, dict):
                continue
            lines.append(
                f"  - {entry.get('id', 'MISSING')}: {entry.get('verdict', 'MISSING')} "
                f"({_text(entry.get('reason'), 240)})"
            )
    else:
        lines.append("- Recorded criteria: none")
    rejections = _bounded_list(validation.get("rejections"), "validation.rejections", 20)
    lines.append(f"- Recorded rejections: {len(rejections)}")
    for entry in rejections:
        if not isinstance(entry, dict):
            continue
        lines.append(
            f"  - item={entry.get('item', '?')}, criterion={entry.get('criterion', '?')}: "
            f"{_text(entry.get('reason'), 300)}"
        )
        if entry.get("fix_hint"):
            lines.append(f"    fix_hint: {_text(entry.get('fix_hint'), 240)}")
    claims = _bounded_list(validation.get("claim_verdicts"), "validation.claim_verdicts", 40)
    lines.append(f"- Claim verdicts: {len(claims)}")
    return lines


def render_packet(
    *,
    plan_path: Path,
    plan: dict[str, Any],
    lesson_path: Path | None,
    lesson: dict[str, Any] | None,
    validation_path: Path | None,
    validation: dict[str, Any] | None,
    sample_id: str,
    scope: str,
    reviewer: str,
) -> str:
    """Build the reviewer packet. Facts only; every score is left blank."""
    if not reviewer.strip():
        raise PacketError("reviewer: a named reviewer is required")
    if not sample_id.strip():
        raise PacketError("sample-id: a stable sample id is required")

    verdict = _text(validation.get("verdict"), 40) if validation else "no validation record supplied"
    lines: list[str] = []
    lines.append(f"# Course quality review: {sample_id}")
    lines.append("")
    lines.append(f"Reviewer: {reviewer.strip()}")
    lines.append(f"Sample: {sample_id.strip()}")
    lines.append(f"Scope: {scope.strip() or 'not declared'}")
    lines.append(f"Validator verdict: {verdict}")
    lines.append("")
    lines.append(
        "This record is not a mastery score, an engagement metric, a badge or a leaderboard. "
        "The eight 1-4 verdicts below are reviewer judgments about course design; they are never "
        "summed, averaged or shown to a learner. The validator's structural pass remains the gate "
        "(`docs/COURSE-QUALITY-RUBRIC.md`)."
    )
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    for label, path in (("plan", plan_path), ("lesson", lesson_path), ("validation", validation_path)):
        if path is None:
            lines.append(f"- {label}: not supplied")
        else:
            lines.append(f"- {label}: `{path}` sha256 `{_sha256(path)}`")
    lines.append("")
    lines.append("## Observed facts")
    lines.append("")
    lines.append("Facts are extracted mechanically. They are not scores and they do not replace the")
    lines.append("reviewer's reading.")
    lines.append("")
    lines.extend(_plan_facts(plan))
    lines.append("")
    if lesson is not None:
        lines.append("### Lesson")
        lines.append("")
        lines.extend(_lesson_facts(lesson))
    else:
        lines.append("### Lesson")
        lines.append("")
        lines.append("- Lesson: not supplied. D3, D4, D5, D7 and D8 cannot be scored from a plan alone.")
    lines.append("")
    if validation is not None:
        lines.append("### Validator record")
        lines.append("")
        lines.extend(_validation_facts(validation))
    else:
        lines.append("### Validator record")
        lines.append("")
        lines.append("- Validation record: not supplied. The verdict above is unknown, not a pass.")
    lines.append("")
    lines.append("## Dimension verdicts")
    lines.append("")
    for dimension_id, dimension_name in DIMENSIONS:
        lines.append(f"### {dimension_id} {dimension_name}")
        lines.append(f"Question: {QUESTIONS[dimension_id]}")
        lines.append("Score: ")
        lines.append("Evidence: ")
        lines.append("Follow-up: ")
        lines.append("")
    lines.append("## Reviewer notes")
    lines.append("")
    lines.append("Limits of this record (missing lesson, author-run review, unverified source ledger,")
    lines.append("fixture instead of a live output) go here. A limit is not a pass.")
    lines.append("")
    return "\n".join(lines)


def _dimension_blocks(text: str) -> list[tuple[str, str, str]]:
    matches = list(HEADING_RE.finditer(text))
    blocks: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group(1), match.group(2), text[start:end]))
    return blocks


def _without_disclaimer(text: str) -> str:
    return text.replace(DISCLAIMER, "")


def _assertion_text(text: str) -> str:
    """Return the record's own claims: disclaimer, quotations and negated mastery removed."""
    return NEGATED_MASTERY_RE.sub(" ", QUOTED_SPAN_RE.sub(" ", _without_disclaimer(text)))


def forbidden_language(text: str) -> list[str]:
    """Return the labels of every refused aggregate or engagement claim the record asserts."""
    scan_text = _assertion_text(text)
    standalone_text = NEGATED_MASTERY_RE.sub(" ", _without_disclaimer(text))
    hits: list[str] = []
    for pattern, label in FORBIDDEN_PATTERNS:
        if re.search(pattern, scan_text, re.IGNORECASE) and label not in hits:
            hits.append(label)
    if (
        not {"aggregate or overall score", "percentage", "mastery claim"} & set(hits)
        and STANDALONE_FORBIDDEN_RE.search(standalone_text)
    ):
        hits.append("aggregate, percentage or mastery claim on its own line")
    return hits


def check_record(text: str) -> list[str]:
    """Return every problem with a completed record. Empty list means the record is valid."""
    errors: list[str] = []
    if len(text) > MAX_RECORD_BYTES:
        return [f"record is {len(text)} characters, over the {MAX_RECORD_BYTES}-character cap"]

    reviewer_match = REVIEWER_RE.search(text)
    if not reviewer_match:
        errors.append("Reviewer: a named reviewer is required on the same line as the label")
    else:
        reviewer = reviewer_match.group(1).strip()
        if (
            not reviewer
            or reviewer.lower() in {"name", "reviewer"}
            or HEADER_PREFIX_RE.match(reviewer)
        ):
            errors.append(
                f"Reviewer: {reviewer!r} is not a named reviewer (blank, a placeholder or a "
                "header line)"
            )
    if not SAMPLE_RE.search(text):
        errors.append("Sample: a stable sample id is required")
    if not SCOPE_RE.search(text):
        errors.append("Scope: the reviewed scope is required")
    if not VERDICT_RE.search(text):
        errors.append("Validator verdict: echo the validator's recorded verdict")
    if DISCLAIMER not in text:
        errors.append("the record must carry the not-a-mastery-score disclaimer")

    for label in forbidden_language(text):
        errors.append(f"forbidden aggregate or engagement language: {label}")

    blocks = _dimension_blocks(text)
    seen: dict[str, list[tuple[str, str]]] = {}
    for dimension_id, dimension_name, body in blocks:
        seen.setdefault(dimension_id, []).append((dimension_name, body))

    expected_ids = [dimension_id for dimension_id, _ in DIMENSIONS]
    extra = sorted(set(seen) - set(expected_ids))
    if extra:
        errors.append(f"unknown dimension ids: {', '.join(extra)}")

    for dimension_id, expected_name in DIMENSIONS:
        entries = seen.get(dimension_id, [])
        if not entries:
            errors.append(f"{dimension_id} {expected_name}: missing")
            continue
        if len(entries) > 1:
            errors.append(f"{dimension_id} {expected_name}: appears {len(entries)} times")
            continue
        name, body = entries[0]
        if name != expected_name:
            errors.append(f"{dimension_id}: title is {name!r}, expected {expected_name!r}")

        score_match = SCORE_RE.search(body)
        if not score_match or not score_match.group(1).strip():
            errors.append(f"{dimension_id}: Score is blank")
            score = None
        else:
            raw = score_match.group(1).strip()
            if raw not in {"1", "2", "3", "4"}:
                errors.append(f"{dimension_id}: Score {raw!r} is not an integer 1 to 4")
                score = None
            else:
                score = int(raw)

        evidence_match = EVIDENCE_RE.search(body)
        evidence = ""
        if evidence_match:
            tail = body[evidence_match.start() :]
            follow_index = tail.find("Follow-up:")
            evidence = tail[len("Evidence:") : follow_index if follow_index >= 0 else len(tail)]
            evidence = " ".join(evidence.split())
        if len(evidence) < EVIDENCE_MIN_CHARS:
            errors.append(
                f"{dimension_id}: Evidence is {len(evidence)} characters, "
                f"under the {EVIDENCE_MIN_CHARS}-character minimum"
            )

        follow_match = FOLLOW_RE.search(body)
        if score is not None:
            if score < 3:
                if not follow_match or not follow_match.group(1).strip():
                    errors.append(
                        f"{dimension_id}: score {score} needs a follow-up reference "
                        "(t_... or H-...); 'none' does not route the finding"
                    )
                else:
                    value = follow_match.group(1).strip()
                    if value.lower() == "none":
                        errors.append(
                            f"{dimension_id}: score {score} cannot say 'Follow-up: none'; a "
                            "dimension below 3 must route to a task id or card id"
                        )
                    elif not FOLLOW_UP_RE.match(value):
                        errors.append(
                            f"{dimension_id}: follow-up {value!r} is not a task id or card id"
                        )
            elif not follow_match:
                errors.append(f"{dimension_id}: score {score} needs 'Follow-up: none'")
            else:
                value = follow_match.group(1).strip()
                if value.lower() != "none":
                    errors.append(
                        f"{dimension_id}: score {score} must say 'Follow-up: none', not {value!r}"
                    )

    order = [dimension_id for dimension_id, _, _ in blocks]
    if order and order != expected_ids:
        errors.append(f"dimension order is {order}, expected {expected_ids}")
    return errors


def command_packet(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan)
    plan = load_json(plan_path, "plan")
    lesson_path = Path(args.lesson) if args.lesson else None
    lesson = load_json(lesson_path, "lesson") if lesson_path else None
    validation_path = Path(args.validation) if args.validation else None
    validation = load_json(validation_path, "validation") if validation_path else None

    text = render_packet(
        plan_path=plan_path,
        plan=plan,
        lesson_path=lesson_path,
        lesson=lesson,
        validation_path=validation_path,
        validation=validation,
        sample_id=args.sample_id,
        scope=args.scope,
        reviewer=args.reviewer,
    )
    destination = Path(args.out) if args.out else None
    if destination is None:
        sys.stdout.write(text)
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    verdict = _text(validation.get("verdict"), 40) if validation else "no validation record"
    print(
        f"wrote {destination}: 8 dimensions, validator verdict={verdict}, "
        f"{len(text)} characters (scores intentionally blank)"
    )
    return 0


def fill_packet(text: str, scores: dict[str, Any]) -> str:
    """Replace the eight blank blocks with the reviewer's written verdicts.

    ``scores`` maps each dimension id to ``{"score": 1-4, "evidence": str,
    "follow_up": "none" | "t_..." | "H-..."}``. Every id is required; an extra id is refused.
    The result still goes through :func:`check_record`, so a malformed entry cannot become a
    valid review.
    """
    expected = [dimension_id for dimension_id, _ in DIMENSIONS]
    missing = [dimension_id for dimension_id in expected if dimension_id not in scores]
    extra = sorted(set(scores) - set(expected))
    if missing:
        raise PacketError(f"scores: missing dimensions {', '.join(missing)}")
    if extra:
        raise PacketError(f"scores: unknown dimensions {', '.join(extra)}")

    matches = list(HEADING_RE.finditer(text))
    if [match.group(1) for match in matches] != expected:
        raise PacketError("packet: the dimension headings are not the expected D1 to D8 order")

    pieces: list[str] = []
    cursor = 0
    for index, match in enumerate(matches):
        dimension_id = match.group(1)
        entry = scores[dimension_id]
        if not isinstance(entry, dict):
            raise PacketError(f"scores.{dimension_id}: must be an object")
        score = entry.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or score not in (1, 2, 3, 4):
            raise PacketError(f"scores.{dimension_id}.score: must be an integer 1 to 4")
        evidence = entry.get("evidence")
        if not isinstance(evidence, str) or len(" ".join(evidence.split())) < EVIDENCE_MIN_CHARS:
            raise PacketError(
                f"scores.{dimension_id}.evidence: must be at least "
                f"{EVIDENCE_MIN_CHARS} characters and name a location, field or quote"
            )
        follow_up = entry.get("follow_up", "none")
        if not isinstance(follow_up, str):
            raise PacketError(f"scores.{dimension_id}.follow_up: must be a string")
        follow_up = follow_up.strip() or "none"
        if score < 3 and follow_up.lower() == "none":
            raise PacketError(
                f"scores.{dimension_id}: a score below 3 needs a follow-up task or card id"
            )
        if score >= 3 and follow_up.lower() != "none":
            raise PacketError(
                f"scores.{dimension_id}: a score of 3 or 4 must use follow_up 'none'"
            )
        if follow_up.lower() != "none" and not FOLLOW_UP_RE.match(follow_up):
            raise PacketError(
                f"scores.{dimension_id}.follow_up: {follow_up!r} is not a task id or card id"
            )

        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end() : block_end]
        # Keep everything after the block (the next heading or the record tail) byte for byte.
        following = block
        for marker in ("### D", "\n## Reviewer notes"):
            position = following.find(marker)
            if position >= 0:
                following = following[position:]
                break
        else:
            following = ""
        pieces.append(text[cursor : match.end()])
        pieces.append(
            f"\nQuestion: {QUESTIONS[dimension_id]}\n"
            f"Score: {score}\n"
            f"Evidence: {' '.join(evidence.split())}\n"
            f"Follow-up: {follow_up}\n\n"
        )
        cursor = block_end - len(following)

    pieces.append(text[cursor:])
    filled = "".join(pieces)
    problems = check_record(filled)
    if problems:
        raise PacketError("filled record is invalid: " + "; ".join(problems))
    return filled


def command_fill(args: argparse.Namespace) -> int:
    packet_path = Path(args.packet)
    if not packet_path.exists():
        print(f"course-quality-review: no packet at {packet_path}", file=sys.stderr)
        return 2
    scores_path = Path(args.scores)
    if not scores_path.exists():
        print(f"course-quality-review: no scores file at {scores_path}", file=sys.stderr)
        return 2
    scores = load_json(scores_path, "scores")
    text = fill_packet(packet_path.read_text(encoding="utf-8"), scores)
    destination = Path(args.out) if args.out else packet_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    print(f"filled {destination}: 8 dimension verdicts, validator verdict echoed")
    return 0


def command_check(args: argparse.Namespace) -> int:
    path = Path(args.record)
    if not path.exists():
        print(f"course-quality-review: no record at {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    errors = check_record(text)
    if errors:
        print(f"course-quality-review: {path} is not a valid review ({len(errors)} problem(s)):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"course-quality-review: {path} PASS (8 dimensions, reviewer named, validator verdict echoed)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    packet = sub.add_parser("packet", help="write a reviewer packet with blank dimension scores")
    packet.add_argument("--plan", required=True, help="generated plan JSON")
    packet.add_argument("--lesson", help="generated lesson JSON")
    packet.add_argument("--validation", help="recorded validation JSON")
    packet.add_argument("--sample-id", required=True, help="stable sample id, e.g. S1")
    packet.add_argument("--scope", default="", help="single, short or full")
    packet.add_argument("--reviewer", required=True, help="named reviewer")
    packet.add_argument("--out", help="write here instead of stdout")
    packet.set_defaults(func=command_packet)

    check = sub.add_parser("check", help="validate a completed review record")
    check.add_argument("record", help="completed markdown record")
    check.set_defaults(func=command_check)

    fill = sub.add_parser("fill", help="fill a packet with the reviewer's eight verdicts")
    fill.add_argument("--packet", required=True, help="packet produced by the packet command")
    fill.add_argument("--scores", required=True, help="JSON object keyed by D1 to D8")
    fill.add_argument("--out", help="write here instead of replacing the packet")
    fill.set_defaults(func=command_fill)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PacketError as exc:
        print(f"course-quality-review: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
