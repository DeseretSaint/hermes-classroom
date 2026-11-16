"""VQ-004: the curated world kit, the no-provider path, lesson scenes and the quality critic.

The acceptance this file proves, in the card's own order:

* a Game course with a fake image provider (and a critic) produces a full kit and is approved;
* a Game course with **no provider** produces the curated field-atlas kit, reaches ``kit_ready``
  and ``approved``, and never shows ``unavailable`` while a kit exists;
* a generated plate carrying OCR text is refused and replaced by the curated kit role;
* a course that requests a lesson scene stores it; one that does not still approves without one;
* ``world.approve`` refuses a partial world and refuses a stored refused plate;
* a curated kit's approval provenance is read from its manifest status: a review-status kit
  (``built_for_owner_review``) registers ``approved: False`` and its world cannot be finally
  approved (``kit_not_owner_approved``), while the shipped ``field_atlas@3`` — the owner's rework
  lineage plus the adopted Home ground — stays approved;
* a grammar with no kit and no provider answers with a **named** unavailable reason, not flat art.

Every world is read through the frozen ``cb.rpc`` v26 response validator, so the test fails if the
new storage (``visual_kit_id``, ``lesson_scene_keys``, a lesson-scene asset row) leaks into a
response the contract does not declare.
"""

from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from coursebook import contracts, domain, executor, visual_kits, world, world_critic
from tests.kernel_support import KernelCase, criteria_with, numeric_spec
from tests.test_world import FakeWorldCritic, FakeWorldMedia, WorldHandlerMixin

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000b4944415478da63fcffff3f0300050001a5f645400000000049454e44ae426082"
)


def make_png(width: int, height: int, *, rgba: tuple[int, int, int, int] = (247, 241, 228, 255)) -> bytes:
    """A real, decodable PNG of an exact size — the loader reads the IHDR, so it must be real."""
    row = b"\x00" + bytes(rgba) * width
    raw = row * height

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def asset(role: str, asset_id: str, path: str, data: bytes, *, textless: bool = True) -> dict:
    size = visual_kits.png_size(data) or (0, 0)
    return {
        "id": asset_id,
        "role": role,
        "path": path,
        "size": [size[0], size[1]],
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "textless": textless,
        "source": "curated_kit",
    }


class FixtureKit:
    """A tiny, valid kit on disk: the same shape field_atlas@2 ships, at test size."""

    def __init__(self, root: Path, *, grammar: str = "field_atlas", version: int = 2) -> None:
        self.root = root
        self.grammar = grammar
        self.version = version
        self.directory = root / grammar
        self.manifest: dict = {}

    def build(
        self,
        *,
        with_section: bool = False,
        with_lesson_scene: bool = True,
        with_cover: bool = True,
        lane: str = "display_plate",
        tooltip: str = "",
    ) -> Path:
        (self.directory / "hero").mkdir(parents=True, exist_ok=True)
        hero = make_png(64, 36)
        (self.directory / "hero" / "home-hero.png").write_bytes(hero)
        roles: dict[str, list[dict]] = {"hero": [asset("hero", "home-hero", "hero/home-hero.png", hero)]}
        if with_cover:
            cover = make_png(40, 50)
            (self.directory / "cover").mkdir(parents=True, exist_ok=True)
            (self.directory / "cover" / "cover-4x5.png").write_bytes(cover)
            roles["cover"] = [asset("cover", "cover-4x5", "cover/cover-4x5.png", cover)]
        if with_lesson_scene:
            scene = make_png(64, 36, rgba=(240, 230, 210, 255))
            (self.directory / "lesson-scene").mkdir(parents=True, exist_ok=True)
            (self.directory / "lesson-scene" / "lesson-room.png").write_bytes(scene)
            roles["lesson_scene"] = [
                asset("lesson_scene", "lesson-room", "lesson-scene/lesson-room.png", scene)
            ]
        if with_section:
            section = make_png(32, 32, rgba=(230, 220, 200, 255))
            (self.directory / "section").mkdir(parents=True, exist_ok=True)
            (self.directory / "section" / "section-1x1.png").write_bytes(section)
            roles["section"] = [asset("section", "section-1x1", "section/section-1x1.png", section)]
        self.manifest = {
            "kit_id": f"{self.grammar}@{self.version}",
            "grammar": self.grammar,
            "version": self.version,
            "label": "Field atlas",
            "lane": lane,
            "status": "owner_rework_of_rejected_v1",
            "palette": {"paper": "#f7f1e4", "ink": "#3a2318"},
            "medium": "opaque gouache on warm paper",
            "composition": "a lantern street in three depth planes",
            "ocr_policy": {"fail_rule": "a token of >= 3 alphanumeric characters at confidence >= 60"},
            "fallbacks": {
                "lesson_scene": ["section", "background"],
                "cover": ["course-master", "background"],
                "hero": ["background"],
            },
            "supersedes": {"kit_id": f"{self.grammar}@1", "status": "rejected_by_owner"},
            "roles": roles,
        }
        if tooltip:
            self.manifest["note"] = tooltip
        path = self.directory / "kit.json"
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        return path

    def rewrite(self, mutate) -> Path:  # type: ignore[no-untyped-def]
        mutate(self.manifest)
        path = self.directory / "kit.json"
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        return path


# ── the loader ──────────────────────────────────────────────────────────────


class VisualKitLoaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fixture = FixtureKit(self.root)
        self.fixture.build()

    def tearDown(self) -> None:
        visual_kits.bind_root(None)
        self.tmp.cleanup()

    def load(self) -> visual_kits.VisualKit:
        return visual_kits.load_kit("field_atlas", root=self.root)

    def test_a_valid_kit_loads_and_every_asset_verifies(self) -> None:
        kit = self.load()
        self.assertEqual(kit.kit_id, "field_atlas@2")
        self.assertEqual(kit.grammar, "field_atlas")
        hero = kit.assets("hero")[0]
        self.assertEqual(hero.size, (64, 36))
        self.assertTrue(kit.assets("lesson_scene")[0].textless)
        self.assertEqual(hero.sha256, hashlib.sha256(make_png(64, 36)).hexdigest())

    def test_a_section_resolves_through_the_declared_fallback_chain(self) -> None:
        plate = self.load().resolve("section", section_key="s1")
        assert plate is not None
        # The kit ships no section plate; the lesson scene answers and *says so*.
        self.assertEqual(plate.role_source, "lesson_scene")
        self.assertEqual(plate.asset.asset_id, "lesson-room")

    def test_a_role_with_its_own_plate_uses_it(self) -> None:
        FixtureKit(self.root).build(with_section=True)
        plate = self.load().resolve("section", section_key="s1")
        assert plate is not None
        self.assertEqual(plate.role_source, "section")

    def test_the_cover_resolves_to_the_mounted_4x5_plate(self) -> None:
        plate = self.load().resolve("cover")
        assert plate is not None
        self.assertEqual(plate.asset.size, (40, 50))
        self.assertAlmostEqual(plate.asset.ratio, 0.8)

    def test_a_tampered_asset_is_refused(self) -> None:
        path = self.root / "field_atlas" / "hero" / "home-hero.png"
        path.write_bytes(make_png(64, 36, rgba=(0, 0, 0, 255)))
        with self.assertRaises(visual_kits.KitError) as caught:
            self.load()
        self.assertEqual(caught.exception.reason, "kit_asset_hash_mismatch")

    def test_a_declared_size_that_does_not_match_the_raster_is_refused(self) -> None:
        self.fixture.rewrite(lambda manifest: manifest["roles"]["hero"][0].update({"size": [65, 36]}))
        with self.assertRaises(visual_kits.KitError) as caught:
            self.load()
        self.assertEqual(caught.exception.reason, "kit_asset_size_mismatch")

    def test_a_missing_file_is_refused(self) -> None:
        (self.root / "field_atlas" / "lesson-scene" / "lesson-room.png").unlink()
        with self.assertRaises(visual_kits.KitError) as caught:
            self.load()
        self.assertEqual(caught.exception.reason, "kit_asset_missing")

    def test_a_press_plate_lane_is_refused(self) -> None:
        FixtureKit(self.root).build(lane="press_plate")
        with self.assertRaises(visual_kits.KitError) as caught:
            self.load()
        self.assertEqual(caught.exception.reason, "kit_wrong_lane")

    def test_a_path_outside_the_kit_directory_is_refused(self) -> None:
        outside = self.root / "cover" / "elsewhere.png"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_bytes(make_png(40, 50))
        self.fixture.rewrite(
            lambda manifest: manifest["roles"]["cover"][0].update({"path": "../cover/elsewhere.png"})
        )
        with self.assertRaises(visual_kits.KitError) as caught:
            self.load()
        self.assertEqual(caught.exception.reason, "kit_asset_path_invalid")

    def test_a_plate_that_is_not_textless_is_refused(self) -> None:
        self.fixture.rewrite(lambda manifest: manifest["roles"]["hero"][0].update({"textless": False}))
        with self.assertRaises(visual_kits.KitError) as caught:
            self.load()
        self.assertEqual(caught.exception.reason, "kit_asset_not_textless")

    def test_a_kit_id_that_does_not_match_grammar_and_version_is_refused(self) -> None:
        self.fixture.rewrite(lambda manifest: manifest.update({"kit_id": "field_atlas@9"}))
        with self.assertRaises(visual_kits.KitError) as caught:
            self.load()
        self.assertEqual(caught.exception.reason, "kit_id_mismatch")

    def test_a_rejected_kit_is_never_a_consumer_kit(self) -> None:
        self.fixture.rewrite(lambda manifest: manifest.update({"status": "rejected_by_owner"}))
        with self.assertRaises(visual_kits.KitError) as caught:
            self.load()
        self.assertEqual(caught.exception.reason, "kit_rejected")

    def test_approval_is_read_from_the_manifest_status(self) -> None:
        # field_atlas@2's status is the D-007 owner-approved rework, so it stays approved.
        self.assertTrue(self.load().owner_approved)
        self.assertEqual(self.load().status, "owner_rework_of_rejected_v1")
        # built_for_owner_review is a preview state, not approval — and it still loads.
        self.fixture.rewrite(lambda manifest: manifest.update({"status": "built_for_owner_review"}))
        review = self.load()
        self.assertFalse(review.owner_approved)
        self.assertEqual(review.approval, visual_kits.APPROVAL_OWNER_REVIEW)
        # An unknown or absent status is never assumed to be approved.
        self.fixture.rewrite(lambda manifest: manifest.update({"status": "some_new_state"}))
        self.assertFalse(self.load().owner_approved)
        self.fixture.rewrite(lambda manifest: manifest.pop("status", None))
        self.assertFalse(self.load().owner_approved)
        # The plain approved spellings are the forward-compatible vocabulary.
        self.fixture.rewrite(lambda manifest: manifest.update({"status": "approved"}))
        self.assertTrue(self.load().owner_approved)

    def test_a_missing_grammar_reports_a_named_reason(self) -> None:
        kit, reason = visual_kits.kit_available("kitchen_table", root=self.root)
        self.assertIsNone(kit)
        assert reason is not None
        self.assertEqual(reason["kit_reason"], "kit_missing")


