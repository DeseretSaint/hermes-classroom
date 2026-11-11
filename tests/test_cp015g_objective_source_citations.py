"""CP-015g D3: objective citations reach every seam that hands a model a source ledger.

The authority is ``gen_plan_documents.document_json -> $.plan.objectives[].source_ids``. It is
propagated by one pure helper into (1) the lesson author and validator ledger, (2) the unit-sections
authoring payload, (3) the deterministic citations stored on new section rows, and (4) the source
impact read. Nothing here re-decides a stored plan or rewrites a section row.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from coursebook import db, generation as gen, sources
from coursebook.research import SourceRecord

from tests.blueprint_support import NOW, blueprint_plan, unit_sections_document, validation_pass, response
from tests.kernel_support import KernelCase
from tests.test_blueprint_units import UnitStageCase
from tests.test_generation import FakeLLM

ROOT = Path(__file__).resolve().parent.parent


def _ledger(count: int = 8) -> list[SourceRecord]:
    """A ledger at the live excerpt scale (the repro row measured 662 bytes per source)."""
    excerpt = "Leaf colour comes from pigments. " * 22
    return [
        SourceRecord(
            source_id=f"src{index:04d}",
            url=f"https://example.org/leaves-{index}",
            title=f"Leaf colour source {index}",
            publisher="example.org",
            source_type="academic",
            fetched_at="2026-11-09T04:21:11Z",
            published_at=None,
            content_hash=f"sha256:{index:064d}",
            excerpt=excerpt[:560],
        )
        for index in range(count)
    ]


def _objectives(*pairs: tuple[int, list[str]]) -> list[dict]:
    return [
        {
            "ordinal": ordinal,
            "title": f"Objective {ordinal}",
            "evidence_target": "comprehension",
            "evidence_criteria": ["Shows the behaviour in a fresh example"],
            "support": "sourced" if source_ids else "unverified",
            "source_ids": list(source_ids),
        }
        for ordinal, source_ids in pairs
    ]


class LessonLedgerCitationTest(unittest.TestCase):
    """R4: the ledger is the section's citations plus the citations of its objectives."""

    def test_section_citations_are_used_as_the_ledger_slice(self) -> None:
        ledger = _ledger(8)
        rows = gen._lesson_ledger({"source_ids": ["src0003", "src0001"]}, ledger)
        self.assertEqual([row["source_id"] for row in rows], ["src0003", "src0001"])

    def test_an_uncited_section_inherits_its_objectives_citations(self) -> None:
        ledger = _ledger(8)
        rows = gen._lesson_ledger(
            {"source_ids": [], "objective_refs": [1, 2]},
            ledger,
            objective_source_ids=["src0001", "src0003"],
        )
        self.assertEqual([row["source_id"] for row in rows], ["src0001", "src0003"])

    def test_section_and_objective_citations_are_deduped_in_first_seen_order(self) -> None:
        ledger = _ledger(8)
        rows = gen._lesson_ledger(
            {"source_ids": ["src0002"]},
            ledger,
            objective_source_ids=["src0002", "src0001"],
        )
        self.assertEqual([row["source_id"] for row in rows], ["src0002", "src0001"])

    def test_the_objective_slice_is_capped_at_eight_rows(self) -> None:
        ledger = _ledger(10)
        rows = gen._lesson_ledger(
            {"source_ids": []},
            ledger,
            objective_source_ids=[f"src{index:04d}" for index in range(10)],
        )
        self.assertEqual(len(rows), 8)
        self.assertEqual(
            [row["source_id"] for row in rows],
            [f"src{index:04d}" for index in range(8)],
        )

    def test_neither_citation_falls_back_to_the_first_four_briefs(self) -> None:
        ledger = _ledger(6)
        rows = gen._lesson_ledger({"source_ids": [], "objective_refs": [1]}, ledger)
        self.assertEqual([row["source_id"] for row in rows], [s.source_id for s in ledger[:4]])

    def test_author_and_validator_receive_the_identical_slice(self) -> None:
        ledger = _ledger(8)
        plan = {"objectives": _objectives((1, ["src0003", "src0001"]))}
        section = {"section_id": "sec1", "ordinal": 1, "objective_refs": [1], "source_ids": []}
        author = gen.build_lesson_request(
            plan=plan, section=section, objective=None, recipe="casual", dials={},
            locale=None, sources=ledger,
        )
        validator = gen.build_lesson_validation_request(
            lesson={}, page={}, section=section, objective=None, recipe="casual", dials={},
            locale=None, sources=ledger, plan=plan,
        )
        author_payload = json.loads(author.input_text)
        validator_payload = json.loads(validator.input_text)
        self.assertEqual(
            [row["source_id"] for row in author_payload["sources"]],
            ["src0003", "src0001"],
        )
        self.assertEqual(author_payload["sources"], validator_payload["sources"])

    def test_an_eight_row_slice_keeps_both_requests_inside_the_single_byte_bound(self) -> None:
        ledger = _ledger(8)
        plan = {"objectives": _objectives((1, [f"src{i:04d}" for i in range(8)]))}
        section = {"section_id": "sec1", "ordinal": 1, "objective_refs": [1], "source_ids": []}
        author = gen.build_lesson_request(
            plan=plan, section=section, objective=None, recipe="casual", dials={},
            locale=None, sources=ledger,
        )
        validator = gen.build_lesson_validation_request(
            lesson={}, page={}, section=section, objective=None, recipe="casual", dials={},
            locale=None, sources=ledger, plan=plan,
        )
        bound = gen.REQUEST_BYTES_BOUNDS["single"]
        print(
            "CP-015g D3 measured bytes: lesson author",
            len(author.input_text.encode("utf-8")),
            "validator",
            len(validator.input_text.encode("utf-8")),
            "bound",
            bound,
        )
        self.assertLessEqual(len(author.input_text.encode("utf-8")), bound)
        self.assertLessEqual(len(validator.input_text.encode("utf-8")), bound)

    def test_a_legacy_plan_without_objective_citations_is_unchanged(self) -> None:
        ledger = _ledger(6)
        # The v1 shape: no ``objectives`` key and no citations anywhere.
        rows = gen._lesson_ledger({"source_ids": []}, ledger)
        self.assertEqual([row["source_id"] for row in rows], [s.source_id for s in ledger[:4]])
        request = gen.build_lesson_request(
            plan={}, section={"source_ids": []}, objective=None, recipe="casual", dials={},
            locale=None, sources=ledger,
        )
        payload = json.loads(request.input_text)
        self.assertEqual(
            [row["source_id"] for row in payload["sources"]],
            [s.source_id for s in ledger[:4]],
        )


