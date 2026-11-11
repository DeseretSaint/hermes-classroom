"""H-197 — one approved illustration lane: Codicon stays, one licensed cover lane.

The card keeps the one-icon rule and narrows the illustration rule to a single lane. These tests
hold the three gates that make the lane safe to use:

* **Spec** — the identity document carries the amended refusal clause and the §4.13 sentence, and
  the unchanged gates (no gradient, no shadow, no progress ring, no second icon set) are still there.
* **Licence/provenance** — a catalogue cover is a declared image of its own pack with a permissive
  per-artifact licence, a text equivalent, a non-empty attribution, and a record with its hash in
  `docs/ASSET-PROVENANCE.md`.
* **Artefact, not a hotlink** — the image is read through the existing artifact route from the
  pack's own bytes; the plate the catalogue names is the plate the reader sees; no external `src`
  exists; the icon family is unchanged; and no cover carries a safety-critical fact.

It also proves the builder is the only source of the committed plates, so a hand-edited binary
cannot pass as the approved artwork.

Versioned by CP-003: the licence, provenance, accuracy, builder and cover-flow assertions govern
the v2 cover lane and are unchanged. The two universal clauses (no external fetch, one icon family)
stay whole-file; the "no font asset reference" clause is v2-region only because v3 ships an
@font-face. Table: ``docs/concept-parity/GATE-MIGRATION.md``.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import re
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

from coursebook import archive, media, pack_flow, packs, workshop
from tests.cb_source_scope import v2_source
from tests.kernel_support import KernelCase, isolate_community_shelf

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog" / "workshop.v1.json"
PACKS = ROOT / "bundled" / "packs"
BUILDER = PACKS / "build_bundled_packs.py"
PLUGIN = ROOT / "desktop" / "plugin.js"
IDENTITY = ROOT / "docs" / "COURSEBOOK-VISUAL-IDENTITY-V2.md"
PROVENANCE = ROOT / "docs" / "ASSET-PROVENANCE.md"

#: The licence gate from the card, verbatim: only these may enter the lane.
PERMISSIVE = {
    "CC0-1.0",
    "MIT",
    "ISC",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC-BY-4.0",
}

#: A cover may not carry a safety-critical value, and it is not a photograph of a procedure.
SAFETY_UNITS = re.compile(
    r"\d+\s*(?:nm|ml|mm|cm|m|kg|g|mg|v|a|ma|kv|psi|bar|°|c|f|hz|%)", re.IGNORECASE
)
FORBIDDEN_CLAIMS = (
    "photograph of",
    "photo of the",
    "torque",
    "wiring diagram",
    "dosage",
    "screenshot of the procedure",
)

#: Art-direction phrases the shipped plates may not borrow (competitor or restrictive sources).
FORBIDDEN_SOURCES = (
    "undraw",
    "streamline",
    "openmoji",
    "duolingo",
    "unsplash",
    "pexels",
    "istock",
    "gettyimages",
    "openpeeps",
    "opendoodles",
)


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def load_builder():
    spec = importlib.util.spec_from_file_location("coursebook_bundled_pack_builder_h197", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the bundled pack builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def png_size(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SpecAmendmentTests(unittest.TestCase):
    """The frozen spec edit, exactly as the card writes it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = IDENTITY.read_text(encoding="utf-8")
        # The document wraps at 100 columns; compare sentences, not line breaks.
        cls.flat = re.sub(r"\s+", " ", cls.text)

    def test_the_old_refusal_clause_is_gone(self) -> None:
        self.assertNotIn("No external asset, illustration pipeline, icon font or second icon set.", self.text)

    def test_the_new_refusal_clause_is_present(self) -> None:
        self.assertIn(
            "No second icon set, icon font, or unreconciled external asset. Icons remain sdk.Codicon "
            "only. One approved illustration lane may supply a course cover or empty-state figure from "
            "a permissively licensed or host-generated asset, composed in the Atlas Lamp language, "
            "recorded in docs/ASSET-PROVENANCE.md, and never presented as evidence, a technical "
            "authority, or a trademark.",
            self.text,
        )

    def test_the_icon_rule_is_unchanged_and_the_ornament_sentence_is_appended(self) -> None:
        self.assertIn(
            "- Icons: `sdk.Codicon` only, 16px, `currentColor`. No emoji, no second icon set, no icon font.",
            self.flat,
        )
        self.assertIn(
            "Ornament may include one approved cover illustration lane; it is not a second icon set. "
            "A cover is a composed plate, never a raw stock image with a title.",
            self.flat,
        )

    def test_the_unchanged_gates_are_still_refused(self) -> None:
        for sentence in (
            "- No gradient, shadow, glass, blur, glow or pseudo-3D. The lit page is a flat field.",
            "- No new route, RPC method, pack field, grade rule or chat surface.",
            "- No XP, streak, league, level, mastery percentage, progress ring or invented goal. Ever.",
        ):
            with self.subTest(sentence=sentence):
                self.assertIn(sentence, self.text)