class RealFieldAtlasKitTest(unittest.TestCase):
    """The owner-approved kit in the checkout — the one the live product mounts."""

    def test_the_shipped_kit_validates_and_covers_every_contract_role(self) -> None:
        visual_kits.bind_root(None)
        kit = visual_kits.load_kit("field_atlas")
        self.assertEqual(kit.kit_id, "field_atlas@3")
        # field_atlas@3 is the owner's rework lineage (D-007) plus the adopted Home ground, so it
        # records owner approval rather than an unreviewed preview.
        self.assertTrue(kit.owner_approved)
        self.assertEqual(kit.assets("hero")[0].size, (1344, 768))
        self.assertEqual(len(kit.assets("cover")), 6)
        cover = kit.resolve("cover")
        assert cover is not None
        self.assertEqual(cover.role_source, "cover")
        self.assertEqual(cover.asset.size, (640, 800))
        # Still no section role: the place plate answers, recorded as such.
        section = kit.resolve("section", section_key="s1")
        assert section is not None
        self.assertEqual(section.role_source, "lesson_scene")
        self.assertEqual(section.asset.size, (1344, 768))
        # The Home stage backdrop is a kit role on trunk, and its row truthfully records that the
        # bytes are a derived copy rather than art curated for this kit.
        ground = kit.resolve("home_ground")
        assert ground is not None
        self.assertEqual(ground.role_source, "home_ground")
        self.assertEqual(ground.asset.size, (1344, 768))
        self.assertEqual(ground.asset.source, "derived")

    def test_every_grammar_kit_trunk_ships_loads_and_resolves_its_roles(self) -> None:
        """All eight kits on the shelf are loadable, not just the one the shelf test names."""
        visual_kits.bind_root(None)
        shelf = visual_kits.default_root()
        grammars = sorted(path.name for path in shelf.iterdir() if path.is_dir())
        self.assertEqual(len(grammars), 8, grammars)
        for grammar in grammars:
            with self.subTest(grammar=grammar):
                kit = visual_kits.load_kit(grammar)
                self.assertEqual(kit.grammar, grammar)
                self.assertEqual(kit.kit_id, f"{grammar}@{kit.version}")
                self.assertEqual(kit.manifest.get("lane"), visual_kits.DISPLAY_LANE)
                # Every kit answers a hero, a 4:5 display cover and a lesson scene, and a
                # section always resolves (its own plate or the manifest's fallback chain).
                for role in ("hero", "cover", "lesson_scene", "section"):
                    plate = kit.resolve(role, section_key="s1")
                    self.assertIsNotNone(plate, f"{grammar}: no plate for {role}")
                    assert plate is not None
                    self.assertTrue(plate.asset.textless)
                    self.assertEqual(plate.asset.kit_id, kit.kit_id)


# ── the curated (no provider) world ────────────────────────────────────────


