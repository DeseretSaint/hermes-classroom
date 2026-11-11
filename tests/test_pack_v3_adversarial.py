"""Adversarial cases for the ``cb.pack`` v3 ``presentation`` import path.

Every case here is a pack a hostile (or merely buggy) author can actually build: a v3 manifest is
just JSON plus bytes, and ``pack.import`` is the trust boundary that turns it into a course a
learner opens. These tests assert the boundary refuses what it cannot honestly reconstruct, and
that what it does import is a world the product can read back and re-approve.

The rules under test are the ones the contract promises: a pack's world block is *Game* art and
identity only; a plate is a declared visual whose bytes match; and an imported Game course's world
has to satisfy the same ``world_brief`` contract a generated world does, or the course imports
broken and every later ``world.read`` fails.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from coursebook import archive, artifacts, db, generation, pack_flow, packs, world
from tests.kernel_support import KernelCase
from tests.test_pack_presentation_roundtrip import GamePackRoundTripCase

STYLE_HASH = "sha256:" + "a" * 64
PROMPT_HASH = "sha256:" + "b" * 64
#: A PNG magic header is all ``artifacts.sniff_mime`` needs; plate bytes are never decoded here.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 64


def _section_id(ordinal: int) -> str:
    """The exporter's objective id shape (``world_brief.sections[].id`` is a minted identifier)."""
    return f"obj-{ordinal:04d}-authored-world-section"


def _objective(ordinal: int) -> dict:
    return {
        "objective_id": f"obj_{ordinal}",
        "ordinal": ordinal,
        "title": f"Objective {ordinal}",
        "evidence_target": "discrimination",
        "evidence_criteria": ["Names B", "Names A", "Names the cue"],
        "sections": [
            {
                "section_id": f"sec_{ordinal}",
                "title": f"Section {ordinal}",
                "path": f"sections/section-{ordinal}.md",
            }
        ],
        "checks": [
            {
                "check_id": f"chk_{ordinal}",
                "version": 1,
                "evidence_target": "discrimination",
                "stimulus": f"Which line is the confession for item {ordinal}?",
                "rubric": ["Chooses B", "Chooses A", "Names the cue"],
                "reference_answer": f"B is the confession for item {ordinal}",
                "audit_state": "passed",
            }
        ],
    }


def _brief(objectives: int = 2, *, sections: list | None = None, **overrides) -> dict:
    brief = {
        "course_id": "crs_source",
        "title": "Crafted world",
        "subject_domain": "reasoning",
        "end_capability": "tell a confession from banter",
        "audience": "adult learner",
        "level": "novice",
        "locale": "en-US",
        "tone": "practical, calm, competent",
        "safety_class": "none",
        "motifs": ["line", "cue"],
        "forbidden": [],
        "sections": sections
        if sections is not None
        else [{"id": _section_id(ordinal), "title": f"Objective {ordinal}"}
              for ordinal in range(1, objectives + 1)],
    }
    brief.update(overrides)
    return brief


