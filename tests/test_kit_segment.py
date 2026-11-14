"""UI-K1: the curated `field_atlas@3` plates reach the shipped module, keyed and hash-checked.

This module reads the owner-approved kit (`assets/visual-kits/field_atlas/kit.json`), the encodes
this build ships under `assets/kit/`, the generated data-url segment and the built `plugin.js`.
It proves four things:

* the nine embedded plates are exactly the kit's hero, home ground, lesson scene and six covers;
* every row's recorded source hash is the kit's own declaration, and the file it names hashes to
  that value — the pipeline cannot drift onto a re-derived or re-painted plate;
* the segment and the shipped module stay inside their budgets, with the segment counted once;
* `cb3KitSource` and `cb3KitCoverFor` in the built module resolve the pack ids and the title and
  subject words the card names, and return null for a course no approved plate covers.

What this does NOT prove: that the plates look like the approved contact sheet. The owner approved
the sheet on 2026-11-11; this card moves those bytes onto the product surface.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
KIT = ASSETS / "visual-kits" / "field_atlas"
KIT_JSON = KIT / "kit.json"
KIT_MANIFEST = ASSETS / "kit" / "manifest.json"
GENERATED = ROOT / "desktop" / "cb-assets.generated.js"
PLUGIN = ROOT / "desktop" / "plugin.js"
BUILDER = ROOT / "scripts" / "build_cb_assets.py"

SEGMENT_BUDGET = 2_500_000
PLUGIN_BUDGET = 4_500_000

COVERS = (
    "japanese-cover-3x2",
    "parent-cover-3x2",
    "technical-cover-3x2",
    "japanese-cover-4x5",
    "parent-cover-4x5",
    "technical-cover-4x5",
)
FULL_PLATES = ("home-hero", "home-ground", "field-atlas-lesson-room")
PLATE_IDS = FULL_PLATES + COVERS
KIT_PREFIX = "cb.asset.kit.field_atlas."


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _kit() -> dict:
    return json.loads(KIT_JSON.read_text(encoding="utf-8"))


def _declared() -> dict:
    """Every source the kit declares, keyed by its path inside the kit directory.

    A full role declares two files: its rendered plate and, where it has one, a provider source.
    The build encodes exactly one of them per role (``resolution.emit`` decides which), and either
    may be a row's ``master``.
    """
    kit = _kit()
    declared = {}
    for role in ("hero", "home_ground", "lesson_scene"):
        declared[kit["roles"][role][0]["path"]] = kit["roles"][role][0]["sha256"]
        source = kit["resolution"][role].get("source") or {}
        if source.get("path"):
            declared[source["path"]] = source["sha256"]
    for row in kit["roles"]["cover"]:
        declared[row["path"]] = row["sha256"]
    return declared


def _rows() -> list[dict]:
    return json.loads(KIT_MANIFEST.read_text(encoding="utf-8"))


def _segment() -> dict:
    text = GENERATED.read_text(encoding="utf-8")
    start = text.index("Object.freeze(") + len("Object.freeze(")
    return json.loads(text[start : text.rindex(");")])


def _kit_entries() -> dict:
    return {
        key: row
        for key, row in _segment()["assets"].items()
        if key.startswith(KIT_PREFIX)
    }


def _kit_rel(master: str) -> str:
    """The path of a kit source inside ``assets/visual-kits/field_atlas/``."""
    prefix = "assets/visual-kits/%s/" % KIT.name
    return master.split(prefix, 1)[1] if master.startswith(prefix) else ""


class KitRows(unittest.TestCase):
    def test_the_nine_approved_plates_are_the_nine_embedded_plates(self):
        ids = {row["provenance_id"] for row in _rows()}
        self.assertEqual(ids, {KIT_PREFIX + plate for plate in PLATE_IDS})
        self.assertEqual(set(_kit_entries()), ids)

    def test_every_row_records_the_kits_own_source_hash(self):
        declared = _declared()
        kit_id = _kit()["kit_id"]
        for row in _rows():
            with self.subTest(plate=row["provenance_id"]):
                self.assertEqual(row["kit_id"], kit_id)
                source = _kit_rel(row["master"])
                self.assertTrue(source, "row does not name a kit source: %s" % row["master"])
                self.assertIn(source, declared, row["master"])
                self.assertEqual(row["master_sha256"], declared[source],
                                 "%s records a source hash kit.json does not declare" % row["path"])

    def test_every_source_file_still_hashes_to_its_declaration(self):
        for row in _rows():
            with self.subTest(plate=row["path"]):
                source = ROOT / row["master"]
                self.assertTrue(source.is_file(), row["master"])
                self.assertEqual(_sha(source.read_bytes()), row["master_sha256"], row["master"])

    def test_no_kit_row_reads_the_procedural_masters(self):
        for row in _rows():
            with self.subTest(plate=row["path"]):
                for field in ("path", "master", "source"):
                    self.assertNotIn("assets/masters/", row[field], "%s reads %s" % (field, row[field]))
        self.assertNotIn("assets/masters/", BUILDER.read_text(encoding="utf-8").split("# curated kit", 1)[1].split("manifests = {", 1)[0],
                         "the kit branch names a masters path")

    def test_each_shipped_encode_matches_its_row_and_the_segment(self):
        entries = _kit_entries()
        for row in _rows():
            with self.subTest(plate=row["path"]):
                path = ROOT / row["path"]
                self.assertTrue(path.is_file(), row["path"])
                self.assertEqual(_sha(path.read_bytes()), row["sha256"], row["path"])
                self.assertEqual(path.stat().st_size, row["bytes"], row["path"])
                entry = entries[row["provenance_id"]]
                self.assertEqual(entry["sha256"], row["sha256"])
                self.assertEqual(entry["path"], row["path"])
                payload = base64.b64decode(entry["src"].split(",", 1)[1])
                self.assertEqual(_sha(payload), row["sha256"], row["path"])
                self.assertEqual(len(payload), row["bytes"], row["path"])

    def test_no_plate_is_emitted_above_its_natural_size(self):
        declared = _declared()
        from PIL import Image

        for row in _rows():
            with self.subTest(plate=row["path"]):
                source = _kit_rel(row["master"])
                with Image.open(KIT / source) as natural:
                    self.assertLessEqual(row["width"], natural.width, row["path"])
                    self.assertLessEqual(row["height"], natural.height, row["path"])
                self.assertIn(source, declared)

    def test_the_full_plates_use_their_declared_emit_sizes(self):
        # Per-role resolution: hero and home_ground emit their 1344x768 plate, lesson_scene its
        # 2688x1536 provider source. Nothing in between, and nothing upscaled.
        allowed = {("home-hero", 1344, 768), ("home-ground", 1344, 768),
                   ("field-atlas-lesson-room", 2688, 1536)}
        for row in _rows():
            if row["kit_role"] == "cover":
                continue
            with self.subTest(plate=row["path"]):
                plate = row["provenance_id"].rsplit(".", 1)[1]
                self.assertIn((plate, row["width"], row["height"]), allowed)
                emit = _kit()["resolution"][row["kit_role"]]["emit"]
                self.assertEqual([row["width"], row["height"]], emit, row["path"])
        self.assertLessEqual(GENERATED.stat().st_size, SEGMENT_BUDGET)

    def test_covers_keep_their_natural_aspect_and_size(self):
        kit = _kit()
        sizes = {row["id"]: tuple(row["size"]) for row in kit["roles"]["cover"]}
        for row in _rows():
            if row["kit_role"] != "cover":
                continue
            with self.subTest(plate=row["path"]):
                plate = row["provenance_id"].rsplit(".", 1)[1]
                self.assertEqual((row["width"], row["height"]), sizes[plate])
                self.assertEqual(row["quality"], 80)


class Budgets(unittest.TestCase):
    def test_the_segment_is_under_2_5mb(self):
        self.assertLessEqual(GENERATED.stat().st_size, SEGMENT_BUDGET)

    def test_the_shipped_module_carries_the_segment_within_4_5mb(self):
        self.assertLessEqual(PLUGIN.stat().st_size, PLUGIN_BUDGET)
        text = PLUGIN.read_text(encoding="utf-8")
        self.assertIn("cb.asset.kit.field_atlas.home-hero", text)


class CoverMapping(unittest.TestCase):
    """The accessors are read from the built module, not from a test-only copy of the source."""

    PROBE = r"""