class CuratedWorldTest(WorldHandlerMixin, KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        FixtureKit(self.root).build()
        visual_kits.bind_root(self.root)
        world.bind_media(None)
        world_critic.bind(ocr=world_critic.UNAVAILABLE, vision=world_critic.UNAVAILABLE)
        created = self.ok(
            "course.create",
            {
                "title": "Japanese at the cafe",
                "recipe": "committed",
                "goal": "Greet staff, order a drink and thank them at a Tokyo cafe",
                "subject_domain": "language",
                "level": "L0",
            },
        )["result"]
        self.course_id = created["course_id"]
        self.plan_id = created["plan_id"]
        for title in ("Before-meal greetings", "Ordering a drink", "After-meal thanks"):
            domain.record_objective(
                self.plan_id,
                title=title,
                evidence_target="procedure",
                criteria=criteria_with(numeric_spec()),
            )

    def tearDown(self) -> None:
        world.bind_media(None)
        world_critic.reset()
        visual_kits.bind_root(None)
        self.tmp.cleanup()
        super().tearDown()

    # -- helpers ------------------------------------------------------------

    def _approved_world(self) -> dict:
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "concepts"},
            expected_revision=0,
            idempotency_key="vq4-concepts",
        )
        self.assertEqual(executor.pump_once(limit=1)[0]["state"], "completed")
        read = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(read["world"]["state"], "concepts_ready")
        board = read["world"]["concepts"][0]
        self.ok(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": read["world"]["world_id"],
                "stage": "style",
                "approved_hash": board["style_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="vq4-style",
        )
        after_style = self.ok("world.read", {"course_id": self.course_id})["result"]
        queued = self.ok(
            "world.generate",
            {
                "course_id": self.course_id,
                "stage": "kit",
                "style_id": board["style_id"],
            },
            expected_revision=after_style["revision"],
            idempotency_key="vq4-kit",
        )["result"]
        view = executor.pump_once(limit=1)[0]
        self.assertEqual(view["state"], "completed", view)
        ready = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(ready["world"]["state"], "kit_ready", queued)
        return ready

    def _approve_final(self, read: dict) -> dict:
        return self.ok(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": read["world"]["world_id"],
                "stage": "final",
                "approved_hash": read["world"]["kit_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="vq4-final",
        )

    def _set_kit_status(self, status: str) -> None:
        """Rewrite the fixture manifest's own status, as the owner or a kit build would."""
        path = self.root / "field_atlas" / "kit.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["status"] = status
        path.write_text(json.dumps(manifest), encoding="utf-8")

    # -- acceptance ---------------------------------------------------------

    def test_no_provider_builds_three_curated_directions(self) -> None:
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "concepts"},
            expected_revision=0,
            idempotency_key="vq4-curated-concepts",
        )
        view = executor.pump_once(limit=1)[0]
        self.assertEqual(view["state"], "completed")
        self.assertEqual(view["checkpoint"]["source"], "curated_kit")
        self.assertEqual(view["checkpoint"]["kit_id"], "field_atlas@2")
        read = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(read["world"]["state"], "concepts_ready")
        concepts = read["world"]["concepts"]
        self.assertEqual(len(concepts), 3)
        self.assertEqual(len({item["artifact_id"] for item in concepts}), 3)
        # The stored brief records the kit this world was built on; the wire brief does not carry it.
        stored = json.loads(
            self.scalar("SELECT brief_json FROM course_worlds WHERE course_id = ?", (self.course_id,))
        )
        self.assertEqual(stored["visual_kit_id"], "field_atlas@2")
        self.assertNotIn("visual_kit_id", read["world"]["brief"])
        # No provider call, no invented usage.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs WHERE state = 'completed'"), 1)
        usage = self.scalar("SELECT COUNT(*) FROM usage_events")
        self.assertEqual(int(usage or 0), 0)

    def test_the_curated_kit_reaches_kit_ready_and_approval(self) -> None:
        read = self._approved_world()
        roles = {(item["role"], item["section_key"]) for item in read["world"]["assets"]}
        sections = [item["id"] for item in read["world"]["brief"]["sections"]]
        self.assertIn(("hero", ""), roles)
        self.assertIn(("cover", ""), roles)
        for section_id in sections:
            self.assertIn(("section", section_id), roles)

        approved = self._approve_final(read)["result"]
        self.assertEqual(approved["state"], "approved")
        switched = self.ok(
            "course.mode.set",
            {"course_id": self.course_id, "mode": "game"},
            expected_revision=read["revision"] + 1,
            idempotency_key="vq4-mode",
        )["result"]
        self.assertEqual(switched["mode"], "game")
        self.assertFalse(switched["requires_world"])

    def test_every_curated_plate_records_curated_provenance(self) -> None:
        read = self._approved_world()
        rows = self.rows(
            "SELECT a.provenance_json AS provenance_json FROM world_assets wa"
            " JOIN artifacts a ON a.id = wa.artifact_id WHERE wa.world_id = ?",
            (read["world"]["world_id"],),
        )
        self.assertTrue(rows)
        for row in rows:
            provenance = json.loads(row["provenance_json"])
            self.assertEqual(provenance["source"], "curated_kit")
            self.assertEqual(provenance["kit_id"], "field_atlas@2")
            self.assertTrue(provenance["approved"])
            self.assertEqual(provenance["approval"], "curated_kit_approved_once")
            self.assertEqual(provenance["kit_status"], "owner_rework_of_rejected_v1")

    def test_a_review_status_kit_registers_plates_as_not_owner_approved(self) -> None:
        # VQ-008's seven kits ship this status while their contact sheets await the owner.
        self._set_kit_status("built_for_owner_review")
        read = self._approved_world()
        rows = self.rows(
            "SELECT a.provenance_json AS provenance_json FROM world_assets wa"
            " JOIN artifacts a ON a.id = wa.artifact_id WHERE wa.world_id = ?",
            (read["world"]["world_id"],),
        )
        self.assertTrue(rows)
        for row in rows:
            provenance = json.loads(row["provenance_json"])
            self.assertEqual(provenance["source"], "curated_kit")
            self.assertIs(provenance["approved"], False)
            self.assertEqual(provenance["approval"], "curated_kit_owner_review")
            self.assertEqual(provenance["kit_status"], "built_for_owner_review")
            self.assertNotEqual(provenance["approval"], "curated_kit_approved_once")

    def test_a_review_status_kit_world_is_refused_final_approval(self) -> None:
        self._set_kit_status("built_for_owner_review")
        read = self._approved_world()
        error = self.err(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": read["world"]["world_id"],
                "stage": "final",
                "approved_hash": read["world"]["kit_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="vq4-review-final",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        details = error["details"]
        self.assertEqual(details["reason"], "kit_not_owner_approved")
        self.assertEqual(details["kit_id"], "field_atlas@2")
        self.assertEqual(details["kit_status"], "built_for_owner_review")
        self.assertIn("hero:", details["roles"])
        after = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(after["world"]["state"], "kit_ready")
        self.assertIsNone(after["world"]["approved_at"])

    def test_a_withdrawn_approval_is_refused_at_final_approval(self) -> None:
        # The world was built while the kit was approved; the owner then withdraws approval before
        # the world is blessed. Approval reads the manifest at the moment it runs, not the plate's
        # registration snapshot, so the world is refused and the status reported is the current one.
        read = self._approved_world()
        self._set_kit_status("built_for_owner_review")
        error = self.err(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": read["world"]["world_id"],
                "stage": "final",
                "approved_hash": read["world"]["kit_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="vq4-withdrawn-final",
        )
        self.assertEqual(error["details"]["reason"], "kit_not_owner_approved")
        self.assertEqual(error["details"]["kit_status"], "built_for_owner_review")
        after = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(after["world"]["state"], "kit_ready")
        self.assertIsNone(after["world"]["approved_at"])

    def test_an_owner_approval_after_review_opens_the_gate_and_restates_the_plates(self) -> None:
        # A preview world is not permanently poisoned: once the owner approves the kit, the same
        # world can be approved, and its plates' provenance is restated from the manifest the
        # approval was made against.
        self._set_kit_status("built_for_owner_review")
        read = self._approved_world()
        refused = self.err(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": read["world"]["world_id"],
                "stage": "final",
                "approved_hash": read["world"]["kit_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="vq4-review-first",
        )
        self.assertEqual(refused["details"]["reason"], "kit_not_owner_approved")
        self._set_kit_status("approved")
        after = self.ok("world.read", {"course_id": self.course_id})["result"]
        approved = self._approve_final(after)["result"]
        self.assertEqual(approved["state"], "approved")
        rows = self.rows(
            "SELECT a.provenance_json AS provenance_json FROM world_assets wa"
            " JOIN artifacts a ON a.id = wa.artifact_id WHERE wa.world_id = ?",
            (read["world"]["world_id"],),
        )
        self.assertTrue(rows)
        for row in rows:
            provenance = json.loads(row["provenance_json"])
            self.assertEqual(provenance["source"], "curated_kit")
            self.assertIs(provenance["approved"], True)
            self.assertEqual(provenance["approval"], "curated_kit_approved_once")
            self.assertEqual(provenance["kit_status"], "approved")

    def test_a_reused_plate_follows_the_manifest_status_in_both_directions(self) -> None:
        # The store dedupes by content, so the second registration reuses the first row. Approval
        # is read from the manifest each time, so the row is restated rather than frozen at the
        # status it first saw: review -> approved, and approved -> review.
        kit = visual_kits.load_kit("field_atlas", root=self.root)
        plate = kit.resolve("hero", section_key="", course_id=self.course_id)
        assert plate is not None
        store = visual_kits.artifact_store()

        def register(current: visual_kits.VisualKit) -> dict:
            return visual_kits.register_asset(
                store,
                kit=current,
                plate=plate,
                requested_role="hero",
                section_key="",
                course_id=self.course_id,
                prompt_hash="p" * 64,
                style_hash="s" * 64,
            )

        first = register(kit)
        self.assertIs(first["provenance"]["approved"], True)
        artifact_id = first["artifact_id"]

        self._set_kit_status("built_for_owner_review")
        review = register(visual_kits.load_kit("field_atlas", root=self.root))
        self.assertEqual(review["artifact_id"], artifact_id)
        self.assertIs(review["provenance"]["approved"], False)
        self.assertEqual(review["provenance"]["approval"], visual_kits.APPROVAL_OWNER_REVIEW)
        self.assertEqual(review["provenance"]["kit_status"], "built_for_owner_review")

        self._set_kit_status("owner_rework_of_rejected_v1")
        restored = register(visual_kits.load_kit("field_atlas", root=self.root))
        self.assertIs(restored["provenance"]["approved"], True)
        self.assertEqual(restored["provenance"]["approval"], visual_kits.APPROVAL_APPROVED)
        self.assertEqual(restored["provenance"]["kit_status"], "owner_rework_of_rejected_v1")
        stored = json.loads(
            str(self.scalar("SELECT provenance_json FROM artifacts WHERE id = ?", (artifact_id,)))
        )
        self.assertIs(stored["approved"], True)
        self.assertEqual(stored["kit_status"], "owner_rework_of_rejected_v1")

    def test_a_requested_lesson_scene_is_stored_keyed_by_its_section(self) -> None:
        read = self._approved_world()
        sections = [item["id"] for item in read["world"]["brief"]["sections"]]
        scenes = self.rows(
            "SELECT role, section_id, section_key, artifact_id FROM world_assets"
            " WHERE world_id = ? AND role = 'lesson_scene'",
            (read["world"]["world_id"],),
        )
        self.assertEqual(
            sorted(row["section_key"] for row in scenes), sorted(sections[:2])
        )
        for row in scenes:
            self.assertEqual(row["section_id"], row["section_key"])
            self.assertTrue(row["artifact_id"])
        # The wire asset list is the contract's three roles; the scene rows are resolution data the
        # frozen record cannot express yet.
        self.assertNotIn("lesson_scene", {item["role"] for item in read["world"]["assets"]})
        self._approve_final(read)

    def test_a_course_that_requests_no_scene_approves_without_one(self) -> None:
        # A technical course: the brief builder asks for no lesson scene at all.
        created = self.ok(
            "course.create",
            {
                "title": "Replace a head gasket",
                "recipe": "committed",
                "goal": "Replace a head gasket on a four-cylinder engine",
                "subject_domain": "technical_procedure",
                "level": "novice",
            },
        )["result"]
        course_id, plan_id = created["course_id"], created["plan_id"]
        FixtureKit(self.root, grammar="workshop_manual").build()
        domain.record_objective(
            plan_id,
            title="Before you lift the car",
            evidence_target="procedure",
            criteria=criteria_with(numeric_spec()),
        )
        self.ok(
            "world.generate",
            {"course_id": course_id, "stage": "concepts"},
            expected_revision=0,
            idempotency_key="vq4-workshop-concepts",
        )
        executor.pump_once(limit=1)
        read = self.ok("world.read", {"course_id": course_id})["result"]
        board = read["world"]["concepts"][0]
        self.ok(
            "world.approve",
            {
                "course_id": course_id,
                "world_id": read["world"]["world_id"],
                "stage": "style",
                "approved_hash": board["style_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="vq4-workshop-style",
        )
        ready = self.ok("world.read", {"course_id": course_id})["result"]
        self.ok(
            "world.generate",
            {"course_id": course_id, "stage": "kit", "style_id": board["style_id"]},
            expected_revision=ready["revision"],
            idempotency_key="vq4-workshop-kit",
        )
        self.assertEqual(executor.pump_once(limit=1)[0]["state"], "completed")
        built = self.ok("world.read", {"course_id": course_id})["result"]
        self.assertEqual(built["world"]["state"], "kit_ready")
        self.assertEqual(
            int(
                self.scalar(
                    "SELECT COUNT(*) FROM world_assets WHERE world_id = ? AND role = 'lesson_scene'",
                    (built["world"]["world_id"],),
                )
            ),
            0,
        )
        approved = self.ok(
            "world.approve",
            {
                "course_id": course_id,
                "world_id": built["world"]["world_id"],
                "stage": "final",
                "approved_hash": built["world"]["kit_hash"],
            },
            expected_revision=built["revision"],
            idempotency_key="vq4-workshop-final",
        )["result"]
        self.assertEqual(approved["state"], "approved")

    def test_a_grammar_with_no_kit_and_no_provider_is_unavailable_with_a_reason(self) -> None:
        created = self.ok(
            "course.create",
            {
                "title": "Replace a head gasket",
                "recipe": "committed",
                "goal": "Replace a head gasket on a four-cylinder engine",
                "subject_domain": "technical_procedure",
            },
        )["result"]
        course_id = created["course_id"]
        self.ok(
            "world.generate",
            {"course_id": course_id, "stage": "concepts"},
            expected_revision=0,
            idempotency_key="vq4-no-kit-concepts",
        )
        view = executor.pump_once(limit=1)[0]
        self.assertEqual(view["state"], "failed")
        read = self.ok("world.read", {"course_id": course_id})["result"]
        self.assertEqual(read["world"]["state"], "unavailable")
        self.assertEqual(read["world"]["error"]["reason"], "curated_kit_unavailable")
        self.assertEqual(read["world"]["error"]["grammar"], "workshop_manual")
        self.assertEqual(read["world"]["error"]["kit_reason"], "kit_missing")
        self.assertEqual(read["fallback"], "textbook")

    def test_a_partial_curated_world_is_refused_and_never_approved(self) -> None:
        read = self._approved_world()
        world_id = read["world"]["world_id"]
        section_id = read["world"]["brief"]["sections"][0]["id"]
        # A kit that lost a section plate cannot be approved: the row is removed from the world.
        self.execute(
            "DELETE FROM world_assets WHERE world_id = ? AND role = 'section' AND section_key = ?",
            (world_id, section_id),
        )
        error = self.err(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": world_id,
                "stage": "final",
                "approved_hash": read["world"]["kit_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="vq4-partial-final",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "partial_world")
        self.assertIn(f"section:{section_id}", error["details"]["missing_roles"])

    def test_a_stored_refused_plate_is_never_approved(self) -> None:
        from coursebook import artifacts as artifacts_mod

        read = self._approved_world()
        world_id = read["world"]["world_id"]
        refused = artifacts_mod.ArtifactStore().save(
            course_id=self.course_id,
            kind="visual",
            data=PNG + b"refused",
            mime="image/png",
            provenance={
                "role": "orientation",
                "source": "generated",
                "textless": True,
                "approved": False,
                "critic": {"passed": False, "reasons": ["ocr_readable_text"]},
            },
        )
        self.execute(
            "UPDATE world_assets SET artifact_id = ? WHERE world_id = ? AND role = 'cover'",
            (str(refused["artifact_id"]), world_id),
        )
        error = self.err(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": world_id,
                "stage": "final",
                "approved_hash": read["world"]["kit_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="vq4-refused-final",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "plate_not_approved")
        self.assertEqual(error["details"]["roles"], ["cover:"])

    def test_a_stored_kit_id_that_is_not_on_disk_is_a_named_refusal(self) -> None:
        read = self._approved_world()
        world_id = read["world"]["world_id"]
        stored = json.loads(
            str(self.scalar("SELECT brief_json FROM course_worlds WHERE id = ?", (world_id,)))
        )
        stored["visual_kit_id"] = "field_atlas@1"
        self.execute(
            "UPDATE course_worlds SET brief_json = ? WHERE id = ?",
            (json.dumps(stored), world_id),
        )
        # A regenerate on the recorded kit must not silently substitute another version: the job
        # refuses with the named reason and the world is unavailable, never rebuilt on @2.
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "concepts"},
            expected_revision=read["revision"],
            idempotency_key="vq4-stale-kit",
        )
        executor.pump_once(limit=1)
        after = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(after["world"]["state"], "unavailable")
        self.assertEqual(after["world"]["error"]["reason"], "curated_kit_unavailable")
        self.assertEqual(after["world"]["error"]["kit_reason"], "kit_id_not_on_disk")

    def test_the_wire_contract_v26_still_validates_a_world_with_lesson_scenes(self) -> None:
        from coursebook import api
        from tests.kernel_support import request

        read = self._approved_world()
        world.ensure_registered()
        response = api.dispatch(request("world.read", {"course_id": self.course_id}))
        self.assertTrue(response["ok"], response.get("error"))
        contracts.validate_response_payload("world.read", response["result"])
        approved = self._approve_final(read)
        contracts.validate_response_payload("world.approve", approved["result"])


# ── the generated world, with the critic ───────────────────────────────────


class RealKitCuratedWorldTest(WorldHandlerMixin, KernelCase):
    """The same no-provider flow, on the owner-approved kit in the checkout.

    This is the acceptance sentence itself: a Game course with no provider produces the curated
    field-atlas kit and reaches ``kit_ready`` and ``approved``.
    """

    def setUp(self) -> None:
        super().setUp()
        visual_kits.bind_root(None)
        world.bind_media(None)
        world_critic.bind(ocr=world_critic.UNAVAILABLE, vision=world_critic.UNAVAILABLE)
        created = self.ok(
            "course.create",
            {
                "title": "Japanese at the cafe",
                "recipe": "committed",
                "goal": "Greet staff, order a drink and thank them at a Tokyo cafe",
                "subject_domain": "language",
                "level": "L0",
            },
        )["result"]
        self.course_id = created["course_id"]
        self.plan_id = created["plan_id"]
        for title in ("Before-meal greetings", "Ordering a drink", "After-meal thanks"):
            domain.record_objective(
                self.plan_id,
                title=title,
                evidence_target="procedure",
                criteria=criteria_with(numeric_spec()),
            )

    def tearDown(self) -> None:
        world.bind_media(None)
        world_critic.reset()
        visual_kits.bind_root(None)
        super().tearDown()

    def test_the_shipped_kit_serves_a_course_with_no_provider(self) -> None:
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "concepts"},
            expected_revision=0,
            idempotency_key="vq4-real-concepts",
        )
        self.assertEqual(executor.pump_once(limit=1)[0]["state"], "completed")
        read = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(read["world"]["state"], "concepts_ready")
        concepts = read["world"]["concepts"]
        self.assertEqual(len(concepts), 3)
        self.assertEqual(len({item["artifact_id"] for item in concepts}), 3)
        board = concepts[0]
        self.ok(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": read["world"]["world_id"],
                "stage": "style",
                "approved_hash": board["style_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="vq4-real-style",
        )
        ready = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.ok(
            "world.generate",
            {
                "course_id": self.course_id,
                "stage": "kit",
                "style_id": board["style_id"],
            },
            expected_revision=ready["revision"],
            idempotency_key="vq4-real-kit",
        )
        view = executor.pump_once(limit=1)[0]
        self.assertEqual(view["state"], "completed", view)
        self.assertEqual(view["checkpoint"]["kit_id"], "field_atlas@3")
        built = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(built["world"]["state"], "kit_ready")
        self.assertNotEqual(built["world"]["state"], "unavailable")
        approved = self.ok(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": built["world"]["world_id"],
                "stage": "final",
                "approved_hash": built["world"]["kit_hash"],
            },
            expected_revision=built["revision"],
            idempotency_key="vq4-real-final",
        )["result"]
        self.assertEqual(approved["state"], "approved")
        # The hero and the cover are the shipped kit's own plates, at their shipped sizes.
        rows = self.rows(
            "SELECT wa.role AS role, a.bytes AS bytes, a.content_hash AS content_hash,"
            " a.provenance_json AS provenance_json"
            " FROM world_assets wa JOIN artifacts a ON a.id = wa.artifact_id"
            " WHERE wa.world_id = ? ORDER BY wa.role",
            (built["world"]["world_id"],),
        )
        hero = next(row for row in rows if row["role"] == "hero")
        provenance = json.loads(hero["provenance_json"])
        self.assertEqual(provenance["source"], "curated_kit")
        self.assertEqual(provenance["kit_id"], "field_atlas@3")
        self.assertEqual(provenance["kit_asset_size"], [1344, 768])
        self.assertEqual(hero["bytes"], 1577821)
        # The served hero is the shipped file, asserted by hash: the artifact's content address is
        # the bytes on disk and the manifest's own declared sha256, re-derived here rather than
        # remembered.
        shipped = visual_kits.kits_root() / "field_atlas" / "hero" / "home-hero.png"
        shipped_hash = hashlib.sha256(shipped.read_bytes()).hexdigest()
        self.assertEqual(
            shipped_hash,
            "1c7c48e836d9aa3e709d28ecdab9a597358af18a0e2cddc4b5d7ba75912c79b6",
        )
        self.assertEqual(hero["content_hash"], "sha256:" + shipped_hash)
        self.assertEqual(provenance["kit_asset_sha256"], shipped_hash)
        self.assertEqual(
            int(
                self.scalar(
                    "SELECT COUNT(*) FROM world_assets WHERE world_id = ? AND role = 'lesson_scene'",
                    (built["world"]["world_id"],),
                )
            ),
            2,
        )


class GeneratedWorldTest(WorldHandlerMixin, KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        FixtureKit(self.root).build()
        visual_kits.bind_root(self.root)
        self.fake = FakeWorldMedia()
        self.critic = FakeWorldCritic()
        world.bind_media(self.fake)
        world_critic.bind(ocr=self.critic.ocr, vision=self.critic.vision)
        created = self.ok(
            "course.create",
            {
                "title": "Japanese at the cafe",
                "recipe": "committed",
                "goal": "Greet staff, order a drink at a Tokyo cafe",
                "subject_domain": "language",
                "level": "L0",
            },
        )["result"]
        self.course_id = created["course_id"]
        self.plan_id = created["plan_id"]
        for title in ("Before-meal greetings", "Ordering a drink"):
            domain.record_objective(
                self.plan_id,
                title=title,
                evidence_target="procedure",
                criteria=criteria_with(numeric_spec()),
            )

    def tearDown(self) -> None:
        world.bind_media(None)
        world_critic.reset()
        visual_kits.bind_root(None)
        self.tmp.cleanup()
        super().tearDown()

    def _to_style(self) -> dict:
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "concepts"},
            expected_revision=0,
            idempotency_key="vq4g-concepts",
        )
        self.assertEqual(executor.pump_once(limit=1)[0]["state"], "completed")
        read = self.ok("world.read", {"course_id": self.course_id})["result"]
        board = read["world"]["concepts"][0]
        self.ok(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": read["world"]["world_id"],
                "stage": "style",
                "approved_hash": board["style_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="vq4g-style",
        )
        return {"read": self.ok("world.read", {"course_id": self.course_id})["result"], "board": board}

    def test_a_fake_provider_produces_a_full_kit_and_an_approved_world(self) -> None:
        state = self._to_style()
        board = state["board"]
        read = state["read"]
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "kit", "style_id": board["style_id"]},
            expected_revision=read["revision"],
            idempotency_key="vq4g-kit",
        )
        view = executor.pump_once(limit=1)[0]
        self.assertEqual(view["state"], "completed", view)
        self.assertEqual(view["checkpoint"]["refusals"], [])
        # hero, cover, two sections, two lesson scenes
        self.assertEqual(view["checkpoint"]["assets"], 6)
        self.assertEqual(len(self.fake.calls), 3 + 6)
        built = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(built["world"]["state"], "kit_ready")
        approved = self.ok(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": built["world"]["world_id"],
                "stage": "final",
                "approved_hash": built["world"]["kit_hash"],
            },
            expected_revision=built["revision"],
            idempotency_key="vq4g-final",
        )["result"]
        self.assertEqual(approved["state"], "approved")
        # Every generated plate carries the critic verdict that admitted it.
        rows = self.rows(
            "SELECT a.provenance_json AS provenance_json FROM world_assets wa"
            " JOIN artifacts a ON a.id = wa.artifact_id WHERE wa.world_id = ?",
            (built["world"]["world_id"],),
        )
        for row in rows:
            provenance = json.loads(row["provenance_json"])
            self.assertEqual(provenance["source"], "generated")
            self.assertTrue(provenance["critic"]["passed"])

    def test_an_ocr_bearing_plate_is_refused_and_replaced_by_the_curated_role(self) -> None:
        state = self._to_style()
        board, read = state["board"], state["read"]
        self.critic.ocr_text = "COURSEBOOK"
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "kit", "style_id": board["style_id"]},
            expected_revision=read["revision"],
            idempotency_key="vq4g-ocr-kit",
        )
        view = executor.pump_once(limit=1)[0]
        self.assertEqual(view["state"], "completed", view)
        refusals = {item["role"]: item for item in view["checkpoint"]["refusals"]}
        self.assertIn("hero", refusals)
        self.assertEqual(refusals["hero"]["reasons"], ["ocr_readable_text"])
        self.assertEqual(refusals["hero"]["replaced_by"], "curated_kit")
        # One retry per refused role, then the curated role answers.
        self.assertEqual(refusals["hero"]["attempts"], 2)
        self.assertTrue(view["checkpoint"]["curated_fallbacks"])
        built = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(built["world"]["state"], "kit_ready")
        hero = next(
            item for item in built["world"]["assets"] if item["role"] == "hero"
        )
        provenance = json.loads(
            self.scalar(
                "SELECT provenance_json FROM artifacts WHERE id = ?", (hero["artifact_id"],)
            )
        )
        self.assertEqual(provenance["source"], "curated_kit")
        self.assertEqual(provenance["kit_id"], "field_atlas@2")
        # Every plate stored on the world is either certified by the critic or the approved kit;
        # no OCR-bearing generated plate reached world_assets.
        rows = self.rows(
            "SELECT a.provenance_json AS provenance_json FROM world_assets wa"
            " JOIN artifacts a ON a.id = wa.artifact_id WHERE wa.world_id = ?",
            (built["world"]["world_id"],),
        )
        self.assertTrue(rows)
        for row in rows:
            provenance = json.loads(row["provenance_json"])
            if provenance["source"] == "generated":
                self.assertTrue(provenance["critic"]["passed"])
                self.assertNotIn("ocr_readable_text", provenance["critic"]["reasons"])
            else:
                self.assertEqual(provenance["source"], "curated_kit")

    def test_a_host_with_no_critic_uses_the_curated_kit_instead_of_an_uncertified_plate(self) -> None:
        world_critic.bind(ocr=world_critic.UNAVAILABLE, vision=world_critic.UNAVAILABLE)
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "concepts"},
            expected_revision=0,
            idempotency_key="vq4g-nocritic-concepts",
        )
        view = executor.pump_once(limit=1)[0]
        self.assertEqual(view["state"], "completed")
        read = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(read["world"]["state"], "concepts_ready")
        provenance = json.loads(
            self.scalar(
                "SELECT provenance_json FROM artifacts WHERE id = ?",
                (read["world"]["concepts"][0]["artifact_id"],),
            )
        )
        self.assertEqual(provenance["source"], "curated_kit")
        self.assertEqual(len(self.fake.calls), 0)

    def test_a_provider_refusal_is_filled_by_the_curated_role_and_recorded(self) -> None:
        state = self._to_style()
        board, read = state["board"], state["read"]
        section_id = read["world"]["brief"]["sections"][1]["id"]
        self.fake.fail_when = f"Section scene {section_id}"
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "kit", "style_id": board["style_id"]},
            expected_revision=read["revision"],
            idempotency_key="vq4g-partial",
        )
        view = executor.pump_once(limit=1)[0]
        # The curated kit exists, so the missing section is filled by its approved role: the kit is
        # complete and approvable, and the fallback is recorded rather than hidden.
        self.assertEqual(view["state"], "completed", view)
        filled = [
            item
            for item in view["checkpoint"]["curated_fallbacks"]
            if item["role"] == "section" and item["section_key"] == section_id
        ]
        self.assertEqual(len(filled), 1)
        self.assertEqual(filled[0]["kit_role"], "lesson_scene")
        built = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(built["world"]["state"], "kit_ready")


