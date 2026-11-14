"""UP-19: the pronunciation attempt reports word recognition, not pronunciation.

The card's failure, observed at HEAD (``coursebook/pronunciation.py:508`` and ``:520``): the
assessment diffs the recogniser's words against the target and calls the ratio an accuracy, leaves
``phoneme_accuracy`` at null, and returns ``meets_target`` to any take whose words came back. A
learner who says the right words in a way the recogniser is barely sure of reads as a pass, and a
learner whose accent the recogniser mangles reads as ``needs_practice`` — and neither result says
which of those happened, because the payload never states what it measured.

This module proves the fix against the real dispatcher and a real migrated profile:

* the assessment is labelled with what it compared (``measure = word_recognition``), carries the
  backend's own caveat in words, and says ``phoneme_accuracy`` is null because no phoneme was
  measured;
* every word row carries the recogniser's own confidence, a missed word included, so a misheard
  accent is readable apart from a word the learner did not say;
* the strongest verdict is gated on the weakest matched word: under
  ``pronunciation.MIN_WORD_CONFIDENCE`` — or with no per-word confidence at all — ``meets_target``
  is refused and the verdict is held at ``close`` with ``gated`` true;
* an unassessed take claims no measure and no caveat rather than an empty promise.

The named acceptance test is
``test_the_assessment_reports_word_recognition_not_pronunciation``. It fails at HEAD: the payload
has no ``measure``, no ``caveat`` at all, an empty word confidence on a miss, and reports
``meets_target`` for a take the recogniser was 28% confident of.
"""

from __future__ import annotations

import json
import unittest

from coursebook import pronunciation, stt
from tests.kernel_support import KernelCase
from tests.test_pronunciation import FakeStt, data_url, wav_bytes


class PronunciationRecognitionTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.prepare_lesson()
        self.fake = FakeStt()
        stt.configure(self.fake)

    def tearDown(self) -> None:
        stt.reset_adapter()
        super().tearDown()

    def attempt(self, *, key: str, nonce: str = "nonce-up19", target: str = "good morning") -> dict:
        return self.dispatch(
            "pronunciation.attempt",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": self.lesson["objective_id"],
                "attempt_nonce": nonce,
                "target": target,
                "locale": "en-US",
                "audio_data_url": data_url(wav_bytes()),
            },
            expected_revision=self.lesson["revision"],
            idempotency_key=key,
        )

    def low_confidence_take(self, **kwargs) -> dict:
        """The right words, heard badly: every word matches, every confidence under the floor."""
        self.fake.text = "good morning"
        self.fake.confidence = 0.44
        self.fake.words = [
            {"word": "good", "probability": 0.33},
            {"word": "morning", "probability": 0.28},
        ]
        return self.attempt(**kwargs)

    # ── the named acceptance test ────────────────────────────────────────

    def test_the_assessment_reports_word_recognition_not_pronunciation(self) -> None:
        response = self.low_confidence_take(key="key-up19-low")
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        self.assertEqual(result["status"], "assessed")
        self.assertTrue(result["recorded"])
        assessment = result["assessment"]

        # What was measured, in the payload's own words — not a pronunciation claim.
        self.assertEqual(assessment["measure"], "word_recognition")
        self.assertIsInstance(assessment["caveat"], str)
        self.assertIn("recogniser", assessment["caveat"])
        self.assertIn("pronunciation", assessment["caveat"])
        self.assertIn("no phoneme", assessment["caveat"].lower())
        self.assertIsNone(
            assessment["phoneme_accuracy"],
            "no phoneme was measured, so no phoneme accuracy exists",
        )

        # The comparison itself is unchanged: the words did match.
        self.assertEqual(assessment["word_accuracy"], 1.0)
        self.assertTrue(all(word["match"] for word in assessment["words"]))

        # Every word carries the recogniser's own confidence, and the gate refused the pass.
        self.assertEqual([word["confidence"] for word in assessment["words"]], [0.33, 0.28])
        self.assertEqual(assessment["min_word_confidence"], 0.28)
        self.assertTrue(assessment["gated"])
        self.assertEqual(assessment["verdict"], "close")
        self.assertNotEqual(assessment["verdict"], "meets_target")
        self.assertIn("low confidence", assessment["caveat"])

        # The stored row cannot grow a stronger claim than the response made.
        row = self.rows("SELECT * FROM pronunciation_attempts")[0]
        self.assertEqual(row["verdict"], "close")
        stored = json.loads(row["assessment_json"])
        self.assertEqual(stored["measure"], "word_recognition")
        self.assertTrue(stored["gated"])
        self.assertEqual(stored["caveat"], assessment["caveat"])

    # ── the missed word, and the gate's two edges ────────────────────────

    def test_a_missed_word_reports_the_confidence_of_what_was_heard(self) -> None:
        self.fake.text = "good evening"
        self.fake.words = [
            {"word": "good", "probability": 0.88},
            {"word": "evening", "probability": 0.71},
        ]
        assessment = self.attempt(key="key-up19-miss")["result"]["assessment"]
        lines = {word["expected"]: word for word in assessment["words"]}
        self.assertFalse(lines["morning"]["match"])
        self.assertEqual(lines["morning"]["heard"], "evening")
        # The recogniser was 71% sure of the word it did hear: that is the fact a learner needs to
        # tell an accent it misheard from a word it never said.
        self.assertEqual(lines["morning"]["confidence"], 0.71)
        self.assertEqual(lines["good"]["confidence"], 0.88)
        self.assertEqual(assessment["verdict"], "needs_practice")
        self.assertFalse(assessment["gated"], "a miss is a miss, not a gated pass")
        self.assertEqual(assessment["caveat"], pronunciation.RECOGNISER_CAVEAT)

    def test_a_confident_take_still_meets_the_target(self) -> None:
        assessment = self.attempt(key="key-up19-clear")["result"]["assessment"]
        self.assertEqual(assessment["verdict"], "meets_target")
        self.assertFalse(assessment["gated"])
        self.assertEqual(assessment["min_word_confidence"], 0.92)
        self.assertEqual(assessment["caveat"], pronunciation.RECOGNISER_CAVEAT)

    def test_a_take_with_no_per_word_confidence_cannot_claim_the_target(self) -> None:
        # A recogniser that returns a transcript but no word probabilities leaves nothing to gate
        # on: the strongest verdict is withheld rather than assumed.
        self.fake.text = "good morning"
        self.fake.words = []
        assessment = self.attempt(key="key-up19-unrated")["result"]["assessment"]
        self.assertEqual(assessment["word_accuracy"], 1.0)
        self.assertIsNone(assessment["min_word_confidence"])
        self.assertTrue(assessment["gated"])
        self.assertEqual(assessment["verdict"], "close")
        self.assertEqual(assessment["caveat"], pronunciation.UNRATED_CONFIDENCE_CAVEAT)

    def test_an_unassessed_take_claims_no_measure_and_no_caveat(self) -> None:
        self.fake.fail = "model_unavailable"
        result = self.attempt(key="key-up19-none")["result"]
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["recorded"])
        assessment = result["assessment"]
        self.assertEqual(assessment["measure"], "none")
        self.assertIsNone(assessment["caveat"])
        self.assertFalse(assessment["gated"])
        self.assertIsNone(assessment["min_word_confidence"])
        self.assertIsNone(assessment["phoneme_accuracy"])
        self.assertEqual(assessment["verdict"], "unavailable")
        self.assertEqual(self.rows("SELECT * FROM pronunciation_attempts"), [])

    def test_a_replayed_attempt_keeps_the_label_it_was_stored_with(self) -> None:
        first = self.attempt(key="key-up19-replay")["result"]
        replay = self.attempt(key="key-up19-replay")["result"]
        self.assertEqual(replay, first)
        self.assertEqual(replay["assessment"]["measure"], "word_recognition")
        self.assertIn("recogniser", replay["assessment"]["caveat"])


