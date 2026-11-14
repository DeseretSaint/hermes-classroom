"""Upgrade 13: a miss names the rule, and the teaching turn is told what failed.

At HEAD a ``not_yet`` carried one deterministic grader sentence (``does not match an accepted
answer``, ``outside tolerance by 0.5``) and the continuation prompt carried the verdict, the next
action, the evidence class and an objective id — never the rule the check tests. So the pane could
print no reason and the tutor could not say what to do differently.

After this change a check may author the rule (and a rule per accepted-answer group) on its stored
reference; a non-pass returns a ``feedback`` block naming that rule, the learner's own answer and
one next action; ``attempt.submit`` carries it to the pane, a replay rebuilds it from the stored
attempt, and ``pre_turn`` puts it in the teaching turn's context.

The rules the block must not break, each pinned here:

* the authored rule may not restate an accepted answer (the leak that turns a retry into a copy
  task), enforced at seal time;
* a miss can never name ``complete_objective``: a wrong answer does not grant access;
* no pipeline word (``criteria``, criterion ids) reaches the chat context.
"""

from __future__ import annotations

import unittest

from coursebook import generation, grading, turn, validators
from tests.kernel_support import KernelCase, numeric_spec
from tests.test_turn import _STORED, GateCase

#: One authored rule a learner can act on. Deliberately contains neither the reference value nor
#: the learner's answer.
_RULE = "Read the scale to one decimal place before you compare the two readings."
_NEXT = "retry_attempt"


def ruled_numeric_spec(value: str = "42.7", *, rule: str = _RULE, next_action: str = _NEXT,
                       groups: list[dict] | None = None) -> dict:
    spec = numeric_spec(value)
    feedback: dict = {"rule": rule, "next_action": next_action}
    if groups is not None:
        feedback["groups"] = groups
    spec["reference"]["feedback"] = feedback
    return spec


class MissFeedbackResultTest(unittest.TestCase):
    """The graded result itself, with no database in the way."""

    def grade(self, reference: dict, text: str) -> grading.GradingResult:
        return grading.grade_closed(
            reference=validators.seal_reference(reference),
            rubric={"pass_rule": "all"},
            answer={"kind": "text", "text": text},
        )

    def test_a_not_yet_grading_result_carries_the_authored_rule(self) -> None:
        reference = ruled_numeric_spec()["reference"]
        graded = self.grade(reference, "41.2")
        self.assertEqual(graded.verdict, "not_yet")
        # Before: the only thing returned was the deterministic grader sentence.
        self.assertEqual(graded.criteria[0]["observed"], "outside tolerance by 1.5")
        self.assertEqual(graded.feedback["rule"], _RULE)
        self.assertEqual(graded.feedback["next_action"], _NEXT)
        self.assertEqual(graded.feedback["answer"], "41.2")
        self.assertEqual(graded.feedback["observed"], "outside tolerance by 1.5")

    def test_a_pass_carries_no_miss_feedback(self) -> None:
        graded = self.grade(ruled_numeric_spec()["reference"], "42.7")
        self.assertEqual(graded.verdict, "pass")
        self.assertIsNone(graded.feedback)

    def test_a_selection_miss_names_the_rule_of_the_group_it_was_closest_to(self) -> None:
        reference = validators.seal_reference({
            "kind": "selection",
            "answers": [["a", "b"], ["c", "d"]],
            "feedback": {
                "rule": "Name the two steps this check asks for, in either order.",
                "groups": [
                    {"answers": ["a", "b"], "rule": "Both steps belong to the warm-up, not the braise."},
                    {"answers": ["c", "d"], "rule": "The resting step comes after the braise, not before it."},
                ],
            },
        })
        graded = grading.grade_closed(
            reference=reference,
            rubric={"pass_rule": "all"},
            answer={"kind": "selection", "selection": ["c"]},
        )
        self.assertEqual(graded.verdict, "not_yet")
        self.assertEqual(graded.feedback["rule"], "The resting step comes after the braise, not before it.")

    def test_a_reference_without_an_authored_rule_returns_no_block(self) -> None:
        graded = self.grade(numeric_spec("42.7")["reference"], "41.2")
        self.assertEqual(graded.verdict, "not_yet")
        self.assertIsNone(graded.feedback)