class UnitSectionsPayloadTest(unittest.TestCase):
    """R2: the unit author sees each objective's support and citations, and the citation rule."""

    def _request(self):
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2, reviews=[1, 0])
        plan["objectives"][0].update(support="sourced", source_ids=["src0001", "src0002"])
        plan["objectives"][1]["support"] = "unverified"
        plan["objectives"][1].pop("source_ids", None)
        objectives = [obj for obj in plan["objectives"] if int(obj["unit_ref"]) == 1]
        return gen.build_unit_sections_request(
            plan=plan,
            unit=next(unit for unit in plan["units"] if int(unit["ordinal"]) == 1),
            objectives=objectives,
            goal=plan["learner_outcome"],
            recipe="casual",
            locale=None,
            sources=[],
            research_status="unavailable",
        )

    def test_objectives_carry_support_and_citation_identifiers(self) -> None:
        payload = json.loads(self._request().input_text)
        by_ordinal = {int(obj["ordinal"]): obj for obj in payload["objectives"]}
        self.assertEqual(by_ordinal[1]["support"], "sourced")
        self.assertEqual(by_ordinal[1]["source_ids"], ["src0001", "src0002"])
        self.assertEqual(by_ordinal[2]["support"], "unverified")
        self.assertEqual(by_ordinal[2]["source_ids"], [])

    def test_instructions_state_the_citation_rule(self) -> None:
        instructions = self._request().instructions
        self.assertIn("cites the sources that back its objective", instructions)
        self.assertIn("union of the sources of the objectives it reinforces", instructions)
        self.assertIn("objective with no citations is not a reason to cite anything else", instructions)

    def test_prompt_version_advanced_and_the_docs_row_matches(self) -> None:
        # The merged tree carries CP-015g's unit-scope and CP-015h's construct-shape rules on the
        # same instruction text this card adds the citation rule to, so the label advanced to v3
        # rather than reusing v2 for a second, different text (docs/GENERATION.md §1).
        self.assertEqual(gen.UNIT_SECTIONS_PROMPT_VERSION, "unit-sections-prompt.v3")
        docs = (ROOT / "docs" / "GENERATION.md").read_text(encoding="utf-8")
        self.assertIn(
            f"| Unit-sections author | `coursebook.unit_sections.generate` | "
            f"`{gen.UNIT_SECTIONS_PROMPT_VERSION}` | `UNIT_SECTIONS_SCHEMA` |",
            docs,
        )