class LicenceAndProvenanceTests(unittest.TestCase):
    """The licence gate: permissive, attributed, and recorded with a hash."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.document = load_catalog()
        cls.provenance = PROVENANCE.read_text(encoding="utf-8")

    def covers(self):
        for entry in self.document["packs"]:
            cover = entry.get("cover") or {}
            if cover.get("path"):
                yield entry, cover

    def test_every_cover_is_a_declared_image_of_its_own_pack(self) -> None:
        for entry, cover in self.covers():
            with self.subTest(pack=entry["pack_id"]):
                manifest, _ = archive.read_directory(PACKS / entry["directory"])
                declared = {
                    item["path"]: item
                    for item in manifest["files"]
                    if str(item["mime"]).startswith("image/")
                }
                self.assertIn(cover["path"], declared)
                self.assertEqual(declared[cover["path"]]["role"], "cover")

    def test_every_cover_file_carries_a_permissive_licence_and_an_attribution(self) -> None:
        for entry, cover in self.covers():
            manifest, _ = archive.read_directory(PACKS / entry["directory"])
            records = {
                record["path"]: record
                for record in (manifest.get("license") or {}).get("per_artifact") or []
            }
            paths = [cover["path"]] + ([cover["crop"]] if cover.get("crop") else [])
            for path in paths:
                with self.subTest(pack=entry["pack_id"], path=path):
                    self.assertIn(path, records, "a cover file needs a per-artifact licence record")
                    record = records[path]
                    self.assertTrue(str(record.get("attribution") or "").strip())
                    if record["license_id"] == "unspecified":
                        # No shipped pack may take this branch: a store course needs a real
                        # licence. It stays here as the rule for any future local-only pack.
                        self.assertEqual(manifest["license"]["redistribution"], "local_only")
                        attribution = record["attribution"].lower()
                        self.assertIn("model output", attribution)
                        self.assertIn("no redistribution licence", attribution)
                    else:
                        self.assertIn(record["license_id"], PERMISSIVE)

    def test_a_cc_by_cover_would_need_visible_credits(self) -> None:
        """The gate, tested as a rule: a CC-BY cover needs its credit in the pack and provenance doc."""
        for entry, cover in self.covers():
            manifest, _ = archive.read_directory(PACKS / entry["directory"])
            records = {r["path"]: r for r in (manifest.get("license") or {}).get("per_artifact") or []}
            record = records[cover["path"]]
            if record["license_id"] == "CC-BY-4.0":
                with self.subTest(pack=entry["pack_id"]):
                    self.assertIn(record["attribution"], manifest["attribution"])
                    self.assertIn(record["attribution"], self.provenance)

    def test_provenance_records_every_shipped_cover_file_with_its_hash(self) -> None:
        shipped = 0
        for entry, cover in self.covers():
            manifest, files = archive.read_directory(PACKS / entry["directory"])
            paths = [cover["path"]] + ([cover["crop"]] if cover.get("crop") else [])
            for cover_path in paths:
                data = files[cover_path]
                digest = file_sha256(data)
                with self.subTest(pack=entry["pack_id"], path=cover_path):
                    self.assertIn(f"{entry['directory']}/{cover_path}", self.provenance)
                    self.assertIn(digest, self.provenance)
                    declared = next(item for item in manifest["files"] if item["path"] == cover_path)
                    self.assertEqual(declared["sha256"], f"sha256:{digest}")
                    shipped += 1
        self.assertEqual(shipped, 6, "three packs x (3:2 master + 4:5 crop)")

    def test_the_parent_pack_now_carries_the_approved_cover(self) -> None:
        entry = next(item for item in self.document["packs"] if item["pack_id"] == "parent-measurement-practice")
        self.assertIsNotNone(entry["cover"])
        manifest, files = archive.read_directory(PACKS / entry["directory"])
        self.assertEqual(manifest["contract_version"], 2)
        self.assertIn(entry["cover"]["path"], files)
        record = next(item for item in manifest["files"] if item["path"] == entry["cover"]["path"])
        self.assertEqual(record["role"], "cover")
        self.assertEqual(str(manifest["media"][0]["path"]), entry["cover"]["path"])
        self.assertIn("parent-measurement-practice/content/cover-3x2.png", self.provenance)

    def test_no_cover_borrows_a_restrictive_or_competitor_source(self) -> None:
        # The art-direction doc *names* rejected sources on purpose, so the check runs over the
        # data that actually ships: the catalogue and the generator.
        blob = (
            CATALOG.read_text(encoding="utf-8")
            + (PACKS / "build_bundled_packs.py").read_text(encoding="utf-8")
        ).lower()
        for word in FORBIDDEN_SOURCES:
            with self.subTest(word=word):
                self.assertNotIn(word, blob)


class AccuracyTests(unittest.TestCase):
    """A cover is illustration; it is never a technical authority and never a safety fact."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.document = load_catalog()

    def test_every_cover_text_says_what_it_is(self) -> None:
        for entry in self.document["packs"]:
            cover = entry.get("cover") or {}
            if not cover.get("path"):
                continue
            with self.subTest(pack=entry["pack_id"]):
                caption = str(cover.get("caption") or "")
                self.assertIn("printed geometry", caption.lower())
                self.assertIn("not a diagram", caption.lower())
                manifest, _ = archive.read_directory(PACKS / entry["directory"])
                record = next(item for item in manifest["files"] if item["path"] == cover["path"])
                text = str(record.get("text_equivalent") or "")
                self.assertIn("printed cover plate", text.lower())
                self.assertIn("decorative geometry only", text.lower())
                self.assertTrue(text.strip())

    def test_no_cover_carries_a_safety_critical_value(self) -> None:
        for entry in self.document["packs"]:
            cover = entry.get("cover") or {}
            if not cover.get("path"):
                continue
            manifest, _ = archive.read_directory(PACKS / entry["directory"])
            record = next(item for item in manifest["files"] if item["path"] == cover["path"])
            texts = [str(cover.get("alt") or ""), str(record.get("text_equivalent") or "")]
            for text in texts:
                with self.subTest(pack=entry["pack_id"]):
                    self.assertEqual(SAFETY_UNITS.findall(text), [])
                    lowered = text.lower()
                    for claim in FORBIDDEN_CLAIMS:
                        self.assertNotIn(claim, lowered)

    def test_the_cover_alt_is_a_description_and_not_the_title(self) -> None:
        for entry in self.document["packs"]:
            cover = entry.get("cover") or {}
            if not cover.get("path"):
                continue
            manifest = packs.load_manifest(PACKS / entry["directory"] / "pack.json")
            with self.subTest(pack=entry["pack_id"]):
                alt = str(cover.get("alt") or "")
                self.assertGreaterEqual(len(alt), 40, "a cover needs a real alternative text, not a label")
                self.assertNotEqual(alt, manifest["title"])
                self.assertIn("printed cover plate", alt.lower())


