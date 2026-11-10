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

import importlib.util
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from coursebook import archive, packs, workshop
from tests.kernel_support import KernelCase

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "bundled" / "packs"
CATALOG = ROOT / "catalog" / "workshop.v1.json"
BUILDER = PACKS / "build_bundled_packs.py"

#: The owner's rule for this card, verbatim.
FIXTURE_WORDING = re.compile(r"demo|sample|fixture", re.IGNORECASE)

COVER_ATTRIBUTION = (
    "Deterministic cover printed by the Coursebook bundled pack builder from flat geometry; "
    "no model output, no text, no third-party source or media. CC0-1.0."
)

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
    for name in ("content_notes", "safety_notes", "accessibility_notes"):
        fields[name] = "\n".join(str(item) for item in manifest.get(name) or [])
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

    def test_no_manifest_field_anywhere_carries_fixture_wording(self) -> None:
        """The flat scan: a new free-text field cannot escape the field list above.

        ``content_notes``, ``safety_notes`` and ``accessibility_notes`` are rendered in the pack
        preview, so the whole serialized manifest is the honest scope, not a chosen key list.
        """
        for entry in self.entries:
            manifest = manifest_for(entry)
            blob = json.dumps(manifest, ensure_ascii=False)
            matches = sorted({match.group(0).lower() for match in FIXTURE_WORDING.finditer(blob)})
            with self.subTest(pack=entry["pack_id"]):
                self.assertEqual(matches, [], f"{entry['pack_id']} manifest carries {matches}")

    def test_shipped_titles_are_the_course_titles(self) -> None:
        for entry in self.entries:
            manifest = manifest_for(entry)
            with self.subTest(pack=entry["pack_id"]):
                self.assertEqual(manifest["title"], SHIPPED_TITLES[entry["pack_id"]])

    def test_every_cover_artifact_is_cc0_deterministic_and_text_free(self) -> None:
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
                    self.assertEqual(right["license_id"], "CC0-1.0")
                    self.assertEqual(right["attribution"], COVER_ATTRIBUTION)
                    self.assertNotIn("model", str(record.get("text_equivalent") or "").lower())
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


class CoverArtTests(unittest.TestCase):
    """A cover is deterministic geometry printed by the builder — never model art with glyphs.

    The host image model bakes garbled lettering into plates (the live Home shelf showed
    ``Asttomamy``/``Repir Fundamentas`` inside the art). Two checks hold the rule: the committed
    bytes must be the generator's own output, and an OCR pass over the shipped file must find no
    text. The course title is DOM text on the card, never part of the image.
    """

    KINDS = {
        "japanese-affection-context-l0": "japanese",
        "parent-measurement-practice": "parent",
        "technical-pack-literacy": "technical",
    }

    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("cp042_bundled_builder", BUILDER)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load the bundled pack builder")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        cls.builder = builder

    def test_committed_cover_is_the_deterministic_generator_output(self) -> None:
        for pack_id, kind in self.KINDS.items():
            folder = PACKS / pack_id / "content"
            with self.subTest(pack=pack_id):
                self.assertEqual(
                    (folder / "cover-3x2.png").read_bytes(),
                    self.builder.deterministic_cover(kind),
                    "the shipped master must be the generator's bytes, not a hand-placed image",
                )
                self.assertEqual(
                    (folder / "cover-4x5.png").read_bytes(),
                    self.builder.deterministic_cover(kind, portrait=True),
                    "the portrait file must be the generator's mechanical crop",
                )

    def test_generator_draws_no_text(self) -> None:
        """The drawing primitives are flat fills only; there is no font path in the generator."""
        source = BUILDER.read_text(encoding="utf-8")
        for forbidden in ("ImageFont", "ImageDraw", "draw.text", "load_default", "truetype", "PIL"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_ocr_finds_no_glyphs_in_a_shipped_cover(self) -> None:
        engine = shutil.which("tesseract")
        if engine is None:
            self.skipTest("no OCR engine on this host; the generator-output check is the remaining proof")
        checked = 0
        for pack_id, _kind in self.KINDS.items():
            for name in ("cover-3x2.png", "cover-4x5.png"):
                image = PACKS / pack_id / "content" / name
                completed = subprocess.run(
                    [engine, str(image), "stdout"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                recognised = "".join(
                    character for character in completed.stdout if character.isalnum()
                )
                with self.subTest(pack=pack_id, file=name):
                    self.assertEqual(recognised, "", f"OCR read text inside the cover: {recognised!r}")
                    checked += 1
        self.assertEqual(checked, 6)


class PackContentShippingTests(unittest.TestCase):
    """Lesson content is served verbatim, so the words in it are user-visible.

    ``coursebook/pack_flow.py`` writes each declared ``section`` file straight into
    ``lesson_segments``; a section or source note that calls the course a demo is shown to the
    learner exactly as written. Scanning the manifest's metadata alone is a false green, so every
    declared text file is scanned here in its staged bytes.
    """

    #: Roles whose declared bytes are prose a learner reads. ``mime`` is the authority; the role
    #: list is the coverage assertion below, so a new prose role cannot slip past unread.
    PROSE_ROLES = ("section", "source_note", "learner_page", "parent_guide", "answer_guide")

    @classmethod
    def setUpClass(cls) -> None:
        cls.entries = catalog_entries()
        cls.manifests = {
            entry["pack_id"]: manifest_for(entry) for entry in cls.entries
        }

    def declared_text_files(self, manifest: dict) -> list[dict]:
        declared = []
        for entry in manifest["files"]:
            mime = str(entry.get("mime") or "")
            if mime.startswith("text/") or str(entry["path"]).endswith((".md", ".txt")):
                declared.append(entry)
        return declared

    def test_every_declared_text_file_is_free_of_fixture_wording(self) -> None:
        for pack_id, manifest in self.manifests.items():
            directory = PACKS / pack_id
            declared = self.declared_text_files(manifest)
            self.assertTrue(declared, f"{pack_id} declares no text file to scan")
            for entry in declared:
                path = str(entry["path"])
                text = (directory / path).read_bytes().decode("utf-8", "replace")
                for number, line in enumerate(text.splitlines(), start=1):
                    with self.subTest(pack=pack_id, path=path, line=number):
                        self.assertIsNone(
                            FIXTURE_WORDING.search(line),
                            f"{pack_id} serves fixture wording to the learner at {path}:{number}: "
                            f"{line.strip()!r}",
                        )

    def test_every_pack_exposes_the_prose_roles_it_ships(self) -> None:
        for pack_id, manifest in self.manifests.items():
            roles = {str(entry.get("role")) for entry in manifest["files"]}
            with self.subTest(pack=pack_id):
                self.assertTrue(roles & {"section", "learner_page"}, f"{pack_id} ships no taught page")
                self.assertTrue(
                    roles & {"source_note", "parent_guide", "answer_guide"},
                    f"{pack_id} ships no supporting prose",
                )
                # No prose role may exist that ``declared_text_files`` would skip silently.
                extra = roles - set(self.PROSE_ROLES) - {"cover", "visual", "narration", "manifest"}
                self.assertEqual(extra, set(), f"{pack_id} ships an unscanned role: {sorted(extra)}")


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
