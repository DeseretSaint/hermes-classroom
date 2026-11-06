"""CB-026 proof: cb.rpc v5's three methods against the real kernel and a real database.

`tests/test_contracts.py` proves the contract set is coherent; it cannot prove that

* a real enrollment's plan/objective rows compose into a contract-shaped ``course.outline``,
* ``check.get`` renders a real check's stimulus and drops a key smuggled into
  ``checks.stimulus_json``,
* the ``lesson.assist`` event is really consumed by the next committed attempt (and that its
  revision bump makes an in-flight submit lose the fence), or
* v5 added no storage,

because all of that lives on the CB-008/CB-022 kernel branch. This module closes the gap: it drives
the real commands through ``api.dispatch`` — the same handlers the Desktop calls — and validates
every payload against ``rpc.v5.json``.

Run it in a worktree that contains the backend kernel:

    python3 -m unittest scripts.proof_contract_v5 -v

Without that backend the module skips with an explicit reason instead of pretending to pass. It is a
proof, not a gate: `tests/test_contracts.py` is the gate that must pass everywhere.
"""

from __future__ import annotations

# This module is branch-dependent by design: it imports the Python kernel, so static analysis on a
# branch without it reports unresolved imports.
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportPossiblyUnboundVariable=false, reportGeneralTypeIssues=false, reportAssignmentType=false, reportArgumentType=false

import json
import os
import unittest

from coursebook import contracts

try:  # The kernel and its fixtures live on Cinder's branches.
    from coursebook import api, domain
    from coursebook.api import RpcError
    from tests.kernel_support import KernelCase, request

    _KERNEL_AVAILABLE = True
    _KERNEL_WHY = ""
except ImportError as exc:  # pragma: no cover - depends on the branch being checked out
    _KERNEL_AVAILABLE = False
    _KERNEL_WHY = f"needs the Python kernel (coursebook/domain.py, tests/kernel_support.py): {exc}"

    class KernelCase(unittest.TestCase):  # type: ignore[no-redef]
        """Placeholder so the module imports (and skips honestly) where the kernel is absent."""


def _dispatch(method: str, payload: dict, **kwargs) -> dict:
    """Run the shipped handler through the real dispatch seam, not a local re-derivation."""
    response = api.dispatch(request(method, payload, **kwargs))
    if not response["ok"]:
        raise RpcError(response["error"])
    return response


def _json(value, default):
    import json

    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def outline_view(enrollment_id: str, *, limit: int = 400) -> dict:
    """Drive the shipped ``course.outline`` handler through dispatch.

    Every assertion below is unchanged from the pre-handler proof: it is the same contract text,
    now checked against the code the Desktop actually calls.
    """
    return _dispatch("course.outline", {"enrollment_id": enrollment_id, "limit": limit})["result"]


def check_view(enrollment_id: str, *, check_id: str | None = None,
               objective_id: str | None = None) -> dict:
    """Drive the shipped ``check.get`` handler; it resolves, authorises, and projects the stimulus."""
    payload = {"enrollment_id": enrollment_id}
    if check_id is not None:
        payload["check_id"] = check_id
    else:
        payload["objective_id"] = objective_id
    return _dispatch("check.get", payload)["result"]


def assist(lesson: dict, kind: str, *, expected_revision: int) -> tuple[int, dict]:
    """Drive the shipped ``lesson.assist`` command (fenced, idempotent, one layer-1 row)."""
    response = _dispatch(
        "lesson.assist",
        {
            "enrollment_id": lesson["enrollment_id"],
            "objective_id": lesson["objective_id"],
            "kind": kind,
        },
        expected_revision=expected_revision,
        idempotency_key=f"proof-assist-{os.urandom(8).hex()}",
    )
    return int(response["revision"]), response["result"]