class UnitSectionsStoreCitationTest(UnitStageCase):
    """R3: stored section citations are derived from the objective citations, then authored ids."""

    def _seed_cited(self, plan: dict, *, ledger_ids: list[str] | None = None) -> str:
        _course_id, plan_id = self.seed(plan)
        if ledger_ids:
            sources = [
                {
                    "source_id": source_id,
                    "url": f"https://example.test/{source_id}",
                    "title": f"Source {source_id}",
                    "publisher": "example.test",
                    "source_type": "web",
                    "fetched_at": "2026-11-11T00:00:00Z",
                    "published_at": None,
                    "content_hash": f"sha256:{index:064d}",
                    "support_status": "unassessed",
                    "claim_links": [],
                    "excerpt": "",
                    "query": "",
                    "truncated": False,
                }
                for index, source_id in enumerate(ledger_ids)
            ]
            with db.transaction() as connection:
                connection.execute(
                    "UPDATE gen_plan_documents SET research_json = ? WHERE plan_id = ?",
                    (
                        json.dumps(
                            {"status": "ok", "sources": sources, "queries": [], "failures": []}
                        ),
                        plan_id,
                    ),
                )
        return plan_id

    def _run(self, plan: dict, plan_id: str, document: dict) -> dict:
        llm = FakeLLM(
            {
                "coursebook.unit_sections.generate": response(document),
                "coursebook.unit_sections.validate": response(validation_pass()),
            }
        )
        return gen.run_unit_sections_job(
            db.connect(),
            {"job_id": None, "brief": {"plan_id": plan_id, "unit_ordinal": 1}},
            llm,
            plan_id=plan_id,
            unit_ordinal=1,
            now=NOW,
        )

    def _stored(self, plan_id: str) -> list[list[str]]:
        with db.read() as connection:
            rows = connection.execute(
                "SELECT source_ids_json FROM gen_plan_sections WHERE plan_id = ? ORDER BY ordinal",
                (plan_id,),
            ).fetchall()
        return [json.loads(row["source_ids_json"]) for row in rows]

    def test_an_empty_authored_batch_stores_the_objective_citations(self) -> None:
        plan = blueprint_plan(scope="short", units=2, objectives_per_unit=2, reviews=[1, 0])
        plan["objectives"][0].update(support="sourced", source_ids=["src0001", "src0002"])
        plan["objectives"][1].update(support="sourced", source_ids=["src0002", "src0003"])
        plan_id = self._seed_cited(plan)
        unit_one = next(unit for unit in plan["units"] if int(unit["ordinal"]) == 1)
        objectives = [obj for obj in plan["objectives"] if int(obj["unit_ref"]) == 1]
        document = unit_sections_document(unit=unit_one, objectives=objectives, reviews=1)
        self._run(plan, plan_id, document)
        stored = self._stored(plan_id)
        self.assertEqual(stored[0], ["src0001", "src0002"])
        self.assertEqual(stored[1], ["src0002", "src0003"])
        # The review reinforces objectives 1 and 2: the union, deduped, first-seen.
        self.assertEqual(stored[2], ["src0001", "src0002", "src0003"])

    def test_authored_ids_follow_the_objective_citations(self) -> None:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        plan["objectives"][0].update(support="sourced", source_ids=["src0001"])
        plan_id = self._seed_cited(plan, ledger_ids=["src0001", "src0002"])
        unit_one = plan["units"][0]
        document = unit_sections_document(unit=unit_one, objectives=plan["objectives"])
        document["sections"][0]["source_ids"] = ["src0002"]
        self._run(plan, plan_id, document)
        stored = self._stored(plan_id)
        self.assertEqual(stored[0], ["src0001", "src0002"])

    def test_the_stored_citation_cap_is_six(self) -> None:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1)
        plan["objectives"][0].update(
            support="sourced",
            source_ids=["src0001", "src0002", "src0003", "src0004", "src0005", "src0006", "src0007"],
        )
        plan_id = self._seed_cited(plan)
        unit_one = plan["units"][0]
        document = unit_sections_document(unit=unit_one, objectives=plan["objectives"])
        self._run(plan, plan_id, document)
        stored = self._stored(plan_id)
        self.assertEqual(stored[0], ["src0001", "src0002", "src0003", "src0004", "src0005", "src0006"])


class SourceImpactObjectiveCitationTest(KernelCase):
    """R5: a section bound to a citing objective counts as citing that source."""

    def test_impact_reports_the_objectives_checks_for_an_objective_only_citation(self) -> None:
        lesson = self.prepare_lesson()
        source_id = "src_objective_only"
        stamp = "2026-11-11T00:00:00Z"
        with db.transaction() as connection:
            gen.ensure_schema(connection)
            connection.execute(
                "INSERT INTO sources (id, course_id, url, title, source_type, published_at,"
                " fetched_at, support_status, claim_count, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (source_id, lesson["course_id"], "https://example.test/objective-only",
                 "Objective source", "web", None, stamp, "unassessed", 1, stamp),
            )
            connection.execute(
                "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint,"
                " plan_hash, document_json, research_json, generation_state, validation_id,"
                " result_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "gpd_objective_only",
                    lesson["plan_id"],
                    lesson["course_id"],
                    "fp-objective-only",
                    "planhash",
                    json.dumps(
                        {
                            "plan": {
                                "objectives": [
                                    {"ordinal": 1, "support": "sourced", "source_ids": [source_id]}
                                ]
                            },
                            "recipe": "committed",
                        }
                    ),
                    json.dumps({"status": "unavailable", "sources": [], "queries": [], "failures": []}),
                    "draft",
                    None,
                    "{}",
                    stamp,
                ),
            )
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                ("sec_objective_only", lesson["plan_id"], 1, "planhash", "Section", "Learn",
                 json.dumps([1]), "[]", "[]"),
            )
        with db.read() as connection:
            result = sources.impact(connection, source_id)
        self.assertEqual(result["objective_ids"], [lesson["objective_id"]])
        self.assertEqual(result["check_ids"], [lesson["check_id"]])


if __name__ == "__main__":
    unittest.main()
