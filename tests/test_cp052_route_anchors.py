"""CP-052: a plate that declares `route_anchors` is read back, not rejected by its own schema.

CP-024's course home places a section on the plate when the stored plate manifest declares that
section's normalised 0–1 coordinate. A stored brief that carried the field made `world.read` fail
its own response validation: the closed `world_brief` record refused the key and the `oneOf` on
`world` collapsed the detail into ``INTERNAL_ERROR … not valid under any of the given schemas``.

Everything here runs through ``api.dispatch`` against the real migrated SQLite store. Rows are
labelled fixtures: they are inserted directly to model a plate manifest that declares geometry —
no course content is authored and no provider is called.
"""

from __future__ import annotations

import json
import unittest

from coursebook import db, world

from tests.kernel_support import KernelCase, numeric_spec


def anchors(section_ids: list[str]) -> list[dict]:
    """Three valid anchors for the first three sections of a fixture plate."""
    return [
        {"anchor_id": f"anc_{index:031d}", "section_id": section_id, "x": x, "y": y}
        for index, (section_id, x, y) in enumerate(
            zip(section_ids, (0.18, 0.51, 0.82), (0.72, 0.44, 0.19)), start=1
        )
    ]


class RouteAnchorReadTest(KernelCase):
    """The wire: one read, three plates (anchored, bare, malformed), real database."""

    def seed_plate(self, route_anchors=None, *, state: str = "approved") -> tuple[str, dict]:
        """Fixture: create a course with three objectives and store one world row for it.

        ``route_anchors`` is called with the derived section ids when it is a callable.
        """
        course_id, plan_id = self.new_course(title="Fixture: route anchors")
        for index in range(3):
            self.seed_objective(plan_id, numeric_spec(str(index + 1)))
        with db.read() as connection:
            brief = world._derive_brief(connection, course_id).as_dict()
        section_ids = [item["id"] for item in brief["sections"]]
        self.assertEqual(len(section_ids), 3, "the fixture needs three sections")
        if callable(route_anchors):
            brief["route_anchors"] = route_anchors(section_ids)
        elif route_anchors is not None:
            brief["route_anchors"] = route_anchors
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO course_worlds (id, course_id, revision, state, brief_json,"
                " concepts_json, created_at, updated_at)"
                " VALUES (?, ?, 1, ?, ?, '[]', '2026-11-10T00:00:00Z', '2026-11-10T00:00:00Z')",
                (f"wld_fixture_{course_id[-8:]}", course_id, state, json.dumps(brief)),
            )
        return course_id, brief

    def test_three_valid_anchors_read_back_byte_identical(self) -> None:
        course_id, brief = self.seed_plate(anchors)
        declared = brief["route_anchors"]
        response = self.ok("world.read", {"course_id": course_id})
        read = response["result"]["world"]["brief"]["route_anchors"]
        self.assertIsInstance(read, list)
        self.assertEqual(read, declared)
        # Order and every key survive: the read never normalises, sorts or re-derives a coordinate.
        self.assertEqual(json.dumps(read), json.dumps(declared))
        # Twice in a row, because this is a read and must not depend on row mutation.
        again = self.ok("world.read", {"course_id": course_id})
        self.assertEqual(again["result"]["world"]["brief"]["route_anchors"], declared)

    def test_the_same_plate_with_no_anchors_reads_exactly_as_before(self) -> None:
        course_id, brief = self.seed_plate()
        response = self.ok("world.read", {"course_id": course_id})
        read = response["result"]["world"]["brief"]
        self.assertNotIn("route_anchors", read, "an absent plate must not grow an empty array")
        self.assertEqual(read, brief)
        self.assertEqual(response["result"]["world"]["state"], "approved")
        self.assertIsNone(response["result"]["fallback"])

    def test_an_off_box_coordinate_is_a_field_error_not_an_internal_one(self) -> None:
        built: dict = {}

        def broken(section_ids: list[str]) -> list[dict]:
            built["anchors"] = anchors(section_ids)
            built["anchors"][1]["x"] = 1.4
            return built["anchors"]

        course_id, _brief = self.seed_plate(broken)
        error = self.err("world.read", {"course_id": course_id})
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertNotEqual(error["code"], "INTERNAL_ERROR")
        self.assertEqual(error["details"]["field"], "route_anchors[1].x")
        self.assertEqual(error["details"]["path"], "world.brief.route_anchors[1].x")
        self.assertIn("route_anchors[1].x", error["message"])

    def test_a_missing_section_id_is_a_field_error_not_an_internal_one(self) -> None:
        def broken(section_ids: list[str]) -> list[dict]:
            value = anchors(section_ids)
            del value[2]["section_id"]
            return value

        course_id, _brief = self.seed_plate(broken)
        error = self.err("world.read", {"course_id": course_id})
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["field"], "route_anchors[2].section_id")
        self.assertEqual(error["details"]["path"], "world.brief.route_anchors[2].section_id")

    def test_a_regenerate_carries_the_stored_anchors_forward(self) -> None:
        course_id, brief = self.seed_plate(anchors)
        with db.read() as connection:
            row = connection.execute(
                "SELECT * FROM course_worlds WHERE course_id = ?", (course_id,)
            ).fetchone()
            merged = world._merged_brief(connection, course_id, row, None).as_dict()
        self.assertEqual(merged["route_anchors"], brief["route_anchors"])
        # Nothing else moved either: the merged brief is the stored one plus the derived rows.
        self.assertEqual(merged["sections"], brief["sections"])

    def test_the_anchor_validator_names_each_refusal(self) -> None:
        first = "sec_00000000000000000000000000000001"
        declared_sections = [{"id": first, "title": "One"}]
        valid = {"anchor_id": "anc_00000000000000000000000000000001", "section_id": first,
                 "x": 0.2, "y": 0.3}
        cases = [
            ("route_anchors[0].y", {"sections": [], "route_anchors": [dict(valid, y=-0.1)]}),
            ("route_anchors[0].x", {"sections": [], "route_anchors": [dict(valid, x=1.4)]}),
            ("route_anchors[0].anchor_id", {"sections": [], "route_anchors": [dict(valid, anchor_id="")]}),
            (
                "route_anchors[0].section_id",
                {
                    "sections": declared_sections,
                    "route_anchors": [dict(valid, section_id="sec_00000000000000000000000000000009")],
                },
            ),
            ("route_anchors[0].x_pct", {"sections": [], "route_anchors": [dict(valid, x_pct=0.2)]}),
            ("route_anchors[0]", {"sections": [], "route_anchors": ["0.2,0.3"]}),
            ("route_anchors", {"sections": [], "route_anchors": {"x": 0.2}}),
        ]
        for field, brief in cases:
            with self.subTest(field=field):
                problem = world.route_anchor_problems(brief)
                self.assertIsNotNone(problem)
                self.assertEqual(problem[0] if problem else None, field)
        duplicate = [dict(valid), dict(valid)]
        problem = world.route_anchor_problems({"sections": [], "route_anchors": duplicate})
        self.assertEqual(problem[0] if problem else None, "route_anchors[1].anchor_id")

    def test_a_plate_without_anchors_has_no_anchor_problem(self) -> None:
        self.assertIsNone(world.route_anchor_problems({"sections": []}))
        self.assertIsNone(world.route_anchor_problems({"sections": [], "route_anchors": []}))

    def test_a_caller_cannot_patch_anchors_onto_a_plate(self) -> None:
        course_id, _brief = self.seed_plate()
        error = self.err(
            "world.generate",
            {
                "course_id": course_id,
                "stage": "concepts",
                "brief_patch": {"route_anchors": []},
            },
            expected_revision=1,
            idempotency_key="cp052-patch-anchors",
        )
        # `brief_patch` is a closed presentation-only object: anchors are the plate's own
        # declaration, not a caller's art direction, so the request is refused before any job.
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertIn("brief_patch", json.dumps(error))
        # The refusal changed nothing: the stored world is still the one the fixture wrote.
        read = self.ok("world.read", {"course_id": course_id})["result"]
        self.assertEqual(read["world"]["state"], "approved")


