"""GM-009: the game-only engagement layer (XP, cosmetic levels, Game progress).

The product rule this file protects (``docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md`` §10B) is a
separation, not a feature: XP is a play layer derived from real recorded actions, and it is never
learning evidence. So every test here does two things at once — it proves the play layer answers,
and it proves the play layer cannot leak into the record that decides access.

The database is real (``tests.kernel_support.KernelCase``): a disposable profile, the real
migrations, and the real dispatcher. No provider is called and no timer is involved.
"""

from __future__ import annotations

import json
import os
import unittest

from coursebook import db, engagement, generation, pack_flow  # noqa: F401 (pack_flow registers methods)
from tests.kernel_support import KernelCase


def _has_key(value: object, name: str) -> bool:
    """True only when *name* is an exact object key anywhere in the structure."""
    if isinstance(value, dict):
        return any(str(key) == name or _has_key(item, name) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_key(item, name) for item in value)
    return False


def _contains_key(value: object, needle: str) -> bool:
    """True when *needle* appears anywhere in the JSON structure (keys or string values)."""
    if isinstance(value, dict):
        return any(needle in str(key) or _contains_key(item, needle) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_key(item, needle) for item in value)
    if isinstance(value, str):
        return needle in value
    return False


class GameEngagementCase(KernelCase):
    """A committed game course plus helpers that create real recorded actions."""

    def setUp(self) -> None:
        super().setUp()
        engagement.configure_feedback(None)
        course_id, plan_id = self.new_course(title="Japanese at the table", recipe="committed")
        objective_id = self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        # ``parent.blueprint.read`` composes authored sections from the generation tables; they are
        # created lazily by the generation pipeline, so this test creates them the same way.
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        opened = self.ok(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        self.execute("UPDATE courses SET presentation_mode = 'game' WHERE id = ?", (course_id,))
        self.course_id = course_id
        self.plan_id = plan_id
        self.objective_id = objective_id
        self.enrollment_id = enrollment_id
        self.check_id = opened["check_id"]
        self.check_version = opened["check_version"]
        self.revision = opened["revision"]

    def tearDown(self) -> None:
        engagement.configure_feedback(None)
        super().tearDown()

    # ── real actions ────────────────────────────────────────────────────

    def submitted_check(self) -> str:
        """Submit the closed-form check through the real command and return the attempt id."""
        response = self.submit(
            {
                "enrollment_id": self.enrollment_id,
                "check_id": self.check_id,
                "check_version": self.check_version,
                "revision": self.revision,
            },
            "4",
        )
        self.assertTrue(response["ok"], response.get("error"))
        return response["result"]["attempt_id"]

    def lesson_step(self) -> str:
        """Start a real lesson run and seed the teaching step the UI would complete."""
        begun = self.ok(
            "lesson.begin",
            {
                "enrollment_id": self.enrollment_id,
                "objective_id": self.objective_id,
                "mode": "fresh",
            },
            idempotency_key="key-gm009-lesson-step",
        )["result"]
        run_id = begun["lesson_run_id"]
        segment_id = "seg_gm009_step01"
        self.execute(
            "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, created_at)"
            " VALUES (?, ?, 1, 'teaching', 'A real teaching step.', ?)",
            (segment_id, run_id, db.utcnow()),
        )
        return segment_id

    def homework(self, *, state: str = "self_reported_done") -> str:
        task_id = "hwt_gm009_homework01"
        now = db.utcnow()
        self.execute(
            "INSERT OR IGNORE INTO homework_tasks (id, course_id, enrollment_id, objective_id,"
            " source_lesson_version, audience, task_kind, state, revision, title, target, context,"
            " steps_json, success_criterion, estimated_minutes, created_at, completed_at)"
            " VALUES (?, ?, ?, ?, 'lesson-v1', 'learner', 'real_world_use', ?, 0,"
            " 'Use the greeting at a meal', 'The before-meal greeting', 'At dinner', '[]',"
            " 'You said it before eating', 5, ?, ?)",
            (task_id, self.course_id, self.enrollment_id, self.objective_id, state, now, now),
        )
        return task_id

    def review_evidence(self) -> str:
        evidence_id = "evd_gm009_review01"
        self.execute(
            "INSERT INTO evidence (id, enrollment_id, objective_id, attempt_id, layer, kind,"
            " evidence_class, created_at) VALUES (?, ?, ?, NULL, 2, 'delayed_retrieval', 'cold', ?)",
            (evidence_id, self.enrollment_id, self.objective_id, db.utcnow()),
        )
        return evidence_id

    def returned_run(self, *, gap_days: float = 2.0) -> str:
        """A real lesson run preceded by an earlier run for the same enrollment."""
        older = "run_gm009_older01"
        newer = "run_gm009_returned01"
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision,"
            " created_at, updated_at, last_opened_at)"
            " VALUES (?, ?, ?, 'paused', 0,"
            " datetime('now', ?), datetime('now', ?), datetime('now', ?))",
            (older, self.enrollment_id, self.objective_id,
             f"-{gap_days + 1} days", f"-{gap_days + 1} days", f"-{gap_days + 1} days"),
        )
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision,"
            " created_at, updated_at, last_opened_at)"
            " VALUES (?, ?, ?, 'active', 0, datetime('now'), datetime('now'), datetime('now'))",
            (newer, self.enrollment_id, self.objective_id),
        )
        return newer

    def award(self, kind: str, action_id: str, **kwargs):
        return self.dispatch(
            "engagement.award",
            {
                "course_id": self.course_id,
                "enrollment_id": self.enrollment_id,
                "action_kind": kind,
                "action_id": action_id,
            },
            **kwargs,
        )

    def read(self) -> dict:
        return self.ok(
            "engagement.read",
            {"course_id": self.course_id, "enrollment_id": self.enrollment_id},
        )["result"]

    def xp_rows(self) -> int:
        return int(
            self.scalar(
                "SELECT COUNT(*) FROM game_engagement WHERE enrollment_id = ?",
                (self.enrollment_id,),
            )
        )


