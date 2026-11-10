"""GM-004 — World Studio, the course world surface and the durable mode switch.

Two kinds of proof, both real:

* the backend half runs through ``api.dispatch`` against the real migrated SQLite database on
  ``cb.rpc`` v24 — so "Game needs an approved world" and "a switch touches no attempt or evidence"
  are behaviours of the shipped wiring, not of a helper;
* the desktop half renders the shipped module through React and asserts the composed DOM: a
  Textbook course has no world surface, every studio state has one primary action, and generated
  or brief text never reaches the UI.

What this does not prove: that a live provider returns usable plates, or that the pixels match the
approved concept frames. The isolated rig and ``docs/visual-review/gm-004/`` carry those.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from coursebook import executor, world
from tests.kernel_support import KernelCase
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules
from tests.test_world import FakeWorldMedia

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

STATIC_HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'
import {
  FieldDeskHome, buildDeskModel, WorldStudio, CourseWorldHero, ModeSwitchDialog
} from './plugin.js'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const lib = (rows) => ({
  items: rows, next_cursor: null, total: rows.length,
  empty_reason: rows.length ? null : 'no_courses', applied_filter: 'all'
})

const quiet = () => {}
const deskProps = {
  libraryStatus: 'ready', libraryError: null, stale: false, busy: false, notice: null,
  online: true, onRetry: quiet, onCreate: null, onSyllabus: null, onPrimary: quiet,
  onOpenSection: quiet, onSeePlan: quiet, onRetryEstimate: quiet, onSelectCourse: quiet,
  onOpenStudio: quiet, onOpen: quiet, onShowAll: quiet, sourcesOpen: false,
  onToggleSources: quiet, sourcesStatus: 'idle', sourcesError: null, sources: null,
  onRetrySources: quiet, outlineStatus: 'idle', outlineError: null, onRetryOutline: quiet,
  implemented: new Set(['library.list', 'course.outline', 'world.read', 'course.mode.set']),
  onBrowseLibrary: quiet, companionEnabled: false, onSetMode: quiet, onWorldChanged: quiet
}

const worldRead = (mode, worldValue) => ({
  status: 'ready', error: null,
  data: { course_id: 'crs_1', presentation_mode: mode, world: worldValue, fallback: worldValue && worldValue.state === 'approved' ? null : 'textbook', revision: worldValue ? worldValue.revision : 0 }
})

if (payload.kind === 'course-home') {
  const desk = buildDeskModel({
    library: lib(payload.rows), outline: null, estimate: null,
    selectedCourseId: payload.rows[0].course_id, outlineState: 'idle'
  })
  process.stdout.write(renderToStaticMarkup(
    React.createElement(FieldDeskHome, { ...deskProps, desk, world: payload.world, notes: { status: 'idle', data: null, error: null } })
  ))
} else if (payload.kind === 'studio') {
  process.stdout.write(renderToStaticMarkup(
    React.createElement(WorldStudio, {
      courseId: 'crs_1', mode: payload.mode || 'game', world: payload.world,
      worldStatus: payload.worldStatus || 'ready', worldError: payload.worldError || null,
      onReload: quiet, onClose: quiet, onChanged: quiet, autoStart: false
    })
  ))
} else if (payload.kind === 'hero') {
  process.stdout.write(renderToStaticMarkup(
    React.createElement(CourseWorldHero, {
      world: payload.world, mode: payload.mode || 'game', sectionPlates: payload.sectionPlates || [],
      narrow: Boolean(payload.narrow), onOpenStudio: quiet, onOpenSection: quiet
    })
  ))
} else if (payload.kind === 'dialog') {
  process.stdout.write(renderToStaticMarkup(
    React.createElement(ModeSwitchDialog, {
      mode: payload.mode || 'textbook', world: payload.world || null, pending: false,
      providerUnavailable: Boolean(payload.providerUnavailable),
      onGenerate: quiet, onOpenStudio: quiet, onSwitch: quiet, onKeep: quiet, onCancel: quiet
    })
  ))
}
"""