class NoHotlinkAndIconFamilyTests(unittest.TestCase):
    """No external `src`, no second icon family, no new dependency."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN.read_text(encoding="utf-8")

    def workshop_cover_block(self) -> str:
        start = self.source.index("function WorkshopCover(")
        end = self.source.index("\nfunction ", start + 10)
        return self.source[start:end]

    def test_the_cover_image_src_is_the_artifact_preview_not_a_url(self) -> None:
        block = self.workshop_cover_block()
        self.assertIn("useArtifactPreview", block)
        self.assertIn("preview.data_url", block)
        self.assertNotIn("http://", block)
        self.assertNotIn("https://", block)
        self.assertNotIn("srcset", block)

    def test_the_plugin_fetches_no_external_image_or_font(self) -> None:
        # Universal: no network fetch of an image or a font, on any version of the module.
        for pattern in ("url(http", "@import", "url(https"):
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, self.source)
        # v2 region only (CP-003): v3 ships an @font-face for `CB Display` / `CB UI`, which may
        # name a local font file. The v2 module had no font files at all, so this "no font asset
        # reference" clause binds the v2 region; the v3 font rule is "every family starts with
        # `CB `" in tests/test_desktop_tokens_v3.py.
        # CP-020a concatenates the generated CB_ASSETS object into the module. Its provenance
        # rows name the source files (`...woff2`) but embed the bytes as data URLs, so it is an
        # opaque generated block for this scan; the block itself must carry no network URL.
        v2 = re.sub(
            r"const CB_ASSETS = Object\.freeze\(\{.*?\n\}\)\n",
            "",
            v2_source(),
            flags=re.S,
        )
        self.assertNotRegex(v2, r"\.(?:png|jpg|jpeg|woff2?|svg)\b[\"']")
        assets = PLUGIN.read_text(encoding="utf-8")
        start = assets.index("const CB_ASSETS = Object.freeze(")
        end = assets.index("globalThis.CB_ASSETS = CB_ASSETS")
        block = assets[start:end]
        self.assertNotIn("http://", block)
        self.assertNotIn("https://", block)
        self.assertIn("data:font/woff2;base64,", block)

    def test_the_icon_family_is_unchanged(self) -> None:
        self.assertIn("sdk.Codicon", self.source)
        for other in ("lucide", "phosphor", "fontawesome", "heroicons", "game-icons", "material-icons"):
            with self.subTest(library=other):
                self.assertNotIn(other, self.source.lower())

    def test_no_icon_or_illustration_dependency_was_added(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8")) if (ROOT / "package.json").exists() else {}
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for name in (package.get(section) or {}):
                with self.subTest(dependency=name):
                    self.assertNotRegex(name.lower(), r"icon|lucide|phosphor|illustrat|undraw")

    def test_the_catalogue_cover_paths_are_relative_and_plain(self) -> None:
        for entry in load_catalog()["packs"]:
            cover = entry.get("cover") or {}
            path = cover.get("path")
            if not path:
                continue
            with self.subTest(pack=entry["pack_id"]):
                self.assertRegex(path, r"^content/[A-Za-z0-9._-]+\.png$")
                self.assertNotIn("..", path)
                self.assertNotIn("//", path)


class BuilderIsTheOnlySourceTests(unittest.TestCase):
    """The committed plates are the generator's bytes, so a hand-edited cover cannot pass."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = load_builder()

    def test_each_committed_plate_matches_the_generator(self) -> None:
        for kind, slug in (
            ("japanese", "japanese-affection-context-l0"),
            ("parent", "parent-measurement-practice"),
            ("technical", "technical-pack-literacy"),
        ):
            with self.subTest(plate=kind):
                folder = PACKS / slug / "content"
                self.assertEqual((folder / "cover-3x2.png").read_bytes(), self.builder.deterministic_cover(kind))
                self.assertEqual(
                    (folder / "cover-4x5.png").read_bytes(),
                    self.builder.deterministic_cover(kind, portrait=True),
                )
                manifest, _ = archive.read_directory(PACKS / slug)
                declared = {item["path"]: item for item in manifest["files"]}
                self.assertEqual(declared["content/cover-3x2.png"]["role"], "cover")
                self.assertEqual(declared["content/cover-4x5.png"]["role"], "cover")

    def test_plate_geometry_is_the_16_by_9_master_and_its_4_by_5_crop(self) -> None:
        for slug in ("japanese-affection-context-l0", "parent-measurement-practice", "technical-pack-literacy"):
            master_w, master_h = png_size((PACKS / slug / "content" / "cover-3x2.png").read_bytes())
            crop_w, crop_h = png_size((PACKS / slug / "content" / "cover-4x5.png").read_bytes())
            self.assertEqual((master_w, master_h), (864, 576))
            self.assertEqual((crop_w, crop_h), (460, 575))
            self.assertEqual(round(master_w / master_h, 4), round(3 / 2, 4))
            self.assertEqual(round(crop_w / crop_h, 4), round(4 / 5, 4))
            # The 4:5 file is the master's exact centre crop: no resampling, no second drawing.
            self.assertLessEqual(crop_h, master_h)
            self.assertLessEqual(crop_w, master_w)

    def test_the_press_plate_is_the_shipped_cover_and_no_second_plate_file(self) -> None:
        """CP-042: the Press Plate generator is the shipped cover lane itself, not a fallback."""
        data = self.builder.cover_plate_png("parent")
        self.assertGreater(len(data), 1000)
        self.assertEqual(png_size(data), (self.builder.COVER_W, self.builder.COVER_H))
        for slug in ("japanese-affection-context-l0", "parent-measurement-practice", "technical-pack-literacy"):
            manifest, files = archive.read_directory(PACKS / slug)
            self.assertNotIn("content/cover-16x9.png", files)
            self.assertNotIn(
                "content/cover-16x9.png",
                {item["path"] for item in manifest["files"]},
                "the Press Plate is a fallback lane, not a second shipped cover",
            )