class RouteAnchorWriteCarryTest(unittest.TestCase):
    """The other half of the defect: `WorldBrief` used to drop the field it did not know."""

    def test_from_mapping_and_as_dict_carry_anchors_verbatim(self) -> None:
        declared = anchors([f"sec_{index:032d}" for index in (1, 2, 3)])
        brief = world.WorldBrief.from_mapping(
            {
                "course_id": "crs_00000000000000000000000000000001",
                "title": "Fixture",
                "sections": [{"id": declared[0]["section_id"], "title": "One"}],
                "route_anchors": declared,
            }
        )
        self.assertEqual([dict(item) for item in brief.route_anchors], declared)
        self.assertEqual(brief.as_dict()["route_anchors"], declared)

    def test_a_brief_without_anchors_writes_no_key(self) -> None:
        brief = world.WorldBrief(course_id="crs_00000000000000000000000000000001", title="Fixture")
        self.assertNotIn("route_anchors", brief.as_dict())
        self.assertEqual(brief.route_anchors, ())

    def test_the_brief_is_not_part_of_the_plate_cache_key(self) -> None:
        # Anchors are geometry, not prompt content: two briefs differing only in anchors must
        # address the same plate bytes.
        declared = anchors([f"sec_{index:032d}" for index in (1, 2, 3)])
        plain = {
            "course_id": "crs_00000000000000000000000000000001",
            "title": "Fixture",
            "subject_domain": "cooking",
            "sections": [{"id": declared[0]["section_id"], "title": "One"}],
        }
        key_plain = world.cache_key(plain, "kitchen_table", "hero", "style-a")
        key_anchored = world.cache_key(
            {**plain, "route_anchors": declared}, "kitchen_table", "hero", "style-a"
        )
        self.assertEqual(key_plain, key_anchored)


if __name__ == "__main__":
    unittest.main()
