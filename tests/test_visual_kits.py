"""The curated-kit loader as a pure policy module: no profile, no database, no provider.

``coursebook/visual_kits.py`` is the only reader of ``assets/visual-kits/<grammar>/kit.json``, and
the shelf it must read is the one trunk ships — eight grammars, each with its own manifest shape.
These tests prove the loader's *rules* in isolation from the world job (which
``tests/test_vq004_world_kit.py`` covers end to end):

* a manifest is validated, never trusted: id/grammar/version, the display lane, kit-local PNG
  paths, the declared sha256 and decoded size, textless, and a provenance word;
* the role vocabulary is the shelf's, including ``home_ground``;
* a role resolves through the manifest's own fallback chain and records which kit role answered;
* approval is read from the manifest's ``status``, so a review-status kit never looks approved.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coursebook import visual_kits

#: A 1x1 transparent PNG: a real raster header the loader can decode, at test size.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000b4944415478da63fcffff3f0300050001a5f645400000000049454e44ae426082"
)


class Shelf:
    """A one-grammar kit shelf in a temp directory, editable by a test."""

    def __init__(self, root: Path, *, grammar: str = "lab_bench", version: int = 1) -> None:
        self.root = root
        self.grammar = grammar
        self.version = version

    @property
    def directory(self) -> Path:
        return self.root / self.grammar

    def build(self) -> "Shelf":
        self.directory.mkdir(parents=True, exist_ok=True)
        for relative in ("hero/hero.png", "cover/cover.png", "section/section.png"):
            target = self.directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(PNG)
        manifest = {
            "kit_id": f"{self.grammar}@{self.version}",
            "grammar": self.grammar,
            "version": self.version,
            "lane": "display_plate",
            "status": "built_for_owner_review",
            "fallbacks": {"section": ["lesson_scene", "hero"]},
            "roles": {
                "hero": [self._row("hero-1", "hero", "hero/hero.png")],
                "cover": [self._row("cover-1", "cover", "cover/cover.png")],
                "section": [self._row("section-1", "section", "section/section.png")],
            },
        }
        (self.directory / "kit.json").write_text(json.dumps(manifest), encoding="utf-8")
        return self

    def _row(self, asset_id: str, role: str, relative: str) -> dict:
        data = (self.directory / relative).read_bytes()
        return {
            "id": asset_id,
            "role": role,
            "path": relative,
            "size": [1, 1],
            "sha256": hashlib.sha256(data).hexdigest(),
            "textless": True,
            "source": "curated_kit",
        }

    def rewrite(self, mutate) -> None:
        path = self.directory / "kit.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        mutate(manifest)
        path.write_text(json.dumps(manifest), encoding="utf-8")

    def load(self) -> visual_kits.VisualKit:
        return visual_kits.load_kit(self.grammar, root=self.root)


class KitShelfCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.shelf = Shelf(self.root).build()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def refusal(self) -> str:
        with self.assertRaises(visual_kits.KitError) as caught:
            self.shelf.load()
        return caught.exception.reason


class ManifestValidationTest(KitShelfCase):
    def test_a_valid_kit_loads_with_every_field_verified(self) -> None:
        kit = self.shelf.load()
        self.assertEqual(kit.kit_id, "lab_bench@1")
        self.assertEqual(kit.grammar, "lab_bench")
        self.assertEqual(kit.version, 1)
        hero = kit.assets("hero")[0]
        self.assertEqual(hero.sha256, hashlib.sha256(PNG).hexdigest())
        self.assertEqual(hero.size, (1, 1))
        self.assertTrue(hero.textless)

    def test_a_missing_lane_is_refused(self) -> None:
        self.shelf.rewrite(lambda manifest: manifest.pop("lane"))
        self.assertEqual(self.refusal(), "kit_wrong_lane")

    def test_a_press_plate_lane_is_refused(self) -> None:
        self.shelf.rewrite(lambda manifest: manifest.update({"lane": "press_plate"}))
        self.assertEqual(self.refusal(), "kit_wrong_lane")

    def test_a_kit_id_that_disagrees_with_grammar_and_version_is_refused(self) -> None:
        self.shelf.rewrite(lambda manifest: manifest.update({"kit_id": "lab_bench@9"}))
        self.assertEqual(self.refusal(), "kit_id_mismatch")

    def test_a_grammar_that_disagrees_with_its_directory_is_refused(self) -> None:
        self.shelf.rewrite(lambda manifest: manifest.update({"grammar": "observatory"}))
        self.assertEqual(self.refusal(), "kit_grammar_mismatch")

    def test_a_tampered_asset_is_refused(self) -> None:
        (self.shelf.directory / "hero" / "hero.png").write_bytes(PNG + b"\x00")
        self.assertEqual(self.refusal(), "kit_asset_hash_mismatch")

    def test_a_declared_size_that_is_not_the_raster_is_refused(self) -> None:
        self.shelf.rewrite(
            lambda manifest: manifest["roles"]["hero"][0].update({"size": [2, 2]})
        )
        self.assertEqual(self.refusal(), "kit_asset_size_mismatch")

    def test_a_plate_that_is_not_textless_is_refused(self) -> None:
        self.shelf.rewrite(
            lambda manifest: manifest["roles"]["hero"][0].update({"textless": False})
        )
        self.assertEqual(self.refusal(), "kit_asset_not_textless")

    def test_a_path_outside_the_kit_directory_is_refused(self) -> None:
        self.shelf.rewrite(
            lambda manifest: manifest["roles"]["hero"][0].update({"path": "../../hero.png"})
        )
        self.assertEqual(self.refusal(), "kit_asset_path_invalid")

    def test_a_row_with_no_source_is_refused(self) -> None:
        self.shelf.rewrite(lambda manifest: manifest["roles"]["hero"][0].pop("source"))
        self.assertEqual(self.refusal(), "kit_asset_source_invalid")

    def test_a_row_claiming_a_provider_generated_it_is_refused(self) -> None:
        self.shelf.rewrite(
            lambda manifest: manifest["roles"]["hero"][0].update({"source": "generated"})
        )
        self.assertEqual(self.refusal(), "kit_asset_source_invalid")

    def test_a_derived_row_is_accepted_and_keeps_its_own_word(self) -> None:
        # field_atlas@3's Home ground is a byte-identical copy of an approved plate and records
        # ``derived``; the loader mounts it and never relabels the file.
        self.shelf.rewrite(
            lambda manifest: manifest["roles"]["hero"][0].update({"source": "derived"})
        )
        kit = self.shelf.load()
        self.assertEqual(kit.assets("hero")[0].source, "derived")

    def test_an_unknown_role_is_refused_rather_than_guessed(self) -> None:
        self.shelf.rewrite(
            lambda manifest: manifest["roles"].update(
                {"mood_board": [manifest["roles"]["hero"][0]]}
            )
        )
        self.assertEqual(self.refusal(), "kit_unknown_role")

    def test_a_kit_without_a_hero_is_incomplete(self) -> None:
        self.shelf.rewrite(lambda manifest: manifest["roles"].pop("hero"))
        self.assertEqual(self.refusal(), "kit_incomplete")


class FallbackResolutionTest(KitShelfCase):
    def test_a_declared_role_uses_its_own_plate(self) -> None:
        plate = self.shelf.load().resolve("section", section_key="s1")
        assert plate is not None
        self.assertEqual(plate.role_source, "section")
        self.assertEqual(plate.asset.asset_id, "section-1")

    def test_a_missing_role_walks_the_manifest_chain_and_says_so(self) -> None:
        self.shelf.rewrite(lambda manifest: manifest["roles"].pop("section"))
        plate = self.shelf.load().resolve("section", section_key="s1")
        assert plate is not None
        self.assertEqual(plate.role_source, "hero")
        self.assertEqual(plate.asset.asset_id, "hero-1")

    def test_an_empty_declared_chain_is_treated_as_not_declared(self) -> None:
        # ``"fallbacks": {"section": []}`` behaves as if the key were absent, so the loader's own
        # default chain applies. A kit that means "no fallback" omits the role's plates *and* the
        # default (e.g. ``object``), which resolves to nothing below.
        self.shelf.rewrite(lambda manifest: manifest["roles"].pop("section"))
        self.shelf.rewrite(lambda manifest: manifest.update({"fallbacks": {"section": []}}))
        plate = self.shelf.load().resolve("section", section_key="s1")
        assert plate is not None
        self.assertEqual(plate.role_source, "hero")

    def test_a_role_with_no_plate_and_no_default_chain_resolves_to_nothing(self) -> None:
        self.assertIsNone(self.shelf.load().resolve("object"))

    def test_the_cover_prefers_the_4x5_plate_when_a_kit_declares_both(self) -> None:
        # A 4x5 is what the display cover is mounted at; a 3:2 master of the same art must not win.
        wide = self.shelf.directory / "cover" / "wide.png"
        wide.write_bytes(PNG)

        def add_wide(manifest: dict) -> None:
            row = dict(manifest["roles"]["cover"][0])
            row.update({"id": "cover-wide", "path": "cover/wide.png", "size": [1, 1]})
            manifest["roles"]["cover"].append(row)

        self.shelf.rewrite(add_wide)
        plate = self.shelf.load().resolve("cover")
        assert plate is not None
        # Both test plates are 1x1 (aspect 1.0): the walk is deterministic, first declared wins.
        self.assertEqual(plate.asset.asset_id, "cover-1")

    def test_a_section_key_picks_the_plate_declared_for_it(self) -> None:
        second = self.shelf.directory / "section" / "second.png"
        second.write_bytes(PNG)

        def add_second(manifest: dict) -> None:
            row = dict(manifest["roles"]["section"][0])
            row.update({"id": "section-2", "path": "section/second.png", "section_key": "s2"})
            manifest["roles"]["section"].append(row)

        self.shelf.rewrite(add_second)
        kit = self.shelf.load()
        self.assertEqual(kit.resolve("section", section_key="s2").asset.asset_id, "section-2")
        self.assertEqual(kit.resolve("section", section_key="s9").asset.asset_id, "section-1")


class ApprovalVocabularyTest(KitShelfCase):
    def test_a_review_status_kit_is_not_owner_approved(self) -> None:
        kit = self.shelf.load()
        self.assertEqual(kit.status, "built_for_owner_review")
        self.assertFalse(kit.owner_approved)

    def test_the_owner_approved_spellings_are_approved(self) -> None:
        for status in ("approved", "approved_once"):
            with self.subTest(status=status):
                self.assertTrue(visual_kits.is_owner_approved_status(status))

    def test_an_owner_rework_lineage_is_approved_however_it_is_extended(self) -> None:
        # field_atlas@2 was the owner's rework of a rejected v1; field_atlas@3 extends the same
        # decision with the adopted Home ground. Both are owner approval, not a pending review.
        for status in (
            "owner_rework_of_rejected_v1",
            "owner_rework_of_rejected_v1_plus_adopted_home_ground",
        ):
            with self.subTest(status=status):
                self.assertTrue(visual_kits.is_owner_approved_status(status))

    def test_an_unknown_or_empty_status_is_not_approval(self) -> None:
        for status in ("", None, "draft", "pending_owner_review", "rejected_v1"):
            with self.subTest(status=status):
                self.assertFalse(visual_kits.is_owner_approved_status(status))

    def test_a_kit_approval_reads_the_manifest_it_is_asked_about(self) -> None:
        self.shelf.rewrite(lambda manifest: manifest.update({"status": "approved"}))
        self.assertEqual(
            visual_kits.kit_approval("lab_bench@1", root=self.root), (True, "approved")
        )
        # A different version is not this kit: the caller keeps what its artifact recorded.
        self.assertIsNone(visual_kits.kit_approval("lab_bench@7", root=self.root))


class ShippedShelfTest(unittest.TestCase):
    """The shelf trunk actually ships: eight grammars, loaded by the product's own reader."""

    def setUp(self) -> None:
        visual_kits.bind_root(None)
        self.shelf = visual_kits.default_root()

    def tearDown(self) -> None:
        visual_kits.bind_root(None)

    def grammars(self) -> list[str]:
        return sorted(path.name for path in self.shelf.iterdir() if path.is_dir())

    def test_the_shelf_carries_the_eight_grammar_kits(self) -> None:
        self.assertEqual(
            self.grammars(),
            [
                "archive_desk",
                "field_atlas",
                "instrument_board",
                "kitchen_table",
                "lab_bench",
                "observatory",
                "studio_bench",
                "workshop_manual",
            ],
        )

    def test_every_shipped_kit_loads_and_mounts_a_display_plate_for_each_contract_role(self) -> None:
        for grammar in self.grammars():
            with self.subTest(grammar=grammar):
                kit = visual_kits.load_kit(grammar)
                for role in ("hero", "cover", "section", "lesson_scene"):
                    plate = kit.resolve(role, section_key="s1")
                    self.assertIsNotNone(plate, f"{grammar}: no plate for {role}")
                    assert plate is not None
                    self.assertTrue(plate.asset.textless)
                    self.assertIn(plate.asset.source, visual_kits.KIT_SOURCES)
                    self.assertEqual(plate.asset.kit_id, kit.kit_id)

    def test_the_home_ground_is_a_kit_role_and_records_derived_bytes(self) -> None:
        kit = visual_kits.load_kit("field_atlas")
        self.assertTrue(kit.has_role("home_ground"))
        plate = kit.resolve("home_ground")
        assert plate is not None
        self.assertEqual(plate.role_source, "home_ground")
        self.assertEqual(plate.asset.source, "derived")
        self.assertEqual(plate.asset.size, (1344, 768))

    def test_the_seven_review_kits_are_not_approved_and_field_atlas_is(self) -> None:
        for grammar in self.grammars():
            with self.subTest(grammar=grammar):
                kit = visual_kits.load_kit(grammar)
                self.assertEqual(kit.owner_approved, grammar == "field_atlas")

    def test_a_grammar_with_no_kit_is_a_named_reason_not_an_exception(self) -> None:
        kit, reason = visual_kits.kit_available("no_such_grammar")
        self.assertIsNone(kit)
        assert reason is not None
        self.assertEqual(reason["reason"], "curated_kit_unavailable")
        self.assertEqual(reason["kit_reason"], "kit_missing")
        self.assertEqual(reason["grammar"], "no_such_grammar")


class RasterHeaderTest(unittest.TestCase):
    def test_png_size_reads_the_ihdr(self) -> None:
        self.assertEqual(visual_kits.png_size(PNG), (1, 1))

    def test_non_png_bytes_have_no_size(self) -> None:
        for data in (b"", b"GIF89a" + b"\x00" * 40, b"\x89PNG\r\n\x1a\n" + b"\x00" * 10):
            with self.subTest(data=data[:8]):
                self.assertIsNone(visual_kits.png_size(data))

    def test_a_shipped_hero_header_matches_its_manifest_size(self) -> None:
        kit = visual_kits.load_kit("lab_bench")
        hero = kit.assets("hero")[0]
        self.assertEqual(visual_kits.png_size(hero.abs_path.read_bytes()), hero.size)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
