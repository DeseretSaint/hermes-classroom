"""UP-38: a plan that declares no visual need is adopted without a floor.

Reproduction. A generated plan declares one ``media_need`` per section and the policy adopted any
declaration that parsed: ``_declared_image_decision`` returned ``none`` for a procedure section
with the reason "the plan declares no visual need for this section". The domain rule that a
procedure carries a schematic existed only on the legacy ``_image_decision`` path, which the
declared-plan path never runs. A bread-baking or repair course therefore arrived with no figure
anywhere, and no warning said the course was authored as text only.

The floor is deliberately narrow, and these cases pin both halves of that:

* a procedure or discrimination objective in a non-symbolic domain cannot declare ``none``; the
  accepted remedies are a deterministic schematic or a cited source image, never an AI picture;
* a language plan and a symbolic-domain plan keep their current verdicts (a phrase and a
  derivation are the evidence; forcing a picture there is the bug, not the fix);
* when the ledger carries no citable asset there is nothing to cite, so the plan is adopted and
  the shortfall is disclosed as the typed warning ``media_floor_unmet`` naming the sections.

Run: ``python3 -m unittest tests.test_up_media_floor``
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from coursebook import generation as gen
from coursebook import policy, research

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "generation"

#: A section that declares no media at all: the shape HEAD adopted without a floor.
NONE_NEED = {
    "construct": "",
    "image": {"level": "none", "role": "none"},
    "audio": {"level": "none", "role": "none"},
}

DOMAIN = "technical_procedure"
DIALS = {"subject_domain": DOMAIN}


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def citable_source() -> research.SourceRecord:
    """A fetched source with quotable prose, so a section could cite an image from it."""
    return research.SourceRecord(
        source_id="SRC_ALPHA",
        url="https://example.org/brake-pad-manual",
        title="Rim brake pad replacement",
        publisher="Example",
        source_type="reference",
        fetched_at="2026-11-08T00:00:00Z",
        published_at=None,
        content_hash="sha256:" + "0" * 64,
        support_status="supported",
        excerpt="Standard polite forms are the safe default. Seat the pad square in the caliper, "
        "then tighten the fastener to the printed torque.",
    )


def procedure_plan() -> dict:
    """The committed brake procedure fixture, with every section declaring no visual.

    ``plan_one_off`` is the real four-section procedure: four ``procedure`` objectives, each with
    its own section. Only the media declaration is changed, so the first rule failure is the floor
    and not a fixture defect.
    """
    plan = copy.deepcopy(fixture("plan_one_off"))
    for section in plan["sections"]:
        section["media_need"] = copy.deepcopy(NONE_NEED)
    return plan


class MediaFloorTest(unittest.TestCase):
    """The domain floor, its two accepted remedies and its one legitimate downgrade."""

    def test_procedure_plan_cannot_declare_no_visual(self) -> None:
        plan = procedure_plan()

        # A citable asset exists, so the author can satisfy the floor; the plan is refused and
        # every one of the four sections is named with a remedy it can actually declare.
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_plan_rules(
                plan,
                recipe="casual",
                dials=DIALS,
                locale="en-US",
                ledger=[citable_source()],
                scope="single",
            )
        reasons = caught.exception.reasons
        floor_reasons = [reason for reason in reasons if "Declare a 'schematic' need" in reason]
        self.assertEqual(len(floor_reasons), 4, reasons)
        for reason in floor_reasons:
            self.assertIn("is not a symbolic domain", reason)
            self.assertIn("'sourced_reference' need", reason)
            self.assertIn("An AI illustration is not a substitute", reason)

        # With no citable asset there is nothing to cite, so the same plan is adopted and the
        # shortfall is disclosed instead of buying another pass with the same answer.
        gen.enforce_plan_rules(
            plan,
            recipe="casual",
            dials=DIALS,
            locale="en-US",
            ledger=[],
            scope="single",
        )
        warnings = gen.media_floor_warnings(
            plan["sections"], recipe="casual", dials=DIALS, locale="en-US", plan=plan, ledger=[]
        )
        self.assertEqual(len(warnings), 1, warnings)
        self.assertTrue(warnings[0].startswith("media_floor_unmet: sections 1, 2, 3, 4"), warnings[0])
        self.assertIn("carries no citable asset", warnings[0])

    def test_language_plan_keeps_its_verdict(self) -> None:
        plan = fixture("plan_ja")
        # Objective 1 is a discrimination and its section declares no visual. The evidence is the
        # phrase and the register contrast, so the floor must not fire.
        gen.enforce_plan_rules(
            plan,
            recipe="committed",
            dials={"level": "L0"},
            locale="ja-JP",
            ledger=[citable_source()],
            scope="short",
        )
        capability = gen.lesson_capability_plan(
            recipe="committed",
            section=plan["sections"][0],
            objective=plan["objectives"][0],
            locale="ja-JP",
            dials={"level": "L0"},
            plan=plan,
        )
        self.assertEqual(
            (capability.image, capability.image_role), ("none", None), capability.reasons
        )
        self.assertIn(
            "the plan declares no visual need for this section", capability.reasons
        )
        self.assertEqual(
            gen.media_floor_warnings(
                plan["sections"],
                recipe="committed",
                dials={"level": "L0"},
                locale="ja-JP",
                plan=plan,
                ledger=[],
            ),
            [],
        )

    def test_symbolic_domain_plan_keeps_its_verdict(self) -> None:
        plan = procedure_plan()
        # The same procedure objectives, declared as a mathematics course: a derivation is
        # symbolic, and an AI illustration of it is refused on purpose, so the floor is silent.
        gen.enforce_plan_rules(
            plan,
            recipe="casual",
            dials={"subject_domain": "mathematics"},
            locale="en-US",
            ledger=[citable_source()],
            scope="single",
        )
        capability = gen.lesson_capability_plan(
            recipe="casual",
            section=plan["sections"][0],
            objective=plan["objectives"][0],
            locale="en-US",
            dials={"subject_domain": "mathematics"},
            plan=plan,
        )
        self.assertEqual(
            (capability.image, capability.image_role), ("none", None), capability.reasons
        )
        self.assertEqual(
            gen.media_floor_warnings(
                plan["sections"],
                recipe="casual",
                dials={"subject_domain": "mathematics"},
                locale="en-US",
                plan=plan,
                ledger=[],
            ),
            [],
        )

    def test_floor_accepts_the_schematic_and_the_cited_source(self) -> None:
        schematic = policy.plan_lesson_capability(
            recipe="casual",
            evidence_target="procedure",
            lesson_intent="Seat the new pad and tighten the caliper fastener.",
            subject_domain=DOMAIN,
            media_need={
                "construct": "the labelled parts diagram of the caliper and pad slot",
                "image": {"level": "required", "role": "schematic"},
                "audio": {"level": "none", "role": "none"},
            },
        )
        self.assertEqual((schematic.image, schematic.image_role), ("required", "schematic"))

        sourced = policy.plan_lesson_capability(
            recipe="casual",
            evidence_target="procedure",
            lesson_intent="Seat the new pad and tighten the caliper fastener.",
            subject_domain=DOMAIN,
            media_need={
                "construct": "the photograph of the worn pad beside the loosened fastener",
                "image": {"level": "required", "role": "sourced_reference"},
                "audio": {"level": "none", "role": "none"},
            },
        )
        self.assertEqual((sourced.image, sourced.image_role), ("required", "sourced_reference"))

    def test_floor_never_accepts_an_illustration_as_the_authority(self) -> None:
        # Context art is never the evidence: an illustration-only declaration leaves the
        # procedure with nothing to check its steps against, so it is refused exactly as ``none``.
        with self.assertRaises(policy.MediaFloorUnmet) as caught:
            policy.plan_lesson_capability(
                recipe="casual",
                evidence_target="procedure",
                lesson_intent="Seat the new pad and tighten the caliper fastener.",
                subject_domain=DOMAIN,
                media_need={
                    "construct": "a picture of a mechanic working on a bicycle",
                    "image": {"level": "optional", "role": "illustration"},
                    "audio": {"level": "none", "role": "none"},
                },
            )
        self.assertIn("context art", str(caught.exception))

    def test_aural_discrimination_is_not_forced_to_carry_a_picture(self) -> None:
        # The recorded music scenario distinguishes two thirds *by sound*. That is a genuine
        # prose/audio subject, so the floor must not demand a schematic for it (UP-38's own
        # adversarial note: a refusal on a genuine prose subject is a bug in the rule).
        aural = policy.plan_lesson_capability(
            recipe="committed",
            evidence_target="discrimination",
            lesson_intent="Teach the sound difference and check the learner can name it.",
            subject_domain="general",
            media_need=copy.deepcopy(NONE_NEED),
        )
        self.assertEqual((aural.image, aural.image_role), ("none", None))

        # The same evidence target with something visible to tell apart is refused: the section's
        # own words name the diagram, and the plan declared no image for it.
        with self.assertRaises(policy.MediaFloorUnmet):
            policy.plan_lesson_capability(
                recipe="committed",
                evidence_target="discrimination",
                lesson_intent="Tell the brass fitting apart from the steel one using the labelled parts diagram.",
                subject_domain="general",
                media_need=copy.deepcopy(NONE_NEED),
            )

    def test_unit_batch_uses_the_same_floor(self) -> None:
        from tests.blueprint_support import blueprint_plan, unit_sections_document

        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1, recipe="casual")
        plan["objectives"][0]["evidence_target"] = "procedure"
        document = unit_sections_document(unit=plan["units"][0], objectives=plan["objectives"])
        sections = document["sections"]
        kwargs = {
            "unit": plan["units"][0],
            "objectives": plan["objectives"],
            "plan": plan,
            "recipe": "casual",
            "dials": DIALS,
            "locale": "en-US",
        }
        # The unit stage is the stage that first sees sections on a blueprint plan, so it runs the
        # same floor: repairable when there is something to cite, disclosed when there is not.
        with self.assertRaises(gen._RuleViolation) as caught:
            gen.enforce_unit_section_rules(sections, ledger=[citable_source()], **kwargs)
        self.assertIn("Declare a 'schematic' need", "\n".join(caught.exception.reasons))

        gen.enforce_unit_section_rules(sections, ledger=[], **kwargs)
        warnings = gen.media_floor_warnings(
            sections, recipe="casual", dials=DIALS, locale="en-US", plan=plan, ledger=[]
        )
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("sections 1", warnings[0])
