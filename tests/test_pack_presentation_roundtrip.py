"""A Game course must survive export and import with its world kit intact.

The promise is "someone else imports this and it just works exactly as it did on the author's
device". For a Game course that is more than text: the course mode, the approved world and the
plates behind the hero, the cover and each section have to travel too. ``cb.pack`` v3 adds one
optional ``presentation`` block for exactly that; these tests drive the real export and import
pipeline and then read the imported world back through ``world.read``.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from coursebook import artifacts, db, generation, pack_flow, packs, world
from tests.kernel_support import KernelCase
from tests.test_course_export import AuthoredCourseCase
from tests.test_world import FakeWorldMedia

NOW = "2026-11-11T12:00:00Z"
STYLE_HASH = "sha256:" + "a" * 64


class GamePackRoundTripCase(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.work = Path(tempfile.mkdtemp(prefix="coursebook-game-pack-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        with db.read() as connection:
            generation.ensure_schema(connection)

    # The authored-course fixture is reused, not re-invented: a Game course differs only in its
    # mode and its world, and its lessons are the same validated pages.
    def seed(self) -> dict:
        seeded = AuthoredCourseCase.seed_course(self, sections=2)
        self.execute(
            "UPDATE courses SET presentation_mode = 'game' WHERE id = ?", (seeded["course_id"],)
        )
        return seeded

    def seed_lessons(self, seeded: dict) -> None:
        AuthoredCourseCase.seed_validated_lessons(self, seeded)

    def seed_world(self, seeded: dict) -> dict:
        store = artifacts.ArtifactStore()
        world_id = "wld_" + seeded["course_id"][-8:]
        asset_ids = {}
        prompts = [("hero", "", "sha256:" + "b" * 64), ("cover", "", "sha256:" + "c" * 64)]
        prompts += [("section", objective_id, "sha256:" + format(ordinal, "064x")) for ordinal, objective_id in
                    enumerate(seeded["objective_ids"], start=1)]
        for index, (role, section_key, prompt_hash) in enumerate(prompts):
            data = FakeWorldMedia.PNG + f"{index}:{role}".encode()
            saved = store.save(
                course_id=seeded["course_id"],
                kind="visual",
                data=data,
                mime="image/png",
                provenance={"generator": "tests", "prompt_hash": prompt_hash},
            )
            asset_ids[(role, section_key)] = str(saved["artifact_id"])
        plates = [(role, key, prompt_hash) for role, key, prompt_hash in prompts]
        kit_hash = world.kit_hash_for(STYLE_HASH, plates)
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO course_worlds (id, course_id, revision, state, brief_json,"
                " concepts_json, selected_concept_id, style_hash, kit_hash, approved_hash,"
                " approved_at, error_json, created_at, updated_at)"
                " VALUES (?, ?, 1, 'approved', ?, '[]', 'concept-1', ?, ?, ?, ?, '{}', ?, ?)",
                (
                    world_id,
                    seeded["course_id"],
                    json.dumps(
                        {
                            "course_id": seeded["course_id"],
                            "title": "Braising at home",
                            "subject_domain": "culinary",
                            "end_capability": "braise without a pressure cooker",
                            "audience": "adult learner",
                            "level": "novice",
                            "locale": "en-US",
                            "tone": "practical, calm, competent",
                            "safety_class": "none",
                            "motifs": ["braise", "pan"],
                            "forbidden": [],
                            "sections": [
                                {"id": objective_id, "title": f"Section {ordinal}"}
                                for ordinal, objective_id in enumerate(seeded["objective_ids"], start=1)
                            ],
                        },
                        sort_keys=True,
                    ),
                    STYLE_HASH,
                    kit_hash,
                    kit_hash,
                    NOW,
                    NOW,
                    NOW,
                ),
            )
            for (role, section_key, prompt_hash) in prompts:
                connection.execute(
                    "INSERT INTO world_assets (id, world_id, role, section_id, section_key,"
                    " artifact_id, style_hash, prompt_hash, textless, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                    (
                        f"was_{role}_{section_key or 'course'}",
                        world_id,
                        role,
                        section_key or None,
                        section_key,
                        asset_ids[(role, section_key)],
                        STYLE_HASH,
                        prompt_hash,
                        NOW,
                    ),
                )
        return {"world_id": world_id, "kit_hash": kit_hash, "asset_ids": asset_ids}

    def export_and_import(self, enrollment_id: str) -> tuple[dict, dict]:
        reviewed = self.ok("course.export.read", {"enrollment_id": enrollment_id})["result"]
        self.assertTrue(reviewed["ready"], reviewed)
        exported = self.ok(
            "course.export",
            {"enrollment_id": enrollment_id, "expected_content_hash": reviewed["content_hash"]},
            idempotency_key="key-game-export-1",
        )["result"]
        archive = Path(
            str(
                self.scalar(
                    "SELECT path FROM artifacts WHERE id = ?",
                    (exported["artifacts"][0]["artifact_id"],),
                )
            )
        )
        staged_id = pack_flow.grant_local_file(archive)
        preview = self.ok("pack.preview", {"staged_id": staged_id})["result"]
        imported = self.ok(
            "pack.import",
            {"staged_id": staged_id, "mode": "fresh"},
            idempotency_key="key-game-import-1",
        )["result"]
        return preview["manifest"], imported


class GamePackExportTest(GamePackRoundTripCase):
    def test_the_export_carries_the_mode_the_world_and_every_plate(self) -> None:
        seeded = self.seed()
        self.seed_lessons(seeded)
        self.seed_world(seeded)

        manifest, _imported = self.export_and_import(seeded["enrollment_id"])

        self.assertEqual(manifest["contract_version"], 3)
        self.assertEqual(manifest["presentation"]["mode"], "game")
        block = manifest["presentation"]["world"]
        self.assertEqual(block["style_hash"], STYLE_HASH)
        self.assertEqual(block["grammar"], world.WorldPolicy.select(block["brief"]))
        self.assertEqual({asset["role"] for asset in block["assets"]}, {"hero", "cover", "section"})
        declared = {entry["path"]: entry for entry in manifest["files"]}
        for asset in block["assets"]:
            self.assertIn(asset["file"], declared)
            self.assertEqual(declared[asset["file"]]["role"], "visual")
            self.assertEqual(declared[asset["file"]]["sha256"], asset["sha256"])
        licensed = {entry["path"] for entry in manifest["license"]["per_artifact"]}
        self.assertEqual(licensed, {asset["file"] for asset in block["assets"]})

    def test_the_imported_course_is_game_with_an_approved_world(self) -> None:
        seeded = self.seed()
        self.seed_lessons(seeded)
        seeded_world = self.seed_world(seeded)

        _manifest, imported = self.export_and_import(seeded["enrollment_id"])

        course = self.rows("SELECT * FROM courses WHERE id = ?", (imported["course_id"],))[0]
        self.assertEqual(course["presentation_mode"], "game")
        read = self.ok("world.read", {"course_id": imported["course_id"]})["result"]
        self.assertEqual(read["presentation_mode"], "game")
        self.assertEqual(read["world"]["state"], "approved")
        self.assertEqual(read["world"]["approved_hash"], read["world"]["kit_hash"])
        roles = {(asset["role"], asset.get("section_key") or "") for asset in read["world"]["assets"]}
        self.assertEqual(len(roles), 4)
        self.assertIn(("hero", ""), roles)
        self.assertIn(("cover", ""), roles)
        # Section plates are re-keyed to the objectives this import created, not to the ids the
        # exporter's database used.
        section_keys = {key for role, key in roles if role == "section"}
        imported_objectives = {
            str(row["id"])
            for row in self.rows(
                "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
                " WHERE p.course_id = ?",
                (imported["course_id"],),
            )
        }
        self.assertEqual(section_keys, imported_objectives)
        self.assertNotEqual(read["world"]["kit_hash"], seeded_world["kit_hash"])

    def test_the_imported_plate_bytes_are_servable_and_unchanged(self) -> None:
        seeded = self.seed()
        self.seed_lessons(seeded)
        seeded_world = self.seed_world(seeded)
        _manifest, imported = self.export_and_import(seeded["enrollment_id"])

        read = self.ok("world.read", {"course_id": imported["course_id"]})["result"]
        original = {}
        for (role, key), artifact_id in seeded_world["asset_ids"].items():
            digest = str(
                self.scalar("SELECT content_hash FROM artifacts WHERE id = ?", (artifact_id,))
            )
            original[(role, key)] = digest
        imported_digests = {
            (asset["role"], asset.get("section_key") or ""): str(
                self.scalar(
                    "SELECT content_hash FROM artifacts WHERE id = ?", (asset["artifact_id"],)
                )
            )
            for asset in read["world"]["assets"]
        }
        self.assertEqual(len(imported_digests), 4)
        for role in ("hero", "cover"):
            self.assertEqual(imported_digests[(role, "")], original[(role, "")])


class GamePackManifestRulesTest(KernelCase):
    def test_a_section_plate_with_no_matching_objective_is_refused(self) -> None:
        document = {
            "contract": "cb.pack",
            "contract_version": 3,
            "pack_id": "authored-test",
            "pack_version": "1.0.0",
            "title": "Test",
            "recipe": "committed",
            "minimum_coursebook_version": "0.1.0",
            "license": {"id": "all-rights-reserved", "redistribution": "local_only"},
            "attribution": "test",
            "objectives": [],
            "files": [],
            "presentation": {
                "mode": "game",
                "world": {
                    "grammar": "field_atlas",
                    "style_id": "concept-1",
                    "style_hash": STYLE_HASH,
                    "kit_hash": "kit",
                    "assets": [
                        {
                            "role": "section",
                            "section_ordinal": 9,
                            "file": "world/section-9.png",
                            "sha256": "sha256:" + "a" * 64,
                            "style_hash": STYLE_HASH,
                            "prompt_hash": "p",
                        }
                    ],
                },
            },
        }
        document = packs.with_content_hash(document)
        with self.assertRaises(packs.PackRejected):
            packs.validate_manifest(document)


class MediaPackRoundTripTest(GamePackRoundTripCase):
    """A section's own generated visual/narration must travel with the lesson."""

    def _attach_media(self, seeded: dict, *, role: str = "visual") -> str:
        store = artifacts.ArtifactStore()
        payload = FakeWorldMedia.PNG + b"lesson-media"
        saved = store.save(
            course_id=seeded["course_id"],
            kind=role,
            data=payload,
            mime="image/png",
            provenance={"generator": "tests", "label": "Illustration"},
        )
        lesson_row = f"lsn_1_{seeded['plan_id']}"
        item = {
            "kind": role,
            "role": role,
            "purpose": "A pan with browned ribs",
            "text_equivalent": "A pan holding browned short ribs.",
            "artifact_id": str(saved["artifact_id"]),
            "mime": "image/png",
            "label": "Illustration",
            "degraded": False,
            "reason": None,
        }
        self.execute(
            "UPDATE gen_lessons SET media_json = ? WHERE id = ?",
            (json.dumps([item]), lesson_row),
        )
        return str(saved["artifact_id"])

    def test_export_carries_the_section_media_and_import_serves_it(self) -> None:
        seeded = self.seed()
        self.seed_lessons(seeded)
        artifact_id = self._attach_media(seeded)

        manifest, imported = self.export_and_import(seeded["enrollment_id"])

        self.assertEqual(len(manifest["media"]), 1)
        link = manifest["media"][0]
        self.assertTrue(link["path"].startswith("media/"))
        declared = {entry["path"]: entry for entry in manifest["files"]}
        self.assertEqual(declared[link["path"]]["role"], "visual")
        self.assertTrue(declared[link["path"]]["text_equivalent"])
        self.assertIn(
            link["path"],
            {entry["path"] for entry in manifest["license"]["per_artifact"]},
        )

        objective_id = self.first_objective(imported["course_id"])
        with db.read() as connection:
            segments = connection.execute(
                "SELECT s.kind, s.artifact_id FROM lesson_segments s"
                " JOIN lesson_runs r ON r.id = s.lesson_run_id"
                " WHERE r.objective_id = ? ORDER BY s.ordinal",
                (objective_id,),
            ).fetchall()
        media = [row for row in segments if row["kind"] == "media"]
        self.assertEqual(len(media), 1)
        # ``artifacts`` is hash-addressed and shared: importing the same bytes in the same profile
        # legitimately reuses the row. What must be true is that the segment resolves to real bytes.
        self.assertTrue(str(media[0]["artifact_id"]))
        path = Path(
            str(
                self.scalar(
                    "SELECT path FROM artifacts WHERE id = ?", (str(media[0]["artifact_id"]),)
                )
            )
        )
        self.assertTrue(path.is_file())
        self.assertTrue(path.read_bytes().endswith(b"lesson-media"))

    def first_objective(self, course_id: str) -> str:
        return str(
            self.scalar(
                "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
                " WHERE p.course_id = ? ORDER BY o.ordinal",
                (course_id,),
            )
        )