# ── prompts ────────────────────────────────────────────────────────────────


class LessonScenePromptTest(unittest.TestCase):
    def _prompts(self, **kwargs):
        from tests.world_fixtures import JAPANESE_L0_BRIEF

        brief = world.WorldBrief.from_mapping(
            {**JAPANESE_L0_BRIEF, "lesson_scene_keys": ["s1", "s2", "s3"]}
        )
        return world.build_kit_prompts(
            brief, "field_atlas", style_id="field_atlas--authored", **kwargs
        )

    def test_at_most_two_lesson_scenes_are_requested(self) -> None:
        prompts = self._prompts()
        scenes = [prompt for prompt in prompts if prompt.role == "lesson_scene"]
        self.assertEqual([prompt.section_id for prompt in scenes], ["s1", "s2"])
        self.assertEqual([prompt.aspect_ratio for prompt in scenes], ["16:9", "16:9"])
        for prompt in scenes:
            body = prompt.prompt.lower()
            self.assertIn("lesson scene", body)
            self.assertIn("place and mood only", body)
            self.assertIn("no instruction diagram, step chart or sequence of steps", body)

    def test_a_brief_that_requests_none_adds_no_spend(self) -> None:
        from tests.world_fixtures import JAPANESE_L0_BRIEF

        brief = world.WorldBrief.from_mapping(JAPANESE_L0_BRIEF)
        prompts = world.build_kit_prompts(brief, "field_atlas", style_id="field_atlas--authored")
        self.assertEqual([item.role for item in prompts], ["hero", "cover", "section", "section", "section"])

    def test_a_key_the_brief_does_not_declare_is_not_paid_for(self) -> None:
        from tests.world_fixtures import JAPANESE_L0_BRIEF

        brief = world.WorldBrief.from_mapping(
            {**JAPANESE_L0_BRIEF, "lesson_scene_keys": ["s9"]}
        )
        prompts = world.build_kit_prompts(brief, "field_atlas", style_id="field_atlas--authored")
        self.assertNotIn("lesson_scene", {item.role for item in prompts})


