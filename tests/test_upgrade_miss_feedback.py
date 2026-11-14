"""Upgrade 13: a miss names the rule, and the teaching turn is told what failed.

At HEAD a ``not_yet`` carried one deterministic grader sentence (``does not match an accepted
answer``, ``outside tolerance by 0.5``) and the continuation prompt carried the verdict, the next
action, the evidence class and an objective id — never the rule the check tests. So the pane could
print no reason and the tutor could not say what to do differently.

After this change a check may author the rule on its stored reference; a non-pass returns a
``feedback`` block naming that rule, the learner's own answer and one next action;
``attempt.submit`` carries it to the pane, a replay rebuilds it from the stored attempt, and
``pre_turn`` puts it in the teaching turn's context.

The rules the block must not break, each pinned here:

* the authored rule may not restate an accepted answer (the leak that turns a retry into a copy
  task), enforced at seal time;
* a miss can never name ``complete_objective``: a wrong answer does not grant access;
* one rule covers the whole check: a per-accepted-answer-group rule is refused at seal time,
  because a wrong answer says nothing about which accepted form the learner was aiming at, so
  picking a group would be a guess and a guessed diagnosis can teach the error;
* no pipeline word (``criteria``, criterion ids) reaches the chat context.
"""

from __future__ import annotations

import re
import unittest

from coursebook import generation, grading, turn, validators
from tests.kernel_support import KernelCase, numeric_spec
from tests.test_turn import _STORED, GateCase

#: One authored rule a learner can act on. Deliberately contains neither the reference value nor
#: the learner's answer.
_RULE = "Read the scale to one decimal place before you compare the two readings."
_NEXT = "retry_attempt"


def ruled_numeric_spec(value: str = "42.7", *, rule: str = _RULE,
                       next_action: str = _NEXT) -> dict:
    spec = numeric_spec(value)
    spec["reference"]["feedback"] = {"rule": rule, "next_action": next_action}
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

    def test_a_selection_miss_names_the_one_rule_the_check_authors(self) -> None:
        reference = validators.seal_reference({
            "kind": "selection",
            "answers": [["a", "b"], ["c", "d"]],
            "feedback": {"rule": "Name the two steps this check asks for, in either order."},
        })
        graded = grading.grade_closed(
            reference=reference,
            rubric={"pass_rule": "all"},
            answer={"kind": "selection", "selection": ["c"]},
        )
        self.assertEqual(graded.verdict, "not_yet")
        self.assertEqual((graded.feedback or {}).get("rule"),
                         "Name the two steps this check asks for, in either order.")

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

    def test_a_per_group_rule_is_refused_because_a_miss_names_no_form(self) -> None:
        """A group rule is a guess, even a clean one: the reviewer's repro sealed a group rule that
        restated its own group's answers and printed it to the learner verbatim.

        Both shapes are refused, because the reason is not the leak — it is that a wrong answer is
        no evidence of which accepted form the learner was aiming at, so *any* per-group rule is
        selected by a guess. Refusing at the seal is what keeps the surface from existing.
        """
        for rule in (
            "The second step is not part of this procedure.",
            "The answer is warm the pan then braise the meat.",
        ):
            with self.subTest(rule=rule):
                with self.assertRaises(validators.ReferenceSpecError) as caught:
                    validators.seal_reference({
                        "kind": "selection",
                        "answers": [["warm the pan", "braise the meat"]],
                        "feedback": {
                            "rule": "Name the two steps this procedure asks for.",
                            "groups": [{"answers": ["warm the pan", "braise the meat"], "rule": rule}],
                        },
                    })
                self.assertIn("per-group rule would be a guess", str(caught.exception))

    def test_a_generated_check_never_ships_a_per_group_rule(self) -> None:
        check = {
            "kind": "quiz",
            "stimulus": {"prompt": "Read the gauge.", "format": "text"},
            "reference_answer": "42.7",
            "accepted_answers": ["42.7"],
            "accepted_alternatives": [["42.7", "forty-two point seven"]],
            "feedback": {
                "rule": _RULE,
                "groups": [{"answers": ["42.7"], "rule": "Read the scale before you compare."}],
            },
        }
        # The authoring schema refuses the key outright...
        feedback_record = generation.LESSON_SCHEMA["properties"]["check"]["properties"]["feedback"]
        self.assertNotIn("groups", feedback_record["properties"])
        # ...and a check that somehow carried one is dropped, not repaired or shipped.
        self.assertNotIn("feedback", generation._reference_payload(check))
        # The same check without the group key keeps its rule, so the drop is the key's doing.
        check.pop("feedback")
        check["feedback"] = {"rule": _RULE}
        self.assertEqual(generation._reference_payload(check)["feedback"]["rule"], _RULE)


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
        # A criterion id never reaches the chat. Matched as a whole token: a bare substring check
        # flaked whenever the freshly minted objective id happened to contain "c1" (seen 3 times in
        # 15 runs), which made the named acceptance test non-deterministic.
        self.assertIsNone(re.search(r"(?<![0-9A-Za-z_])c1(?![0-9A-Za-z_])", context))

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
