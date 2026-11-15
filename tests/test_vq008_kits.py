"""VQ-008 — the kit judge must pass the shipped kits and fail a broken claim.

The rule this file enforces: `--check` passing means nothing if the judge cannot fail. Each mutation
below breaks one load-bearing claim in a copy of `workshop_manual/kit.json`, runs the real judge,
and requires a non-zero exit; the shipped manifest is restored before the test ends.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vq008-kits.py"
KIT = ROOT / "assets" / "visual-kits" / "workshop_manual" / "kit.json"
GRAMMAR = "workshop_manual"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT
    )


class KitJudge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = KIT.read_text()

    @classmethod
    def tearDownClass(cls):
        KIT.write_text(cls.original)

    def _check(self) -> subprocess.CompletedProcess:
        return run("--check-one", GRAMMAR)

    def test_every_grammar_passes(self):
        out = run("--check")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("8 grammars", out.stdout)
        self.assertIn("every claim re-derived", out.stdout)

    def test_tampered_hash_fails(self):
        kit = json.loads(self.original)
        kit["roles"]["hero"][0]["sha256"] = "0" * 64
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("sha256 is stale", out.stdout)
        KIT.write_text(self.original)

    def test_pack_cover_fallback_fails(self):
        kit = json.loads(self.original)
        kit["fallbacks"]["cover"] = ["course-master", "pack-cover"]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("forbidden step", out.stdout)
        KIT.write_text(self.original)

    def test_grammar_drift_fails(self):
        kit = json.loads(self.original)
        kit["palette"]["ochre"] = "#000000"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("palette drifted from the grammar table", out.stdout)
        KIT.write_text(self.original)

    def test_inverted_cannot_do_fails(self):
        # `cannot_do` is the card's safety fence and lives in the grammar table. A manifest that
        # inverts it into permission is a false safety promise, not a copy edit.
        kit = json.loads(self.original)
        kit["cannot_do"] = "art may show a torque value as authority"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("cannot_do drifted from the grammar table", out.stdout)
        KIT.write_text(self.original)

    def test_widened_illustration_role_fails(self):
        kit = json.loads(self.original)
        kit["illustration_role"] = "orientation only; may show measurements and procedures"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("illustration_role drifted from the grammar table", out.stdout)
        KIT.write_text(self.original)

    def test_replaced_subject_cues_fails(self):
        kit = json.loads(self.original)
        kit["subject_cues"] = ["generic classroom", "stock photo"]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("subject_cues drifted from the grammar table", out.stdout)
        KIT.write_text(self.original)

    def test_provider_free_false_fails(self):
        # A kit that needs an image provider is not the provider-free artifact this card ships.
        kit = json.loads(self.original)
        kit["provider_free"] = False
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("provider_free is not true", out.stdout)
        KIT.write_text(self.original)

    def test_wrong_art_bible_fails(self):
        kit = json.loads(self.original)
        kit["art_bible"] = "docs/launch/ART-BIBLE.md"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("art_bible is", out.stdout)
        KIT.write_text(self.original)

    def test_faked_cover_ratio_fails(self):
        kit = json.loads(self.original)
        master = [p for p in kit["roles"]["cover"] if "derived_from" not in p][0]
        master["provenance"]["source_frame"]["ratios"]["natural_vs_shipped"] = 9.99
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("cover ratio natural_vs_shipped", out.stdout)
        KIT.write_text(self.original)

    def test_stale_kernel_pin_fails(self):
        # The kernel claims are content-addressed against plates this card does not own, so they go
        # stale whenever the kernel moves (VQ-006 re-authored the vignette to 2688x1428). A re-pin is
        # only worth anything if the judge still refuses a wrong one.
        kit = json.loads(self.original)
        row = [r for r in kit["kernel"]["assets"]
               if r["path"] == "assets/material/vignette-parchment.webp"][0]
        row["sha256"] = "0" * 64
        row["size"] = [96, 96]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("kernel assets/material/vignette-parchment.webp sha256 is stale", out.stdout)
        self.assertIn("kernel assets/material/vignette-parchment.webp size is stale", out.stdout)
        KIT.write_text(self.original)

    def test_placeholder_name_fails(self):
        kit = json.loads(self.original)
        kit["roles"]["section"][0]["path"] = "section/placeholder.png"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("missing", out.stdout)
        KIT.write_text(self.original)

    def test_faked_quiet_field_fails(self):
        # The quiet-field block is a measurement, so --check must re-measure the band from the
        # shipped pixels instead of reading the numbers the manifest reports.
        kit = json.loads(self.original)
        qf = kit["roles"]["hero"][0]["provenance"]["measured"]["quiet_field"]
        for key in list(qf):
            if isinstance(qf[key], (int, float)) and not isinstance(qf[key], bool):
                qf[key] = 0
        qf["best_contrast"] = 99
        qf["contrast_p5_on_cream"] = 99
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("quiet field", out.stdout)
        KIT.write_text(self.original)

    def test_faked_derived_cover_derivation_fails(self):
        # The 4:5 row nests `derived_from` and is derived from the master's own crop. A sentence
        # naming a frame that was never used must fail, not sail through as untested prose.
        kit = json.loads(self.original)
        derived = [p for p in kit["roles"]["cover"] if "derived_from" in p][0]
        derived["provenance"]["derivation"] = (
            "centre crop of the cover-3x2 natural 40000x30000 frame to 2x2, resized to 640x800"
        )
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("4:5 derivation does not state the crop actually taken", out.stdout)
        KIT.write_text(self.original)

    def test_derived_crop_must_match_master_crop(self):
        kit = json.loads(self.original)
        derived = [p for p in kit["roles"]["cover"] if "derived_from" in p][0]
        derived["provenance"]["source_frame"]["frame"] = [40000, 30000]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("4:5 row names frame", out.stdout)
        KIT.write_text(self.original)

    def test_missing_resolution_fails(self):
        # build_cb_assets.py reads resolution[role].source for a full-bleed plate and stops when
        # it is absent, so a kit without it is not loadable and must not pass acceptance.
        kit = json.loads(self.original)
        del kit["resolution"]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("no resolution block", out.stdout)
        KIT.write_text(self.original)

    def test_stale_generation_log_pin_fails(self):
        kit = json.loads(self.original)
        kit["generation_log"]["rows"] = kit["generation_log"]["rows"] + 1
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("generation_log row count is stale", out.stdout)
        KIT.write_text(self.original)

    def test_kernel_reference_as_role_fails(self):
        # A shared-kernel row is a reference into one kernel. Mounting it as a role would hand a
        # loader an out-of-kit path it cannot open; the judge must refuse that shape.
        kit = json.loads(self.original)
        kit["roles"]["frame"] = [dict(kit["kernel"]["assets"][0])]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("loader vocabulary", out.stdout)
        KIT.write_text(self.original)

    def test_role_path_outside_kit_fails(self):
        kit = json.loads(self.original)
        kit["roles"]["section"][0]["path"] = "../../../assets/objects/clock.webp"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("resolves outside its own kit directory", out.stdout)
        KIT.write_text(self.original)

    def test_missing_kernel_refs_fails(self):
        kit = json.loads(self.original)
        del kit["kernel"]["assets"]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("kernel.assets is missing", out.stdout)
        KIT.write_text(self.original)

    def test_kit_id_mismatch_fails(self):
        kit = json.loads(self.original)
        kit["kit_id"] = "workshop_manual@9"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("is not workshop_manual@1", out.stdout)
        KIT.write_text(self.original)

    def test_duplicate_asset_id_fails(self):
        # VQ-004's loader refuses a repeated roles[].id (kit_duplicate_asset). A manifest the
        # product refuses must not pass the acceptance run.
        kit = json.loads(self.original)
        kit["roles"]["section"][0]["id"] = kit["roles"]["hero"][0]["id"]
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("declared twice", out.stdout)
        self.assertIn("kit_duplicate_asset", out.stdout)
        KIT.write_text(self.original)

    def test_stale_ocr_policy_fails(self):
        # The limitation sentence now states measured recall. A kit that keeps the old, weaker
        # wording (or any other drift) must not pass: the policy is carried verbatim, not prose.
        kit = json.loads(self.original)
        kit["ocr_policy"]["limitation"] = "painted pseudo-lettering is not readable enough for OCR"
        KIT.write_text(json.dumps(kit))
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("ocr_policy drifted", out.stdout)
        KIT.write_text(self.original)

    def test_accepted_row_without_vision_fails(self):
        # The recorded vision pass is the primary textless control, so an accepted attempt with
        # no verdict behind it is a broken claim — the sidecar pin is kept consistent so this
        # fails on the verdict, not on a stale hash.
        import hashlib

        log = KIT.parent / "generation.json"
        original_log = log.read_text()
        try:
            rows = json.loads(original_log)
            accepted = [r for r in rows if r.get("verdict") == "accepted"]
            self.assertTrue(accepted, "the shipped kit has no accepted row to mutate")
            del accepted[0]["vision"]
            log.write_text(json.dumps(rows))
            kit = json.loads(self.original)
            kit["generation_log"]["sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
            kit["generation_log"]["rows"] = len(rows)
            KIT.write_text(json.dumps(kit))
            out = self._check()
            self.assertEqual(out.returncode, 1, out.stdout)
            self.assertIn("records no vision verdict", out.stdout)
        finally:
            log.write_text(original_log)
            KIT.write_text(self.original)


class FieldAtlasJudge(unittest.TestCase):
    """`field_atlas` keeps its own approved shape, but a display-kit loader only reads `roles`, so
    its role vocabulary and duplicate-id rule are judged exactly like the seven."""

    KIT = ROOT / "assets" / "visual-kits" / "field_atlas" / "kit.json"

    @classmethod
    def setUpClass(cls):
        cls.original = cls.KIT.read_text()

    @classmethod
    def tearDownClass(cls):
        cls.KIT.write_text(cls.original)

    def _mutate_and_check(self, mutate, expect: str) -> None:
        try:
            kit = json.loads(self.original)
            mutate(kit)
            self.KIT.write_text(json.dumps(kit))
            out = run("--check-one", "field_atlas")
            self.assertEqual(out.returncode, 1, out.stdout)
            self.assertIn(expect, out.stdout)
        finally:
            self.KIT.write_text(self.original)
            self.assertEqual(self.KIT.read_text(), self.original, "field_atlas not restored")

    def test_unknown_role_fails(self):
        def mutate(kit):
            kit["roles"]["wallpaper"] = [dict(kit["roles"]["hero"][0])]
        self._mutate_and_check(mutate, "loader vocabulary")

    def test_duplicate_asset_id_fails(self):
        def mutate(kit):
            kit["roles"]["fox"][0]["id"] = kit["roles"]["hero"][0]["id"]
        self._mutate_and_check(mutate, "declared twice")


    def test_row_without_a_source_fails(self):
        # The exemption above only relaxes *which* source word is acceptable; a row with no source
        # at all is still a broken claim and must be refused.
        def mutate(kit):
            kit["roles"]["home_ground"][0]["source"] = ""
        self._mutate_and_check(mutate, "row declares no source")


class LoaderVocabulary(unittest.TestCase):
    """The judge's role vocabulary must be the one trunk's readers actually mount.

    `home_ground` joined `field_atlas@3` when the owner-approved Home ground became a kit role, and
    the Home stage backdrop is painted from it (`desktop/plugin.js` role
    `kit.home_ground.home-ground`, asserted by
    `test_desktop_home_scene_geometry.test_the_stage_backdrop_is_the_home_ground_plate`). The judge
    kept a copy of the VQ-004 branch's display-only tuple and refused the manifest the product
    ships. Rather than trust either list, this test derives the vocabulary from the consumer: the
    roles `build_cb_assets.py` emits and the roles the shipped kit manifest records.
    """

    @staticmethod
    def _judge():
        import importlib.util

        spec = importlib.util.spec_from_file_location("vq008_kits", SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load the judge from {SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _build_full_roles() -> tuple[str, ...]:
        """`KIT_FULL_ROLES` from the builder's own source, read without importing PIL/venv code."""
        import ast

        tree = ast.parse((ROOT / "scripts" / "build_cb_assets.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "KIT_FULL_ROLES":
                return tuple(role for role, _quality in ast.literal_eval(node.value))
        raise AssertionError("build_cb_assets.py declares no KIT_FULL_ROLES")

    def test_the_vocabulary_covers_every_role_the_build_mounts(self):
        roles = set(self._judge().KIT_ROLES)
        built = set(self._build_full_roles())
        self.assertIn("home_ground", built,
                      "the builder no longer mounts the Home ground; re-decide the vocabulary")
        self.assertLessEqual(built, roles, f"{built - roles} is mounted by the build but refused "
                                           f"by the judge")

    def test_the_vocabulary_covers_every_shipped_kit_role(self):
        manifest = json.loads((ROOT / "assets" / "kit" / "manifest.json").read_text(encoding="utf-8"))
        shipped = {str(row.get("kit_role") or "") for row in manifest} - {""}
        self.assertIn("home_ground", shipped,
                      "the shipped manifest records no home_ground plate")
        self.assertLessEqual(shipped, set(self._judge().KIT_ROLES),
                             f"{shipped - set(self._judge().KIT_ROLES)} ships but the judge refuses it")

    def test_the_home_stage_backdrop_names_the_role(self):
        # The surface, not a comment: the desktop plugin resolves the ground under this role name.
        plugin = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
        self.assertIn('"role": "kit.home_ground.home-ground"', plugin)


if __name__ == "__main__":
    unittest.main()
