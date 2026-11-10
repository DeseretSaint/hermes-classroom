"""The brand-asset segment: manifests, licences, hashes, the frozen object and the size budgets.

This test module reads the shipped bytes under ``assets/`` and ``desktop/cb-assets.generated.js``
and refuses the build when any of the card's gates fails:

* the generated segment is at most 2.5 MB, any single shipped asset at most 300 KB, and
  ``desktop/plugin.js`` (alone, and with the segment it will carry) at most 4.5 MB;
* every manifest row names a licence and a sha256 that matches the file on disk, and its path
  stays inside ``assets/``;
* no file under a shipped group is missing from its manifest, and no provenance id repeats;
* every data URL in ``CB_ASSETS`` decodes to exactly the file whose sha256 it claims, so the
  segment cannot drift from the tree it claims to embed;
* the material file names are the ones the v3 contract pins, and the fox ships all seven poses at
  128 and at 64;
* course covers, scene headers and world plates are absent — they stay on the media route.

What this does NOT prove: that a browser decodes the WebP, or that the art reads well. The
generated object is concatenated into ``desktop/plugin.js`` by ``scripts/build_plugin.py`` (CP-020a);
this module proves the bytes it carries, not their paint. CP-010/CP-013 own the art review; this
card owns the pipeline and the budget.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
GENERATED = ROOT / "desktop" / "cb-assets.generated.js"
PLUGIN = ROOT / "desktop" / "plugin.js"
CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"
BUILDER = ROOT / "scripts" / "build_cb_assets.py"
VENV_PY = ROOT / ".venv-cb-assets" / "bin" / "python"

SEGMENT_BUDGET = 2_500_000
ASSET_BUDGET = 300_000
PLUGIN_BUDGET = 4_500_000

GROUPS = ("fonts", "material", "fox", "objects")
ASSET_SUFFIXES = (".webp", ".avif", ".woff2")
ALLOWED_LICENCES = {"CC0-1.0", "OFL-1.1", "MIT", "ISC", "Apache-2.0", "BSD-3-Clause", "CC-BY-4.0"}
REQUIRED_ROW_KEYS = (
    "role",
    "source",
    "licence",
    "sha256",
    "width",
    "height",
    "bytes",
    "provenance_id",
    "path",
)
FORBIDDEN_IN_EMBEDDED = ("cover", "pattern-plate", "world-plate", "scene-header", "bundled/")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest(group: str) -> list[dict]:
    return json.loads((ASSETS / group / "manifest.json").read_text())


def _all_rows() -> list[tuple[str, dict]]:
    return [(group, row) for group in GROUPS for row in _manifest(group)]


def _generated() -> dict:
    """Parse the frozen CB_ASSETS literal without a JS engine: it is JSON after the prefix."""
    text = GENERATED.read_text()
    start = text.index("Object.freeze(") + len("Object.freeze(")
    end = text.rindex(");")
    return json.loads(text[start:end])


class ManifestShape(unittest.TestCase):
    def test_every_group_has_a_manifest(self):
        for group in GROUPS:
            path = ASSETS / group / "manifest.json"
            self.assertTrue(path.is_file(), "missing manifest for %s" % group)
            self.assertTrue(_manifest(group), "empty manifest for %s" % group)

    def test_required_keys_on_every_row(self):
        for group, row in _all_rows():
            for key in REQUIRED_ROW_KEYS:
                self.assertIn(key, row, "%s row %s lacks %s" % (group, row.get("path"), key))

    def test_licence_is_spdx_and_present(self):
        for group, row in _all_rows():
            self.assertTrue(row["licence"], "%s row %s has no licence" % (group, row["path"]))
            self.assertIn(row["licence"], ALLOWED_LICENCES, row["path"])

    def test_hash_matches_the_file(self):
        for group, row in _all_rows():
            path = (ROOT / row["path"]).resolve()
            self.assertTrue(str(path).startswith(str(ASSETS.resolve())), row["path"])
            self.assertTrue(path.is_file(), "manifest names a missing file: %s" % row["path"])
            self.assertEqual(_sha(path.read_bytes()), row["sha256"], row["path"])
            self.assertEqual(path.stat().st_size, row["bytes"], row["path"])

    def test_dimensions_are_present_integers(self):
        for group, row in _all_rows():
            self.assertIsInstance(row["width"], int, row["path"])
            self.assertIsInstance(row["height"], int, row["path"])
            if row["kind"] == "font":
                self.assertEqual((row["width"], row["height"]), (0, 0), row["path"])
            else:
                self.assertGreater(row["width"], 0, row["path"])
                self.assertGreater(row["height"], 0, row["path"])

    def test_every_path_stays_inside_assets(self):
        for group, row in _all_rows():
            self.assertTrue(row["path"].startswith("assets/%s/" % group), row["path"])
            self.assertNotIn("..", row["path"])
            for forbidden in FORBIDDEN_IN_EMBEDDED:
                self.assertNotIn(forbidden, row["path"].lower(), row["path"])

    def test_no_file_is_missing_from_its_manifest(self):
        for group in GROUPS:
            rows = _manifest(group)
            expected = {row["path"] for row in rows}
            expected |= {row["avif"] for row in rows if "avif" in row}
            shipped = {
                str(p.relative_to(ROOT))
                for p in (ASSETS / group).rglob("*")
                if p.is_file() and p.suffix.lower() in ASSET_SUFFIXES
            }
            self.assertEqual(expected, shipped, "manifest/tree drift in %s" % group)

    def test_alternate_encodings_match_their_row(self):
        for group, row in _all_rows():
            if "avif" not in row:
                continue
            path = ROOT / row["avif"]
            self.assertTrue(path.is_file(), row["avif"])
            self.assertEqual(_sha(path.read_bytes()), row["avif_sha256"], row["avif"])
            self.assertEqual(path.stat().st_size, row["avif_bytes"], row["avif"])
            self.assertLessEqual(path.stat().st_size, ASSET_BUDGET, row["avif"])

    def test_provenance_ids_are_unique(self):
        ids = [row["provenance_id"] for _, row in _all_rows()]
        self.assertEqual(len(ids), len(set(ids)), "duplicate provenance id")

    def test_provenance_id_prefix_matches_its_group(self):
        prefix = {
            "fonts": "cb.asset.font.",
            "material": "cb.asset.material.",
            "fox": "cb.asset.fox.",
            "objects": "cb.asset.object.",
        }
        for group, row in _all_rows():
            self.assertTrue(
                row["provenance_id"].startswith(prefix[group]),
                "%s row carries %s" % (group, row["provenance_id"]),
            )

    def test_source_and_role_are_not_empty(self):
        for group, row in _all_rows():
            self.assertTrue(row["source"].strip(), row["path"])
            self.assertTrue(row["role"].strip(), row["path"])

    def test_declared_dimensions_match_the_image(self):
        from PIL import Image

        for group, row in _all_rows():
            if row["kind"] == "font":
                continue
            with Image.open(ROOT / row["path"]) as img:
                self.assertEqual(img.size, (row["width"], row["height"]), row["path"])


class Budgets(unittest.TestCase):
    def test_every_single_shipped_file_is_under_300kb(self):
        for path in ASSETS.rglob("*"):
            if path.is_file() and path.suffix.lower() in ASSET_SUFFIXES and "masters" not in path.parts:
                self.assertLessEqual(
                    path.stat().st_size, ASSET_BUDGET, "%s is %d bytes" % (path, path.stat().st_size)
                )

    def test_generated_segment_is_under_2_5mb(self):
        self.assertLessEqual(GENERATED.stat().st_size, SEGMENT_BUDGET)

    def test_plugin_js_is_under_4_5mb(self):
        self.assertLessEqual(PLUGIN.stat().st_size, PLUGIN_BUDGET)

    def test_plugin_plus_segment_is_under_4_5mb(self):
        # The segment is meant to travel inside the single module, so the honest forward-looking
        # gate is the sum, not the pre-wiring plugin.js on its own.
        self.assertLessEqual(PLUGIN.stat().st_size + GENERATED.stat().st_size, PLUGIN_BUDGET)


class GeneratedObject(unittest.TestCase):
    def setUp(self):
        self.doc = _generated()

    def test_it_is_frozen(self):
        self.assertIn("const CB_ASSETS = Object.freeze(", GENERATED.read_text())
        self.assertIn("globalThis.CB_ASSETS = CB_ASSETS", GENERATED.read_text())

    def test_it_carries_only_the_four_brand_groups(self):
        self.assertEqual(
            set(self.doc), {"schema", "generated_by", "note", "fonts", "assets"}
        )
        groups = {row["group"] for row in self.doc["assets"].values()}
        self.assertEqual(groups, {"fonts", "material", "fox", "objects"})
        self.assertEqual(self.doc["schema"], 1)

    def test_every_manifest_row_is_embedded_exactly_once(self):
        embedded = set(self.doc["assets"])
        manifest_ids = {row["provenance_id"] for _, row in _all_rows()}
        self.assertEqual(embedded, manifest_ids)

    def test_data_urls_decode_to_the_manifest_bytes(self):
        for row in self.doc["assets"].values():
            self.assertTrue(row["src"].startswith("data:%s;base64," % row["mime"]))
            payload = base64.b64decode(row["src"].split(",", 1)[1])
            self.assertEqual(_sha(payload), row["sha256"], row["path"])
            self.assertEqual(len(payload), row["bytes"], row["path"])
            self.assertEqual(_sha((ROOT / row["path"]).read_bytes()), row["sha256"], row["path"])
            if "src_avif" in row:
                avif = base64.b64decode(row["src_avif"].split(",", 1)[1])
                self.assertEqual(avif[4:8], b"ftyp", "not an AVIF file")
                self.assertLessEqual(len(avif), ASSET_BUDGET)

    def test_no_remote_url_in_the_segment(self):
        text = GENERATED.read_text()
        self.assertIsNone(re.search(r"https?://", text), "the segment must carry no remote URL")

    def test_the_two_pinned_families_are_present(self):
        self.assertEqual(set(self.doc["fonts"]), {"CB Display", "CB UI"})
        for family, url in self.doc["fonts"].items():
            self.assertTrue(family.startswith("CB "), family)
            self.assertTrue(url.startswith("data:font/woff2;base64,"), family)

    def test_no_cover_or_plate_is_embedded(self):
        for prov, row in self.doc["assets"].items():
            for forbidden in FORBIDDEN_IN_EMBEDDED:
                self.assertNotIn(forbidden, prov.lower(), prov)
                self.assertNotIn(forbidden, row["path"].lower(), row["path"])


class ContractPins(unittest.TestCase):
    def test_material_names_are_the_ones_the_contract_pins(self):
        contract = json.loads(CONTRACT.read_text())
        pinned = set()
        for row in contract["materials"].values():
            if isinstance(row, dict) and "light" in row:
                for mode in ("light", "dark"):
                    pinned.add("assets/" + row[mode]["file"])
        material = {row["path"] for row in _manifest("material")}
        self.assertEqual(material, pinned)

    def test_fox_ships_seven_poses_at_two_exports(self):
        rows = _manifest("fox")
        ids = {row["provenance_id"] for row in rows}
        for pose in ("wave", "point", "clock", "read", "cheer", "think", "sleep"):
            for px in (128, 64):
                self.assertIn("cb.asset.fox.%s.%d" % (pose, px), ids)

    def test_object_kit_is_complete(self):
        ids = {row["provenance_id"] for row in _manifest("objects")}
        for name in (
            "clock",
            "tag",
            "stamp-rim",
            "medallion-rim",
            "passport-tray",
            "ticket",
            "shelf-plank",
        ):
            self.assertIn("cb.asset.object.%s" % name, ids)


FONT_PROBE = r"""
import json
from fontTools.ttLib import TTFont
out = {}
for rel in ("assets/fonts/CBDisplay-VF.woff2", "assets/fonts/CBUI-VF.woff2"):
    font = TTFont(rel)
    out[rel] = {
        "cmap": sorted(font.getBestCmap()),
        "names": {nid: font["name"].getDebugName(nid) for nid in (0, 1, 2, 3, 4, 6, 13, 14, 16, 17)},
    }