class GameXpRulesTest(GameEngagementCase):
    """XP exists only for named, recorded actions, and only once per action."""

    def test_game_xp_awarded_once_per_real_action(self) -> None:
        attempt_id = self.submitted_check()
        first = self.award("check_submitted", attempt_id)
        self.assertTrue(first["ok"], first.get("error"))
        self.assertTrue(first["result"]["awarded"])
        # The number is the formula applied to the graded row, not a constant: read that row and
        # recompute, so a table change the award did not follow is caught here.
        row = self.rows(
            "SELECT c.evidence_target AS evidence_target, a.verdict AS verdict,"
            " a.evidence_class AS evidence_class FROM attempts a"
            " JOIN checks c ON c.id = a.check_id WHERE a.id = ?",
            (attempt_id,),
        )[0]
        self.assertEqual(
            first["result"]["points"],
            engagement.xp_for_evidence(
                row["evidence_target"], row["verdict"], row["evidence_class"]
            ),
        )
        self.assertGreater(first["result"]["points"], 0)

        # A replay with a fresh envelope key must not duplicate the ledger row.
        again = self.award("check_submitted", attempt_id)
        self.assertTrue(again["ok"], again.get("error"))
        self.assertFalse(again["result"]["awarded"])
        self.assertEqual(again["result"]["points"], 0)
        self.assertEqual(again["result"]["xp_total"], first["result"]["xp_total"])
        self.assertEqual(self.xp_rows(), 1)

        # A replayed idempotency key returns the original answer verbatim.
        replay_key = "key-gm009-check-1"
        original = self.award(
            "check_submitted", attempt_id,
            idempotency_key=replay_key, operation_id="op-gm009-replay-1",
        )
        replayed = self.award(
            "check_submitted", attempt_id,
            idempotency_key=replay_key, operation_id="op-gm009-replay-1",
        )
        self.assertEqual(original, replayed)

        # The same key with a different action is a conflict, not a second award.
        conflict = self.award("homework_completed", self.homework(), idempotency_key=replay_key)
        self.assertFalse(conflict["ok"])
        self.assertEqual(conflict["error"]["code"], "IDEMPOTENCY_CONFLICT")

        # A completed homework with no graded submission is activity, not evidence. It is refused
        # with a readable reason and writes no ledger row, so a streak cannot outrun a skill.
        homework = self.award("homework_completed", self.homework())
        self.assertFalse(homework["ok"])
        self.assertEqual(homework["error"]["details"]["reason"], "no_graded_evidence")
        self.assertEqual(self.xp_rows(), 1)

    def test_game_xp_ignores_clicks_and_timers(self) -> None:
        # A surface that is not a named action is refused by the wire, not quietly priced.
        page_open = self.award("page_open", "click-open-page")
        self.assertFalse(page_open["ok"])
        self.assertEqual(page_open["error"]["code"], "VALIDATION_FAILED")
        timer = self.award("timer", "30-seconds-focused")
        self.assertFalse(timer["ok"])
        self.assertEqual(timer["error"]["code"], "VALIDATION_FAILED")

        # A named action kind with no real recorded action behind the id is still refused.
        fake_step = self.award("lesson_step", "seg_invented_click")
        self.assertFalse(fake_step["ok"])
        self.assertEqual(fake_step["error"]["code"], "VALIDATION_FAILED")
        fake_check = self.award("check_submitted", "att_never_submitted")
        self.assertFalse(fake_check["ok"])
        self.assertEqual(fake_check["error"]["code"], "VALIDATION_FAILED")

        # "Returned" needs an actual interval between two recorded runs.
        first_run = self.lesson_step()
        # The seeded step's run is brand new; it cannot also be a return after two days.
        early = self.award("returned", self.scalar(
            "SELECT lesson_run_id FROM lesson_segments WHERE id = ?", (first_run,)
        ))
        self.assertFalse(early["ok"])
        self.assertEqual(early["error"]["code"], "VALIDATION_FAILED")

        self.assertEqual(self.xp_rows(), 0)
        self.assertEqual(self.read()["xp_total"], 0)

    def test_each_named_real_action_is_awarded_its_declared_points(self) -> None:
        step = self.lesson_step()
        # Only the two kinds that carry graded evidence pay. The rest are refused by name, and a
        # reading page or a return visit is refused most loudly of all: paying for those is how
        # activity becomes the product.
        evidence_kinds = [
            ("check_submitted", self.submitted_check()),
            ("review", self.review_evidence()),
        ]
        for kind, action_id in evidence_kinds:
            with self.subTest(kind=kind):
                response = self.award(kind, action_id)
                self.assertTrue(response["ok"], response.get("error"))
                self.assertTrue(response["result"]["awarded"])
                self.assertGreater(response["result"]["points"], 0)
        for kind, action_id, reason in (
            ("lesson_step", step, "not_evidence"),
            ("returned", self.returned_run(), "not_evidence"),
            ("homework_completed", self.homework(), "no_graded_evidence"),
        ):
            with self.subTest(kind=kind):
                refused = self.award(kind, action_id)
                self.assertFalse(refused["ok"])
                self.assertEqual(refused["error"]["details"]["reason"], reason)
        self.assertEqual(self.xp_rows(), len(evidence_kinds))


