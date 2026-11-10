"""CP-005 — the v3 shelf facts: every number and badge on a card comes from one read.

The v3 shelf speaks in sections and checks, not in stars, proofs, ratings or percentages. These
tests hold the backend seam that makes that possible: ``library.list`` returns the seven frozen
``cb.rpc`` v25 fields per item, each one a stored fact or an honest absence, and the UI computes
nothing. The cases the card names — a new course, a course mid-path, a finished course, a
pack-backed course, and a course whose world was rejected — are each exercised against the real
SQLite store, not a fixture of the response shape.

What the fields may never become is asserted too: no rating, no learner count, no percentage, no
invented section total, and no unapproved world plate presented as the course's face.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coursebook import artifacts, contracts, db, workshop
from tests.kernel_support import KernelCase, numeric_spec

#: The additive v25 field set on a ``library_item``. Nothing else was added by CP-005.
SHELF_FIELDS = (
    "sections_done",
    "sections_total",
    "checks_recorded",
    "is_new",
    "subject_label",
    "cover_artifact_id",
    "last_studied_at",
)

#: What a card may never carry: a v3 shelf number is evidence, not a storefront rating.
FORBIDDEN_FIELDS = (
    "rating",
    "stars",
    "review_count",
    "learner_count",
    "enrolled_count",
    "percentage",
    "percent_complete",
    "xp",
    "proofs",
)


class ShelfFactsCase(KernelCase):
    """A course with objectives, an approved plan and a real enrollment."""

    def prepare(
        self,
        *,
        count: int = 3,
        subject_domain: str | None = None,
        title: str = "Learn to braise",
        recipe: str = "committed",
    ) -> dict:
        payload = {"title": title, "recipe": recipe, "goal": "Braise short ribs"}
        if subject_domain is not None:
            payload["subject_domain"] = subject_domain
        created = self.ok("course.create", payload)["result"]
        plan_id = created["plan_id"]
        objective_ids = [self.seed_objective(plan_id, numeric_spec("42.7")) for _ in range(count)]
        enrollment_id = self.new_enrollment(created["course_id"])
        revision = self.approve(enrollment_id, plan_id, 0)
        return {
            "course_id": created["course_id"],
            "plan_id": plan_id,
            "enrollment_id": enrollment_id,
            "objective_ids": objective_ids,
            "revision": revision,
        }

    def pass_objective(self, course: dict, objective_id: str, answer: str = "42.7") -> dict:
        revision = int(
            self.scalar("SELECT revision FROM enrollments WHERE id = ?", (course["enrollment_id"],))
        )
        opened = self.ok(
            "check.open",
            {"enrollment_id": course["enrollment_id"], "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        response = self.submit(
            {
                "enrollment_id": course["enrollment_id"],
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "revision": opened["revision"],
            },
            answer,
        )
        self.assertTrue(response["ok"], response)
        return response["result"]

    def item(self, enrollment_id: str | None = None) -> dict:
        items = self.ok("library.list", {})["result"]["items"]
        if enrollment_id is not None:
            matches = [item for item in items if item["enrollment_id"] == enrollment_id]
            self.assertEqual(len(matches), 1, items)
            return matches[0]
        self.assertEqual(len(items), 1, items)
        return items[0]

    def add_world(self, course_id: str, *, state: str = "approved") -> str:
        """One world row with one cover plate, in *state*; returns the cover artifact id."""
        saved = artifacts.ArtifactStore().save(
            course_id=None,
            kind="visual",
            data=b"\x89PNG\r\n\x1a\n" + b"7" * 32,
            mime="image/png",
            provenance={"generator": "fixture", "notes": "CP-005 world plate"},
        )
        artifact_id = str(saved["artifact_id"])
        now = self.scalar("SELECT strftime('%Y-%m-%dT%H:%M:%SZ', 'now')")
        world_id = f"wld_{course_id}"
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO course_worlds (id, course_id, revision, state, brief_json,"
                " concepts_json, selected_concept_id, style_hash, kit_hash, approved_hash,"
                " approved_at, created_at, updated_at)"
                " VALUES (?, ?, 1, ?, '{}', '[]', 'c1', ?, ?, ?, ?, ?, ?)",
                (
                    world_id,
                    course_id,
                    state,
                    "sha256:" + "c" * 64,
                    "sha256:" + "d" * 64,
                    "sha256:" + "e" * 64 if state == "approved" else None,
                    now if state == "approved" else None,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO world_assets (id, world_id, role, section_id, section_key,"
                " artifact_id, style_hash, prompt_hash, textless, created_at)"
                " VALUES (?, ?, 'cover', NULL, '', ?, ?, ?, 1, ?)",
                (f"was_{world_id}", world_id, artifact_id, "sha256:" + "c" * 64,
                 "sha256:" + "f" * 64, now),
            )
        return artifact_id


class NewCourseTest(ShelfFactsCase):
    def test_one_read_returns_every_shelf_fact_for_a_new_course(self) -> None:
        course = self.prepare(count=3, subject_domain="language")
        item = self.item(course["enrollment_id"])
        self.assertEqual(set(SHELF_FIELDS) <= set(item), True, sorted(item))
        self.assertEqual(item["sections_done"], 0)
        self.assertEqual(item["sections_total"], 3)
        self.assertEqual(item["checks_recorded"], 0)
        self.assertIs(item["is_new"], True)
        self.assertEqual(item["subject_label"], "language")
        self.assertIsNone(item["cover_artifact_id"])
        self.assertIsNone(item["last_studied_at"])

    def test_the_shelf_carries_no_rating_count_or_percentage(self) -> None:
        course = self.prepare(count=1)
        item = self.item(course["enrollment_id"])
        for forbidden in FORBIDDEN_FIELDS:
            self.assertNotIn(forbidden, item, f"library_item carries {forbidden}")
        # Section counts are integers the backend read, never a rendered fraction or a float.
        self.assertIsInstance(item["sections_done"], int)
        self.assertIsInstance(item["sections_total"], int)
        self.assertIsInstance(item["checks_recorded"], int)

    def test_an_undeclared_subject_is_null_not_the_recipe(self) -> None:
        course = self.prepare(count=1)
        item = self.item(course["enrollment_id"])
        self.assertIsNone(item["subject_label"])
        self.assertEqual(item["recipe"], "committed")

    def test_no_plan_objectives_means_zero_sections_not_a_pack_estimate(self) -> None:
        created = self.ok(
            "course.create", {"title": "Empty plan", "recipe": "one_off", "goal": "Learn one thing"}
        )["result"]
        enrollment_id = self.new_enrollment(created["course_id"])
        item = self.item(enrollment_id)
        self.assertEqual(item["sections_done"], 0)
        self.assertEqual(item["sections_total"], 0)
        self.assertIs(item["is_new"], True)


class MidPathTest(ShelfFactsCase):
    def test_mid_path_counts_committed_checks_and_the_last_study_event(self) -> None:
        course = self.prepare(count=3)
        self.pass_objective(course, course["objective_ids"][0])
        item = self.item(course["enrollment_id"])
        self.assertEqual(item["sections_done"], 1)
        self.assertEqual(item["sections_total"], 3)
        self.assertEqual(item["checks_recorded"], 1)
        self.assertIs(item["is_new"], False)
        committed = self.scalar(
            "SELECT MAX(committed_at) FROM attempts WHERE enrollment_id = ?",
            (course["enrollment_id"],),
        )
        self.assertEqual(item["last_studied_at"], committed)

    def test_a_pending_attempt_is_not_a_recorded_check(self) -> None:
        """Only a committed attempt is recorded evidence; a pending one is not a number."""
        course = self.prepare(count=1)
        revision = int(
            self.scalar("SELECT revision FROM enrollments WHERE id = ?", (course["enrollment_id"],))
        )
        opened = self.ok(
            "check.open",
            {"enrollment_id": course["enrollment_id"], "objective_id": course["objective_ids"][0]},
            expected_revision=revision,
        )["result"]
        self.execute(
            "INSERT INTO attempts (id, enrollment_id, check_id, check_version, attempt_nonce,"
            " answer_kind, answer_json, answer_hash, verdict, evidence_class, criteria_json,"
            " grading_provenance_json, state, created_at)"
            " VALUES ('att_pending_cp005', ?, ?, ?, 'nonce-cp005', 'text', '{}', 'sha256:' ||"
            " printf('%064d', 0), NULL, 'cold', '[]', '{}', 'pending',"
            " '2000-01-01T00:00:00Z')",
            (course["enrollment_id"], opened["check_id"], opened["check_version"]),
        )
        item = self.item(course["enrollment_id"])
        self.assertEqual(item["checks_recorded"], 0)
        self.assertIs(item["is_new"], False, "an attempt exists, so the course is not new")
        self.assertEqual(item["last_studied_at"], "2000-01-01T00:00:00Z")


class FinishedCourseTest(ShelfFactsCase):
    def test_a_finished_course_counts_every_section(self) -> None:
        course = self.prepare(count=3)
        for objective_id in course["objective_ids"]:
            self.pass_objective(course, objective_id)
        item = self.item(course["enrollment_id"])
        self.assertEqual(item["sections_total"], 3)
        self.assertEqual(item["sections_done"], 3)
        self.assertEqual(item["checks_recorded"], 3)
        self.assertIs(item["is_new"], False)
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM objectives o JOIN plans pl ON pl.id = o.plan_id"
                " WHERE pl.course_id = ? AND o.state IN ('independent_evidence','delayed_evidence')",
                (course["course_id"],),
            ),
            3,
        )
        # The shelf agrees with the evidence summary it shares a source with, by construction.
        self.assertEqual(item["sections_done"], item["evidence_summary"]["independent"])
        self.assertEqual(item["sections_total"], item["evidence_summary"]["total_objectives"])


class PackBackedCourseTest(ShelfFactsCase):
    PACK = "japanese-affection-context-l0"

    def installed(self) -> dict:
        result = workshop.install(self.PACK)
        self.assertTrue(result["imported"], result)
        return result

    def test_a_pack_backed_course_carries_the_pack_plate(self) -> None:
        installed = self.installed()
        item = self.item(installed["enrollment_id"])
        self.assertIsNotNone(item["cover_artifact_id"])
        # The same plate the storefront serves: one catalogue cover, one artifact, no second read.
        store = next(
            entry for entry in workshop.catalog_view()["items"] if entry["pack_id"] == self.PACK
        )
        self.assertEqual(item["cover_artifact_id"], store["cover"]["artifact_id"])
        self.assertEqual(item["provenance"]["pack_id"], self.PACK)
        self.assertIsNone(item["subject_label"], "a pack import declares no subject domain")
        self.assertGreater(item["sections_total"], 0)
        self.assertEqual(item["sections_total"], item["evidence_summary"]["total_objectives"])
        self.assertIs(item["is_new"], True)
        self.assertIsNone(item["last_studied_at"])

    def test_an_unknown_pack_reports_no_cover_artifact(self) -> None:
        """A pack with no catalogue entry declares no cover; the shelf composes none."""
        installed = workshop.install("parent-measurement-practice")
        item = self.item(installed["enrollment_id"])
        self.assertIsNotNone(item["cover_artifact_id"])
        self.assertIsNotNone(workshop.declared_cover_path_for_pack("parent-measurement-practice"))
        self.assertIsNone(workshop.declared_cover_path_for_pack("no-such-pack"))
        self.assertIsNone(workshop.declared_cover_path_for_pack(None))

    def test_the_first_lesson_visual_is_never_promoted_to_a_cover(self) -> None:
        """With the catalogue's cover withdrawn, the pack's figures stay figures.

        The Japanese pack carries two linked visuals in lesson order. The strict read must return
        None for the cover rather than serve the first one, which is what a loose
        "first visual" lookup would do.
        """
        scratch = Path(tempfile.mkdtemp(prefix="coursebook-cp005-"))
        self.addCleanup(shutil.rmtree, scratch, True)
        document = json.loads(workshop.CATALOG_PATH.read_text(encoding="utf-8"))
        entry = next(e for e in document["packs"] if e["pack_id"] == self.PACK)
        entry.pop("cover", None)
        path = scratch / "workshop.v1.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        original = workshop.CATALOG_PATH
        workshop.CATALOG_PATH = path
        try:
            installed = workshop.install(self.PACK)
            item = self.item(installed["enrollment_id"])
        finally:
            workshop.CATALOG_PATH = original
        self.assertIsNone(item["cover_artifact_id"])
        self.assertIsNotNone(
            self.scalar(
                "SELECT 1 FROM artifacts a JOIN lesson_segments s ON s.artifact_id = a.id"
                " WHERE a.kind = 'visual' LIMIT 1"
            ),
            "the fixture pack is expected to carry visuals; they must not become a cover",
        )

    def test_an_approved_world_plate_wins_over_the_pack_plate(self) -> None:
        installed = self.installed()
        world_cover = self.add_world(installed["course_id"], state="approved")
        item = self.item(installed["enrollment_id"])
        self.assertEqual(item["cover_artifact_id"], world_cover)


class RejectedWorldTest(ShelfFactsCase):
    def test_a_rejected_world_never_supplies_a_cover(self) -> None:
        course = self.prepare(count=1, subject_domain="repair")
        world_cover = self.add_world(course["course_id"], state="failed")
        item = self.item(course["enrollment_id"])
        self.assertIsNone(item["cover_artifact_id"])
        self.assertNotEqual(item["cover_artifact_id"], world_cover)
        # The plate still exists in the artifact store; the shelf simply may not present it.
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM artifacts WHERE id = ?", (world_cover,)), 1
        )

    def test_a_rejected_world_falls_back_to_the_pack_cover(self) -> None:
        installed = workshop.install("japanese-affection-context-l0")
        world_cover = self.add_world(installed["course_id"], state="stale")
        item = self.item(installed["enrollment_id"])
        store = next(
            entry
            for entry in workshop.catalog_view()["items"]
            if entry["pack_id"] == "japanese-affection-context-l0"
        )
        self.assertEqual(item["cover_artifact_id"], store["cover"]["artifact_id"])
        self.assertNotEqual(item["cover_artifact_id"], world_cover)

    def test_approving_the_world_afterwards_makes_its_plate_the_cover(self) -> None:
        course = self.prepare(count=1)
        world_cover = self.add_world(course["course_id"], state="failed")
        self.assertIsNone(self.item(course["enrollment_id"])["cover_artifact_id"])
        self.execute(
            "UPDATE course_worlds SET state = 'approved', approved_at = ? WHERE course_id = ?",
            ("2026-01-01T00:00:00Z", course["course_id"]),
        )
        self.assertEqual(self.item(course["enrollment_id"])["cover_artifact_id"], world_cover)


class ContractFenceTest(unittest.TestCase):
    """The v25 delta itself: seven fields, v24 byte-identical, no new method."""

    def test_v25_is_v24_plus_the_shelf_fact_set(self) -> None:
        v24 = contracts.contract_as("cb.rpc", 24)
        v25 = contracts.contract("cb.rpc")
        self.assertEqual(v25["x-contract-version"], 25)
        self.assertEqual(v25["x-supersedes"], v24["$id"])
        self.assertEqual(
            v25["$defs"]["method"]["enum"], v24["$defs"]["method"]["enum"],
            "CP-005 adds no RPC method; it adds response fields",
        )
        before = v24["$defs"]["library_item"]
        after = v25["$defs"]["library_item"]
        self.assertEqual(set(after["properties"]) - set(before["properties"]), set(SHELF_FIELDS))
        self.assertEqual(set(before["properties"]) - set(after["properties"]), set())
        self.assertEqual(set(before["required"]) - set(after["required"]), set())
        self.assertEqual(set(after["required"]) - set(before["required"]), set(SHELF_FIELDS))

    def test_no_rating_count_or_percentage_property_exists(self) -> None:
        item = contracts.contract("cb.rpc")["$defs"]["library_item"]
        for forbidden in FORBIDDEN_FIELDS:
            self.assertNotIn(forbidden, item["properties"])

    def test_every_shelf_field_is_typed_and_bounded(self) -> None:
        item = contracts.contract("cb.rpc")["$defs"]["library_item"]
        for name in ("sections_done", "sections_total", "checks_recorded"):
            schema = item["properties"][name]
            self.assertEqual(schema["type"], "integer", name)
            self.assertEqual(schema["minimum"], 0, name)
            self.assertIn("maximum", schema, name)
        self.assertEqual(item["properties"]["is_new"]["type"], "boolean")
        self.assertIsNone(item["properties"]["subject_label"].get("minimum"))
        self.assertEqual(item["properties"]["subject_label"]["maxLength"], 60)


if __name__ == "__main__":
    unittest.main()