class CriticTest(unittest.TestCase):
    def tearDown(self) -> None:
        world_critic.reset()

    def _verdict(self, **critic):
        from tests.world_fixtures import JAPANESE_L0_BRIEF

        brief = world.WorldBrief.from_mapping(JAPANESE_L0_BRIEF)
        prompt = world.build_prompt(brief, "field_atlas", role="hero")
        fake = FakeWorldCritic(**critic)
        world_critic.bind(ocr=fake.ocr, vision=fake.vision)
        return world_critic.critique(PNG, prompt=prompt, brief=brief, grammar="field_atlas", role="hero")

    def test_a_clean_plate_passes_both_passes(self) -> None:
        verdict = self._verdict()
        self.assertTrue(verdict.passed)
        self.assertEqual(verdict.reasons, ())
        self.assertEqual(verdict.evidence["ocr"]["readable"], [])

    def test_readable_text_is_a_hard_fail(self) -> None:
        verdict = self._verdict(ocr_text="STEP 3")
        self.assertFalse(verdict.passed)
        self.assertEqual(verdict.reasons, ("ocr_readable_text",))

    def test_a_short_ocr_token_does_not_fail(self) -> None:
        verdict = self._verdict(ocr_text="ab")
        self.assertTrue(verdict.passed)

    def test_a_vision_hard_fail_is_a_refusal(self) -> None:
        verdict = self._verdict(vision_fails=("subject_swap",))
        self.assertFalse(verdict.passed)
        self.assertEqual(verdict.reasons, ("subject_swap",))

    def test_an_unknown_vision_reason_is_not_a_pass(self) -> None:
        verdict = self._verdict(vision_fails=("looks_fine_to_me",))
        self.assertFalse(verdict.passed)
        self.assertEqual(verdict.unavailable, ("critic_unavailable:vision_invalid",))

    def test_a_missing_pass_makes_the_generated_path_unavailable(self) -> None:
        from tests.world_fixtures import JAPANESE_L0_BRIEF

        brief = world.WorldBrief.from_mapping(JAPANESE_L0_BRIEF)
        prompt = world.build_prompt(brief, "field_atlas", role="hero")
        world_critic.bind(ocr=world_critic.UNAVAILABLE, vision=world_critic.UNAVAILABLE)
        verdict = world_critic.critique(
            PNG, prompt=prompt, brief=brief, grammar="field_atlas", role="hero"
        )
        self.assertFalse(verdict.passed)
        self.assertEqual(verdict.status, "unavailable")
        self.assertIn("critic_unavailable:ocr", verdict.unavailable)
        self.assertIn("critic_unavailable:vision", verdict.unavailable)

    def test_a_score_below_the_rubric_floor_refuses_the_plate(self) -> None:
        from tests.world_fixtures import JAPANESE_L0_BRIEF

        brief = world.WorldBrief.from_mapping(JAPANESE_L0_BRIEF)
        prompt = world.build_prompt(brief, "field_atlas", role="hero")

        def ocr(data, mime):
            return []

        def vision(data, context):
            return {"hard_fails": [], "scores": {"composition": 2.0}}

        world_critic.bind(ocr=ocr, vision=vision)
        verdict = world_critic.critique(
            PNG, prompt=prompt, brief=brief, grammar="field_atlas", role="hero"
        )
        self.assertFalse(verdict.passed)
        self.assertIn("score_below_minimum", verdict.reasons)


if __name__ == "__main__":
    unittest.main()
