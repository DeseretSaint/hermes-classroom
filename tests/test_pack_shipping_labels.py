"""CP-042 — the bundled packs are store courses, not demo/sample/fixture props.

The owner ruling of 2026-11-10 ships these courses in the Workshop store: a user adds them to a
library from Discover like any other course. These tests pin the two facts that ruling depends on:

* every bundled pack declares a real licence and ``redistribution == "allowed"``;
* nothing a user can read in the Workshop — pack title, subtitle, level label, licence note,
  attribution, contributors, or the catalogue's editorial copy — is labelled demo, sample or
  fixture.
and one rights fact for the model-produced covers: CC-BY-4.0 with the shipping attribution.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from coursebook import archive, packs, workshop
from tests.kernel_support import KernelCase

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "bundled" / "packs"
CATALOG = ROOT / "catalog" / "workshop.v1.json"

#: The owner's rule for this card, verbatim.
FIXTURE_WORDING = re.compile(r"demo|sample|fixture", re.IGNORECASE)

COVER_ATTRIBUTION = "Model-generated cover produced for this pack; no third-party source or media."

#: ``pack_id -> the exact title the store must show``.
SHIPPED_TITLES = {
    "japanese-affection-context-l0": "Japanese register: affection and closeness",
    "parent-measurement-practice": "Measuring together: a kitchen lesson",
    "technical-pack-literacy": "Reading a pack before you install it",
}


def catalog_entries() -> list[dict]:
    document = json.loads(CATALOG.read_text(encoding="utf-8"))
    return list(document["packs"])


def manifest_for(entry: dict) -> dict:
    manifest, _files = archive.read_directory(PACKS / entry["directory"])
    return manifest


def user_visible_strings(manifest: dict) -> dict[str, str]:
    """The manifest fields the Workshop renders to a learner, flattened to text."""
    fields: dict[str, str] = {
        "title": str(manifest.get("title") or ""),
        "subtitle": str(manifest.get("subtitle") or ""),
        "level_label": str(manifest.get("level_label") or ""),
        "attribution": str(manifest.get("attribution") or ""),
        "license.id": str((manifest.get("license") or {}).get("id") or ""),
        "license.note": str((manifest.get("license") or {}).get("note") or ""),
        "license.redistribution": str((manifest.get("license") or {}).get("redistribution") or ""),
    }
    for index, contributor in enumerate(manifest.get("contributors") or []):
        fields[f"contributors[{index}].name"] = str(contributor.get("name") or "")
        fields[f"contributors[{index}].role"] = str(contributor.get("role") or "")
    return fields


class ManifestShippingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entries = catalog_entries()

    def test_every_bundled_pack_is_a_real_licensed_store_course(self) -> None:
        self.assertEqual(len(self.entries), 3)
        for entry in self.entries:
            manifest = manifest_for(entry)
            with self.subTest(pack=entry["pack_id"]):
                self.assertEqual(manifest["pack_id"], entry["pack_id"])
                license_block = manifest["license"]
                self.assertNotEqual(license_block["id"], "unspecified")
                self.assertEqual(license_block["id"], "CC-BY-4.0")
                self.assertEqual(license_block["redistribution"], "allowed")
                self.assertIn("Operator-directed redistribution, 2026-11-10", license_block["note"])

    def test_every_user_visible_manifest_field_is_free_of_fixture_wording(self) -> None:
        for entry in self.entries:
            manifest = manifest_for(entry)
            for field, text in user_visible_strings(manifest).items():
                with self.subTest(pack=entry["pack_id"], field=field):
                    self.assertIsNone(
                        FIXTURE_WORDING.search(text),
                        f"{entry['pack_id']} {field} still reads as a fixture: {text!r}",
                    )

    def test_shipped_titles_are_the_course_titles(self) -> None:
        for entry in self.entries:
            manifest = manifest_for(entry)
            with self.subTest(pack=entry["pack_id"]):
                self.assertEqual(manifest["title"], SHIPPED_TITLES[entry["pack_id"]])

    def test_every_cover_artifact_is_cc_by_with_the_shipping_attribution(self) -> None:
        checked = 0
        for entry in self.entries:
            manifest = manifest_for(entry)
            covers = {
                str(item["path"]): item
                for item in manifest["files"]
                if str(item.get("role")) == "cover"
            }
            self.assertTrue(covers, f"{entry['pack_id']} declares no cover file")
            records = {
                str(item["path"]): item
                for item in (manifest["license"].get("per_artifact") or [])
            }
            for path, record in covers.items():
                with self.subTest(pack=entry["pack_id"], path=path):
                    self.assertIn(path, records, "a cover needs its own per-artifact licence record")
                    right = records[path]
                    self.assertEqual(right["license_id"], "CC-BY-4.0")
                    self.assertEqual(right["attribution"], COVER_ATTRIBUTION)
                    checked += 1
        self.assertEqual(checked, 6, "three packs x (3:2 master + 4:5 crop)")

    def test_catalog_editorial_copy_is_free_of_fixture_wording(self) -> None:
        for entry in self.entries:
            texts = [entry.get("outcome") or "", entry.get("creator_note") or ""]
            texts += [str(item) for item in entry.get("will_not_teach") or []]
            texts += [str(item.get("note") or "") for item in entry.get("changelog") or []]
            texts += [str(item.get("caption") or "") for item in [entry.get("cover") or {}]]
            for text in texts:
                with self.subTest(pack=entry["pack_id"], text=text[:60]):
                    self.assertIsNone(
                        FIXTURE_WORDING.search(text),
                        f"{entry['pack_id']} catalogue copy still reads as a fixture: {text!r}",
                    )


class CatalogSurfaceTests(KernelCase):
    """The serialized read model the Desktop renders, scanned field by field."""

    def test_catalog_view_renders_no_fixture_wording(self) -> None:
        view = workshop.catalog_view()
        self.assertEqual(view["refused"], [])
        self.assertEqual(view["count"], 3)
        blob = json.dumps(view["items"], ensure_ascii=False)
        matches = sorted({match.group(0).lower() for match in FIXTURE_WORDING.finditer(blob)})
        self.assertEqual(matches, [], f"the Workshop surface still shows fixture wording: {matches}")
        self.assertEqual(sorted(item["pack_id"] for item in view["items"]), sorted(SHIPPED_TITLES))

    def test_catalog_view_shows_the_new_titles(self) -> None:
        view = workshop.catalog_view()
        titles = {item["pack_id"]: item["title"] for item in view["items"]}
        self.assertEqual(titles, SHIPPED_TITLES)


if __name__ == "__main__":
    unittest.main()