class MissFeedbackAuthoringTest(unittest.TestCase):
    """The seal is where an authoring mistake is refused, not the pane."""

    def test_a_check_authors_the_rule_into_its_stored_reference(self) -> None:
        reference = generation._reference_payload({
            "kind": "quiz",
            "stimulus": {"prompt": "Read the gauge.", "format": "text"},
            "reference_answer": "42.7",
            "accepted_answers": ["42.7"],
            "accepted_alternatives": [],
            "feedback": {"rule": _RULE, "next_action": "explain"},
        })
        self.assertEqual(reference["feedback"]["rule"], _RULE)
        self.assertEqual(reference["feedback"]["next_action"], "explain")
        graded = grading.grade_closed(
            reference=reference, rubric={"pass_rule": "all"},
            answer={"kind": "text", "text": "41.2"},
        )
        self.assertEqual(graded.feedback["rule"], _RULE)

    def test_a_leaky_rule_is_dropped_rather_than_shipped(self) -> None:
        reference = generation._reference_payload({
            "kind": "quiz",
            "stimulus": {"prompt": "Read the gauge.", "format": "text"},
            "reference_answer": "42.7",
            "accepted_answers": ["42.7"],
            "accepted_alternatives": [],
            "feedback": {"rule": "Write 42.7, to one decimal place."},
        })
        self.assertNotIn("feedback", reference)

    def test_a_verification_check_authors_no_rule_because_it_is_self_reported(self) -> None:
        reference = generation._reference_payload({
            "kind": "verification",
            "stimulus": {"prompt": "Confirm the steps.", "format": "verification"},
            "reference_answer": "all steps",
            "accepted_answers": ["all steps"],
            "accepted_alternatives": [],
            "feedback": {"rule": _RULE},
        })
        self.assertEqual(reference["kind"], "rubric_only")
        self.assertNotIn("feedback", reference)

    def test_a_rule_that_restates_an_accepted_answer_is_refused(self) -> None:
        spec = {"kind": "exact", "answers": ["suki desu"],
                "feedback": {"rule": "Write suki desu and nothing else."}}
        with self.assertRaises(validators.ReferenceSpecError):
            validators.seal_reference(spec)

    def test_a_miss_may_not_name_the_pass_action(self) -> None:
        spec = {"kind": "exact", "answers": ["alpha"],
                "feedback": {"rule": "Begin the word with the first letter of the alphabet.",
                             "next_action": "complete_objective"}}
        with self.assertRaises(validators.ReferenceSpecError):
            validators.seal_reference(spec)

    def test_a_group_rule_is_sealed_and_kept(self) -> None:
        sealed = validators.seal_reference({
            "kind": "selection",
            "answers": [["a", "b"]],
            "feedback": {"rule": "Select both steps.",
                         "groups": [{"answers": ["a", "b"],
                                     "rule": "The second step is not part of this procedure."}]},
        })
        self.assertEqual(sealed["feedback"]["groups"][0]["rule"],
                         "The second step is not part of this procedure.")
        self.assertEqual(sealed["reference_kind"] if "reference_kind" in sealed else "selection", "selection")


class MissFeedbackBridgeTest(GateCase):
    """`attempt.submit` and `pre_turn` on the real dispatcher and a real database."""

    def test_a_not_yet_result_carries_the_rule_and_the_next_action(self) -> None:
        lesson = self.prepare_bound(ruled_numeric_spec())
        submitted = self.submit(lesson, "41.2", nonce="nonce-miss-1", key="key-miss-1")
        self.assertTrue(submitted["ok"], submitted.get("error"))
        result = submitted["result"]
        self.assertEqual(result["verdict"], "not_yet")
        # The result carries the authored rule, the learner's own answer and one next action.
        self.assertEqual(result["feedback"]["rule"], _RULE)
        self.assertEqual(result["feedback"]["next_action"], _NEXT)
        self.assertEqual(result["feedback"]["answer"], "41.2")
        # The teaching turn is told what failed, and by which rule.
        outcome = turn.pre_turn(_STORED, "41.2")
        context = outcome.hook["context"]
        self.assertEqual(outcome.verdict, "not_yet")
        self.assertIn(_RULE, context)
        self.assertIn("not yet", context)
        # The learner's words stay out of the pipeline's words, and vice versa.
        self.assertNotIn("criteria", context)
        self.assertNotIn("c1", context)

    def test_a_replayed_attempt_rebuilds_the_same_block(self) -> None:
        lesson = self.prepare_bound(ruled_numeric_spec())
        first = self.submit(lesson, "41.2", nonce="nonce-miss-2", key="key-miss-2")
        self.assertTrue(first["ok"], first.get("error"))
        # Same nonce, different key: the prior-attempt path rebuilds the result from the row.
        again = self.submit(lesson, "41.2", nonce="nonce-miss-2", key="key-miss-3")
        self.assertTrue(again["ok"], again.get("error"))
        self.assertEqual(again["result"]["feedback"], first["result"]["feedback"])

    def test_a_check_without_an_authored_rule_still_grades_and_says_nothing_it_does_not_know(self) -> None:
        lesson = self.prepare_bound(numeric_spec("42.7"))
        submitted = self.submit(lesson, "41.2")
        self.assertTrue(submitted["ok"], submitted.get("error"))
        self.assertEqual(submitted["result"]["verdict"], "not_yet")
        self.assertNotIn("feedback", submitted["result"])


if __name__ == "__main__":
    unittest.main()