class CraftedPackCase(KernelCase):
    """Builds a real v3 archive from a hand-written manifest and imports it through the wire."""

    def craft(
        self,
        *,
        mode: str = "game",
        objectives: int = 2,
        brief: dict | None = None,
        world_block: dict | None = None,
        section_ordinals: list | None = None,
        lesson_scene: bool = False,
    ) -> tuple[dict, dict[str, bytes]]:
        files: dict[str, bytes] = {}
        records: list[dict] = []
        for ordinal in range(1, objectives + 1):
            path = f"sections/section-{ordinal}.md"
            data = (
                f"# Section {ordinal}\n\nLine A is banter; line B is the confession, and the cue "
                f"tells them apart for item {ordinal}.\n"
            ).encode()
            files[path] = data
            records.append(
                {
                    "path": path,
                    "sha256": packs.file_sha256(data),
                    "bytes": len(data),
                    "mime": "text/markdown",
                    "role": "section",
                }
            )
        licenses: list[dict] = []
        assets: list[dict] = []
        wanted = section_ordinals if section_ordinals is not None else list(
            range(1, objectives + 1)
        )
        roles = [("hero", None), ("cover", None)] + [("section", item) for item in wanted]
        if lesson_scene:
            roles.append(("lesson_scene", None))
        for role, ordinal in roles:
            path = f"world/{role}-{ordinal if ordinal is not None else 'course'}.png"
            data = PNG + f"{role}:{ordinal}".encode()
            files[path] = data
            records.append(
                {
                    "path": path,
                    "sha256": packs.file_sha256(data),
                    "bytes": len(data),
                    "mime": "image/png",
                    "role": "visual",
                    "text_equivalent": f"Textless plate for {role} {ordinal or 'course'}.",
                    "description": "Textless orientation art.",
                }
            )
            licenses.append({"path": path, "license_id": "CC0-1.0", "attribution": "test"})
            entry = {
                "role": role,
                "file": path,
                "sha256": packs.file_sha256(data),
                "style_hash": STYLE_HASH,
                "prompt_hash": PROMPT_HASH,
                "textless": True,
            }
            if ordinal is not None:
                entry["section_ordinal"] = ordinal
            assets.append(entry)
        self.last_assets = assets
        document = {
            "contract": "cb.pack",
            "contract_version": 3,
            "pack_id": "crafted-v3-adversarial",
            "pack_version": "1.0.0",
            "title": "Crafted pack",
            "recipe": "committed",
            "minimum_coursebook_version": "0.1.0",
            "license": {"id": "CC0-1.0", "redistribution": "allowed", "per_artifact": licenses},
            "attribution": "crafted for the adversarial suite",
            "objectives": [_objective(ordinal) for ordinal in range(1, objectives + 1)],
            "files": records,
            "presentation": {"mode": mode},
        }
        if world_block is not None:
            document["presentation"]["world"] = world_block
        elif brief is not None:
            document["presentation"]["world"] = self.world_block(brief, assets)
        return packs.with_content_hash(document), files

    def world_block(self, brief: dict | None = None, assets: list | None = None) -> dict:
        return {
            "grammar": "field_atlas",
            "style_id": "concept-1",
            "style_hash": STYLE_HASH,
            "kit_hash": STYLE_HASH,
            "brief": brief if brief is not None else _brief(),
            "assets": assets if assets is not None else [],
        }

    def archive_for(self, manifest: dict, files: dict[str, bytes], name: str) -> Path:
        destination = Path(self.home) / f"{name}.zip"
        archive.write_archive(destination, manifest, files)
        return destination

    def raw_archive_for(self, manifest: dict, files: dict[str, bytes], name: str) -> Path:
        """Write the archive the adversary would write: the writer's own checks are not a fence.

        ``archive.write_archive`` runs the same manifest rules, but a pack arrives as bytes from
        somewhere else. These cases must reach ``pack.preview``/``pack.import`` exactly as a
        hand-built zip would.
        """
        destination = Path(self.home) / f"{name}.zip"
        root = f"{manifest['pack_id']}-{manifest['pack_version']}"
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(files):
                bundle.writestr(f"{root}/{path}", files[path])
            bundle.writestr(f"{root}/pack.json", packs.canonical_json_bytes(manifest) + b"\n")
        return destination

    def assert_refused(self, manifest: dict, files: dict[str, bytes], fragment: str) -> None:
        stage = self.raw_archive_for(manifest, files, "refused")
        staged_id = pack_flow.grant_local_file(stage)
        error = self.err("pack.preview", {"staged_id": staged_id})
        self.assertEqual(error["code"], "PACK_REJECTED", error)
        self.assertEqual(error["details"].get("reason"), "pack_not_importable", error)
        self.assertIn(fragment, str(error["message"]))


class PresentationModeRulesTest(CraftedPackCase):
    def test_a_textbook_pack_that_carries_a_world_is_refused(self) -> None:
        # A Textbook course never paints a world: ``course.export`` writes ``{"mode": "textbook"}``
        # and no plate files. A pack that declares a world under Textbook asks the importer to
        # adopt plates no Textbook course can ever show — today they are staged into the artifact
        # store and then dropped, so the pack's declared content silently disappears.
        manifest, files = self.craft(mode="textbook", brief=_brief())

        self.assert_refused(manifest, files, "requires presentation.mode 'game'")

    def test_a_game_pack_whose_world_carries_no_plates_is_refused(self) -> None:
        # ``mode: game`` with no ``world`` is legal and honest. A ``world`` object with an empty
        # ``assets`` list is a contradiction: it names a kit, an approval and a style, and carries
        # none of the art that approval was given for. Import currently ignores the block.
        manifest, files = self.craft(world_block=self.world_block(_brief(), []))

        self.assert_refused(manifest, files, "declares no plates")


class WorldPlateRoleRulesTest(CraftedPackCase):
    def test_a_world_plate_role_the_read_contract_cannot_carry_is_refused(self) -> None:
        # ``cb.pack`` v3 lists ``lesson_scene`` as a world-plate role, but ``cb.rpc``'s
        # ``world_asset`` (what ``world.read`` returns) only carries hero, cover and section. A pack
        # that declares a lesson scene therefore imports a world whose every read is a
        # non-contract result. A lesson scene also has no lesson binding here: the block names no
        # objective for it, so there is nothing to reconstruct onto.
        manifest, files = self.craft(lesson_scene=True, brief=_brief())

        self.assert_refused(manifest, files, "lesson_scene")


