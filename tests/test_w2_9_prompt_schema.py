"""W2-9 — a prompt never asks for a field its own schema forbids, and never forbids an honest gap.

Two measured contradictions (``docs/CREATE-EXPERIENCE-SPEC.md`` items 20 and 21):

* ``mastery_path.plan_policy_lines`` told the v2 plan author that "a gate check writes
  ``independent_evidence``", a key ``PLAN_SCHEMA_V2``'s ``check_plan`` entry removed and
  :func:`enforce_plan_rules` rejects. A request for a field the schema forbids is a guaranteed
  model-side loss: the field is dropped or the whole answer is refused.
* ``_plan_sourcing_rules`` told the author an objective the excerpts do not carry "must not be
  written at all; ... do not leave it at support 'unverified'", contradicting the declared-gap
  contract the validator is built around (``_PLAN_SUPPORT_RULE``, ``curriculum.py``). A prompt that
  forbids an honest gap pushes the author into inventing a citation.

The guard is one consistency test: every *authoring* stage's instruction text is scanned for a
compound JSON key its own schema does not declare. Validation stages are classified separately and
are not scanned for output keys — a validator's instructions must name the artifact's fields
(``check_plan``, ``source_ids``) because it judges them, and those are inputs to that stage, not
keys it writes. The completeness check below fails when a new ``build_*_request`` appears without
being classified here, so a third instance cannot ship unexamined.

Every assertion runs offline against request builders. No provider is called.
"""

from __future__ import annotations

import ast
import re
import unittest
from collections.abc import Callable
from pathlib import Path

from coursebook import generation as gen
from coursebook import mastery_path
from coursebook import research

#: The exact instruction text this card removed, quoted so the guard can be shown to fail on it.
PRE_FIX_MASTERY = (
    "A gate check writes independent_evidence and a delayed cold check writes delayed_evidence."
)
PRE_FIX_SOURCING = (
    "An objective whose claim the excerpts do not carry must not be written at all; do not invent "
    "a citation and do not leave it at support 'unverified' in a finished plan."
)

#: The honesty clause that must survive the item-21 deletion, verbatim from the prompt it was
#: removed from.
HONESTY_CLAUSE = "do not invent a citation"


def property_keys(node, found: set[str]) -> set[str]:
    """Every JSON object property name declared anywhere inside one schema."""
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            found.update(str(key) for key in properties)
            for value in properties.values():
                property_keys(value, found)
        for key in ("items", "additionalProperties", "oneOf", "anyOf", "allOf", "$defs"):
            if key in node:
                property_keys(node[key], found)
    elif isinstance(node, list):
        for item in node:
            property_keys(item, found)
    return found


#: Every compound key any generation/validation schema in this module spells. The scan asks "does
#: this stage's own schema allow the key its prompt names?", so the vocabulary must include keys
#: another version of the contract carries — that is exactly how ``independent_evidence`` slipped
#: into the v2 plan prompt.
KEY_VOCABULARY: set[str] = set()
for _schema in (
    gen.OBJECTIVE_SCHEMA,
    gen.SECTION_SCHEMA,
    gen.CHECK_PLAN_SCHEMA,
    gen.CHECK_PLAN_SCHEMA_V2,
    gen.PLAN_SCHEMA_V1,
    gen.PLAN_SCHEMA_V2,
    gen.UNIT_SECTIONS_SCHEMA,
    gen.LESSON_SCHEMA,
    gen.VALIDATION_SCHEMA,
):
    property_keys(_schema, KEY_VOCABULARY)
#: Only compound (snake_case) names are scanned. ``goal``, ``check``, ``support`` and ``value`` are
#: property names *and* ordinary English words, so matching them would report prose as a field
#: reference and prove nothing. A compound name is how a prompt addresses a JSON field it is not
#: discussing as a concept, and that is the shape both measured contradictions had.
KEY_VOCABULARY = {key for key in KEY_VOCABULARY if "_" in key and len(key) > 3}

