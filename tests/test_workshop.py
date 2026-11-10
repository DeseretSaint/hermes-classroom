"""H-196 — the Workshop catalogue and bundled installer.

The catalogue is editorial data; identity, hashes, structure and trust facts are re-derived from
each pack's own manifest at read time. These tests run against the real bundled fixtures, a real
migrated profile database and the real import gate.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from coursebook import archive, pack_flow, packs, workshop
from tests.kernel_support import KernelCase, request

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog" / "workshop.v1.json"
PACKS = ROOT / "bundled" / "packs"


class CatalogDocumentTests(unittest.TestCase):
    """The catalogue is bounded data, and every entry names a real, verified pack."""

    def test_catalogue_lists_three_real_bundled_packs(self) -> None:
        document = workshop.load_catalog()
        entries = document["packs"]
        self.assertEqual(len(entries), 3)
        self.assertEqual(
            sorted(entry["pack_id"] for entry in entries),
            ["japanese-affection-context-l0", "parent-measurement-practice", "technical-pack-literacy"],
        )

    def test_every_entry_matches_its_manifest_and_verifies(self) -> None:
        document = workshop.load_catalog()
        for entry in document["packs"]:
            with self.subTest(pack=entry["pack_id"]):
                manifest, trust = workshop._read_entry(entry)
                self.assertEqual(str(manifest["content_hash"]), entry["content_hash"])
                self.assertEqual(str(manifest["pack_version"]), entry["pack_version"])
                self.assertTrue(trust["integrity"]["hashes_match"])
                self.assertIn("integrity_verified", trust["trust"]["labels"])
                self.assertIn("automated_checks_passed", trust["trust"]["labels"])

    def test_catalogue_entries_cannot_name_a_path(self) -> None:
        for slug in ("../japanese-affection-context-l0", "/etc", "japanese affection", "", "..", "pack/name"):
            with self.subTest(slug=slug):
                with self.assertRaises(workshop.WorkshopError):
                    workshop._bundled_directory(slug)

    def test_catalogue_is_editorial_only(self) -> None:
        """No rating, learner count, price or publication field may enter the catalogue."""
        document = json.loads(CATALOG.read_text(encoding="utf-8"))
        forbidden = {"rating", "ratings", "reviews", "price", "learners", "students", "installs", "published"}
        for entry in document["packs"]:
            with self.subTest(pack=entry["pack_id"]):
                self.assertEqual(forbidden & set(entry), set())
        self.assertEqual(forbidden & set(document), set())

    def test_a_catalogue_hash_that_drifted_is_refused_not_rendered(self) -> None:
        document = json.loads(CATALOG.read_text(encoding="utf-8"))
        document["packs"][0]["content_hash"] = "sha256:" + "0" * 64
        original = workshop.CATALOG_PATH
        scratch = Path(tempfile.mkdtemp(prefix="coursebook-workshop-"))
        self.addCleanup(shutil.rmtree, scratch, True)
        path = scratch / "workshop.v1.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        workshop.CATALOG_PATH = path
        try:
            view = workshop.catalog_view()
        finally:
            workshop.CATALOG_PATH = original
        self.assertEqual(view["count"], 2)
        self.assertEqual(len(view["refused"]), 1)
        self.assertEqual(view["refused"][0]["pack_id"], document["packs"][0]["pack_id"])
        self.assertNotIn(
            document["packs"][0]["pack_id"], [item["pack_id"] for item in view["items"]]
        )


class InstallTests(KernelCase):
    """Add to library is one catalogued id, one atomic import, and never a duplicate."""

    def setUp(self) -> None:
        super().setUp()
        # The staging area is cached per data root; point it at this test's home.
        pack_flow._STAGING.clear()

    def tearDown(self) -> None:
        pack_flow._STAGING.clear()
        super().tearDown()

    def test_install_imports_then_returns_the_existing_course(self) -> None:
        first = workshop.install("japanese-affection-context-l0")
        self.assertTrue(first["imported"])
        self.assertTrue(first["course_id"].startswith("crs_"))
        second = workshop.install("japanese-affection-context-l0")
        self.assertFalse(second["imported"])
        self.assertEqual(second["course_id"], first["course_id"])
        self.assertEqual(second["enrollment_id"], first["enrollment_id"])
        library = self.dispatch("library.list", {"filter": "all", "limit": 50})
        self.assertEqual(library["ok"], True, library)
        self.assertEqual(library["result"]["total"], 1)

    def test_install_does_not_touch_learner_history(self) -> None:
        first = workshop.install("technical-pack-literacy")
        before = self.dispatch("library.list", {"filter": "all", "limit": 50})["result"]["items"][0]
        again = workshop.install("technical-pack-literacy")
        after = self.dispatch("library.list", {"filter": "all", "limit": 50})["result"]["items"][0]
        self.assertEqual(again["enrollment_id"], first["enrollment_id"])
        self.assertEqual(before["updated_at"], after["updated_at"])
        self.assertEqual(before["revision"], after["revision"])
        self.assertEqual(before["evidence_summary"], after["evidence_summary"])

    def test_install_refuses_an_unknown_or_traversing_id(self) -> None:
        for pack_id in ("../japanese-affection-context-l0", "not-a-pack", ""):
            with self.subTest(pack_id=pack_id):
                with self.assertRaises(workshop.WorkshopError):
                    workshop.install(pack_id)
        self.assertEqual(self.dispatch("library.list", {"filter": "all", "limit": 50})["result"]["total"], 0)

    def test_install_is_the_only_write_and_carries_no_learner_data(self) -> None:
        """The install result names the course, never a transcript, note or attempt."""
        result = workshop.install("technical-pack-literacy")
        forbidden = {"transcript", "notes", "attempts", "mastery", "reflections", "credentials", "path"}
        self.assertEqual(forbidden & set(result), set())
        self.assertNotIn("path", json.dumps(result).lower())


class CatalogViewTests(KernelCase):
    """The Discover read is one call, and its cover is a real artifact only when one exists."""

    def setUp(self) -> None:
        super().setUp()
        pack_flow._STAGING.clear()

    def tearDown(self) -> None:
        pack_flow._STAGING.clear()
        super().tearDown()

    def test_typographic_fallback_before_install(self) -> None:
        view = workshop.catalog_view()
        self.assertEqual(view["count"], 3)
        by_id = {item["pack_id"]: item for item in view["items"]}
        japanese = by_id["japanese-affection-context-l0"]
        self.assertEqual(japanese["cover"]["kind"], "typographic")
        self.assertIsNone(japanese["cover"]["artifact_id"])
        self.assertIsNone(japanese["installed"])
        self.assertTrue(all(item["cover"]["kind"] == "typographic" for item in view["items"]))
        self.assertEqual(view["refused"], [])

    def test_sections_and_minutes_are_the_manifest_own_counts(self) -> None:
        manifest = packs.load_manifest(PACKS / "japanese-affection-context-l0" / "pack.json")
        view = workshop.catalog_view()
        item = next(entry for entry in view["items"] if entry["pack_id"] == "japanese-affection-context-l0")
        self.assertEqual(item["objective_count"], len(manifest["objectives"]))
        self.assertEqual(
            item["minutes"], sum(int(objective["estimated_minutes"]) for objective in manifest["objectives"])
        )
        self.assertEqual(
            item["section_count"],
            sum(len(objective["sections"]) for objective in manifest["objectives"]),
        )

    def test_cover_is_the_packs_own_visual_after_install(self) -> None:
        workshop.install("japanese-affection-context-l0")
        view = workshop.catalog_view()
        item = next(entry for entry in view["items"] if entry["pack_id"] == "japanese-affection-context-l0")
        self.assertEqual(item["cover"]["kind"], "artifact")
        self.assertTrue(str(item["cover"]["artifact_id"]).startswith("art_"))
        # H-197: the plate the catalogue names is the plate that is served — not merely "some
        # visual". The artifact's bytes must be the declared cover file, byte for byte.
        document = workshop.load_catalog()
        entry = next(e for e in document["packs"] if e["pack_id"] == "japanese-affection-context-l0")
        manifest, files = archive.read_directory(PACKS / "japanese-affection-context-l0")
        declared = next(f for f in manifest["files"] if f["path"] == entry["cover"]["path"])
        self.assertEqual(declared["role"], "cover")
        self.assertIn("painted", (item["cover"]["alt"] or "").lower())
        # The artifact must resolve through the same media route the lesson uses.
        from coursebook import media

        preview = media.preview_artifact(str(item["cover"]["artifact_id"]))
        self.assertEqual(preview["ok"], True, preview)
        self.assertTrue(str(preview.get("data_url") or "").startswith("data:image/png"))
        served = base64.b64decode(str(preview["data_url"]).split(",", 1)[1])
        self.assertEqual(packs.file_sha256(served), declared["sha256"])
        self.assertEqual(served, files[entry["cover"]["path"]])

    def test_installed_pack_carries_the_real_next_step(self) -> None:
        workshop.install("parent-measurement-practice")
        view = workshop.catalog_view()
        item = next(entry for entry in view["items"] if entry["pack_id"] == "parent-measurement-practice")
        self.assertIsNotNone(item["installed"])
        self.assertIn(item["installed"]["next_step"]["kind"], {"start_lesson", "resume_lesson"})
        self.assertEqual(item["installed"]["evidence_summary"]["total_objectives"], 2)

    def test_trust_labels_are_separate_and_never_a_safe_claim(self) -> None:
        view = workshop.catalog_view()
        forbidden = {"safe", "verified", "approved", "recommended", "score", "rating"}
        for item in view["items"]:
            with self.subTest(pack=item["pack_id"]):
                self.assertTrue(item["validated"])
                self.assertIn("integrity_verified", item["trust_labels"])
                self.assertIn("automated_checks_passed", item["trust_labels"])
                self.assertNotIn("human_review_recorded", item["trust_labels"])
                self.assertEqual(forbidden & set(item), set())


class RouteTests(unittest.TestCase):
    """The two host seams return data for every refusal; neither takes a path."""

    def test_routes_are_registered_and_take_no_path(self) -> None:
        source = (ROOT / "dashboard" / "plugin_api.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/workshop/catalog")', source)
        self.assertIn('@router.post("/workshop/install")', source)
        start = source.index('@router.post("/workshop/install")')
        block = source[start : start + 2500]
        self.assertNotIn('body.get("path")', block)
        self.assertIn('body.get("pack_id")', block)


if __name__ == "__main__":
    unittest.main()
