"""CP-025b — World Studio and Parent Studio on the v3 primitives.

The card's contract, in executable form:

* the two segments CP-025b owns (`desktop/src/97-world.js`, `desktop/src/95-studio.js`) paint from
  the v3 contract only: no v2 `--cb-` token, no `CB_TYPE`/`CB_SANS`/`CB_SERIF` reader, no raw
  colour, no hand-written shadow, no decorative gradient, no viewport unit;
* the World Studio is one surface with one primary in every state, its own paper cards instead of
  the v2 accent bars, and no host `sdk.Button` / `sdk.EmptyState` / `sdk.ErrorState` / `sdk.Loader`
  chrome on Coursebook's route;
* Parent Studio keeps its entrances as authored v3 tabs (a shape *and* `aria-selected`), never the
  host `sdk.SegmentedControl`, and it stays free of game chrome — no XP, no medallion, no stamp
  stepper, no challenge card. Its adult-only copy is unchanged.

What this does NOT prove: that a browser paints the v3 material correctly, or that the composed
screens keep the composition anchors. Those are the reviewer's live cells and the v3 rubric.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules
from tests.cb_source_scope import GRADIENT, HEX, SHADOW, VW

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
WORLD_SEGMENT = ROOT / "desktop" / "src" / "97-world.js"
STUDIO_SEGMENT = ROOT / "desktop" / "src" / "95-studio.js"

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'
import { WorldStudio, StudioEntranceTabs, ModeSwitchDialog } from './plugin.js'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const quiet = () => {}
let html = ''
if (payload.kind === 'studio') {
  html = renderToStaticMarkup(
    React.createElement(WorldStudio, {
      courseId: 'crs_1', mode: payload.mode || 'game', world: payload.world,
      worldStatus: payload.worldStatus || 'ready', worldError: payload.worldError || null,
      onReload: quiet, onClose: quiet, onChanged: quiet, autoStart: false
    })
  )
} else if (payload.kind === 'tabs') {
  html = renderToStaticMarkup(
    React.createElement(StudioEntranceTabs, { value: payload.value || 'plans', onChange: quiet })
  )
} else if (payload.kind === 'dialog') {
  html = renderToStaticMarkup(
    React.createElement(ModeSwitchDialog, {
      mode: payload.mode || 'textbook', world: payload.world || null, pending: false,
      providerUnavailable: Boolean(payload.providerUnavailable),
      onGenerate: quiet, onOpenStudio: quiet, onSwitch: quiet, onKeep: quiet, onCancel: quiet
    })
  )
}
process.stdout.write(JSON.stringify({ html }))
"""


def _world_value(*, state: str = "concepts_ready", mode_ready: bool = False) -> dict:
    """A `world.read` payload in the shape GM-004 ships, built here so this file is self-contained."""
    concepts = [
        {
            "style_id": "wld_1--field_atlas",
            "label": "field_atlas",
            "prompt_hash": "sha256:" + "1" * 64,
            "style_hash": "sha256:" + "1" * 64,
            "artifact_id": "art_concept_1",
            "palette": ["#1A1713", "#5C5347", "#E8A93A"],
            "medium": "ink on paper",
            "role": "orientation",
            "textless": True,
        },
        {
            "style_id": "wld_1--observatory",
            "label": "observatory",
            "prompt_hash": "sha256:" + "2" * 64,
            "style_hash": "sha256:" + "2" * 64,
            "artifact_id": "art_concept_2",
            "palette": ["#1A1713", "#5C5347", "#E8A93A"],
            "medium": "ink on paper",
            "role": "orientation",
            "textless": True,
        },
        {
            "style_id": "wld_1--studio_bench",
            "label": "studio_bench",
            "prompt_hash": "sha256:" + "3" * 64,
            "style_hash": "sha256:" + "3" * 64,
            "artifact_id": "art_concept_3",
            "palette": ["#1A1713", "#5C5347", "#E8A93A"],
            "medium": "ink on paper",
            "role": "orientation",
            "textless": True,
        },
    ]
    assets = [
        {"role": "hero", "artifact_id": "art_hero"},
        {"role": "cover", "artifact_id": "art_cover"},
        {"role": "section", "section_id": "obj_1", "section_key": "obj_1", "artifact_id": "art_sec_1"},
        {"role": "section", "section_id": "obj_2", "section_key": "obj_2", "artifact_id": "art_sec_2"},
    ]
    return {
        "world_id": "wld_1",
        "state": state,
        "revision": 3,
        "brief": {
            "title": "Replace a head gasket",
            "subject_domain": "technical_procedure",
            "end_capability": "Replace a head gasket on a four-cylinder engine",
            "sections": [{"id": "obj_1", "title": "Before you lift the car"},
                         {"id": "obj_2", "title": "Removing the head"}],
        },
        "concepts": concepts if state in ("concepts_ready", "style_selected", "kit_ready", "approved") else [],
        "selected_concept_id": "wld_1--field_atlas" if mode_ready else None,
        "style_hash": "sha256:" + "1" * 64 if mode_ready else None,
        "kit_hash": "sha256:" + "9" * 64 if state in ("kit_ready", "approved") else None,
        "approved_hash": "sha256:" + "9" * 64 if state == "approved" else None,
        "error": None,
        "assets": assets,
    }


class RenderCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-cp025b-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        stage_desktop_node_modules(cls.root)
        write_sdk_stub(cls.root, SDK_STUB)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, payload: dict) -> str:
        case = self.root / "payload.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        completed = subprocess.run(
            ["node", "harness.mjs", str(case)], cwd=self.root, capture_output=True, text=True, timeout=240
        )
        self.assertEqual(completed.returncode, 0, completed.stderr[-4000:])
        # React warns on the console only; a key spread or an unknown prop is still a defect.
        self.assertNotIn("Warning:", completed.stderr, completed.stderr[-2000:])
        return json.loads(completed.stdout)["html"]


class WorldStudioSourceTest(unittest.TestCase):
    """The segment paints from the contract, or the screen is a second material system."""

    def setUp(self) -> None:
        self.text = WORLD_SEGMENT.read_text(encoding="utf-8")

    def test_only_v3_tokens_and_v3_type_readers(self) -> None:
        stray = [token for token in re.findall(r"var\(--cb-[a-z0-9-]+\)", self.text)]
        self.assertEqual(stray, [], f"v2 tokens on a v3 surface: {stray[:8]}")
        for reader in ("CB_TYPE.", "CB_SANS", "CB_SERIF", "CB_MONO"):
            self.assertNotIn(reader, self.text, f"{reader} is the v2 type system")

    def test_no_raw_colour_shadow_gradient_or_viewport_unit(self) -> None:
        self.assertEqual(HEX.findall(self.text), [], "raw colour outside the token contract")
        self.assertEqual(SHADOW.findall(self.text), [], "a shadow escaped the v3 elevation tokens")
        self.assertEqual(GRADIENT.findall(self.text), [], "a decorative gradient on a v3 surface")
        self.assertEqual(VW.findall(self.text), [], "a viewport unit measures the window, not the route")

    def test_no_decorative_kicker_or_thick_state_bar(self) -> None:
        # SPEC-V3 §3.4: no kicker above a heading. UX standards: no thick decorative border bars.
        self.assertNotIn("textTransform: 'uppercase'", self.text)
        self.assertNotRegex(self.text, r"borderLeft:\s*'[2-9]px")
        self.assertNotRegex(self.text, r"borderTop:\s*'[2-9]px")

    def test_the_one_action_system_is_the_v3_pill(self) -> None:
        self.assertNotIn("CbAction", self.text, "the retired field-atlas action name is back")
        self.assertNotIn("sdk.Button", self.text, "host-blue button chrome on Coursebook's route")
        for host in ("sdk.EmptyState", "sdk.ErrorState", "sdk.Loader"):
            self.assertNotIn(host, self.text, f"{host} is host chrome, not a v3 surface")
        self.assertIn("PillAction", self.text)

    def test_primitive_change_requests_are_not_written_here(self) -> None:
        # The card may not edit 80-components/75-tokens/10-primitives; it also may not redefine them.
        for name in ("function PillAction", "function PaperCard", "function FoxPose", "function Medallion"):
            self.assertNotIn(name, self.text, f"{name} belongs to 85-v3-primitives.js")