class GamePackAdversarialRulesTest(KernelCase):
    def _document(self, presentation: dict, recipe: str = "committed") -> dict:
        document = {
            "contract": "cb.pack",
            "contract_version": 3,
            "pack_id": "authored-adversarial",
            "pack_version": "1.0.0",
            "title": "Test",
            "recipe": recipe,
            "minimum_coursebook_version": "0.1.0",
            "license": {"id": "all-rights-reserved", "redistribution": "local_only"},
            "attribution": "test",
            "objectives": [
                {
                    "objective_id": "obj_1",
                    "ordinal": 1,
                    "title": "One",
                    "evidence_target": "recall",
                    "evidence_criteria": ["a", "b", "c"],
                    "sections": [],
                    "checks": [],
                }
            ],
            "files": [],
            "presentation": presentation,
        }
        return packs.with_content_hash(document)

    def test_a_parent_pack_cannot_declare_game(self) -> None:
        document = self._document({"mode": "game"}, recipe="parent")
        with self.assertRaises(packs.PackRejected):
            packs.validate_manifest(document)

    def test_the_world_brief_refuses_unknown_keys(self) -> None:
        document = self._document(
            {
                "mode": "game",
                "world": {
                    "grammar": "field_atlas",
                    "style_id": "c1",
                    "style_hash": STYLE_HASH,
                    "kit_hash": STYLE_HASH,
                    "brief": {"course_id": "crs_1", "attempts": [{"answer": "leaked"}]},
                    "assets": [],
                },
            }
        )
        with self.assertRaises(packs.PackRejected):
            packs.validate_manifest(document)

    def test_a_style_id_longer_than_the_wire_allows_is_refused(self) -> None:
        document = self._document(
            {
                "mode": "game",
                "world": {
                    "grammar": "field_atlas",
                    "style_id": "s" * 81,
                    "style_hash": STYLE_HASH,
                    "kit_hash": STYLE_HASH,
                    "assets": [],
                },
            }
        )
        with self.assertRaises(packs.PackRejected):
            packs.validate_manifest(document)