#: Cues that mark a mention as a prohibition ("do not emit count or independent_evidence") rather
#: than an instruction to author the field. A prompt may legitimately forbid keys a schema lacks.
_PROHIBITION = re.compile(
    r"\b(do not|don't|never|must not|may not|cannot|not|without|no)\b", re.IGNORECASE
)

#: A prohibition aimed at the declared ``support: 'unverified'`` gap. The item-21 clause is prose,
#: not a field reference, so the key scan above cannot see it; this is its own measured shape.
_DECLARED_GAP_PROHIBITION = re.compile(
    r"\b(do not|don't|never|must not|may not|cannot)\b[^.]{0,160}?"
    r"\b(leave|end|write|keep|set|be)\b[^.]{0,80}?\bunverified\b",
    re.IGNORECASE,
)


def sentences(text: str) -> list[str]:
    """Instruction text split into sentence-sized units, one clause at a time."""
    lines: list[str] = []
    for line in str(text or "").splitlines():
        lines.extend(part for part in re.split(r"(?<=\.)\s+", line) if part.strip())
    return lines


def asks_for(sentence: str, key: str) -> bool:
    """Does this sentence name *key* outside a prohibition?"""
    for match in re.finditer(rf"(?<![a-z0-9_]){re.escape(key)}(?![a-z0-9_])", sentence):
        if not _PROHIBITION.search(sentence[: match.start()]):
            return True
    return False


def forbidden_keys(schema: dict) -> list[str]:
    """The compound keys some schema in this module spells but *this* stage's schema does not."""
    permitted = property_keys(schema or {}, set())
    return sorted(KEY_VOCABULARY - permitted)


def key_violations(stage: str, instructions: str, schema: dict) -> list[str]:
    """Every place this stage's text asks for a key its own schema forbids, stage named."""
    found: list[str] = []
    forbidden = forbidden_keys(schema)
    for sentence in sentences(instructions):
        for key in forbidden:
            if asks_for(sentence, key):
                found.append(f"{stage} asks for key {key!r}, which its schema forbids: {sentence.strip()}")
    return found


def declared_gap_violations(stage: str, instructions: str) -> list[str]:
    """Every place this stage's text forbids the honest ``support: 'unverified'`` gap."""
    found: list[str] = []
    for sentence in sentences(instructions):
        if "unverified" not in sentence.lower():
            continue
        if _DECLARED_GAP_PROHIBITION.search(sentence):
            found.append(f"{stage} forbids a declared gap the kernel records: {sentence.strip()}")
    return found


def research_unavailable() -> research.ResearchRun:
    return research.ResearchRun(
        status="unavailable", queries=[], sources=[], reason="no search seam in this test"
    )


def _plan() -> dict:
    return {"title": "t", "scope": "short", "goal": "g", "objectives": [], "units": [], "check_plan": []}


def _unit() -> dict:
    return {"ordinal": 1, "title": "u", "goal": "g", "target_lessons": 3, "prereq_unit_ordinals": []}


def plan_v1() -> gen.LLMRequest:
    return gen.build_plan_request(
        goal="Order coffee in Japanese",
        recipe="committed",
        dials={},
        locale="ja-JP",
        research_run=research_unavailable(),
    )


def plan_v2() -> gen.LLMRequest:
    return gen.build_plan_request(
        goal="Order coffee in Japanese",
        recipe="committed",
        dials={},
        locale="ja-JP",
        research_run=research_unavailable(),
        scope="short",
    )


def plan_v1_repair() -> gen.LLMRequest:
    return gen.build_plan_request(
        goal="Order coffee in Japanese",
        recipe="committed",
        dials={},
        locale="ja-JP",
        research_run=research_unavailable(),
        feedback="fix this",
        previous_draft={"title": "x", "objectives": []},
    )


def plan_v2_repair() -> gen.LLMRequest:
    return gen.build_plan_request(
        goal="Order coffee in Japanese",
        recipe="committed",
        dials={},
        locale="ja-JP",
        research_run=research_unavailable(),
        scope="short",
        feedback="fix this",
        previous_draft={"title": "x", "objectives": []},
    )