@unittest.skipUnless(_KERNEL_AVAILABLE, _KERNEL_WHY)
class V5OutlineProof(KernelCase):
    def assert_valid(self, method: str, result: dict) -> None:
        contracts.validate_response_payload(method, result)

    def test_outline_is_built_from_the_real_draft_plan(self) -> None:
        self.assertEqual(contracts.audit_contracts(), [])
        self.assertGreaterEqual(contracts.WIRE_CONTRACT_VERSION, 5)
        self.assertEqual(contracts.contract_version("cb.rpc"), contracts.WIRE_CONTRACT_VERSION)

        course_id, plan_id = self.new_course()
        first = self.seed_objective(plan_id)
        second = self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)

        result = outline_view(enrollment_id)
        self.assert_valid("course.outline", result)
        self.assertEqual(result["total"], 2)
        self.assertFalse(result["truncated"])
        # No approval yet: the Plan tab must show the draft, not an error and not a fake approval.
        self.assertEqual(result["plan"]["plan_id"], plan_id)
        self.assertEqual(result["plan"]["state"], "draft")
        self.assertRegex(result["plan"]["plan_hash"], r"^sha256:[a-f0-9]{64}$")
        self.assertEqual([entry["objective_id"] for entry in result["objectives"]], [first, second])
        self.assertEqual([entry["ordinal"] for entry in result["objectives"]], [1, 2])
        for entry in result["objectives"]:
            self.assertEqual(entry["check_state"], "none")
            self.assertEqual(entry["attempt_count"], 0)
            self.assertFalse(entry["independent"])
            self.assertIsNone(entry["last_opened_at"])

    def test_outline_is_bounded_and_reports_the_true_total(self) -> None:
        course_id, plan_id = self.new_course()
        for _ in range(3):
            self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)

        bounded = outline_view(enrollment_id, limit=2)
        self.assert_valid("course.outline", bounded)
        self.assertEqual(len(bounded["objectives"]), 2)
        self.assertEqual(bounded["total"], 3)
        self.assertTrue(bounded["truncated"])

    def test_outline_tracks_check_state_attempts_and_independence(self) -> None:
        lesson = self.prepare_lesson()
        opened = outline_view(lesson["enrollment_id"])["objectives"][0]
        self.assertEqual(opened["check_state"], "open")

        # A hinted pass: the evidence class changes what the record may claim.
        domain_revision, _ = assist(lesson, "hint_request", expected_revision=lesson["revision"])
        lesson["revision"] = domain_revision
        submitted = self.submit(lesson, "4")
        self.assertTrue(submitted["ok"], submitted)
        self.assertEqual(submitted["result"]["evidence_class"], "hinted")

        after = outline_view(lesson["enrollment_id"])["objectives"][0]
        self.assertEqual(after["check_state"], "closed")
        self.assertEqual(after["attempt_count"], 1)
        self.assertFalse(after["independent"])
        self.assertEqual(after["state"], "introduced")

        # A cold pass on a second objective is the only thing that reaches independence.
        cold = self.prepare_lesson()
        self.assertTrue(self.submit(cold, "4")["ok"])
        cold_section = outline_view(cold["enrollment_id"])["objectives"][0]
        self.assertTrue(cold_section["independent"])
        self.assertEqual(cold_section["state"], "independent_evidence")

    def test_outline_and_check_views_carry_no_answer_authority(self) -> None:
        lesson = self.prepare_lesson()
        outline = outline_view(lesson["enrollment_id"])
        check = check_view(lesson["enrollment_id"], check_id=lesson["check_id"])
        for forbidden in ("reference_answer", "reference", "reference_json", "rubric",
                          "rubric_json", "accepted_answers", "grading_provenance", "check_spec"):
            self.assertNotIn(forbidden, outline)
            self.assertNotIn(forbidden, check)
            for entry in outline["objectives"]:
                self.assertNotIn(forbidden, entry)
        # The real check row does hold the answer; the view must not carry it.
        stored = _json(self.rows(
            "SELECT reference_json FROM checks WHERE id = ?", (lesson["check_id"],)
        )[0]["reference_json"], {})
        self.assertEqual(stored, {"kind": "numeric", "value": "4", "tolerance": {"abs": "0"}})
        self.assertNotIn("\"value\": \"4\"", json.dumps(check))
        self.assertNotIn("numeric", json.dumps(check))

    def test_check_get_by_id_and_by_objective_agree(self) -> None:
        lesson = self.prepare_lesson()
        by_id = check_view(lesson["enrollment_id"], check_id=lesson["check_id"])
        by_objective = check_view(lesson["enrollment_id"], objective_id=lesson["objective_id"])
        self.assert_valid("check.get", by_id)
        self.assertEqual(by_id, by_objective)
        # The kernel spec has no format: an open answer, not a missing field.
        self.assertEqual(by_id["stimulus"]["format"], "text")
        self.assertEqual(by_id["stimulus"]["choices"], [])
        self.assertEqual(by_id["attempt_count"], 0)

    def test_check_get_renders_a_selection_item_and_drops_a_smuggled_key(self) -> None:
        lesson = self.prepare_lesson()
        smuggled = {
            "prompt": "Which expression is polite to a professor?",
            "format": "selection",
            "choices": ["ありがとう", "ありがとうございます"],
            "learner_instructions": "Choose one option.",
            # A manifest that put its answer inside the stimulus must not reach the pane.
            "reference_answer": "ありがとうございます",
            "rubric": ["politeness"],
        }
        self.execute(
            "UPDATE checks SET stimulus_json = ? WHERE id = ?",
            (domain._json_dump(smuggled), lesson["check_id"]),
        )
        result = check_view(lesson["enrollment_id"], check_id=lesson["check_id"])
        self.assert_valid("check.get", result)
        self.assertEqual(result["stimulus"]["format"], "selection")
        self.assertEqual(result["stimulus"]["choices"], ["ありがとう", "ありがとうございます"])
        self.assertEqual(result["stimulus"]["learner_instructions"], "Choose one option.")
        self.assertNotIn("reference_answer", result["stimulus"])
        self.assertNotIn("rubric", result["stimulus"])

    def test_check_get_refuses_a_check_from_another_course(self) -> None:
        mine = self.prepare_lesson()
        theirs = self.prepare_lesson()
        with self.assertRaises(RpcError) as caught:
            check_view(mine["enrollment_id"], check_id=theirs["check_id"])
        self.assertEqual(caught.exception.error["code"], "VALIDATION_FAILED")
        self.assertEqual(caught.exception.error["details"].get("reason"), "check_not_in_enrollment_course")
        with self.assertRaises(RpcError) as missing:
            check_view(mine["enrollment_id"], check_id="chk_never_existed")
        self.assertEqual(missing.exception.error["code"], "NOT_FOUND")

    def test_assist_event_is_written_and_consumed_by_the_next_attempt(self) -> None:
        lesson = self.prepare_lesson()
        revision, result = assist(lesson, "hint_request", expected_revision=lesson["revision"])
        self.assert_valid("lesson.assist", result)
        self.assertEqual(result["evidence_class"], "hinted")
        self.assertEqual(revision, lesson["revision"] + 1)

        event = self.rows("SELECT * FROM evidence WHERE id = ?", (result["event_id"],))[0]
        self.assertEqual(int(event["layer"]), 1)
        self.assertEqual(event["kind"], "hint_request")
        self.assertIsNone(event["attempt_id"])

        lesson["revision"] = revision
        submitted = self.submit(lesson, "4")
        self.assertTrue(submitted["ok"], submitted)
        self.assertEqual(submitted["result"]["evidence_class"], "hinted")
        consumed = self.rows("SELECT * FROM evidence WHERE id = ?", (result["event_id"],))[0]
        self.assertEqual(consumed["attempt_id"], submitted["result"]["attempt_id"])

        # A second assist on a fresh open check, with the shown answer taking precedence.
        fresh = self.prepare_lesson()
        shown_revision, shown = assist(fresh, "answer_shown", expected_revision=fresh["revision"])
        self.assert_valid("lesson.assist", shown)
        self.assertEqual(shown["evidence_class"], "answer_shown")
        self.assertEqual(shown_revision, fresh["revision"] + 1)

    def test_assist_bump_makes_an_in_flight_submit_lose_the_fence(self) -> None:
        lesson = self.prepare_lesson()
        stale_revision = lesson["revision"]
        assist(lesson, "answer_shown", expected_revision=stale_revision)
        lesson["revision"] = stale_revision  # the pane still holds the pre-hint revision
        response = self.submit(lesson, "4")
        self.assertFalse(response["ok"])
        self.assertIn(response["error"]["code"], {"STALE_REVISION", "CHECK_STALE"})
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 0)

    def test_assist_requires_an_open_check(self) -> None:
        lesson = self.prepare_lesson()
        self.assertTrue(self.submit(lesson, "4")["ok"])  # pass closes the check
        with self.assertRaises(RpcError) as caught:
            assist(lesson, "hint_request", expected_revision=lesson["revision"] + 1)
        self.assertEqual(caught.exception.error["code"], "VALIDATION_FAILED")
        self.assertEqual(caught.exception.error["details"].get("reason"), "no_open_check")

    def test_v5_added_no_storage(self) -> None:
        tables = {row["name"] for row in self.rows(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )}
        declared = set(contracts.contract("cb.db")["tables"])
        self.assertEqual(tables, declared, "the database and cb.db v2 disagree about storage")
        self.assertEqual(set(contracts.error_codes()),
                         set(contracts.contract("cb.errors")["code_catalog"]))


if __name__ == "__main__":
    unittest.main()