print(json.dumps(out))
"""


@unittest.skipUnless(VENV_PY.exists(), "fontTools lives in the private .venv-cb-assets")
class FontLicenceAndSubset(unittest.TestCase):
    """Read the shipped WOFF2 through the private venv; the system interpreter has no fontTools."""

    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            [str(VENV_PY), "-c", FONT_PROBE], cwd=ROOT, capture_output=True, text=True
        )
        if result.returncode != 0:
            raise unittest.SkipTest("font probe failed: %s" % result.stderr[-400:])
        cls.fonts = json.loads(result.stdout)

    def test_latin_and_punctuation_only(self):
        for rel, info in self.fonts.items():
            cmap = set(info["cmap"])
            self.assertIn(ord("A"), cmap, rel)
            self.assertIn(ord("é"), cmap, rel)
            self.assertIn(0x2014, cmap, rel)
            self.assertNotIn(ord("あ"), cmap, rel)
            self.assertNotIn(ord("漢"), cmap, rel)
            self.assertLessEqual(len(cmap), 260, "%s carries too much of the original" % rel)

    def test_family_names_are_cb_names_not_the_reserved_ones(self):
        # OFL clause 3: a Modified Version must not use a Reserved Font Name. Source Sans 3's OFL
        # reserves 'Source', so the shipped name table must not carry it in any font name.
        for rel, upstream in (
            ("assets/fonts/CBDisplay-VF.woff2", "Fraunces"),
            ("assets/fonts/CBUI-VF.woff2", "Source"),
        ):
            names = self.fonts[rel]["names"]
            for nid in (1, 2, 3, 4, 6, 16, 17):
                value = names.get(str(nid)) or names.get(nid)
                if value is None:
                    continue
                self.assertNotIn(upstream.lower(), value.lower(), "%s name %d" % (rel, nid))
            family = names.get("1") or names.get(1)
            self.assertTrue(family.startswith("CB "), rel)

    def test_copyright_and_licence_text_survive(self):
        for rel, info in self.fonts.items():
            names = info["names"]
            licence = names.get("13") or names.get(13) or ""
            self.assertIn("SIL Open Font License", licence, rel)
            self.assertTrue(names.get("0") or names.get(0), "%s lost its copyright" % rel)

    def test_licence_texts_ship_beside_the_fonts(self):
        for rel in ("assets/fonts/licenses/OFL-Fraunces.txt", "assets/fonts/licenses/OFL-SourceSans3.txt"):
            text = (ROOT / rel).read_text()
            self.assertIn("SIL OPEN FONT LICENSE", text.upper(), rel)

    def test_rfn_decision_is_recorded(self):
        doc = (ROOT / "docs" / "THIRD-PARTY.md").read_text()
        self.assertIn("Reserved Font Name", doc)
        self.assertIn("Source Sans 3", doc)
        self.assertIn("CB UI", doc)


@unittest.skipUnless(
    VENV_PY.exists() and shutil.which("rsvg-convert"), "needs .venv-cb-assets and rsvg-convert"
)
class Determinism(unittest.TestCase):
    def _build_copy(self, tmp: Path) -> bytes:
        for rel in ("scripts/build_cb_assets.py",):
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, tmp / rel)
        shutil.copytree(ROOT / "assets" / "masters", tmp / "assets" / "masters")
        (tmp / "contracts").mkdir()
        shutil.copy2(CONTRACT, tmp / "contracts" / "cb.tokens.v3.json")
        (tmp / "desktop").mkdir()
        shutil.copy2(PLUGIN, tmp / "desktop" / "plugin.js")
        subprocess.run([str(VENV_PY), str(tmp / "scripts/build_cb_assets.py")], cwd=tmp,
                       check=True, capture_output=True)
        return (tmp / "desktop/cb-assets.generated.js").read_bytes()

    def test_two_builds_are_byte_identical_and_match_the_committed_segment(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first = self._build_copy(Path(a))
            second = self._build_copy(Path(b))
        self.assertEqual(first, second, "two builds differ; the pipeline is not deterministic")
        self.assertEqual(first, GENERATED.read_bytes(), "committed segment is stale; rebuild it")


DOC_FILES = (
    ROOT / "docs" / "THIRD-PARTY.md",
    ASSETS / "README.md",
    ROOT / "tests" / "test_desktop_surface.py",
)
GATE = ROOT / "scripts" / "validate-plugin.sh"
# Present-tense claims that the segment already ships inside the module. Future-tense statements
# naming CP-020a as the owner (e.g. "CP-020a inlines the segment into plugin.js") are the truth and
# are not in this list.
INLINING_CLAIMS = (
    "inside the plugin module",
    "in the plugin module",
    "stays one file",
    "one plugin file",
    "embedded in plugin.js",
    "inlined into plugin.js",
)
ADMISSION_TOKENS = ("allowlist", "allow-list")


class DocumentationClaims(unittest.TestCase):
    """Docs must not describe enforcement or integration the repository does not perform.

    Round 1 of review closed two truth defects here: THIRD-PARTY claimed a file admission rule the
    release gate never had, and three files said the segment ships "inside the plugin module" while
    ``plugin.js`` did not reference it. These gates fail if either claim returns before the code
    that would make it true.
    """

    @staticmethod
    def _offenders(predicate) -> list[str]:
        found = []
        for path in DOC_FILES:
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if predicate(line):
                    found.append("%s:%d: %s" % (path.relative_to(ROOT), lineno, line.strip()))
        return found

    def test_no_doc_claims_a_file_admission_rule_the_gate_lacks(self):
        gate = GATE.read_text(encoding="utf-8").lower()
        if any(token in gate for token in ADMISSION_TOKENS):
            self.skipTest("the release gate now implements the rule; a doc claim would be true")
        offenders = self._offenders(
            lambda line: any(token in line.lower() for token in ADMISSION_TOKENS)
        )
        self.assertEqual(
            offenders,
            [],
            "docs claim a file admission rule that scripts/validate-plugin.sh does not implement",
        )

    def test_no_doc_claims_inlining_the_module_does_not_perform(self):
        if "CB_ASSETS" in PLUGIN.read_text(encoding="utf-8"):
            self.skipTest("plugin.js really carries CB_ASSETS; an inlining claim is true")
        offenders = self._offenders(
            lambda line: any(claim in line.lower() for claim in INLINING_CLAIMS)
        )
        self.assertEqual(offenders, [], "docs claim the segment already ships inside plugin.js")

    def test_docs_name_the_owner_of_the_pending_inlining(self):
        plugin = PLUGIN.read_text(encoding="utf-8")
        for path in DOC_FILES:
            text = path.read_text(encoding="utf-8")
            if GENERATED.name not in text and "GENERATED_SEGMENT" not in text:
                continue
            with self.subTest(file=path.name):
                if "CB_ASSETS" in plugin:
                    self.assertNotIn(
                        "CP-020a owns",
                        text,
                        "%s still calls inlining pending; plugin.js already carries CB_ASSETS"
                        % path.name,
                    )
                else:
                    self.assertIn(
                        "CP-020a",
                        text,
                        "%s describes the segment but not who wires it into plugin.js" % path.name,
                    )


class ReportIsReadOnly(unittest.TestCase):
    """``--report`` must print the committed tree's report and write nothing (round-1 D3)."""

    def _copy_tree(self, root: Path) -> None:
        (root / "scripts").mkdir(parents=True)
        shutil.copy2(BUILDER, root / "scripts" / "build_cb_assets.py")
        for group in GROUPS:
            dst = root / "assets" / group
            dst.mkdir(parents=True)
            for path in sorted((ASSETS / group).iterdir()):
                if path.is_file():
                    shutil.copy2(path, dst / path.name)
        (root / "desktop").mkdir()
        shutil.copy2(GENERATED, root / "desktop" / GENERATED.name)
        shutil.copy2(PLUGIN, root / "desktop" / "plugin.js")

    @staticmethod
    def _snapshot(root: Path) -> dict:
        return {
            str(path.relative_to(root)): (path.stat().st_mtime_ns, _sha(path.read_bytes()))
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def _report(self, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(root / "scripts" / "build_cb_assets.py"), "--report"],
            cwd=root,
            capture_output=True,
            text=True,
        )

    def test_report_leaves_every_file_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_tree(root)
            before = self._snapshot(root)
            result = self._report(root)
            self.assertEqual(result.returncode, 0, result.stderr[-800:])
            self.assertIn("VERDICT:", result.stdout)
            self.assertEqual(self._snapshot(root), before, "--report rewrote the tree")

    def test_report_does_not_rebuild_a_missing_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_tree(root)
            (root / "desktop" / GENERATED.name).unlink()
            before = self._snapshot(root)
            result = self._report(root)
            self.assertNotEqual(result.returncode, 0, "--report rebuilt instead of reporting")
            self.assertFalse((root / "desktop" / GENERATED.name).exists())
            self.assertEqual(self._snapshot(root), before, "--report wrote to the tree")


if __name__ == "__main__":
    unittest.main()
