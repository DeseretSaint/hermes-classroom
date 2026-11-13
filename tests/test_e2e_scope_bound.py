"""The unit-sections stage must fit the scope bound its own plan declared (E2E review G1).

Measured 2026-11-13 on a live full-scope plan (12 objectives, 4 units, 6 sources): the
``coursebook.unit_sections.generate`` payload was 25,786 bytes compact and was refused at the
24,000-byte default before the first model call. A legal full course could not author a lesson.
The bound is already scope-aware (``REQUEST_BYTES_BOUNDS``); the unit stage simply never used it,
and it handed every research source to every unit instead of the rows that unit cites.
"""

from __future__ import annotations

import json
import unittest

from coursebook import generation as gen
from coursebook.research import SourceRecord

from tests.blueprint_support import blueprint_plan


def _ledger(count: int = 6, *, chars: int = 1200) -> list[SourceRecord]:
    excerpt = ("Poached eggs need a gentle simmer and a short clock. " * 40)[:chars]
    return [
        SourceRecord(
            source_id=f"src{index:04d}",
            url=f"https://example.org/egg-{index}",
            title=f"Egg source {index}",
            publisher="example.org",
            source_type="web_page",
            fetched_at="2026-11-13T00:35:25Z",
            published_at=None,
            content_hash=f"sha256:{index:064d}",
            excerpt=excerpt,
        )
        for index in range(count)
    ]


class ScopeBoundTest(unittest.TestCase):
    def test_the_bound_scales_with_the_declared_scope(self) -> None:
        self.assertEqual(gen._request_bound("single"), 24000)
        self.assertEqual(gen._request_bound("short"), 24000)
        self.assertEqual(gen._request_bound("full"), 48000)
        self.assertEqual(gen._request_bound(None), 24000)

    def _full_plan(self, *, cited: int) -> dict:
        plan = blueprint_plan(scope="full", units=4, objectives_per_unit=3)
        for index, objective in enumerate(plan["objectives"], start=1):
            if index <= cited:
                objective["support"] = "sourced"
                objective["source_ids"] = [f"src{index - 1:04d}"]
                objective["source_quote"] = "Poached eggs need a gentle simmer."
            else:
                objective["support"] = "unverified"
                objective.pop("source_ids", None)
        return plan

    def _unit(self, plan: dict) -> dict:
        return next(unit for unit in plan["units"] if int(unit["ordinal"]) == 1)

    def _objectives(self, plan: dict) -> list[dict]:
        return [obj for obj in plan["objectives"] if int(obj["unit_ref"]) == 1]

    def test_a_unit_sees_only_the_rows_its_own_objectives_cite(self) -> None:
        plan = self._full_plan(cited=1)
        objectives = self._objectives(plan)
        selected = gen._unit_cited_sources(plan, objectives, _ledger())
        self.assertEqual([row.source_id for row in selected], ["src0000"])

    def test_an_uncited_unit_gets_the_lesson_cap_not_the_whole_ledger(self) -> None:
        plan = self._full_plan(cited=0)
        objectives = self._objectives(plan)
        selected = gen._unit_cited_sources(plan, objectives, _ledger())
        self.assertEqual(len(selected), 4)

    def test_a_full_scope_request_with_six_sources_fits_its_own_bound(self) -> None:
        # The measured failure: six 1200-character rows plus a twelve-objective plan. The unit
        # request must build (no GenerationRejected) and stay inside the 48 kB full bound.
        plan = self._full_plan(cited=6)
        request = gen.build_unit_sections_request(
            plan=plan,
            unit=self._unit(plan),
            objectives=self._objectives(plan),
            goal=plan["learner_outcome"],
            recipe="committed",
            locale=None,
            sources=_ledger(),
            research_status="ok",
        )
        self.assertLessEqual(len(request.input_text), gen.REQUEST_BYTES_BOUNDS["full"])
        self.assertEqual(
            [row["source_id"] for row in json.loads(request.input_text)["sources"]],
            [f"src{index:04d}" for index in range(6)],
        )

    def test_the_author_and_the_validator_see_the_same_ledger(self) -> None:
        plan = self._full_plan(cited=6)
        sources = _ledger()
        objectives = self._objectives(plan)
        author = gen.build_unit_sections_request(
            plan=plan,
            unit=self._unit(plan),
            objectives=objectives,
            goal=plan["learner_outcome"],
            recipe="committed",
            locale=None,
            sources=gen._unit_cited_sources(plan, objectives, sources),
            research_status="ok",
        )
        validator = gen.build_unit_sections_validation_request(
            plan=plan,
            unit=self._unit(plan),
            objectives=objectives,
            sections=[{"title": "x", "lesson_intent": "y" * 40, "objective_refs": [1]}],
            goal=plan["learner_outcome"],
            recipe="committed",
            locale=None,
            sources=gen._unit_cited_sources(plan, objectives, sources),
            research_status="ok",
        )
        self.assertEqual(
            [row["source_id"] for row in json.loads(author.input_text)["sources"]],
            [row["source_id"] for row in json.loads(validator.input_text)["sources"]],
        )
        self.assertLessEqual(len(validator.input_text), gen.REQUEST_BYTES_BOUNDS["full"])


if __name__ == "__main__":
    unittest.main()