class StoredAssessmentLabelTest(unittest.TestCase):
    """A row written before the label existed is replayed with the label its fields support."""

    def test_an_old_stored_assessment_gains_the_label_and_keeps_its_numbers(self) -> None:
        old = {
            "transcript": "good morning",
            "target": "good morning",
            "locale": "en-US",
            "provider": "coursebook_local_whisper",
            "model": "base",
            "language": "en",
            "unit": "word",
            "word_accuracy": 1.0,
            "phoneme_accuracy": None,
            "confidence": 0.93,
            "words": [
                {"expected": "good", "heard": "good", "match": True, "confidence": 0.94},
                {"expected": "morning", "heard": "morning", "match": True, "confidence": 0.92},
            ],
            "verdict": "meets_target",
            "evidence_class": "model_assessed",
        }
        labelled = pronunciation.labelled_assessment(old)
        self.assertEqual(labelled["measure"], "word_recognition")
        self.assertEqual(labelled["caveat"], pronunciation.RECOGNISER_CAVEAT)
        self.assertFalse(labelled["gated"])
        self.assertIsNone(labelled["min_word_confidence"])
        self.assertEqual(labelled["word_accuracy"], 1.0)
        self.assertEqual(labelled["verdict"], "meets_target")
        self.assertNotIn("measure", old, "the stored row itself is never rewritten in place")

    def test_an_old_unassessed_record_gains_no_caveat(self) -> None:
        labelled = pronunciation.labelled_assessment(
            {"transcript": None, "word_accuracy": None, "phoneme_accuracy": None,
             "verdict": "unavailable", "evidence_class": "model_assessed"}
        )
        self.assertEqual(labelled["measure"], "none")
        self.assertIsNone(labelled["caveat"])
        self.assertFalse(labelled["gated"])


class CaveatCopyTest(unittest.TestCase):
    def test_every_caveat_fits_the_contract_and_never_claims_a_phoneme(self) -> None:
        for caveat in (
            pronunciation.RECOGNISER_CAVEAT,
            pronunciation.LOW_CONFIDENCE_CAVEAT,
            pronunciation.UNRATED_CONFIDENCE_CAVEAT,
        ):
            self.assertLessEqual(len(caveat), 400)
            self.assertIn("recogniser", caveat)
            self.assertIn("pronunciation", caveat)
            self.assertNotIn("you pronounced", caveat)

    def test_the_gate_floor_is_a_real_recogniser_probability(self) -> None:
        self.assertGreater(pronunciation.MIN_WORD_CONFIDENCE, 0)
        self.assertLess(pronunciation.MIN_WORD_CONFIDENCE, pronunciation.MEETS_TARGET)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