class WorldStudioRenderTest(RenderCase):
    STATES = {
        "not_requested": False,
        "concepts_generating": False,
        "concepts_ready": False,
        "style_selected": True,
        "kit_generating": True,
        "kit_ready": True,
        "approved": True,
    }

    def test_every_state_has_exactly_one_primary(self) -> None:
        for state, ready in self.STATES.items():
            with self.subTest(state=state):
                html = self.render({"kind": "studio", "world": _world_value(state=state, mode_ready=ready)})
                self.assertEqual(html.count('data-cb3-pill="primary"'), 1, html[:600])
                self.assertEqual(html.count('data-cb-world-primary="'), 1, html[:600])

    def test_state_markers_and_escape_hatches_survive(self) -> None:
        for state in ("not_requested", "concepts_ready", "kit_ready", "approved"):
            with self.subTest(state=state):
                html = self.render({"kind": "studio", "world": _world_value(state=state, mode_ready=True)})
                self.assertIn(f'data-cb-world-studio="{state}"', html)
                self.assertIn('role="dialog"', html)
                self.assertIn('aria-modal="true"', html)
                self.assertIn('aria-labelledby="cb-world-studio-title"', html)
                self.assertEqual(html.count("<h2"), 1)
                self.assertIn("Use Textbook mode", html)
                self.assertIn("Cancel", html)

    def test_the_sheet_is_named_in_the_states_that_skip_the_body_head(self) -> None:
        # aria-labelledby pointed at an id only the body head renders; the read-failure, unsupported
        # and loading states rendered no such element, so the dialog had no accessible name.
        for status in ("unsupported", "error", "loading"):
            with self.subTest(status=status):
                html = self.render({
                    "kind": "studio", "world": None, "worldStatus": status,
                    "worldError": {"code": "HOST_UNAVAILABLE", "message": "backend down"},
                })
                self.assertIn('aria-labelledby="cb-world-studio-title"', html)
                self.assertIn('id="cb-world-studio-title"', html)
                self.assertEqual(html.count("<h2"), 1, "one heading names the sheet")

    def test_concept_boards_are_paper_cards_with_one_named_direction(self) -> None:
        html = self.render({"kind": "studio", "world": _world_value(state="concepts_ready")})
        self.assertEqual(html.count('data-cb3-card="paper"'), 3)
        self.assertEqual(html.count('data-cb3-pill="primary"'), 1, "one board is the primary choice")
        # Two board doors, three footer doors (another set, Textbook, Cancel) and the sheet's Close.
        self.assertEqual(html.count('data-cb3-pill="quiet"'), 6)
        self.assertIn("Field atlas", html)
        self.assertIn("Observatory", html)
        self.assertIn("Use this direction", html)

    def test_the_world_brief_is_never_rendered_as_ui_copy(self) -> None:
        poisoned = _world_value(state="concepts_ready")
        poisoned["brief"]["tone"] = "TORQUE 90 NM — STEP 3"
        html = self.render({"kind": "studio", "world": poisoned})
        self.assertNotIn("TORQUE 90 NM", html)
        self.assertNotIn("data:image", html, "a static render has no served artifact")

    def test_mode_dialog_keeps_one_primary_and_plain_consequences(self) -> None:
        html = self.render({"kind": "dialog", "world": None})
        self.assertEqual(html.count('data-cb3-pill="primary"'), 1)
        self.assertIn("Game mode is not available yet. Generate a game world?", html)
        self.assertIn('data-cb-mode-primary="generate"', html)


class ParentStudioSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = STUDIO_SEGMENT.read_text(encoding="utf-8")

    def test_only_v3_tokens_and_v3_type_readers(self) -> None:
        stray = re.findall(r"var\(--cb-[a-z0-9-]+\)", self.text)
        self.assertEqual(stray, [], f"v2 tokens on a v3 surface: {stray[:8]}")
        for reader in ("CB_TYPE.", "CB_SANS", "CB_SERIF"):
            self.assertNotIn(reader, self.text, f"{reader} is the v2 type system")

    def test_entrance_tabs_are_authored_not_host_chrome(self) -> None:
        self.assertNotIn("jsx(sdk.SegmentedControl", self.text,
                         "the host segmented control is not Coursebook's tab system")
        self.assertIn("'data-cb3-tab': item.id", self.text)
        self.assertIn("'aria-selected': current ? 'true' : 'false'", self.text)
        self.assertIn("role: 'tab'", self.text)
        self.assertIn("borderBottom: current ? '3px solid var(--cb3-terracotta)'", self.text)

    def test_the_view_switcher_measures_the_route_not_the_window(self) -> None:
        self.assertNotIn("min-[47.5rem]", self.text, "a window breakpoint on a route-relative surface")
        self.assertIn("useCbViewportWidth()", self.text)
        self.assertIn("'data-cb3-view-tab': option.id", self.text)

    def test_parent_studio_carries_no_game_chrome(self) -> None:
        for surface in ("FoxPose", "Medallion", "StampNode", "ChallengeCard", "EvidenceTray"):
            self.assertNotIn(surface, self.text, f"{surface} is game/lesson chrome, not Parent Studio")
        for word in ("xp_total", "xp_into_level", "level_label", "Streak"):
            self.assertNotIn(word, self.text, f"{word} is a game metric; Parent Studio reports evidence")

    def test_adult_only_copy_survives(self) -> None:
        for line in (
            "Prepare a lesson for a child",
            "Plans for your child",
            "no child chat, no child persona",
            "never points, levels or rankings",
        ):
            self.assertIn(line, self.text, f"the adult-only rule lost its words: {line}")

    def test_no_decorative_border_bar_on_a_parent_view(self) -> None:
        self.assertNotRegex(self.text, r"border-l-[2-9]\b")
        self.assertNotRegex(self.text, r"borderLeft:\s*'[2-9]px")


class ParentStudioRenderTest(RenderCase):
    def test_entrance_tabs_mark_the_current_one_by_shape_and_word(self) -> None:
        html = self.render({"kind": "tabs", "value": "takehome"})
        self.assertEqual(html.count('role="tab"'), 3)
        self.assertEqual(html.count('aria-selected="true"'), 1)
        self.assertIn('data-cb3-tab="takehome" data-current="true"', html)
        self.assertIn("My lesson plans", html)
        self.assertIn("Take-home from a lesson", html)
        self.assertIn("Homework", html)


if __name__ == "__main__":
    unittest.main()