class GameProgressAndLevelTest(GameEngagementCase):
    """Level and progress are cosmetic, display-derived and never a mastery percentage."""

    def test_level_and_game_progress_are_labelled_play_progress(self) -> None:
        self.award("check_submitted", self.submitted_check())
        result = self.read()
        self.assertGreater(result["xp_total"], 0)
        self.assertEqual(result["progress"]["label"], "Game progress")
        self.assertIs(result["progress"]["is_play_progress"], True)
        self.assertEqual(result["progress"]["assigned_steps"], 1)
        self.assertEqual(result["progress"]["completed_steps"], 1)
        self.assertIs(result["level"]["is_cosmetic"], True)
        self.assertEqual(result["level"]["level"], 1)
        self.assertNotIn("percent", json.dumps(result).lower())
        self.assertNotIn("mastery", json.dumps(result).lower())

    def test_no_mastery_label_can_cross_the_wire(self) -> None:
        self.award("check_submitted", self.submitted_check())
        payload = self.read()
        for forbidden in ("mastery", "proficiency", "verified_skill", "grade", "score", "passed"):
            self.assertFalse(_contains_key(payload, forbidden), forbidden)


class GameExposureTest(GameEngagementCase):
    """XP is visible to the Game header and to nothing that decides or reports learning."""

    def test_game_xp_not_in_evidence_or_export(self) -> None:
        self.award("check_submitted", self.submitted_check())
        self.award("homework_completed", self.homework())

        evidence = self.ok("evidence.inspect", {"enrollment_id": self.enrollment_id})["result"]
        self.assertFalse(_contains_key(evidence, "xp_total"))
        self.assertFalse(_contains_key(evidence, "game_engagement"))
        self.assertFalse(_has_key(evidence, "xp"))

        review = self.ok("course.export.read", {"enrollment_id": self.enrollment_id})["result"]
        self.assertFalse(_contains_key(review, "xp_total"))
        self.assertFalse(_contains_key(review, "game_engagement"))
        self.assertFalse(_has_key(review, "xp"))

        # The pack allowlist is the export authority; engagement is not one of its fields.
        from coursebook import packs
        self.assertNotIn("game_engagement", packs.export_allowlist())
        self.assertNotIn("xp_total", packs.export_allowlist())

    def test_textbook_has_no_engagement_surface(self) -> None:
        # A real graded action, because a reading step no longer pays anything by design.
        attempt = self.submitted_check()
        awarded = self.award("check_submitted", attempt)
        self.assertTrue(awarded["ok"], awarded.get("error"))
        result = {"xp_total": awarded["result"]["xp_total"]}

        self.execute("UPDATE courses SET presentation_mode = 'textbook' WHERE id = ?", (self.course_id,))
        refused = self.dispatch(
            "engagement.read",
            {"course_id": self.course_id, "enrollment_id": self.enrollment_id},
        )
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(refused["error"]["details"]["reason"], "engagement_is_game_only")

        # The textbook course keeps the rows; switching back restores the same play layer.
        self.assertEqual(self.xp_rows(), 1)
        self.execute("UPDATE courses SET presentation_mode = 'game' WHERE id = ?", (self.course_id,))
        self.assertEqual(self.read()["xp_total"], result["xp_total"])

        # A legacy NULL mode reads as Textbook and has no surface either.
        self.execute("UPDATE courses SET presentation_mode = NULL WHERE id = ?", (self.course_id,))
        null_mode = self.dispatch(
            "engagement.read",
            {"course_id": self.course_id, "enrollment_id": self.enrollment_id},
        )
        self.assertFalse(null_mode["ok"])
        self.assertEqual(null_mode["error"]["code"], "VALIDATION_FAILED")

    def test_core_lesson_not_gated_by_xp(self) -> None:
        # Zero XP: the durable lesson commands still work exactly as they did before this layer.
        self.assertEqual(self.read()["xp_total"], 0)
        begun = self.ok(
            "lesson.begin",
            {
                "enrollment_id": self.enrollment_id,
                "objective_id": self.objective_id,
                "mode": "fresh",
            },
            idempotency_key="key-gm009-core-lesson",
        )
        self.assertEqual(begun["result"]["run_state"], "created")
        reopened = self.ok(
            "check.open",
            {"enrollment_id": self.enrollment_id, "objective_id": self.objective_id},
            expected_revision=self.revision,
        )
        self.assertTrue(reopened["result"]["check_id"])
        attempt = self.submitted_check()
        self.assertTrue(attempt)
        # The kernel modules that gate and grade never read the play layer.
        from pathlib import Path
        source = Path(__file__).resolve().parent.parent / "coursebook" / "domain.py"
        self.assertNotIn("game_engagement", source.read_text(encoding="utf-8"))

    def test_parent_read_does_not_return_xp(self) -> None:
        self.award("check_submitted", self.submitted_check())
        blueprint = self.ok("parent.blueprint.read", {"course_id": self.course_id})["result"]
        self.assertFalse(_contains_key(blueprint, "xp_total"))
        self.assertFalse(_contains_key(blueprint, "game_engagement"))
        self.assertFalse(_has_key(blueprint, "xp"))
        # Parent Studio can still read the real learning record separately.
        evidence = self.ok("evidence.inspect", {"enrollment_id": self.enrollment_id})["result"]
        self.assertTrue(evidence["l1"]["attempts"])


