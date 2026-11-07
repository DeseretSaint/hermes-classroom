"""The transactional kernel: one transition per answer, and no way to fake one.

These are the acceptance cases for CB-002. Each one runs against the real database and the real
``attempt.submit`` handler; the only thing faked is an aux grader, and only where a test is
proving that a grader failure advances nothing.
"""

from __future__ import annotations

import threading
import time
import unittest

from coursebook import db, domain, grading
from tests.kernel_support import KernelCase, criteria_with, numeric_spec


def open_spec() -> dict:
    return {
        "audit_state": "passed",
        "stimulus": {"prompt": "Explain braising."},
        "reference": {"kind": "rubric_only"},
        "rubric": {"construct": "comprehension", "pass_rule": "all",
                   "criteria": [{"id": "c1", "description": "Explains low-and-slow"}]},
    }


class TransitionTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.prepare_lesson()

    def count(self, table: str, where: str = "1=1", params: tuple = ()) -> int:
        return int(self.scalar(f"SELECT COUNT(*) FROM {table} WHERE {where}", params))

    def test_a_pass_commits_exactly_one_transition(self) -> None:
        response = self.submit(self.lesson, "4")
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["evidence_class"], "cold")
        self.assertEqual(result["next_action"], "complete_objective")
        self.assertEqual(result["revision"], self.lesson["revision"] + 1)
        self.assertEqual(len(result["criteria"]), 1)
        self.assertTrue(result["criteria"][0]["met"])

        enrollment_id = self.lesson["enrollment_id"]
        self.assertEqual(self.count("attempts", "enrollment_id = ?", (enrollment_id,)), 1)
        self.assertEqual(self.count("transitions", "enrollment_id = ?", (enrollment_id,)), 3)
        last = self.rows(
            "SELECT * FROM transitions WHERE enrollment_id = ? ORDER BY to_revision DESC LIMIT 1",
            (enrollment_id,),
        )[0]
        self.assertEqual(last["to_revision"], self.lesson["revision"] + 1)
        self.assertEqual(last["attempt_id"], result["attempt_id"])
        self.assertEqual(last["next_action"], "complete_objective")

        layers = self.rows("SELECT layer, kind, evidence_class FROM evidence WHERE enrollment_id = ?",
                           (enrollment_id,))
        self.assertEqual({row["layer"] for row in layers}, {1, 2})
        self.assertEqual(self.scalar("SELECT state FROM objectives WHERE id = ?",
                                     (self.lesson["objective_id"],)), "independent_evidence")
        self.assertEqual(self.scalar("SELECT state FROM checks WHERE id = ?", (self.lesson["check_id"],)), "closed")

    def test_a_second_answer_to_a_closed_check_creates_no_attempt(self) -> None:
        first = self.submit(self.lesson, "4")["result"]
        error = self.err(
            "attempt.submit",
            {"enrollment_id": self.lesson["enrollment_id"], "check_id": self.lesson["check_id"],
             "check_version": self.lesson["check_version"], "attempt_nonce": "nonce-second-0001",
             "answer": {"kind": "text", "text": "4"}},
            expected_revision=first["revision"],
            idempotency_key="second-answer-key",
        )
        self.assertEqual(error["code"], "CHECK_STALE")
        self.assertEqual(error["details"]["current_revision"], first["revision"])
        self.assertEqual(self.count("attempts"), 1)
        self.assertEqual(self.count("transitions", "attempt_id IS NOT NULL"), 1)

    def test_duplicate_nonce_is_ignored(self) -> None:
        nonce = "nonce-duplicate-01"
        first = self.submit(self.lesson, "4", nonce=nonce)["result"]
        replay = self.submit(self.lesson, "4", nonce=nonce, revision=first["revision"],
                             key="different-key-same-nonce")["result"]
        self.assertEqual(replay, first)
        self.assertEqual(self.count("attempts"), 1)
        self.assertEqual(self.count("transitions", "attempt_id IS NOT NULL"), 1)

    def test_same_key_replays_the_persisted_result(self) -> None:
        first = self.submit(self.lesson, "4", key="submit-key-0001")["result"]
        again = self.submit(self.lesson, "4", key="submit-key-0001", revision=first["revision"])["result"]
        self.assertEqual(again, first)
        self.assertEqual(self.count("attempts"), 1)
        self.assertEqual(self.count("transitions", "attempt_id IS NOT NULL"), 1)

    def test_same_key_with_a_different_answer_is_a_conflict(self) -> None:
        self.submit(self.lesson, "4", key="submit-key-0002")
        error = self.err(
            "attempt.submit",
            {"enrollment_id": self.lesson["enrollment_id"], "check_id": self.lesson["check_id"],
             "check_version": self.lesson["check_version"], "attempt_nonce": "nonce-conflict-001",
             "answer": {"kind": "text", "text": "5"}},
            expected_revision=self.lesson["revision"] + 1,
            idempotency_key="submit-key-0002",
        )
        self.assertEqual(error["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.count("attempts"), 1)

    def test_stale_revision_is_refused_before_grading(self) -> None:
        error = self.err(
            "attempt.submit",
            {"enrollment_id": self.lesson["enrollment_id"], "check_id": self.lesson["check_id"],
             "check_version": self.lesson["check_version"], "attempt_nonce": "nonce-stale-0001",
             "answer": {"kind": "text", "text": "4"}},
            expected_revision=self.lesson["revision"] - 1,
            idempotency_key="stale-key-0001",
        )
        self.assertEqual(error["code"], "STALE_REVISION")
        self.assertEqual(error["details"]["current_revision"], self.lesson["revision"])
        self.assertEqual(self.count("attempts"), 0)

    def test_stale_check_version_is_refused(self) -> None:
        error = self.err(
            "attempt.submit",
            {"enrollment_id": self.lesson["enrollment_id"], "check_id": self.lesson["check_id"],
             "check_version": self.lesson["check_version"] + 1, "attempt_nonce": "nonce-check-stale",
             "answer": {"kind": "text", "text": "4"}},
            expected_revision=self.lesson["revision"],
            idempotency_key="check-stale-key",
        )
        self.assertEqual(error["code"], "CHECK_STALE")
        self.assertEqual(error["details"]["check_version"], self.lesson["check_version"])
        self.assertEqual(self.count("attempts"), 0)

    def test_answer_outside_the_size_bound_is_a_validation_failure(self) -> None:
        error = self.err(
            "attempt.submit",
            {"enrollment_id": self.lesson["enrollment_id"], "check_id": self.lesson["check_id"],
             "check_version": self.lesson["check_version"], "attempt_nonce": "nonce-too-long-01",
             "answer": {"kind": "text", "text": "x" * 8001}},
            expected_revision=self.lesson["revision"],
            idempotency_key="too-long-key-01",
        )
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(self.count("attempts"), 0)

    def test_a_retry_after_feedback_is_hinted_and_never_independent_evidence(self) -> None:
        first = self.submit(self.lesson, "5")["result"]
        self.assertEqual(first["verdict"], "not_yet")
        self.assertEqual(first["evidence_class"], "cold")
        self.assertEqual(self.scalar("SELECT state FROM objectives WHERE id = ?",
                                     (self.lesson["objective_id"],)), "needs_review")
        self.assertEqual(self.count("evidence", "layer = 2"), 0)

        second = self.submit(self.lesson, "4", revision=first["revision"])["result"]
        self.assertEqual(second["verdict"], "pass")
        self.assertEqual(second["evidence_class"], "hinted")
        self.assertEqual(second["next_action"], "review_objective")
        self.assertEqual(self.scalar("SELECT state FROM objectives WHERE id = ?",
                                     (self.lesson["objective_id"],)), "needs_review")
        self.assertEqual(self.count("evidence", "layer = 2"), 0, "a hinted pass is not independent evidence")

    def test_override_grants_access_without_a_pass(self) -> None:
        result = self.ok(
            "attempt.override",
            {"enrollment_id": self.lesson["enrollment_id"], "check_id": self.lesson["check_id"],
             "reason": "Learner already knows this."},
            expected_revision=self.lesson["revision"],
        )["result"]
        self.assertEqual(result["evidence_class"], "override")
        self.assertEqual(result["next_action"], "complete_objective")
        attempt = self.rows("SELECT * FROM attempts WHERE id = ?", (result["attempt_id"],))[0]
        self.assertEqual(attempt["evidence_class"], "override")
        self.assertEqual(attempt["verdict"], "not_yet", "an override is access, never a pass")
        self.assertEqual(self.scalar("SELECT state FROM objectives WHERE id = ?",
                                     (self.lesson["objective_id"],)), "overridden")
        self.assertEqual(self.count("evidence", "layer = 2"), 0)

    def test_paused_binding_refuses_a_submit(self) -> None:
        self.execute(
            "INSERT INTO bindings (id, enrollment_id, profile, status, revision, updated_at)"
            " VALUES ('bnd_paused_0001', ?, 'cinder', 'paused', 0, '2026-01-01T00:00:00+00:00')",
            (self.lesson["enrollment_id"],),
        )
        error = self.err(
            "attempt.submit",
            {"enrollment_id": self.lesson["enrollment_id"], "check_id": self.lesson["check_id"],
             "check_version": self.lesson["check_version"], "attempt_nonce": "nonce-paused-001",
             "answer": {"kind": "text", "text": "4"}},
            expected_revision=self.lesson["revision"],
            idempotency_key="paused-key-0001",
        )
        self.assertEqual(error["code"], "BINDING_NOT_ACTIVE")
        self.assertEqual(self.count("attempts"), 0)

    def test_criteria_observations_never_contain_the_reference(self) -> None:
        lesson = self.prepare_lesson({"audit_state": "passed", "stimulus": {"prompt": "Name the word."},
                                      "reference": {"kind": "exact", "answers": ["correct-word",
                                                                                 "hidden-reference-word"]},
                                      "rubric": {"pass_rule": "all"}})
        result = self.submit(lesson, "correct-word")["result"]
        self.assertNotIn("hidden-reference-word", repr(result["criteria"]))
        history = self.ok("quiz.history", {"enrollment_id": lesson["enrollment_id"]})["result"]
        self.assertNotIn("hidden-reference-word", repr(history))
        self.assertEqual(history["attempts"][0]["attempt_id"], result["attempt_id"])

    def test_duplicate_transition_revision_is_rejected_by_the_database(self) -> None:
        with db.transaction() as connection:
            last = connection.execute(
                "SELECT to_revision FROM transitions WHERE enrollment_id = ? ORDER BY to_revision DESC LIMIT 1",
                (self.lesson["enrollment_id"],),
            ).fetchone()
            with self.assertRaises(Exception):
                connection.execute(
                    "INSERT INTO transitions (id, enrollment_id, attempt_id, from_revision, to_revision,"
                    " next_action, created_at) VALUES ('trn_duplicate_01', ?, NULL, ?, ?, 'continue', 'now')",
                    (self.lesson["enrollment_id"], last["to_revision"] - 1, last["to_revision"]),
                )


class GradingFailureTest(KernelCase):
    def tearDown(self) -> None:
        grading.configure_aux_grader(None)
        super().tearDown()

    def test_grader_failure_persists_needs_retry_and_advances_nothing(self) -> None:
        lesson = self.prepare_lesson(open_spec())
        response = self.submit(lesson, "a long explanation")
        self.assertTrue(response["ok"], response.get("error"))
        result = response["result"]
        self.assertEqual(result["verdict"], "needs_retry")
        self.assertEqual(result["next_action"], "retry_grading")
        self.assertEqual(result["revision"], lesson["revision"], "no transition may be consumed")
        attempt = self.rows("SELECT * FROM attempts WHERE id = ?", (result["attempt_id"],))[0]
        self.assertEqual(attempt["state"], "failed")
        self.assertEqual(attempt["verdict"], "needs_retry")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM transitions WHERE attempt_id IS NOT NULL"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 0)
        self.assertEqual(self.scalar("SELECT state FROM objectives WHERE id = ?", (lesson["objective_id"],)),
                         "not_started")

    def test_a_needs_retry_attempt_is_replayed_not_regraded(self) -> None:
        lesson = self.prepare_lesson(open_spec())
        first = self.submit(lesson, "answer one", key="retry-key-0001")["result"]
        replay = self.submit(lesson, "answer one", key="retry-key-0001")["result"]
        self.assertEqual(replay, first)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 1)

    def test_the_grader_runs_with_no_transaction_open(self) -> None:
        lesson = self.prepare_lesson(open_spec())
        observations: list[int] = []

        def grader(**kwargs):
            observations.append(db.active_transactions())
            # A write from another connection must succeed: the submit holds no writer lock while
            # it is grading. A transaction left open here would block until the busy timeout.
            started = time.monotonic()
            with db.transaction() as connection:
                connection.execute(
                    "INSERT INTO notebook_entries (id, enrollment_id, objective_id, kind, note, tags_json,"
                    " created_at, updated_at) VALUES ('nbt_during_grade', ?, ?, 'personal_note', 'x', '[]',"
                    " '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
                    (lesson["enrollment_id"], lesson["objective_id"]),
                )
            self.assertLess(time.monotonic() - started, 1.0)
            return {"verdict": "pass", "criteria": [{"id": "c1", "observed": "clear", "met": True}]}

        grading.configure_aux_grader(grader, task_name="test")
        result = self.submit(lesson, "a long explanation")["result"]
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(observations, [0])

    def test_concurrent_submits_commit_one_transition_and_one_conflict(self) -> None:
        lesson = self.prepare_lesson()
        barrier = threading.Barrier(2)
        responses: list[dict] = []

        def worker(index: int) -> None:
            barrier.wait()
            responses.append(self.dispatch(
                "attempt.submit",
                {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"],
                 "check_version": lesson["check_version"], "attempt_nonce": f"nonce-race-{index:04d}",
                 "answer": {"kind": "text", "text": "4"}},
                expected_revision=lesson["revision"],
                idempotency_key=f"race-key-{index:04d}",
            ))

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(len(responses), 2)
        wins = [response for response in responses if response["ok"]]
        losses = [response for response in responses if not response["ok"]]
        self.assertEqual(len(wins), 1, responses)
        self.assertEqual(losses[0]["error"]["code"], "STALE_REVISION")
        self.assertEqual(losses[0]["error"]["details"]["current_revision"], lesson["revision"] + 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM transitions WHERE attempt_id IS NOT NULL"), 1)


class RecoveryTest(KernelCase):
    def test_startup_reconciliation_never_promotes_leftover_state(self) -> None:
        lesson = self.prepare_lesson()
        self.execute(
            "INSERT INTO attempts (id, enrollment_id, check_id, check_version, attempt_nonce, answer_kind,"
            " answer_json, answer_hash, verdict, evidence_class, criteria_json, grading_provenance_json,"
            " state, created_at, committed_at) VALUES ('att_leftover_01', ?, ?, ?, 'nonce-leftover', 'text',"
            " '{}', 'sha256:x', NULL, 'cold', '[]', '{}', 'pending', '2026-01-01T00:00:00+00:00', NULL)",
            (lesson["enrollment_id"], lesson["check_id"], lesson["check_version"]),
        )
        job = self.ok("jobs.create", {"kind": "research", "brief": {}})["result"]["job_id"]
        self.execute(
            "UPDATE jobs SET state = 'running', lease_owner = 'worker-1',"
            " lease_expires_at = '2026-01-01T00:00:00.000000+00:00' WHERE id = ?",
            (job,),
        )
        counts = db.recover_interrupted()
        self.assertEqual(counts, {"attempts": 1, "jobs": 1})
        attempt = self.rows("SELECT * FROM attempts WHERE id = 'att_leftover_01'")[0]
        self.assertEqual(attempt["state"], "failed")
        self.assertEqual(attempt["verdict"], "needs_retry")
        self.assertEqual(self.scalar("SELECT state FROM jobs WHERE id = ?", (job,)), "interrupted_requires_retry")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM transitions WHERE attempt_id = 'att_leftover_01'"), 0)

    def test_recovery_is_idempotent(self) -> None:
        self.assertEqual(db.recover_interrupted(), {"attempts": 0, "jobs": 0})


class EvidenceClassTest(KernelCase):
    def test_self_reported_observation_is_layer_one_only(self) -> None:
        lesson = self.prepare_lesson()
        before = self.scalar("SELECT state FROM objectives WHERE id = ?", (lesson["objective_id"],))
        domain.record_observation(lesson["enrollment_id"], lesson["objective_id"],
                                  evidence_class="self_reported", kind="instruction_complete")
        layers = self.rows("SELECT layer, evidence_class FROM evidence")
        self.assertEqual(layers, [{"layer": 1, "evidence_class": "self_reported"}])
        self.assertEqual(self.scalar("SELECT state FROM objectives WHERE id = ?", (lesson["objective_id"],)), before)

    def test_cannot_self_assert_independent_evidence(self) -> None:
        lesson = self.prepare_lesson()
        from coursebook.api import RpcError

        with self.assertRaises(RpcError) as raised:
            domain.record_observation(lesson["enrollment_id"], lesson["objective_id"], evidence_class="cold")
        self.assertEqual(raised.exception.error["code"], "POLICY_VIOLATION")

    def test_cannot_self_assert_a_hint_class_as_an_observation(self) -> None:
        lesson = self.prepare_lesson()
        from coursebook.api import RpcError

        with self.assertRaises(RpcError) as raised:
            domain.record_observation(lesson["enrollment_id"], lesson["objective_id"],
                                      evidence_class="override")
        self.assertEqual(raised.exception.error["code"], "POLICY_VIOLATION")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 0)

    def test_the_note_is_persisted_verbatim(self) -> None:
        """H-54 regression: before cb.db v9 this note was accepted and silently dropped.

        ``record_observation(..., note=...)`` had no ``note`` column to write to, so the row landed
        with the prose gone. The assertion below fails against the pre-fix INSERT (``note`` reads
        back NULL) and passes only when the note is written in the same transaction.
        """
        lesson = self.prepare_lesson()
        note = "Read the passage aloud without being asked, then explained the ending."
        evidence_id = domain.record_observation(
            lesson["enrollment_id"], lesson["objective_id"],
            evidence_class="parent_reported", note=note,
        )
        row = self.rows("SELECT * FROM evidence WHERE id = ?", (evidence_id,))[0]
        self.assertEqual(row["note"], note)
        self.assertIsNone(row["attempt_id"])
        self.assertEqual(row["layer"], 1)
        self.assertEqual(row["kind"], "observation")
        self.assertEqual(row["evidence_class"], "parent_reported")

    def test_no_note_stays_null_rather_than_an_empty_string(self) -> None:
        lesson = self.prepare_lesson()
        evidence_id = domain.record_observation(
            lesson["enrollment_id"], lesson["objective_id"], evidence_class="self_reported"
        )
        self.assertIsNone(self.scalar("SELECT note FROM evidence WHERE id = ?", (evidence_id,)))

    def test_an_over_long_note_is_refused_not_truncated(self) -> None:
        lesson = self.prepare_lesson()
        from coursebook.api import RpcError

        with self.assertRaises(RpcError) as raised:
            domain.record_observation(
                lesson["enrollment_id"], lesson["objective_id"],
                evidence_class="self_reported", note="x" * (domain.OBSERVATION_NOTE_LIMIT + 1),
            )
        self.assertEqual(raised.exception.error["code"], "VALIDATION_FAILED")
        self.assertEqual(raised.exception.error["details"]["reason"], "note_too_long")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 0)

    def test_a_note_at_the_bound_is_accepted(self) -> None:
        lesson = self.prepare_lesson()
        note = "x" * domain.OBSERVATION_NOTE_LIMIT
        evidence_id = domain.record_observation(
            lesson["enrollment_id"], lesson["objective_id"], evidence_class="self_reported", note=note
        )
        self.assertEqual(self.scalar("SELECT note FROM evidence WHERE id = ?", (evidence_id,)), note)

    def test_database_rejects_an_evidence_class_outside_the_contract(self) -> None:
        lesson = self.prepare_lesson()
        with db.read() as connection:
            with self.assertRaises(Exception):
                connection.execute(
                    "INSERT INTO evidence (id, enrollment_id, objective_id, layer, kind, evidence_class,"
                    " created_at) VALUES ('evd_bad_0001', ?, ?, 2, 'mastery', 'mastered', 'now')",
                    (lesson["enrollment_id"], lesson["objective_id"]),
                )