class WorldKitBudgetRulesTest(CraftedPackCase):
    def test_a_world_kit_above_the_plate_budget_is_refused(self) -> None:
        # The kit budget is one hero, one cover and at most six section plates, and ``world.read``
        # returns at most ten assets. A large course (12 objectives) with a plate for every one
        # imports today and then makes ``world.read`` a non-contract result, because the stored
        # world carries fourteen assets.
        manifest, files = self.craft(
            objectives=12, section_ordinals=list(range(1, 13)), brief=_brief(2)
        )

        self.assert_refused(manifest, files, "kit budget")


class WorldBriefContractRulesTest(CraftedPackCase):
    def test_a_brief_the_product_cannot_read_back_is_refused(self) -> None:
        # The pack schema's ``brief`` is looser than ``cb.rpc`` ``world_brief``: every field is
        # optional there. Import copies the block into ``course_worlds.brief_json`` nearly
        # verbatim, so a brief missing ``audience``/``tone``/``safety_class`` imports "successfully"
        # and then makes ``world.read`` return a non-contract result (INTERNAL_ERROR) for the life
        # of the course.
        incomplete = _brief()
        for key in ("audience", "level", "locale", "tone", "safety_class", "motifs", "forbidden"):
            incomplete.pop(key)
        manifest, files = self.craft(brief=incomplete)

        self.assert_refused(manifest, files, "brief")

    def test_a_brief_with_more_sections_than_a_world_brief_holds_is_refused(self) -> None:
        # The pack schema allows 12 brief sections; ``world_brief`` allows 6 (the kit budget). A
        # pack may not store a brief the read contract rejects.
        brief = _brief(
            2, sections=[{"id": _section_id(i), "title": f"S{i}"} for i in range(1, 8)]
        )
        manifest, files = self.craft(brief=brief)

        self.assert_refused(manifest, files, "brief")

    def test_a_route_anchor_outside_the_plate_box_is_refused(self) -> None:
        # ``route_anchors`` is the one brief field the pack schema leaves open (additionalProperties
        # true). A malformed coordinate imports today and every later ``world.read`` refuses with
        # VALIDATION_FAILED: the course has a world that cannot be shown at all.
        brief = _brief(
            route_anchors=[
                {"anchor_id": "anchor-1", "section_id": _section_id(1), "x": 2.0, "y": 0.5}
            ]
        )
        manifest, files = self.craft(brief=brief)

        self.assert_refused(manifest, files, "route_anchors")

    def test_a_route_anchor_naming_an_unknown_section_is_refused(self) -> None:
        brief = _brief(
            route_anchors=[
                {"anchor_id": "anchor-1", "section_id": _section_id(9), "x": 0.5, "y": 0.5}
            ]
        )
        manifest, files = self.craft(brief=brief)

        self.assert_refused(manifest, files, "route_anchors")


class CraftedWorldReconstructionTest(CraftedPackCase):
    def test_a_readable_crafted_world_imports_and_reads_back(self) -> None:
        manifest, files = self.craft(brief=_brief())
        stage = self.archive_for(manifest, files, "readable")
        staged_id = pack_flow.grant_local_file(stage)
        imported = self.ok(
            "pack.import", {"staged_id": staged_id, "mode": "fresh"}, idempotency_key="key-adversarial-read"
        )["result"]

        read = self.ok("world.read", {"course_id": imported["course_id"]})["result"]
        self.assertEqual(read["presentation_mode"], "game")
        self.assertEqual(read["world"]["state"], "approved")
        self.assertEqual(read["world"]["brief"]["course_id"], imported["course_id"])

    def test_a_world_with_no_brief_still_imports_and_reads_back(self) -> None:
        # ``brief`` is optional in the pack contract. A kit without one is still art and identity;
        # the importer must store a readable brief for it rather than a block ``world.read``
        # rejects.
        manifest, files = self.craft(brief=_brief())
        manifest["presentation"]["world"].pop("brief")
        manifest = packs.with_content_hash(manifest)
        stage = self.archive_for(manifest, files, "no-brief")
        staged_id = pack_flow.grant_local_file(stage)
        imported = self.ok(
            "pack.import",
            {"staged_id": staged_id, "mode": "fresh"},
            idempotency_key="key-adversarial-no-brief",
        )["result"]

        read = self.ok("world.read", {"course_id": imported["course_id"]})["result"]
        self.assertEqual(read["world"]["brief"]["course_id"], imported["course_id"])
        self.assertTrue(read["world"]["brief"]["sections"])

    def test_brief_sections_are_rekeyed_to_the_objectives_this_import_created(self) -> None:
        # A brief that names a section with no objective ordinal cannot be seated; the sections it
        # can seat keep their authored titles and gain the imported objective ids as identity.
        brief = _brief(
            sections=[
                {"id": _section_id(1), "title": "Authored one"},
                {"id": _section_id(2), "title": "Authored two"},
                {"id": _section_id(3), "title": "Objective this pack does not carry"},
            ]
        )
        manifest, files = self.craft(brief=brief)
        stage = self.archive_for(manifest, files, "rekey")
        staged_id = pack_flow.grant_local_file(stage)
        imported = self.ok(
            "pack.import", {"staged_id": staged_id, "mode": "fresh"}, idempotency_key="key-adversarial-rekey"
        )["result"]

        read = self.ok("world.read", {"course_id": imported["course_id"]})["result"]
        objective_ids = [
            str(row["id"])
            for row in self.rows(
                "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
                " WHERE p.course_id = ? ORDER BY o.ordinal",
                (imported["course_id"],),
            )
        ]
        self.assertEqual(
            [section["id"] for section in read["world"]["brief"]["sections"]], objective_ids
        )
        self.assertEqual(
            [section["title"] for section in read["world"]["brief"]["sections"]],
            ["Authored one", "Authored two"],
        )