def lesson() -> gen.LLMRequest:
    return gen.build_lesson_request(
        plan={},
        section={"source_ids": []},
        objective=None,
        recipe="casual",
        dials={},
        locale=None,
        sources=[],
    )


def lesson_repair() -> gen.LLMRequest:
    return gen.build_lesson_request(
        plan={},
        section={"source_ids": []},
        objective=None,
        recipe="casual",
        dials={},
        locale=None,
        sources=[],
        feedback="fix this",
        previous_draft={"section_title": "x", "segments": []},
    )


def unit_sections() -> gen.LLMRequest:
    return gen.build_unit_sections_request(
        plan=_plan(),
        unit=_unit(),
        objectives=[],
        goal="g",
        recipe="casual",
        locale=None,
        sources=[],
        research_status="unavailable",
    )


def unit_sections_repair() -> gen.LLMRequest:
    return gen.build_unit_sections_request(
        plan=_plan(),
        unit=_unit(),
        objectives=[],
        goal="g",
        recipe="casual",
        locale=None,
        sources=[],
        research_status="unavailable",
        feedback="fix this",
    )


def plan_validation() -> list[gen.LLMRequest]:
    return gen.build_plan_validation_requests(
        plan=_plan(),
        goal="g",
        recipe="casual",
        dials={},
        locale=None,
        research_run=research_unavailable(),
        scope="short",
    )


def lesson_validation() -> gen.LLMRequest:
    return gen.build_lesson_validation_request(
        lesson={"section_title": "x", "segments": [], "check": {}},
        page={},
        section={"source_ids": []},
        objective=None,
        recipe="casual",
        dials={},
        locale=None,
        sources=[],
    )


def unit_sections_validation() -> gen.LLMRequest:
    return gen.build_unit_sections_validation_request(
        plan=_plan(),
        unit=_unit(),
        objectives=[],
        sections=[],
        goal="g",
        recipe="casual",
        locale=None,
        sources=[],
        research_status="unavailable",
    )


#: Every ``build_*_request`` in ``generation.py``, mapped to a callable that builds it. The
#: completeness test below reads this module's own source and fails if a builder is missing, so a
#: new stage cannot be added to the pipeline without being classified for this scan.
BUILDERS: dict[
    str, Callable[[], gen.LLMRequest | list[gen.LLMRequest]] | None
] = {
    "build_plan_request": None,  # covered by four labelled variants below
    "build_plan_validation_requests": plan_validation,
    "build_lesson_request": None,  # covered by two labelled variants below
    "build_lesson_validation_request": lesson_validation,
    "build_unit_sections_request": None,  # covered by two labelled variants below
    "build_unit_sections_validation_request": unit_sections_validation,
}

#: The labelled calls each multi-variant builder is exercised through.
BUILDER_VARIANTS: dict[str, tuple[Callable[[], gen.LLMRequest], ...]] = {
    "build_plan_request": (plan_v1, plan_v2, plan_v1_repair, plan_v2_repair),
    "build_lesson_request": (lesson, lesson_repair),
    "build_unit_sections_request": (unit_sections, unit_sections_repair),
}


def all_stage_requests() -> list[tuple[str, str, gen.LLMRequest]]:
    """``(builder, label, request)`` for every stage this module builds, labelled for failures."""
    stages: list[tuple[str, str, gen.LLMRequest]] = []
    for builder, callable_ in BUILDERS.items():
        variants = BUILDER_VARIANTS.get(builder)
        if variants:
            for variant in variants:
                built = variant()
                label = variant.__name__.replace("_", " ")
                stages.append((builder, label, built))
            continue
        assert callable_ is not None, builder
        built = callable_()
        if isinstance(built, list):
            for index, request in enumerate(built):
                stages.append((builder, f"{builder} pass {index}", request))
        else:
            stages.append((builder, builder, built))
    return stages


