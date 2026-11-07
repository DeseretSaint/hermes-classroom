"""H-40: the harness produces a non-Japanese course from a free-form goal on the shipped path.

This is the re-run of H-09's acceptance test after blueprint v2: a goal enters the real product
path, the pipeline researches, plans, is independently validated, is approved, authors unit
sections and lessons, serves a page and grades an attempt — with nothing from the Japanese pack
involved and no provider called.

The model is a recorded transcript (``audit/adversarial/harness-e2e/transcripts``) replayed through
the real pipeline; the test asserts that label too.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "audit" / "adversarial" / "harness-e2e" / "harness_e2e.py"
_spec = importlib.util.spec_from_file_location("harness_e2e_h40", RUNNER)
assert _spec and _spec.loader
harness_e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness_e2e)
run_scenario = harness_e2e.run_scenario
run_ceiling_probe = harness_e2e.run_ceiling_probe

EVIDENCE = ROOT / "audit" / "adversarial" / "harness-e2e" / "evidence"
NAMES = ("bicycle_single", "music_short", "soldering_full")


class HarnessEndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.results = {}
        cls.homes = []
        for name in NAMES:
            home = Path(tempfile.mkdtemp(prefix=f"coursebook-h40-{name}-")) / "home"
            home.mkdir(parents=True)
            cls.homes.append(home.parent)
            cls.results[name] = run_scenario(name, home=home)
        home = Path(tempfile.mkdtemp(prefix="coursebook-h40-ceiling-")) / "home"
        home.mkdir(parents=True)
        cls.homes.append(home.parent)
        cls.ceiling = run_ceiling_probe(home)
        evidence = cls.results["soldering_full"]
        evidence["ceiling_probe"] = cls.ceiling
        evidence["assertions"] = harness_e2e._assert_scenario(
            "soldering_full", evidence["scenario"], evidence
        )
        evidence["verdict"] = "PASS" if all(evidence["assertions"].values()) else "FAIL"

    @classmethod
    def tearDownClass(cls) -> None:
        for path in cls.homes:
            shutil.rmtree(path, ignore_errors=True)

    def test_every_scenario_passes_its_own_assertions(self) -> None:
        for name, evidence in self.results.items():
            self.assertEqual(evidence["verdict"], "PASS", (name, evidence["assertions"]))
            for check, value in evidence["assertions"].items():
                self.assertTrue(value, f"{name}: {check}")

    def test_the_three_scopes_are_the_ones_the_card_named(self) -> None:
        scopes = {name: evidence["scenario"]["scope"] for name, evidence in self.results.items()}
        self.assertEqual(
            scopes, {"bicycle_single": "single", "music_short": "short",
                     "soldering_full": "full"}
        )

    def test_single_is_exactly_one_unit_and_one_verification(self) -> None:
        evidence = self.results["bicycle_single"]
        self.assertEqual(evidence["observations"]["units"], 1)
        self.assertEqual(evidence["observations"]["objectives"], 1)
        self.assertEqual(evidence["observations"]["checks"], 1)
        self.assertEqual(evidence["steps"]["grading"][0]["submit"]["result"]["verdict"], "pass")
        self.assertEqual(
            evidence["steps"]["grading"][0]["submit"]["result"]["evidence_class"], "self_reported"
        )

    def test_short_grades_correct_and_wrong_on_the_exact_lane(self) -> None:
        evidence = self.results["music_short"]
        lanes = evidence["observations"]["check_lanes"]
        self.assertTrue(lanes)
        self.assertTrue(all(lane["reference_kind"] == "exact" for lane in lanes))
        rows = {row["label"]: row["submit"]["result"] for row in evidence["steps"]["grading"]}
        self.assertEqual(rows["correct"]["verdict"], "pass")
        self.assertEqual(rows["wrong"]["verdict"], "not_yet")

    def test_full_declares_prerequisites_and_honours_the_plan_bound(self) -> None:
        evidence = self.results["soldering_full"]
        units = evidence["observations"]["outline_units"]
        self.assertGreaterEqual(len(units), 2)
        self.assertTrue(any(unit["prereq_unit_ordinals"] for unit in units))
        self.assertTrue(self.ceiling["at_bound"]["accepted"], self.ceiling["at_bound"])
        self.assertTrue(self.ceiling["over_bound"]["rejected"], self.ceiling["over_bound"])

    def test_units_are_user_enqueued_not_executor_chained(self) -> None:
        for name, evidence in self.results.items():
            for stage in evidence["steps"]["unit_stages"] + evidence["steps"]["lesson_stages"]:
                self.assertFalse(stage["chained_a_job"], name)

    def test_approval_is_fail_closed_and_happens_after_validation(self) -> None:
        for name, evidence in self.results.items():
            self.assertEqual(evidence["observations"]["validation_verdict"], "pass", name)
            self.assertEqual(evidence["observations"]["plan_state_after_approval"], "approved", name)
            refusals = evidence["steps"]["approval_refusals"]
            self.assertEqual(len(refusals), 2, name)
            for refusal in refusals:
                self.assertFalse(refusal["ok"], (name, refusal))
                self.assertEqual(refusal["state_after"], "draft", name)

    def test_every_scenario_was_generated_from_a_non_japanese_goal(self) -> None:
        for name, evidence in self.results.items():
            self.assertTrue(evidence["assertions"]["no_japanese_content_in_plan"], name)
            self.assertTrue(evidence["assertions"]["no_japanese_content_in_lessons"], name)
            self.assertNotIn("ja", (evidence["scenario"]["locale"] or "").lower(), name)

    def test_the_served_lesson_never_announces_the_answer_key(self) -> None:
        for name, evidence in self.results.items():
            self.assertTrue(evidence["assertions"]["no_answer_key_in_served_lesson"], name)

    def test_the_run_is_labelled_as_a_recorded_transcript(self) -> None:
        for evidence in self.results.values():
            self.assertEqual(evidence["labels"]["provider_calls"], 0)
            self.assertIn("RECORDED", evidence["labels"]["model"])
            self.assertIn("RECORDED", evidence["labels"]["validator"])

    def test_the_checked_in_evidence_packet_is_current(self) -> None:
        """The committed JSON must describe the same verdict this run produced."""
        for name, evidence in self.results.items():
            committed = json.loads((EVIDENCE / f"{name}.json").read_text(encoding="utf-8"))
            self.assertEqual(committed["verdict"], "PASS", name)
            self.assertEqual(committed["assertions"], evidence["assertions"], name)
            self.assertEqual(committed["scenario"], evidence["scenario"], name)
        committed_probe = json.loads(
            (EVIDENCE / "soldering_full.json").read_text(encoding="utf-8")
        )["ceiling_probe"]
        self.assertEqual(committed_probe["at_bound"]["accepted"], True)
        self.assertEqual(committed_probe["over_bound"]["rejected"], True)


if __name__ == "__main__":
    unittest.main()
