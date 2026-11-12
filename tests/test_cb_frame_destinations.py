"""The destination frame registry covers every destination, and names its sources.

`scripts/cb-frame.py --all` is the one command that photographs the route destinations the fleet
rule reviews. This test pins the two properties a reviewer relies on without running the renderer:

* the registry still covers every destination the UI-K14 card names (a deleted or renamed entry
  would silently drop a surface from the sweep);
* every frame names where its data came from, and every mounted component is exported by the
  shipped module — a frame may not photograph a private copy or an invented fixture.

The rendered artefacts themselves live under `.coursebook/frames` and are not committed; the
manifest schema (`module_sha256`, `fixture_source`, `host_stylesheet`) is asserted against a real
run by the card's evidence, not here.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts import cb_frame_fixtures as fixtures

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = {
    "workshop-discover",
    "workshop-library",
    "workshop-provenance",
    "workshop-pack",
    "courses-list",
    "courses-empty",
    "courses-detail",
    "create-empty",
    "create-single",
    "create-short",
    "create-full",
    "syllabus-intake",
    "syllabus-parse",
    "syllabus-alignment",
    "studio-list",
    "studio-brief",
    "studio-detail",
    "takehome-shelf",
    "homework-studio",
    "home-settings",
}


def _skeleton() -> dict:
    """Enough of the fixture build for `frames()` to resolve ids and sources, no backend."""
    return {
        "runtime": {"ok": True},
        "health": {"ok": True},
        "rest_media": {},
        "catalog_fresh": {"items": []},
        "catalog_installed": {"items": []},
        "install": {"ok": True},
        "library_empty": {"result": {"items": [], "total": 0}},
        "library_full": {"result": {"items": [], "total": 0}},
        "packs": {"result": {"items": []}},
        "course_row": {"course_id": "c", "enrollment_id": "e", "title": "Course"},
        "course_id": "c",
        "enrollment_id": "e",
        "objective_id": "o",
        "detail_rpc": {},
        "installed_item": {"pack_id": "p", "title": "P"},
        "parent_list": {"result": {"items": []}},
        "parent_course_row": {"course_id": "c2", "enrollment_id": "e2"},
        "parent_detail_rpc": {},
        "homework_library": {"result": {"items": []}},
        "homework_sources": {"result": {"objectives": []}},
        "homework_read": {"result": {"task": {"task_id": "t"}}},
        "homework_store": {},
        "syllabus_parse": {"blocks": []},
        "syllabus_alignment": {"items": []},
        "implemented": ["library.list"],
        "sources": {},
        "create_goal": "g",
        "create_dials": {},
        "create_scopes": ["single", "short", "full"],
    }


def _module_exports() -> set[str]:
    text = (ROOT / "desktop" / "src" / "99-tutor.js").read_text(encoding="utf-8")
    block = re.search(r"\nexport \{(.*?)\n\}", text, flags=re.S)
    if block is None:
        raise AssertionError("99-tutor.js has no named export block")
    # The block carries section comments (`// Home (CP-022, 30-home.js)`) between names; they are
    # not exports and a naive comma split would treat them as ones.
    names = re.sub(r"//[^\n]*", "", block.group(1))
    return {name.strip() for name in names.split(",") if name.strip()}


class DestinationRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.frames = fixtures.frames(_skeleton())

    def test_registry_covers_every_destination_the_card_names(self) -> None:
        ids = {frame["id"] for frame in self.frames}
        self.assertEqual(sorted(REQUIRED - ids), [], "destinations dropped from the sweep")
        self.assertEqual(sorted(ids - REQUIRED), [], "unexpected destination ids")

    def test_every_destination_has_one_frame_per_scope(self) -> None:
        ids = [frame["id"] for frame in self.frames]
        self.assertEqual(len(ids), len(set(ids)), "duplicate frame id")
        self.assertEqual(sum(1 for name in ids if name.startswith("create-")), 4)

    def test_every_frame_names_its_fixture_source(self) -> None:
        for frame in self.frames:
            self.assertTrue(frame.get("source"), f"{frame['id']} names no fixture source")
            self.assertIsInstance(frame["source"], list)
            self.assertIn("implemented", frame)
            # Each source label must be one the fixture builder documents, so a manifest cannot
            # cite a name nobody can trace back to a real read.
            for label in frame["source"]:
                self.assertIn(label, fixtures_known_sources(), f"{frame['id']} cites unknown source {label}")

    def test_every_mounted_surface_is_exported_by_the_shipped_module(self) -> None:
        exports = _module_exports()
        for frame in self.frames:
            self.assertIn(
                frame["surface"],
                exports,
                f"{frame['id']} mounts {frame['surface']}, which the shipped module does not export",
            )


def fixtures_known_sources() -> set[str]:
    """The source keys the fixture builder documents (the labels a manifest may cite)."""
    return {
        "catalog_fresh",
        "catalog_installed",
        "library_empty",
        "library_full",
        "course_row",
        "course_detail",
        "pack_list",
        "parent",
        "homework",
        "syllabus",
        "create",
        "settings",
    }


if __name__ == "__main__":
    unittest.main()
