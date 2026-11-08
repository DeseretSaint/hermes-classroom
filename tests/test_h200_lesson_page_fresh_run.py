"""H-200 — a fresh run must not blank the served page, and a live check must stay reachable.

The measured defect (H-178b, live rig 127.0.0.1:44219): pressing **"Start a fresh run"** on a
pack-authored section replaced the served document with ``state: "empty"``, ``blocks: []``,
``check_id: null`` while the objective's check stayed ``state: "open"``. The page's teaching rows
were still on disk under the abandoned run; ``lesson.page`` read only the *newest* run's segments,
and ``lesson.begin`` created that newest run empty.

These tests exercise the real read path (``lesson.page`` through ``api.dispatch``) against a real
SQLite database:

* a fresh run carries the durable teaching rows forward, so the served page keeps its blocks and
  its open check (fails on 98aedde: the new run had no segments);
* a database already damaged by the old behaviour — an empty newest run above a run that holds the
  page — is still served from the run that has the rows, while the runtime keeps reporting the
  newest (session) run;
* the cold check keeps ``state = "open"`` and ``attempt_count = 0`` across the fresh run.
"""

from __future__ import annotations

import unittest

from tests.kernel_support import KernelCase, numeric_spec


class FreshRunPageCase(KernelCase):
    def _seed_section(self) -> dict:
        """A section whose page is durable teaching rows, the shape a pack import writes."""
        course_id, plan_id = self.new_course()
        objective_id = self.seed_objective(plan_id, numeric_spec())
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        begun = self.ok(
            "lesson.begin",
            {"enrollment_id": enrollment_id, "objective_id": objective_id, "mode": "fresh"},
            idempotency_key="h200-seed-begin",
        )["result"]
        run_id = begun["lesson_run_id"]
        self.execute(
            "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, created_at)"
            " VALUES (?, ?, 1, 'teaching', ?, '2026-11-08T00:00:00Z')",
            ("seg_h200_teaching", run_id, "Lesson 2 — choosing by addressee and setting."),
        )
        self.execute(
            "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, created_at)"
            " VALUES (?, ?, 2, 'check_prompt', ?, '2026-11-08T00:00:00Z')",
            ("seg_h200_prompt", run_id, "Context: an adult speaker addressing a respected adult."),
        )
        opened = self.ok(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
            idempotency_key="h200-seed-check",
        )["result"]
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "objective_id": objective_id,
            "enrollment_id": enrollment_id,
            "run_id": run_id,
            "check_id": opened["check_id"],
        }

    def _page(self, section: dict) -> dict:
        result = self.ok(
            "lesson.page",
            {"enrollment_id": section["enrollment_id"], "objective_id": section["objective_id"]},
        )["result"]
        return result

    def test_fresh_run_keeps_blocks_and_the_open_check(self) -> None:
        section = self._seed_section()
        before = self._page(section)
        self.assertGreater(len(before["document"]["blocks"]), 0)
        self.assertEqual(before["document"]["check_id"], section["check_id"])

        again = self.ok(
            "lesson.begin",
            {
                "enrollment_id": section["enrollment_id"],
                "objective_id": section["objective_id"],
                "mode": "fresh",
            },
            idempotency_key="h200-second-begin",
        )["result"]
        self.assertNotEqual(again["lesson_run_id"], section["run_id"])

        after = self._page(section)
        # The measured shape this test pins: on 98aedde this was state="empty", blocks=0,
        # check_id=None with the check still open and unreachable.
        self.assertNotEqual(after["document"]["state"], "empty")
        self.assertGreater(len(after["document"]["blocks"]), 0)
        self.assertEqual(after["document"]["check_id"], section["check_id"])
        self.assertEqual(after["runtime"]["lesson_run_id"], again["lesson_run_id"])

        checks = {row["check_id"]: row for row in after["checks"]}
        self.assertEqual(checks[section["check_id"]]["state"], "open")
        self.assertEqual(checks[section["check_id"]]["attempt_count"], 0)

    def test_page_reads_the_newest_run_that_carries_segments(self) -> None:
        """The already-damaged shape: an empty newest run above the run that holds the page."""
        section = self._seed_section()
        # A blank run above the content, exactly as the old fresh-run defect left the live store.
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision,"
            " created_at, updated_at, last_opened_at)"
            " VALUES ('run_h200_blank', ?, ?, 'active', 0, '2099-01-01T00:00:00Z',"
            " '2099-01-01T00:00:00Z', '2099-01-01T00:00:00Z')",
            (section["enrollment_id"], section["objective_id"]),
        )
        page = self._page(section)
        self.assertGreater(len(page["document"]["blocks"]), 0)
        self.assertNotEqual(page["document"]["state"], "empty")
        self.assertEqual(page["document"]["check_id"], section["check_id"])
        # The runtime still reports the newest (session) run, not the page source.
        self.assertEqual(page["runtime"]["lesson_run_id"], "run_h200_blank")


if __name__ == "__main__":
    unittest.main()