class RoundTripWorldIdentityTest(GamePackRoundTripCase):
    """A real exported Game pack must import into a world that is still a working world."""

    def setUp(self) -> None:
        super().setUp()
        self.work = Path(tempfile.mkdtemp(prefix="coursebook-adversarial-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        with db.read() as connection:
            generation.ensure_schema(connection)

    def test_the_imported_world_can_be_reapproved(self) -> None:
        # ``world.approve`` re-checks that every brief section has a plate. Export writes the
        # author's objective ids into ``brief.sections``; import re-keys the plates to its own
        # objective ids. If the brief is not re-keyed with them, the imported world reports
        # ``partial_world`` and can never be re-approved, even though every plate is present.
        seeded = self.seed()
        self.seed_lessons(seeded)
        self.seed_world(seeded)
        _manifest, imported = self.export_and_import(seeded["enrollment_id"])

        read = self.ok("world.read", {"course_id": imported["course_id"]})["result"]
        objective_ids = {
            str(row["id"])
            for row in self.rows(
                "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
                " WHERE p.course_id = ?",
                (imported["course_id"],),
            )
        }
        self.assertEqual(
            {section["id"] for section in read["world"]["brief"]["sections"]}, objective_ids
        )
        approved = self.ok(
            "world.approve",
            {
                "course_id": imported["course_id"],
                "world_id": read["world"]["world_id"],
                "approved_hash": read["world"]["kit_hash"],
                "stage": "final",
            },
            expected_revision=read["revision"],
            idempotency_key="key-adversarial-reapprove",
        )["result"]
        self.assertEqual(approved["world"]["state"], "approved")

    def test_route_anchors_still_point_at_the_sections_this_import_created(self) -> None:
        seeded = self.seed()
        self.seed_lessons(seeded)
        self.seed_world(seeded)
        # The author's plate declares route geometry over the authoring objective ids (CP-052).
        brief = json.loads(
            str(
                self.scalar(
                    "SELECT brief_json FROM course_worlds WHERE course_id = ?",
                    (seeded["course_id"],),
                )
            )
        )
        brief["route_anchors"] = [
            {"anchor_id": f"anchor-{index}", "section_id": objective_id, "x": 0.25, "y": 0.5}
            for index, objective_id in enumerate(seeded["objective_ids"][:2], start=1)
        ]
        self.execute(
            "UPDATE course_worlds SET brief_json = ? WHERE course_id = ?",
            (json.dumps(brief, sort_keys=True), seeded["course_id"]),
        )

        _manifest, imported = self.export_and_import(seeded["enrollment_id"])

        read = self.ok("world.read", {"course_id": imported["course_id"]})["result"]
        objective_ids = [
            str(row["id"])
            for row in self.rows(
                "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
                " WHERE p.course_id = ? ORDER BY o.ordinal",
                (imported["course_id"],),
            )
        ]
        anchors = read["world"]["brief"]["route_anchors"]
        self.assertEqual([anchor["section_id"] for anchor in anchors], objective_ids)
        self.assertEqual([anchor["anchor_id"] for anchor in anchors], ["anchor-1", "anchor-2"])