class ObservationRecordRpcTest(KernelCase):
    """``observation.record`` on the wire: one layer-1 row per accepted class, key-fenced.

    ``cb.rpc`` v14 declares this method with an ``idempotency_key`` and no ``expected_revision``
    (the write cannot move the enrollment aggregate), so there is deliberately no stale-revision
    case here: under v14 a ``STALE_REVISION`` refusal is unreachable, and a test for it would be
    asserting a fence the contract does not have.
    """

    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.prepare_lesson()

    def record(self, lesson: dict | None = None, *, key: str | None = "obs-key-0001",
               **overrides) -> dict:
        lesson = lesson or self.lesson
        payload = {
            "enrollment_id": lesson["enrollment_id"],
            "objective_id": lesson["objective_id"],
            "evidence_class": "self_reported",
        }
        payload.update(overrides)
        return self.dispatch("observation.record", payload, idempotency_key=key)

    def evidence_rows(self) -> list[dict]:
        return self.rows("SELECT * FROM evidence ORDER BY rowid")

    def test_every_accepted_class_writes_exactly_one_row_and_the_note_round_trips(self) -> None:
        for evidence_class in domain._OBSERVATION_CLASSES:
            with self.subTest(evidence_class=evidence_class):
                note = f"What the {evidence_class} reporter saw."
                response = self.record(
                    evidence_class=evidence_class, note=note,
                    key=f"obs-key-{evidence_class}",
                )
                self.assertTrue(response["ok"], response.get("error"))
                self.assertEqual(
                    set(response["result"]), {"evidence_id", "evidence_class", "revision"}
                )
                self.assertEqual(response["result"]["evidence_class"], evidence_class)
                # The echo is the enrollment revision, read but not bumped.
                self.assertEqual(response["result"]["revision"], self.lesson["revision"])
                row = self.rows(
                    "SELECT * FROM evidence WHERE id = ?", (response["result"]["evidence_id"],)
                )[0]
                self.assertEqual(row["note"], note)
                self.assertEqual(row["layer"], 1)
                self.assertEqual(row["kind"], "observation")
                self.assertEqual(row["attempt_id"], None)
                self.assertEqual(row["evidence_class"], evidence_class)
        self.assertEqual(len(self.evidence_rows()), 2)
        self.assertEqual(
            self.scalar("SELECT revision FROM enrollments WHERE id = ?", (self.lesson["enrollment_id"],)),
            self.lesson["revision"],
        )

    def test_cold_and_override_are_refused_with_policy_violation(self) -> None:
        for evidence_class in ("cold", "override", "hinted", "answer_shown"):
            with self.subTest(evidence_class=evidence_class):
                error = self.record(evidence_class=evidence_class, key=f"obs-key-{evidence_class}")["error"]
                self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(self.evidence_rows(), [])

    def test_a_cross_course_objective_is_refused(self) -> None:
        course_id, plan_id = self.new_course(title="A different course")
        self.new_enrollment(course_id)
        foreign_objective = self.seed_objective(plan_id)
        response = self.record(objective_id=foreign_objective, key="obs-key-cross-course")
        error = response["error"]
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["reason"], "objective_not_in_enrollment_course")
        self.assertEqual(error["details"]["field"], "objective_id")
        self.assertEqual(self.evidence_rows(), [])

    def test_the_same_key_replays_and_a_different_payload_conflicts(self) -> None:
        first = self.record(note="Said it unprompted.", key="obs-key-replay-1")["result"]
        again = self.record(note="Said it unprompted.", key="obs-key-replay-1")["result"]
        self.assertEqual(again, first)
        self.assertEqual(len(self.evidence_rows()), 1)

        conflict = self.record(note="A different sentence.", key="obs-key-replay-1")
        self.assertFalse(conflict["ok"])
        self.assertEqual(conflict["error"]["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(len(self.evidence_rows()), 1)

    def test_a_missing_idempotency_key_is_refused_by_the_envelope(self) -> None:
        response = self.record(key=None)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(self.evidence_rows(), [])

    def test_an_over_long_note_is_refused_at_the_wire_and_the_kernel(self) -> None:
        over = "x" * (domain.OBSERVATION_NOTE_LIMIT + 1)
        wire = self.record(note=over, key="obs-key-too-long")
        self.assertFalse(wire["ok"])
        self.assertEqual(wire["error"]["code"], "VALIDATION_FAILED")

        # The handler's own bound, reached without the wire validator: the kernel refuses rather
        # than truncating, and nothing is written.
        from coursebook.api import RpcError

        with self.assertRaises(RpcError) as raised:
            domain.observation_record(
                {
                    "enrollment_id": self.lesson["enrollment_id"],
                    "objective_id": self.lesson["objective_id"],
                    "evidence_class": "self_reported",
                    "note": over,
                },
                {"idempotency_key": "obs-key-too-long-kernel", "operation_id": "op-direct"},
            )
        self.assertEqual(raised.exception.error["details"]["reason"], "note_too_long")
        self.assertEqual(self.evidence_rows(), [])

    def test_an_observation_writes_no_attempt_transition_or_verdict(self) -> None:
        before = {
            "attempts": self.scalar("SELECT COUNT(*) FROM attempts"),
            "transitions": self.scalar("SELECT COUNT(*) FROM transitions"),
            "revision": self.scalar(
                "SELECT revision FROM enrollments WHERE id = ?", (self.lesson["enrollment_id"],)
            ),
        }
        accepted = self.record(note="Watched them do it.", key="obs-key-no-state")["result"]
        # Nothing a grade would leave behind moved.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM attempts"), before["attempts"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM transitions"), before["transitions"])
        self.assertEqual(
            self.scalar(
                "SELECT revision FROM enrollments WHERE id = ?", (self.lesson["enrollment_id"],)
            ),
            before["revision"],
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM evidence WHERE attempt_id IS NOT NULL"), 0
        )
        # No verdict can be read for this enrollment because no attempt exists.
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM attempts a JOIN checks c ON c.id = a.check_id"
                " WHERE a.enrollment_id = ?",
                (self.lesson["enrollment_id"],),
            ),
            0,
        )
        # The objective did not move.
        self.assertEqual(
            self.scalar("SELECT state FROM objectives WHERE id = ?", (self.lesson["objective_id"],)),
            "not_started",
        )
        # ...and the row is the one read back as a layer-1 event.
        bundle = self.ok("evidence.inspect", {"enrollment_id": self.lesson["enrollment_id"]})["result"]
        events = {event["evidence_id"]: event for event in bundle["l1"]["events"]}
        self.assertIn(accepted["evidence_id"], events)
        self.assertEqual(events[accepted["evidence_id"]]["layer"], 1)
        self.assertEqual(events[accepted["evidence_id"]]["kind"], "observation")
        self.assertEqual(events[accepted["evidence_id"]]["evidence_class"], "self_reported")
        self.assertIsNone(events[accepted["evidence_id"]]["attempt_id"])
        self.assertEqual(bundle["l1"]["attempts"], [])
        # L2 stays empty: an observation is never independent evidence.
        self.assertEqual(bundle["l2"]["objectives"][0]["L2_evidence_ids"], [])
        self.assertFalse(bundle["l2"]["objectives"][0]["independent"])

    def test_the_envelope_revision_fence_is_absent_by_contract(self) -> None:
        # v14: the key is the fence. A stale expected_revision describes a fence this method does
        # not have, so it is neither required nor checked — the write is an append.
        response = self.dispatch(
            "observation.record",
            {
                "enrollment_id": self.lesson["enrollment_id"],
                "objective_id": self.lesson["objective_id"],
                "evidence_class": "parent_reported",
            },
            idempotency_key="obs-key-no-revision-fence",
            expected_revision=self.lesson["revision"] - 1,
        )
        self.assertTrue(response["ok"], response.get("error"))
        self.assertEqual(response["result"]["revision"], self.lesson["revision"])
        self.assertEqual(len(self.evidence_rows()), 1)


class RegistrationTest(unittest.TestCase):
    def test_every_kernel_handler_is_in_the_contract_and_registered(self) -> None:
        from coursebook import api
        from coursebook.contracts import method_names

        for method in domain.KERNEL_METHODS:
            with self.subTest(method=method):
                self.assertIn(method, method_names())
                self.assertIs(api.METHOD_HANDLERS.get(method), domain.HANDLERS[method])

    def test_importing_the_package_registers_the_kernel(self) -> None:
        import importlib

        from coursebook import api, hooks

        importlib.import_module("coursebook.hooks")
        self.assertIn("attempt.submit", api.implemented_methods())
        self.assertIn("notebook.list", api.implemented_methods())
        self.assertIsNotNone(hooks.pre_llm_call)


if __name__ == "__main__":
    unittest.main()