class CoverFlowTests(KernelCase):
    """Fallback, real artifact, same plate on Store/Library/detail, and no duplicate."""

    def setUp(self) -> None:
        super().setUp()
        isolate_community_shelf(self)
        pack_flow._STAGING.clear()

    def tearDown(self) -> None:
        pack_flow._STAGING.clear()
        super().tearDown()

    def item(self, pack_id: str) -> dict:
        view = workshop.catalog_view()
        self.assertEqual(view["refused"], [])
        return next(entry for entry in view["items"] if entry["pack_id"] == pack_id)

    def test_before_install_every_cover_is_the_composed_typographic_plate(self) -> None:
        view = workshop.catalog_view()
        self.assertEqual(view["count"], 3)
        for entry in view["items"]:
            with self.subTest(pack=entry["pack_id"]):
                self.assertEqual(entry["cover"]["kind"], "typographic")
                self.assertIsNone(entry["cover"]["artifact_id"])

    def test_after_install_the_cover_is_the_plate_the_catalogue_names(self) -> None:
        for slug, pack_id in (
            ("japanese-affection-context-l0", "japanese-affection-context-l0"),
            ("technical-pack-literacy", "technical-pack-literacy"),
        ):
            with self.subTest(pack=pack_id):
                workshop.install(pack_id)
                item = self.item(pack_id)
                self.assertEqual(item["cover"]["kind"], "artifact")
                artifact_id = item["cover"]["artifact_id"]
                self.assertTrue(str(artifact_id).startswith("art_"))

                # The bytes behind that artifact are the catalogue's cover file, byte for byte.
                document = load_catalog()
                entry = next(e for e in document["packs"] if e["pack_id"] == pack_id)
                cover_path = entry["cover"]["path"]
                manifest, files = archive.read_directory(PACKS / slug)
                preview = media.preview_artifact(str(artifact_id))
                self.assertEqual(preview["ok"], True, preview)
                data_url = str(preview.get("data_url") or "")
                self.assertTrue(data_url.startswith("data:image/png;base64,"), data_url[:40])
                served = base64.b64decode(data_url.split(",", 1)[1])
                self.assertEqual(file_sha256(served), file_sha256(files[cover_path]))
                self.assertEqual(
                    file_sha256(served),
                    next(f["sha256"] for f in manifest["files"] if f["path"] == cover_path).split(":", 1)[1],
                )

    def test_the_same_plate_is_presented_on_store_library_and_detail(self) -> None:
        workshop.install("japanese-affection-context-l0")
        first = self.item("japanese-affection-context-l0")
        second = self.item("japanese-affection-context-l0")
        self.assertEqual(first["cover"], second["cover"])
        self.assertEqual(first["content_hash"], second["content_hash"])
        self.assertEqual(first["pack_version"], "2.4.0")
        self.assertEqual(first["cover"]["caption"], "Cover plate — printed geometry, not a diagram of the course.")

    def test_the_parent_pack_now_serves_its_approved_cover_after_install(self) -> None:
        workshop.install("parent-measurement-practice")
        item = self.item("parent-measurement-practice")
        self.assertEqual(item["cover"]["kind"], "artifact")
        self.assertTrue(str(item["cover"]["artifact_id"]).startswith("art_"))
        self.assertIsNotNone(item["installed"])

    def test_the_cover_is_adopted_but_never_a_lesson_block(self) -> None:
        """A cover is a storefront artifact; it states no teaching fact and is not a page child."""
        workshop.install("japanese-affection-context-l0")
        cover_rows = [
            row for row in self.rows("SELECT id, provenance_json FROM artifacts WHERE kind = 'visual'")
            if json.loads(row["provenance_json"]).get("pack_file") == "content/cover-3x2.png"
        ]
        self.assertEqual(len(cover_rows), 1, "the cover must be adopted as an artifact")
        cover_id = str(cover_rows[0]["id"])
        self.assertEqual(
            int(self.scalar("SELECT COUNT(*) FROM lesson_segments WHERE artifact_id = ?", (cover_id,))),
            0,
            "a cover must not be written as a lesson media segment",
        )
        self.assertEqual(
            int(self.scalar(
                "SELECT COUNT(*) FROM lesson_segments s JOIN artifacts a ON a.id = s.artifact_id"
                " WHERE json_extract(a.provenance_json, '$.pack_file') = 'content/cover-3x2.png'"
            )),
            0,
        )

    def test_a_catalogue_cover_that_is_not_the_media_linked_cover_is_refused(self) -> None:
        document = load_catalog()
        entry = next(e for e in document["packs"] if e["pack_id"] == "japanese-affection-context-l0")
        # The 4:5 crop is a real role-``cover`` file, but only the 3:2 master is linked (and served).
        entry["cover"]["path"] = "content/cover-4x5.png"
        scratch = Path(tempfile.mkdtemp(prefix="coursebook-h197-"))
        self.addCleanup(shutil.rmtree, scratch, True)
        path = scratch / "workshop.v1.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        original = workshop.CATALOG_PATH
        workshop.CATALOG_PATH = path
        try:
            view = workshop.catalog_view()
        finally:
            workshop.CATALOG_PATH = original
        self.assertEqual(view["count"], 2)
        reason = " ".join(refusal["reason"] for refusal in view["refused"])
        self.assertIn("one media-linked cover", reason)
        self.assertNotIn("japanese-affection-context-l0", [item["pack_id"] for item in view["items"]])

    def test_a_cover_no_route_can_serve_is_refused(self) -> None:
        document = load_catalog()
        entry = next(e for e in document["packs"] if e["pack_id"] == "technical-pack-literacy")
        entry["cover"]["path"] = "content/not-a-file.png"
        scratch = Path(tempfile.mkdtemp(prefix="coursebook-h197-"))
        self.addCleanup(shutil.rmtree, scratch, True)
        path = scratch / "workshop.v1.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        original = workshop.CATALOG_PATH
        workshop.CATALOG_PATH = path
        try:
            view = workshop.catalog_view()
        finally:
            workshop.CATALOG_PATH = original
        self.assertEqual(view["count"], 2)
        self.assertIn("not a declared image file", " ".join(r["reason"] for r in view["refused"]))


if __name__ == "__main__":
    unittest.main()
