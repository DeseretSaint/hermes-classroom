"""H-40: the harness produces a non-Japanese course from a free-form goal on the shipped path.

This is the re-run of H-09's acceptance test after blueprint v2: a goal enters the real product
path, the pipeline researches, plans, is independently validated, is approved, authors unit
sections and lessons, serves a page and grades an attempt — with nothing from the Japanese pack
involved and no provider called.

The model is a recorded transcript (``audit/adversarial/harness-e2e/transcripts``) replayed through
the real pipeline; the test asserts that label too.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coursebook import generation
from coursebook import text_completeness

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


PACKET = ROOT / "audit" / "adversarial" / "harness-e2e"
MANIFEST = PACKET / "manifest.json"
SCOPES = {"bicycle_single": "single", "music_short": "short", "soldering_full": "full"}


def _committed_plan(name: str) -> dict:
    return json.loads((EVIDENCE / f"{name}.json").read_text(encoding="utf-8"))["plan_document"]


class ScopeBoundsContractTest(unittest.TestCase):
    """D6: the scope bound must be checked against the declared contract, and must be able to fail.

    The question this answers is not "did the generator obey its own table" (that cannot fail) but
    "does the plan this run produced sit inside the band the RPC contract, the plan schema and the
    declared per-scope expectation publish". A deliberately out-of-band plan must be refused by the
    same function the harness asserts on.
    """

    def test_the_three_committed_plans_match_the_declared_bounds(self) -> None:
        for name, scope in SCOPES.items():
            with self.subTest(name=name):
                plan = _committed_plan(name)
                self.assertTrue(
                    harness_e2e.scope_matches_documented_bounds(scope, plan),
                    harness_e2e.scope_bound_violations(scope, plan),
                )

    def test_the_contract_schema_and_expectations_agree(self) -> None:
        declared = harness_e2e.declared_scope_bounds()
        self.assertEqual(declared["problems"], [])
        self.assertEqual(tuple(declared["contract_scopes"]), ("single", "short", "full"))
        self.assertEqual(declared["schema_objectives"], (1, 40))
        self.assertEqual(declared["schema_units"], (1, 12))
        self.assertEqual(declared["expectations"]["full"]["objectives"], (9, 40))
        self.assertEqual(declared["expectations"]["single"]["objectives"], (1, 1))

    def test_an_out_of_band_full_plan_fails_the_assertion(self) -> None:
        """The historical D6 shape defect: a six-objective plan labelled `full`."""
        plan = copy.deepcopy(_committed_plan("soldering_full"))
        plan["objectives"] = plan["objectives"][:6]
        plan["check_plan"] = plan["check_plan"][:6]
        self.assertEqual(plan["scope"], "full")
        violations = harness_e2e.scope_bound_violations("full", plan)
        self.assertTrue(violations, "a 6-objective `full` plan was accepted as in band")
        self.assertFalse(harness_e2e.scope_matches_documented_bounds("full", plan))
        self.assertTrue(any("objective" in reason for reason in violations), violations)

    def test_a_padded_single_plan_fails_the_assertion(self) -> None:
        """The other historical defect: one-off padded to four objectives (D1's shape)."""
        plan = copy.deepcopy(_committed_plan("bicycle_single"))
        template = plan["objectives"][0]
        plan["objectives"] = [
            {**template, "ordinal": ordinal,
             "title": f"{template['title']} ({ordinal})",
             "evidence_criteria": [criterion
                                   for criterion in template.get("evidence_criteria") or []]
             + [f"restated point {ordinal}"]}
            for ordinal in (1, 2, 3, 4)
        ]
        plan["check_plan"] = [
            {**plan["check_plan"][0], "objective_ref": ordinal}
            for ordinal in (1, 2, 3, 4)
        ]
        self.assertEqual(plan["scope"], "single")
        self.assertFalse(harness_e2e.scope_matches_documented_bounds("single", plan))
        self.assertTrue(harness_e2e.scope_bound_violations("single", plan))

    def test_the_declared_ceiling_passes_and_one_past_it_does_not(self) -> None:
        base = _committed_plan("soldering_full")

        def sized(objectives: int) -> dict:
            plan = copy.deepcopy(base)
            template = plan["objectives"][0]
            plan["objectives"] = [
                {**template, "ordinal": ordinal}
                for ordinal in range(1, objectives + 1)
            ]
            plan["check_plan"] = [
                {**plan["check_plan"][0], "objective_ref": ordinal}
                for ordinal in range(1, objectives + 1)
            ]
            return plan

        self.assertTrue(harness_e2e.scope_matches_documented_bounds("full", sized(40)))
        self.assertFalse(harness_e2e.scope_matches_documented_bounds("full", sized(41)))
        # A plan that contradicts the brief's scope is out of band too.
        self.assertFalse(harness_e2e.scope_matches_documented_bounds("full", sized(6)))


class PacketManifestTest(unittest.TestCase):
    """D7: the packet is content-addressed, byte-reproducible, and tamper-evident."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.homes = []
        cls.fresh = {}
        for name in NAMES:
            home = Path(tempfile.mkdtemp(prefix=f"coursebook-h45-{name}-")) / "home"
            home.mkdir(parents=True)
            cls.homes.append(home.parent)
            cls.fresh[name] = run_scenario(name, home=home)
        home = Path(tempfile.mkdtemp(prefix="coursebook-h45-ceiling-")) / "home"
        home.mkdir(parents=True)
        cls.homes.append(home.parent)
        cls.fresh["soldering_full"]["ceiling_probe"] = run_ceiling_probe(home)
        evidence = cls.fresh["soldering_full"]
        evidence["assertions"] = harness_e2e._assert_scenario(
            "soldering_full", evidence["scenario"], evidence
        )
        evidence["verdict"] = "PASS" if all(evidence["assertions"].values()) else "FAIL"
        home = Path(tempfile.mkdtemp(prefix="coursebook-h45-partial-")) / "home"
        home.mkdir(parents=True)
        cls.homes.append(home.parent)
        cls.fresh["partial"] = harness_e2e.run_partial_unit_probe(home)

    @classmethod
    def tearDownClass(cls) -> None:
        for path in cls.homes:
            shutil.rmtree(path, ignore_errors=True)

    def test_the_manifest_covers_every_evidence_file_and_input(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIn("evidence", manifest)
        self.assertIn("inputs", manifest)
        for path in sorted(EVIDENCE.iterdir()):
            self.assertIn(path.name, manifest["evidence"], f"{path.name} is not in the manifest")
            self.assertRegex(manifest["evidence"][path.name]["sha256"], r"^[0-9a-f]{64}$")
        for name, scope in SCOPES.items():
            entry = manifest["inputs"][name]
            self.assertEqual(entry["scope"], scope)
            self.assertRegex(entry["transcript_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(entry["brief_sha256"], r"^[0-9a-f]{64}$")
            self.assertIn("recorded-transcript-h40", entry["model_transcript_id"])
            self.assertIn("recorded-validator-h40", entry["validator_transcript_id"])

    def test_the_committed_packet_verifies_clean(self) -> None:
        self.assertEqual(harness_e2e.verify_packet(), [])

    def test_fresh_evidence_reproduces_the_committed_bytes(self) -> None:
        for name, evidence in self.fresh.items():
            if name == "partial":
                continue
            with self.subTest(name=name):
                fresh = (harness_e2e._json_dump(evidence) + "\n").encode("utf-8")
                committed = (EVIDENCE / f"{name}.json").read_bytes()
                self.assertEqual(
                    harness_e2e.sha256_bytes(fresh), harness_e2e.sha256_bytes(committed),
                    f"{name}: a re-run is not byte-identical to the committed packet",
                )
        fresh_partial = (harness_e2e._json_dump(self.fresh["partial"]) + "\n").encode("utf-8")
        self.assertEqual(
            harness_e2e.sha256_bytes(fresh_partial),
            harness_e2e.sha256_bytes((EVIDENCE / "partial_unit_batch.json").read_bytes()),
        )

    def test_a_changed_transcript_reads_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "packet"
            shutil.copytree(PACKET, root)
            target = root / "transcripts" / "music_short.json"
            original = target.read_text(encoding="utf-8")
            target.write_text(original.replace("circle of fifths", "circle of fifths ", 1),
                              encoding="utf-8")
            problems = harness_e2e.verify_packet(root)
            self.assertTrue(problems, "a changed transcript was accepted as fresh")
            self.assertTrue(any("music_short" in problem for problem in problems), problems)

    def test_a_changed_evidence_file_reads_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "packet"
            shutil.copytree(PACKET, root)
            target = root / "evidence" / "bicycle_single.json"
            original = target.read_text(encoding="utf-8")
            target.write_text(original + "\n", encoding="utf-8")
            problems = harness_e2e.verify_packet(root)
            self.assertTrue(problems, "a changed evidence file was accepted as fresh")
            self.assertTrue(any("bicycle_single" in problem for problem in problems), problems)


class ShortCompletenessTest(unittest.TestCase):
    """H-46b: the harness's authored shorts are whole sentences, never 2/3 word prefixes.

    H-46 refuses a short that stops mid-sentence, and the H-40 harness synthesised exactly that
    shape (D8's recorded ``"... lift the wheel out"``). These assertions pin the authoring contract
    without a pipeline run, so the fixture cannot silently drift back to the rejected shape.
    """

    def _recorded_pairs(self):
        for path in sorted(harness_e2e.TRANSCRIPTS.glob("*.json")):
            transcript = json.loads(path.read_text(encoding="utf-8"))
            for title, lesson in transcript["lessons"].items():
                for field in ("practice", "criterion", "explanation"):
                    yield (
                        f"{path.stem}:{title}:{field}",
                        str(lesson[field]),
                        str(lesson[f"{field}_short"]),
                    )
                deep = f"The step is done and checked. {lesson['criterion']}"
                yield (
                    f"{path.stem}:{title}:worked_example",
                    deep,
                    harness_e2e._shorten(deep),
                )

    def test_every_authored_short_is_a_complete_sentence(self) -> None:
        seen = 0
        for label, deep, short in self._recorded_pairs():
            with self.subTest(label=label, short=short):
                self.assertLess(len(short), len(deep), f"{label}: the short omits nothing")
                self.assertEqual(
                    text_completeness.completeness_problems(short, where="short"), [],
                    f"{label}: the authored short is not a finished text",
                )
                self.assertEqual(
                    generation._short_problems([{"short": short, "deep": deep}]), [],
                    f"{label}: the authored short breaks the omission-only contract",
                )
                seen += 1
        self.assertGreaterEqual(seen, 30, "the recordings did not supply the lesson text")

    def test_every_lesson_carries_an_authored_short(self) -> None:
        for path in sorted(harness_e2e.TRANSCRIPTS.glob("*.json")):
            transcript = json.loads(path.read_text(encoding="utf-8"))
            for title, lesson in transcript["lessons"].items():
                for field in ("practice", "criterion", "explanation"):
                    self.assertTrue(
                        str(lesson.get(f"{field}_short") or "").strip(),
                        f"{path.stem}: {title}: {field}_short is missing",
                    )

    def test_the_fallback_synthesiser_is_still_gate_clean(self) -> None:
        """``_shorten`` remains a fallback; any text it compresses must still be admissible."""
        for path in sorted(harness_e2e.TRANSCRIPTS.glob("*.json")):
            transcript = json.loads(path.read_text(encoding="utf-8"))
            for title, lesson in transcript["lessons"].items():
                for field in ("practice", "criterion", "explanation"):
                    deep = str(lesson[field])
                    short = harness_e2e._shorten(deep)
                    with self.subTest(label=f"{path.stem}:{title}:{field}", short=short):
                        self.assertLess(len(short), len(deep))
                        self.assertEqual(
                            text_completeness.completeness_problems(short, where="short"), []
                        )
                        self.assertEqual(
                            generation._short_problems([{"short": short, "deep": deep}]), []
                        )

    def test_a_multi_sentence_body_keeps_its_first_complete_sentence(self) -> None:
        deep = "The step is done and checked. Seat the new tube by hand, inflate in small steps."
        self.assertEqual(harness_e2e._shorten(deep), "The step is done and checked.")

    def test_the_recorded_d8_clip_is_no_longer_synthesised(self) -> None:
        deep = (
            "Deflate the tyre fully, open the brake quick-release, and lift the wheel out of the "
            "dropouts without levering the bead."
        )
        words = deep.split()
        clipped = " ".join(words[: max(2, (len(words) * 2) // 3)])
        short = harness_e2e._shorten(deep)
        self.assertNotEqual(short, clipped, "the 2/3 word prefix D8 recorded is back")
        self.assertTrue(short.endswith("."), short)
        self.assertEqual(text_completeness.completeness_problems(short, where="short"), [])


if __name__ == "__main__":
    unittest.main()