import fs from 'node:fs'
import { createHash } from 'node:crypto'

globalThis.__CB_TEST_WIDTH__ = '1344'
const mod = await import('./plugin.js')

const sha = (url) => {
  if (!url) return null
  const comma = String(url).indexOf(',')
  if (comma < 0) return null
  return createHash('sha256').update(Buffer.from(String(url).slice(comma + 1), 'base64')).digest('hex')
}

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
process.stdout.write(JSON.stringify({
  covers: payload.courses.map((course) => mod.cb3KitCoverFor(course)),
  sources: payload.ids.map((id) => ({ id, sha: sha(mod.cb3KitSource(id)) }))
}))
"""

    module: Path | None = None

    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        root = Path(tempfile.mkdtemp(prefix="coursebook-ui-k1-probe-"))
        (root / "plugin.js").write_text(PLUGIN.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "probe.mjs").write_text(cls.PROBE, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.module = root

    def probe(self, courses: list, ids: list[str]) -> dict:
        if self.module is None:
            raise unittest.SkipTest("the module probe did not mount")
        case = self.module / "case.json"
        case.write_text(json.dumps({"courses": courses, "ids": ids}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.module / "probe.mjs"), str(case)],
            cwd=self.module, capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def test_the_three_pack_ids_map_to_their_approved_pair(self):
        ids = ["japanese-affection-context-l0", "parent-measurement-practice",
               "technical-pack-literacy"]
        out = self.probe([{"pack_id": pid, "title": "", "subject_domain": ""} for pid in ids], [])
        self.assertEqual(out["covers"], [
            {"id3x2": "japanese-cover-3x2", "id4x5": "japanese-cover-4x5"},
            {"id3x2": "parent-cover-3x2", "id4x5": "parent-cover-4x5"},
            {"id3x2": "technical-cover-3x2", "id4x5": "technical-cover-4x5"},
        ])

    def test_a_kyoto_title_maps_to_japanese(self):
        courses = [
            {"title": "Order coffee and ask for the bill in Kyoto"},
            {"pack_id": "", "title": "Nihongo greetings"},
            {"subject_domain": "Japanese"},
            {"title": "Measuring together: a kitchen lesson"},
            {"title": "Reading a pack before you install it"},
        ]
        out = self.probe(courses, [])
        self.assertEqual([c["id3x2"].split(".")[-1] if c else None for c in out["covers"]], [
            "japanese-cover-3x2",
            "japanese-cover-3x2",
            "japanese-cover-3x2",
            "parent-cover-3x2",
            "technical-cover-3x2",
        ])

    def test_a_course_no_plate_covers_returns_null(self):
        out = self.probe([{"title": "Advanced linear algebra"}, {}, None], [])
        self.assertEqual(out["covers"], [None, None, None])

    def test_the_accessor_resolves_the_approved_plates_by_hash(self):
        rows = {row["provenance_id"].rsplit(".", 1)[1]: row["sha256"] for row in _rows()}
        out = self.probe([], ["home-hero", "field-atlas-lesson-room", "japanese-cover-3x2", "no-such-plate"])
        self.assertEqual(
            {item["id"]: item["sha"] for item in out["sources"]},
            {
                "home-hero": rows["home-hero"],
                "field-atlas-lesson-room": rows["field-atlas-lesson-room"],
                "japanese-cover-3x2": rows["japanese-cover-3x2"],
                "no-such-plate": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