class PromptSchemaAgreementTest(unittest.TestCase):
    """One test: no generation stage asks for a key its own schema forbids, or forbids a gap."""

    def test_every_generation_stage_prompt_agrees_with_the_schema_it_is_parsed_into(self) -> None:
        violations: list[str] = []
        authoring_purposes: set[str] = set()
        for builder, label, request in all_stage_requests():
            self.assertIsNotNone(request.schema, f"{label} has no schema to agree with")
            # A validator's instructions must name the artifact's fields it judges (``check_plan``,
            # ``source_ids``); those are its inputs, not keys it writes into its own answer. Only a
            # stage that authors an artifact is held to its own output schema's key set.
            if not request.purpose.endswith(".generate"):
                continue
            authoring_purposes.add(request.purpose)
            violations.extend(key_violations(label, request.instructions, request.schema))
            if label.startswith("plan v"):
                violations.extend(declared_gap_violations(label, request.instructions))

        # The scan must actually be looking at every authoring stage the module builds. If a new
        # generation purpose appears, this fails rather than silently escaping the guard.
        self.assertEqual(
            authoring_purposes,
            {
                "coursebook.plan.generate",
                "coursebook.lesson.generate",
                "coursebook.unit_sections.generate",
            },
            "an authoring stage is missing from the prompt/schema scan",
        )
        self.assertEqual(violations, [], "\n".join(violations))

    def test_every_request_builder_in_the_module_is_classified(self) -> None:
        source = Path(gen.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        builders = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and re.fullmatch(r"build_.*_requests?", node.name)
        }
        self.assertEqual(
            builders,
            set(BUILDERS),
            "a request builder exists that the prompt/schema scan does not classify",
        )

    def test_the_guard_fails_on_the_pre_fix_prompts_and_names_both_stages(self) -> None:
        """The item-20 and item-21 text, scanned exactly as the guard scans today's prompts."""
        mastery_hits = key_violations("plan v2", PRE_FIX_MASTERY, gen.PLAN_SCHEMA_V2)
        self.assertTrue(mastery_hits, "the scan no longer sees the independent_evidence request")
        self.assertTrue(any("independent_evidence" in hit for hit in mastery_hits))
        self.assertTrue(any(hit.startswith("plan v2") for hit in mastery_hits))

        # The sourcing rule is shared instruction text, so the clause contradicted both plan
        # prompts. The failure message must name the stage, not just the sentence.
        for stage in ("plan v1", "plan v2"):
            gap_hits = declared_gap_violations(stage, PRE_FIX_SOURCING)
            self.assertTrue(gap_hits, f"the scan no longer sees the declared-gap clause in {stage}")
            self.assertTrue(any(hit.startswith(stage) for hit in gap_hits))

    def test_the_mastery_directives_use_the_truthful_form_the_schema_accepts(self) -> None:
        text = " ".join(mastery_path.plan_policy_lines())
        self.assertNotIn("independent_evidence", text)
        # The field still means something; the prompt names it as harness-recorded evidence and
        # states the only keys a check_plan entry carries, instead of asking for a field.
        self.assertIn("recorded by the harness as independent evidence", text)
        self.assertIn("a check_plan entry carries objective_ref, kind and evidence_target only", text)

    def test_the_sourcing_rules_allow_a_declared_gap_and_keep_the_honesty_clause(self) -> None:
        rules = " ".join(gen._plan_sourcing_rules())
        self.assertEqual(declared_gap_violations("plan v1", rules), [])
        self.assertNotIn("must not be written at all", rules)
        self.assertNotIn("do not leave it at support 'unverified'", rules)
        self.assertIn("declared gap", rules)
        self.assertIn("set support to 'unverified'", rules)
        # Item 21 deletes the clause, not the honesty rule.
        self.assertIn(HONESTY_CLAUSE, rules)
        for request in (plan_v1(), plan_v2()):
            self.assertIn(HONESTY_CLAUSE, request.instructions)


if __name__ == "__main__":
    unittest.main()