def row(index: int = 1) -> dict:
    return {
        "enrollment_id": "enr_0000000000000001",
        "course_id": "crs_0000000000000001",
        "title": "Replace a head gasket",
        "subtitle": None,
        "recipe": "committed",
        "level_label": None,
        "locale": None,
        "learner_label": None,
        "enrollment_status": "active",
        "course_status": "active",
        "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
        "next_step": {"kind": "resume_lesson", "label": "Resume this lesson"},
        "evidence_summary": {
            "independent": 0,
            "review_due": 0,
            "total_objectives": 2,
            "current_objective_id": "obj_1",
        },
        "warning": None,
        "updated_at": "2026-11-09T18:00:00.000000+00:00",
        "revision": 1,
    }


def concept(index: int, grammar: str) -> dict:
    return {
        "style_id": f"wld_1--{grammar}",
        "label": grammar,
        "prompt_hash": "sha256:" + str(index) * 64,
        "style_hash": "sha256:" + str(index) * 64,
        "artifact_id": f"art_concept_{index}",
        "palette": ["#1A1713", "#5C5347", "#E8A93A"],
        "medium": "ink on paper",
        "role": "orientation",
        "textless": True,
    }


def world_value(*, state: str = "approved", mode_ready: bool = True, error=None, missing=None) -> dict:
    concepts = [concept(1, "workshop_manual"), concept(2, "service_bay"), concept(3, "cutaway_atlas")]
    assets = []
    if state in ("kit_ready", "approved"):
        assets = [
            {"role": "hero", "section_id": None, "section_key": "hero", "artifact_id": "art_hero",
             "style_hash": "sha256:" + "1" * 64, "prompt_hash": "sha256:" + "2" * 64, "textless": True},
            {"role": "cover", "section_id": None, "section_key": "cover", "artifact_id": "art_cover",
             "style_hash": "sha256:" + "1" * 64, "prompt_hash": "sha256:" + "3" * 64, "textless": True},
            {"role": "section", "section_id": "obj_1", "section_key": "obj_1", "artifact_id": "art_s1",
             "style_hash": "sha256:" + "1" * 64, "prompt_hash": "sha256:" + "4" * 64, "textless": True},
            {"role": "section", "section_id": "obj_2", "section_key": "obj_2", "artifact_id": "art_s2",
             "style_hash": "sha256:" + "1" * 64, "prompt_hash": "sha256:" + "5" * 64, "textless": True},
        ]
    return {
        "world_id": "wld_1",
        "state": state,
        "revision": 4,
        "brief": {
            "course_id": "crs_0000000000000001",
            "title": "Replace a head gasket",
            "subject_domain": "technical_procedure",
            "end_capability": "Replace a head gasket on a four-cylinder engine",
            "audience": "adult learner",
            "level": "novice",
            "locale": "en-US",
            "tone": "practical, calm, competent",
            "safety_class": "workshop",
            "motifs": ["service bay", "tool wall"],
            "forbidden": ["text", "logos"],
            "sections": [{"id": "obj_1", "title": "Before you lift the car"},
                         {"id": "obj_2", "title": "Removing the head"}],
        },
        "concepts": concepts,
        "selected_concept_id": "wld_1--workshop_manual" if mode_ready else None,
        "style_hash": "sha256:" + "1" * 64 if mode_ready else None,
        "kit_hash": "sha256:" + "9" * 64 if state in ("kit_ready", "approved") else None,
        "approved_hash": "sha256:" + "9" * 64 if state == "approved" else None,
        "approved_at": "2026-11-09T18:05:00.000000+00:00" if state == "approved" else None,
        "error": error,
        "updated_at": "2026-11-09T18:05:00.000000+00:00",
        "assets": assets,
    }


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-gm004-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "static.mjs").write_text(STATIC_HARNESS, encoding="utf-8")
        node_modules = cls.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "static.mjs"), str(case)],
            cwd=self.root, capture_output=True, text=True, timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return result.stdout


# ── backend: the mode switch ───────────────────────────────────────────────────


class ModeSwitchTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.fake = FakeWorldMedia()
        world.bind_media(self.fake)
        self.course_id, self.plan_id = self.new_course(title="Replace a head gasket")
        self.enrollment_id = self.new_enrollment(self.course_id)

    def tearDown(self) -> None:
        world.bind_media(None)
        super().tearDown()

    def _approved_world(self) -> dict:
        # Resume from whatever the world already is: a fresh course starts at concepts, while a
        # caller that has already chosen a style continues from there instead of regenerating.
        current = self.ok("world.read", {"course_id": self.course_id})["result"]
        state = (current["world"] or {}).get("state", "not_requested")
        if state in ("not_requested", None):
            self.ok(
                "world.generate", {"course_id": self.course_id, "stage": "concepts"},
                expected_revision=current["revision"], idempotency_key="gm004-concepts",
            )
            self.assertEqual(executor.pump_once(limit=1)[0]["state"], "completed")
            current = self.ok("world.read", {"course_id": self.course_id})["result"]
            state = current["world"]["state"]
        board = current["world"]["concepts"][0]
        if state in ("concepts_ready", "unavailable", "failed"):
            board = current["world"]["concepts"][0]
            selected = self.ok(
                "world.approve",
                {"course_id": self.course_id, "world_id": current["world"]["world_id"],
                 "stage": "style", "approved_hash": board["style_hash"]},
                expected_revision=current["revision"], idempotency_key="gm004-style",
            )["result"]
            current = self.ok("world.read", {"course_id": self.course_id})["result"]
        else:
            selected = current
            board = current["world"]["concepts"][0]
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "kit", "style_id": board["style_id"]},
            expected_revision=current["revision"], idempotency_key="gm004-kit",
        )
        self.assertEqual(executor.pump_once(limit=1)[0]["state"], "completed")
        kit = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.ok(
            "world.approve",
            {"course_id": self.course_id, "world_id": kit["world"]["world_id"],
             "stage": "final", "approved_hash": kit["world"]["kit_hash"]},
            expected_revision=kit["revision"], idempotency_key="gm004-final",
        )
        return self.ok("world.read", {"course_id": self.course_id})["result"]

    def test_switch_to_game_requires_approved_world(self) -> None:
        """Game without an approved world is refused with a reason; Textbook never is."""
        read = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(read["presentation_mode"], "textbook")
        self.assertIsNone(read["world"])
        self.assertEqual(read["fallback"], "textbook")

        refused = self.ok(
            "course.mode.set", {"course_id": self.course_id, "mode": "game"},
            expected_revision=read["revision"], idempotency_key="gm004-mode-1",
        )["result"]
        self.assertTrue(refused["requires_world"])
        self.assertEqual(refused["mode"], "textbook")
        self.assertEqual(refused["world_state"], "not_requested")
        unchanged = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(unchanged["presentation_mode"], "textbook")
        self.assertIsNone(unchanged["world"])

        # A style choice alone is not an approved world.
        self.ok(
            "world.generate", {"course_id": self.course_id, "stage": "concepts"},
            expected_revision=0, idempotency_key="gm004-concepts-2",
        )
        executor.pump_once(limit=1)
        concepts = self.ok("world.read", {"course_id": self.course_id})["result"]
        board = concepts["world"]["concepts"][0]
        self.ok(
            "world.approve",
            {"course_id": self.course_id, "world_id": concepts["world"]["world_id"],
             "stage": "style", "approved_hash": board["style_hash"]},
            expected_revision=concepts["revision"], idempotency_key="gm004-style-2",
        )
        style_only = self.ok("world.read", {"course_id": self.course_id})["result"]
        still = self.ok(
            "course.mode.set", {"course_id": self.course_id, "mode": "game"},
            expected_revision=style_only["revision"], idempotency_key="gm004-mode-2",
        )["result"]
        self.assertTrue(still["requires_world"])
        self.assertEqual(still["world_state"], "style_selected")

        # A final-approved kit lets the course enter Game mode.
        approved = self._approved_world()
        switched = self.ok(
            "course.mode.set", {"course_id": self.course_id, "mode": "game"},
            expected_revision=approved["revision"], idempotency_key="gm004-mode-3",
        )["result"]
        self.assertFalse(switched["requires_world"])
        self.assertEqual(switched["mode"], "game")
        after = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(after["presentation_mode"], "game")
        self.assertIsNone(after["fallback"])

        # Textbook is immediate, keeps the world and its assets, and needs no generation.
        hidden = self.ok(
            "course.mode.set", {"course_id": self.course_id, "mode": "textbook"},
            expected_revision=after["revision"], idempotency_key="gm004-mode-4",
        )["result"]
        self.assertFalse(hidden["requires_world"])
        self.assertEqual(hidden["mode"], "textbook")
        kept = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(kept["presentation_mode"], "textbook")
        self.assertEqual(kept["world"]["state"], "approved")
        self.assertEqual(len(kept["world"]["assets"]), 2)
        # `fallback` names the Textbook presentation only when no world is approved; the approved
        # world stays stored and is what a switch back to Game reuses.
        self.assertIsNone(kept["fallback"])

        # And switching back reuses the approved world without regenerating it.
        calls_before = len(self.fake.calls)
        self.ok(
            "course.mode.set", {"course_id": self.course_id, "mode": "game"},
            expected_revision=kept["revision"], idempotency_key="gm004-mode-5",
        )
        self.assertEqual(len(self.fake.calls), calls_before)

    def test_switch_does_not_touch_attempts_or_evidence(self) -> None:
        """A mode switch changes presentation only: no attempt, transition, check or hash moves."""
        objective_id = self.seed_objective(self.plan_id)
        revision = self.approve(self.enrollment_id, self.plan_id, 0)
        opened = self.ok(
            "check.open", {"enrollment_id": self.enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        submitted = self.submit(
            {
                "enrollment_id": self.enrollment_id,
                "check_id": opened["check_id"],
                "check_version": opened["check_version"],
                "revision": opened["revision"],
            },
            "4",
        )
        self.assertTrue(submitted["ok"], submitted)

        snapshot_sql = {
            "attempts": "SELECT * FROM attempts ORDER BY id",
            "transitions": "SELECT * FROM transitions ORDER BY rowid",
            "checks": "SELECT * FROM checks ORDER BY id",
            "objectives": "SELECT * FROM objectives ORDER BY id",
        }
        before = {name: self.rows(sql) for name, sql in snapshot_sql.items()}
        self.assertGreater(len(before["attempts"]), 0, "the fixture recorded no attempt")

        approved = self._approved_world()
        game = self.ok(
            "course.mode.set", {"course_id": self.course_id, "mode": "game"},
            expected_revision=approved["revision"], idempotency_key="gm004-ev-game",
        )["result"]
        self.assertEqual(game["mode"], "game")
        read = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.ok(
            "course.mode.set", {"course_id": self.course_id, "mode": "textbook"},
            expected_revision=read["revision"], idempotency_key="gm004-ev-textbook",
        )
        after = {name: self.rows(sql) for name, sql in snapshot_sql.items()}
        for name in snapshot_sql:
            self.assertEqual(before[name], after[name], f"the mode switch rewrote {name}")

    def test_textbook_create_records_no_world_intent(self) -> None:
        """Creation intent is stored honestly: Game is game, everything else reads Textbook."""
        textbook, _ = self.new_course(title="Textbook course")
        mode = self.scalar("SELECT presentation_mode FROM courses WHERE id = ?", (textbook,))
        self.assertIsNone(mode)
        read = self.ok("world.read", {"course_id": textbook})["result"]
        self.assertEqual(read["presentation_mode"], "textbook")
        self.assertIsNone(read["world"])

        game = self.ok(
            "course.create",
            {"title": "Game course", "recipe": "committed", "goal": "Replace a head gasket",
             "presentation_mode": "game"},
        )["result"]["course_id"]
        self.assertEqual(self.scalar("SELECT presentation_mode FROM courses WHERE id = ?", (game,)), "game")
        read_game = self.ok("world.read", {"course_id": game})["result"]
        self.assertEqual(read_game["presentation_mode"], "game")
        self.assertIsNone(read_game["world"], "creation intent invented a world")
        self.assertEqual(read_game["fallback"], "textbook")
        # No world job was queued: a Game course's concepts wait for its draft plan.
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM jobs WHERE kind = 'media' AND state IN ('queued','running')"),
            0,
        )


# ── desktop: the course world surface ─────────────────────────────────────────


class CourseWorldSurfaceTest(Base):
    def test_textbook_has_no_world_surface(self) -> None:
        html = self.render({
            "kind": "course-home",
            "rows": [row()],
            "world": {"status": "ready", "error": None,
                      "data": {"course_id": "crs_0000000000000001", "presentation_mode": "textbook",
                               "world": None, "fallback": "textbook", "revision": 0}},
        })
        self.assertIn('data-cb-desk="ready"', html)
        self.assertIn('data-cb-mode-badge="textbook"', html)
        self.assertNotIn("data-cb-world=", html)
        self.assertNotIn("data-cb-world-hero", html)
        self.assertNotIn("Open World Studio", html)

    def test_game_course_home_paints_hero_sections_and_mode(self) -> None:
        html = self.render({
            "kind": "course-home",
            "rows": [row()],
            "world": {"status": "ready", "error": None,
                      "data": {"course_id": "crs_0000000000000001", "presentation_mode": "game",
                               "world": world_value(), "fallback": None, "revision": 4}},
        })
        self.assertIn('data-cb-world="game"', html)
        self.assertIn("data-cb-world-hero", html)
        self.assertIn('data-cb-mode-badge="game"', html)
        self.assertIn('data-cb-world-section="obj_1"', html)
        self.assertIn('data-cb-world-section="obj_2"', html)
        self.assertIn("Before you lift the car", html)
        # The hero plate is art with an authored label; the title is real DOM text.
        self.assertIn('data-cb-world-plate="hero"', html)
        self.assertIn("Replace a head gasket", html)
        self.assertNotIn("stars", html.lower())

    def test_game_course_home_without_approval_names_the_gate(self) -> None:
        html = self.render({
            "kind": "course-home",
            "rows": [row()],
            "world": {"status": "ready", "error": None,
                      "data": {"course_id": "crs_0000000000000001", "presentation_mode": "game",
                               "world": world_value(state="concepts_ready", mode_ready=False),
                               "fallback": "textbook", "revision": 2}},
        })
        self.assertIn('data-cb-world="unapproved"', html)
        self.assertIn("World not approved yet", html)
        self.assertIn("Open World Studio", html)
        self.assertNotIn("data-cb-world-hero", html)


# ── desktop: the World Studio ─────────────────────────────────────────────────


class WorldStudioTest(Base):
    def studio(self, world_payload, **overrides) -> str:
        return self.render({"kind": "studio", "world": world_payload, "mode": overrides.pop("mode", "game"), **overrides})

    def test_world_studio_state_matrix(self) -> None:
        cases = {
            "not_requested": {"state": "not_requested", "mode_ready": False},
            "concepts_generating": {"state": "concepts_generating", "mode_ready": False},
            "concepts_ready": {"state": "concepts_ready", "mode_ready": False},
            "style_selected": {"state": "style_selected"},
            "kit_generating": {"state": "kit_generating"},
            "kit_ready": {"state": "kit_ready"},
            "approved": {"state": "approved"},
        }
        expected_primary = {
            "not_requested": "concepts",
            "concepts_generating": None,
            "concepts_ready": "direction",
            "style_selected": "kit",
            "kit_generating": None,
            "kit_ready": "approve",
            "approved": "change",
        }
        for state, kwargs in cases.items():
            with self.subTest(state=state):
                html = self.studio(world_value(**kwargs))
                self.assertIn(f'data-cb-world-studio="{state}"', html)
                self.assertIn("Choose the world for this course", html)
                self.assertEqual(html.count('data-cb-world-primary="'), 1, state)
                primary = expected_primary[state]
                if primary:
                    self.assertIn(f'data-cb-world-primary="{primary}"', html)
                else:
                    self.assertIn('data-cb-world-primary="wait"', html)
                if state == "concepts_ready":
                    self.assertEqual(html.count("data-cb-world-concept="), 3, "the three boards")
                    self.assertIn("Use this direction", html)
                    self.assertIn("Try another set", html)
                if state == "kit_ready":
                    self.assertIn("data-cb-world-kit", html)
                    self.assertIn('data-cb-mode-badge', html)
                if state == "approved":
                    self.assertIn("This world is approved.", html)
                # Every state keeps a way out.
                self.assertIn("Use Textbook mode", html)
                self.assertIn("Cancel", html)

    def test_world_studio_rejects_embedded_text(self) -> None:
        """No brief or failure text is rendered as UI copy, and a plate is never a text surface."""
        poisoned = world_value(state="kit_ready")
        poisoned["brief"]["tone"] = "TORQUE 90 NM — STEP 3"
        poisoned["brief"]["motifs"] = ["tighten to 90 NM", "sequence 1-3-4-2"]
        poisoned["error"] = {"reason": "partial_world", "message": "APPLY 90 NM IN ORDER"}
        html = self.studio(poisoned)
        for poison in ("TORQUE 90 NM", "tighten to 90 NM", "sequence 1-3-4-2", "APPLY 90 NM IN ORDER"):
            self.assertNotIn(poison, html, "generated/brief text reached the UI")
        self.assertNotIn("<canvas", html)
        self.assertNotIn("data:image", html)

        # Every plate that paints is an image with an authored caption, and the labels are the
        # brief's real section titles rather than a generic "Section card".
        self.assertIn('data-cb-world-plate="cover"', html)
        for caption in ("Library cover", "Before you lift the car", "Removing the head"):
            self.assertIn(caption, html)
        self.assertEqual(html.count("data-cb-world-plate-art"), 0,
                         "a static render has no served artifact, so no <img> should paint")

    def test_world_studio_provider_and_partial_states_are_named(self) -> None:
        unavailable = world_value(state="unavailable", mode_ready=False)
        unavailable["error"] = {"reason": "provider_unavailable"}
        html = self.studio(unavailable)
        self.assertIn('data-cb-world-provider="unavailable"', html)
        self.assertIn("image generation is not configured", html)
        self.assertIn('data-cb-world-primary="retry-concepts"', html)

        partial = world_value(state="failed", mode_ready=True)
        partial["error"] = {"reason": "partial_world", "missing_roles": ["section:obj_2"]}
        html = self.studio(partial)
        self.assertIn('data-cb-world-partial="section:obj_2"', html)
        self.assertIn("Some plates are missing", html)
        self.assertNotIn('data-cb-world-primary="approve"', html, "a partial world must not be approvable")

    def test_world_studio_reads_its_own_failure(self) -> None:
        html = self.render({"kind": "studio", "world": None, "mode": "game",
                            "worldStatus": "error", "worldError": {"code": "HOST_UNAVAILABLE", "message": "backend down"}})
        self.assertIn("The course world could not be read", html)
        self.assertIn("Try again", html)

    def test_world_studio_teacher_layout(self) -> None:
        """One heading, one primary, three authored boards, direction closed until asked for."""
        html = self.studio(world_value(state="concepts_ready", mode_ready=False))
        self.assertEqual(html.count("<h2"), 1, "the studio has more than one h2")
        self.assertEqual(html.count('data-cb-world-primary="'), 1)
        self.assertEqual(html.count('data-cb-world-concept="'), 3)
        self.assertIn("Workshop manual", html)
        self.assertIn("Direction", html)
        self.assertIn('data-cb-world-direction="closed"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertIn('aria-labelledby="cb-world-studio-title"', html)

    def test_mode_dialog_copy_and_consequences(self) -> None:
        no_world = self.render({"kind": "dialog", "world": None})
        # The card's literal prompt, with exactly Studio and Cancel.
        self.assertIn("Game mode is not available yet. Generate a game world?", no_world)
        self.assertIn("Studio", no_world)
        self.assertIn("Cancel", no_world)
        self.assertEqual(no_world.count("data-cb-mode-primary="), 1)
        self.assertNotIn("data-cb-mode-keep", no_world)

        approved = self.render({"kind": "dialog", "world": world_value(state="approved")})
        self.assertIn("This course already has a world.", approved)
        self.assertIn("Switch to Game mode", approved)

        in_progress = self.render({"kind": "dialog", "world": world_value(state="style_selected")})
        self.assertIn("A world is not approved yet.", in_progress)
        self.assertIn("Open World Studio", in_progress)

        provider = self.render({"kind": "dialog", "world": world_value(state="unavailable", mode_ready=False),
                                "providerUnavailable": True})
        self.assertIn("image provider is not configured", provider)
        self.assertIn("your lessons are unchanged", provider)


if __name__ == "__main__":
    unittest.main()
