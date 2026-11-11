"""H-89 — declared frequency inventories and deterministic vocabulary sequencing.

No third-party frequency list is bundled: the source audit (``docs/FREQUENCY-INVENTORY.md``)
rejected every candidate on licence or metadata grounds. These tests therefore prove the seam,
not a coverage premise:

* a plan takes its opening vocabulary targets from a declared fixture inventory in rank order;
* a missing inventory produces the typed ``frequency_inventory_unavailable`` path and no items;
* a second language uses the same contract and the same checks;
* duplicate, out-of-band, skipped-rank and function-word targets are refused;
* H-88's curriculum brief and sequence rules still reach the author.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path

from coursebook import frequency, generation as gen, research
from tests.blueprint_support import (
    blueprint_plan,
    response as support_response,
    validation_pass,
    validation_responder,
)
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    plan_fixture,
    source_ids_from,
    validation_from_fixture,
)

FIXTURES = Path(__file__).parent / "fixtures" / "frequency"
NOW = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)


def load(name: str = "ja-core-v1.json") -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def selection(name: str = "ja-core-v1.json", band: str | None = "band-core"):
    inventory = frequency.load_inventory(load(name))
    return frequency.select_inventory(inventory, band_id=band, language=inventory.language)


def brief_with(document: dict, *, language: str = "ja", band: str = "band-core") -> dict:
    return {
        "goal": "Order coffee politely in Japanese",
        "recipe": "committed",
        "dials": {"depth": "working"},
        "locale": "ja-JP",
        "level": "L0",
        "subject_domain": "language",
        "scope": "short",
        "frequency_inventory": {"document": document, "band": band},
    }


def plan_job(brief: dict) -> dict:
    return {
        "job_id": "job-plan-h89",
        "kind": "plan",
        "attempt_id": "attempt-1",
        "brief": brief,
    }


def japanese_plan(target_items: dict[int, list[str]] | None = None) -> dict:
    plan = blueprint_plan(scope="short", units=1, objectives_per_unit=4, recipe="committed")
    for objective in plan["objectives"]:
        items = (target_items or {}).get(int(objective["ordinal"]))
        if items:
            objective["target_items"] = items
    return plan


class InventoryContractTest(unittest.TestCase):
    def test_the_bundled_fixture_satisfies_the_frozen_contract(self) -> None:
        inventory = frequency.load_inventory(load())
        self.assertEqual(inventory.language, "ja")
        self.assertEqual(inventory.modality, "mixed")
        self.assertEqual(inventory.licence, "CC0-1.0")
        self.assertTrue(frequency.bundle_eligible(inventory))
        self.assertEqual(inventory.content_hash, frequency.rows_content_hash(load()["rows"]))
        self.assertEqual(len(inventory.rows), 15)
        self.assertEqual(len(inventory.band_rows("band-core")), 12)

    def test_the_spanish_fixture_uses_the_same_contract(self) -> None:
        inventory = frequency.load_inventory(load("es-core-v1.json"))
        self.assertEqual(inventory.language, "es")
        self.assertEqual([row["lemma"] for row in inventory.band_rows("band-core")][:2], ["agua", "comer"])

    def test_an_edited_row_breaks_the_declared_hash(self) -> None:
        document = copy.deepcopy(load())
        document["rows"][2]["lemma"] = "お湯"
        with self.assertRaises(frequency.FrequencyInventoryError) as caught:
            frequency.load_inventory(document)
        self.assertIn("content_hash", str(caught.exception))

    def test_a_rank_gap_is_refused(self) -> None:
        document = copy.deepcopy(load())
        document["rows"][4]["rank"] = 99
        document["content_hash"] = frequency.rows_content_hash(document["rows"])
        with self.assertRaises(frequency.FrequencyInventoryError) as caught:
            frequency.load_inventory(document)
        self.assertIn("contiguous", str(caught.exception))

    def test_a_row_outside_its_declared_band_is_refused(self) -> None:
        document = copy.deepcopy(load())
        document["rows"][11]["band"] = "band-extension"
        document["content_hash"] = frequency.rows_content_hash(document["rows"])
        with self.assertRaises(frequency.FrequencyInventoryError) as caught:
            frequency.load_inventory(document)
        self.assertIn("outside band", str(caught.exception))

    def test_a_language_mismatch_is_refused_not_coerced(self) -> None:
        inventory = frequency.load_inventory(load())
        with self.assertRaises(frequency.FrequencyInventoryError) as caught:
            frequency.select_inventory(inventory, band_id="band-core", language="es-MX")
        self.assertIn("language", str(caught.exception))


class VocabularySequenceRuleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.selection = selection()

    def reasons(self, items: dict[int, list[str]]) -> list[str]:
        objectives = [
            {"ordinal": ordinal, "target_items": lemmas}
            for ordinal, lemmas in sorted(items.items())
        ]
        return frequency.plan_vocabulary_reasons(objectives, self.selection)

    def test_the_opening_content_items_in_rank_order_pass(self) -> None:
        # The band's grammar rows (は rank 1, です rank 2) are excluded; the content rows begin
        # at 水 (rank 3). Four declared items must be the first four of that content list.
        self.assertEqual(self.reasons({1: ["水", "これ"], 2: ["食べる", "私"]}), [])

    def test_a_duplicate_item_is_refused(self) -> None:
        reasons = self.reasons({1: ["水", "これ"], 2: ["水"]})
        self.assertTrue(any("appears in objectives" in reason for reason in reasons), reasons)

    def test_an_item_from_another_band_is_refused(self) -> None:
        reasons = self.reasons({1: ["水", "新幹線"]})
        self.assertTrue(any("not the declared band" in reason for reason in reasons), reasons)

    def test_a_function_word_is_grammar_not_a_vocabulary_card(self) -> None:
        reasons = self.reasons({1: ["は"]})
        self.assertTrue(any("function words are grammar" in reason for reason in reasons), reasons)

    def test_skipping_a_rank_is_refused_even_when_order_is_ascending(self) -> None:
        reasons = self.reasons({1: ["水", "私"]})
        self.assertTrue(any("prefix" in reason for reason in reasons), reasons)

    def test_out_of_order_targets_are_refused(self) -> None:
        reasons = self.reasons({1: ["食べる", "水"]})
        self.assertTrue(any("ascending frequency rank" in reason for reason in reasons), reasons)

    def test_no_vocabulary_at_all_is_refused_when_a_band_is_declared(self) -> None:
        reasons = frequency.plan_vocabulary_reasons([{"ordinal": 1}], self.selection)
        self.assertTrue(any("must name its opening vocabulary" in reason for reason in reasons), reasons)

    def test_items_without_an_inventory_are_refused(self) -> None:
        reasons = frequency.plan_vocabulary_reasons(
            [{"ordinal": 1, "target_items": ["水"]}], None
        )
        self.assertTrue(any("no frequency inventory is available" in reason for reason in reasons), reasons)


class PlanRequestSeamTest(unittest.TestCase):
    def test_the_prompt_carries_the_inventory_source_licence_hash_and_rules(self) -> None:
        inventory_selection = selection()
        request = gen.build_plan_request(
            goal="Order coffee politely",
            recipe="committed",
            dials={"depth": "working"},
            locale="ja-JP",
            research_run=research.ResearchRun(status="unavailable", queries=[], sources=[], reason="test"),
            level="L0",
            subject_domain="language",
            scope="short",
            frequency_selection=inventory_selection,
        )
        payload = json.loads(request.input_text)
        block = payload["vocabulary_inventory"]
        self.assertEqual(block["status"], "inventory")
        self.assertEqual(block["source_id"], "coursebook-fixture-ja-v1")
        self.assertEqual(block["content_hash"], inventory_selection.inventory.content_hash)
        self.assertEqual(block["band"]["id"], "band-core")
        self.assertEqual(block["content_items"][0]["lemma"], "水")
        self.assertEqual([row["lemma"] for row in block["grammar_items"]], ["は", "です"])
        # H-88's brief is still present, and the vocabulary rules are additional, not a replacement.
        self.assertEqual(payload["curriculum"]["language"]["target_language"], "Japanese")
        self.assertIn("Vocabulary inventory", request.instructions)
        self.assertIn("grammar_items", request.instructions)
        self.assertIn("Sequence units by prerequisite dependency", request.instructions)

    def test_the_validation_request_sees_the_same_inventory(self) -> None:
        inventory_selection = selection()
        request = gen.build_plan_validation_requests(
            plan=japanese_plan({1: ["水"]}),
            goal="Order coffee politely",
            recipe="committed",
            dials={"depth": "working"},
            locale="ja-JP",
            research_run=research.ResearchRun(status="unavailable", queries=[], sources=[], reason="test"),
            level="L0",
            subject_domain="language",
            scope="short",
            frequency_selection=inventory_selection,
        )[0]
        payload = json.loads(request.input_text)
        self.assertEqual(payload["vocabulary_inventory"]["content_hash"], inventory_selection.inventory.content_hash)

    def test_the_unavailable_prompt_forbids_items_and_percentages(self) -> None:
        request = gen.build_plan_request(
            goal="Order coffee politely",
            recipe="committed",
            dials={"depth": "working"},
            locale="ja-JP",
            research_run=research.ResearchRun(status="unavailable", queries=[], sources=[], reason="test"),
            level="L0",
            subject_domain="language",
            scope="short",
            frequency_status={
                "status": "unverified",
                "reason": frequency.WARNING_UNAVAILABLE,
                "detail": "the brief declares no frequency inventory",
            },
        )
        payload = json.loads(request.input_text)
        self.assertEqual(payload["vocabulary_inventory"]["status"], "unverified")
        self.assertIn("Do not set `target_items`", request.instructions)
        self.assertIn("coverage percentage", request.instructions)


class PlanJobVocabularyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        gen.ensure_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def run_plan(self, plan: dict, brief: dict) -> dict:
        llm = FakeLLM(
            {
                "coursebook.plan.generate": support_response(plan),
                "coursebook.plan.validate": validation_responder(
                    support_response, validation_pass(), model="fake-validator"
                ),
            }
        )
        return gen.run_plan_job(self.connection, plan_job(brief), llm, FakeSearch(), now=NOW)

    def test_a_japanese_plan_takes_its_opening_vocabulary_in_rank_order(self) -> None:
        plan = japanese_plan({1: ["水", "これ"], 2: ["食べる", "私"], 3: ["行く"]})
        result = self.run_plan(plan, brief_with(load()))
        # GEN-1: this fixture cites no fetched source, so the pass is model_assessed and the
        # plan is parked for review; the vocabulary sequencing below is what this test owns.
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["validation"]["outcome"], gen.OUTCOME_MODEL_ASSESSED)
        self.assertTrue(result["validation"]["facts_unverified"])
        vocabulary = result["vocabulary"]
        self.assertEqual(vocabulary["status"], "inventory")
        self.assertEqual(vocabulary["source_id"], "coursebook-fixture-ja-v1")
        self.assertEqual(vocabulary["content_hash"], frequency.rows_content_hash(load()["rows"]))
        self.assertEqual(vocabulary["band"]["id"], "band-core")
        self.assertEqual(
            [(item["objective_ordinal"], item["rank"], item["lemma"]) for item in vocabulary["items"]],
            [(1, 3, "水"), (1, 4, "これ"), (2, 5, "食べる"), (2, 6, "私"), (3, 7, "行く")],
        )
        # The stored document is the authority the later stages read.
        row = self.connection.execute(
            "SELECT document_json FROM gen_plan_documents WHERE plan_id = ?", (result["plan_id"],)
        ).fetchone()
        stored = json.loads(row["document_json"])["plan"]
        self.assertEqual(stored["objectives"][0]["target_items"], ["水", "これ"])

    def test_a_missing_inventory_is_typed_and_invents_nothing(self) -> None:
        brief = brief_with(load())
        brief.pop("frequency_inventory")
        result = self.run_plan(japanese_plan(), brief)
        vocabulary = result["vocabulary"]
        self.assertEqual(vocabulary["status"], "unverified")
        self.assertEqual(vocabulary["reason"], frequency.WARNING_UNAVAILABLE)
        self.assertEqual(vocabulary["items"], [])
        self.assertIsNone(vocabulary["content_hash"])
        self.assertTrue(
            any(warning.startswith(frequency.WARNING_UNAVAILABLE) for warning in result["warnings"]),
            result["warnings"],
        )
        row = self.connection.execute(
            "SELECT document_json FROM gen_plan_documents WHERE plan_id = ?", (result["plan_id"],)
        ).fetchone()
        stored = json.loads(row["document_json"])["plan"]
        self.assertTrue(all("target_items" not in obj for obj in stored["objectives"]))

    def test_a_declared_but_missing_file_is_unavailable_not_fabricated(self) -> None:
        brief = brief_with(load())
        brief["frequency_inventory"] = {"path": "/nonexistent/h89-inventory.json", "band": "band-core"}
        result = self.run_plan(japanese_plan(), brief)
        self.assertEqual(result["vocabulary"]["status"], "unverified")
        self.assertEqual(result["vocabulary"]["reason"], frequency.WARNING_UNAVAILABLE)
        self.assertIn("missing", result["vocabulary"]["detail"])

    def test_a_spanish_course_uses_the_same_seam(self) -> None:
        plan = blueprint_plan(scope="short", units=1, objectives_per_unit=4, recipe="committed")
        plan["objectives"][0]["target_items"] = ["agua", "comer"]
        plan["objectives"][1]["target_items"] = ["casa"]
        brief = {
            "goal": "Order at a cafe in Spanish",
            "recipe": "committed",
            "dials": {"depth": "working"},
            "locale": "es-MX",
            "level": "L0",
            "subject_domain": "language",
            "scope": "short",
            "frequency_inventory": {"document": load("es-core-v1.json"), "band": "band-core"},
        }
        result = self.run_plan(plan, brief)
        vocabulary = result["vocabulary"]
        self.assertEqual(vocabulary["status"], "inventory")
        self.assertEqual(vocabulary["source_id"], "coursebook-fixture-es-v1")
        self.assertEqual(
            [(item["rank"], item["lemma"]) for item in vocabulary["items"]],
            [(1, "agua"), (2, "comer"), (3, "casa")],
        )

    def test_an_out_of_band_plan_is_parked_with_the_reason(self) -> None:
        plan = japanese_plan({1: ["水", "新幹線"]})
        result = self.run_plan(plan, brief_with(load()))
        self.assertEqual(result["status"], "needs_review")
        joined = " ".join(result.get("rejection_reasons") or [])
        self.assertIn("not the declared band", joined)

    def test_a_skipped_rank_is_parked_with_the_reason(self) -> None:
        plan = japanese_plan({1: ["水", "私"]})
        result = self.run_plan(plan, brief_with(load()))
        self.assertEqual(result["status"], "needs_review")
        joined = " ".join(result.get("rejection_reasons") or [])
        self.assertIn("prefix", joined)

    def test_a_legacy_v1_plan_uses_the_same_vocabulary_seam(self) -> None:
        def builder(request):
            document = plan_fixture("plan_ja", source_ids_from(request))
            document["objectives"][0]["target_items"] = ["水", "これ"]
            document["objectives"][1]["target_items"] = ["食べる"]
            return support_response(document)

        brief = brief_with(load())
        brief.pop("scope")  # no scope => the pre-blueprint v1 schema
        llm = FakeLLM(
            {
                "coursebook.plan.generate": builder,
                "coursebook.plan.validate": validation_from_fixture(),
            }
        )
        result = gen.run_plan_job(self.connection, plan_job(brief), llm, FakeSearch(), now=NOW)
        self.assertEqual(result["status"], "draft")
        self.assertEqual(
            [(item["rank"], item["lemma"]) for item in result["vocabulary"]["items"]],
            [(3, "水"), (4, "これ"), (5, "食べる")],
        )

    def test_a_non_language_course_is_not_applicable(self) -> None:
        plan = blueprint_plan(scope="single", units=1, objectives_per_unit=1, recipe="one_off")
        brief = {
            "goal": "Replace bicycle brake pads",
            "recipe": "one_off",
            "dials": {"depth": "survey"},
            "locale": None,
            "subject_domain": "technical_procedure",
            "scope": "single",
        }
        result = self.run_plan(plan, brief)
        self.assertEqual(result["vocabulary"]["status"], "not_applicable")
        self.assertEqual(result["vocabulary"]["items"], [])


if __name__ == "__main__":
    unittest.main()