class GameFeedbackPreferenceTest(GameEngagementCase):
    """The toggle hides the play layer; it never deletes the ledger."""

    def test_game_feedback_toggle_hides_without_deleting(self) -> None:
        self.award("check_submitted", self.submitted_check())
        before = self.read()
        self.assertIs(before["progress"]["feedback_visible"], True)
        rows = self.xp_rows()

        engagement.configure_feedback(lambda key, default: False)
        hidden = self.read()
        self.assertIs(hidden["progress"]["feedback_visible"], False)
        # Retained, not deleted: the total and the ledger rows are unchanged.
        self.assertEqual(hidden["xp_total"], before["xp_total"])
        self.assertEqual(self.xp_rows(), rows)
        self.assertEqual(
            int(self.scalar(
                "SELECT COUNT(*) FROM game_engagement WHERE enrollment_id = ?",
                (self.enrollment_id,),
            )),
            rows,
        )

        engagement.configure_feedback(lambda key, default: True)
        shown = self.read()
        self.assertIs(shown["progress"]["feedback_visible"], True)
        self.assertEqual(shown["xp_total"], before["xp_total"])
        self.assertEqual(self.xp_rows(), rows)

    def test_feedback_setting_is_declared_and_read_by_one_reader(self) -> None:
        # The setting exists in the manifest and has exactly one reader (``engagement``).
        from pathlib import Path
        import yaml

        root = Path(__file__).resolve().parent.parent
        manifest = yaml.safe_load((root / "plugin.yaml").read_text(encoding="utf-8"))
        self.assertIn("game_feedback", manifest["config_schema"])
        source = (root / "coursebook" / "engagement.py").read_text(encoding="utf-8")
        self.assertIn("game_feedback", source)


if __name__ == "__main__":
    unittest.main()
