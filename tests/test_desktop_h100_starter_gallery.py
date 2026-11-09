"""H-100: the default create form is a neutral goal gallery, not a bike-repair demo.

``desktop/plugin.js`` ships one uncompiled ESM file, so the gallery is rendered with
``react-dom/server`` and the same stub ``@hermes/plugin-sdk`` seam
``tests/test_desktop_lesson_views.py`` uses. The gallery component is pure (no hooks), so the
harness can also walk the returned element tree, fire each example's ``onClick`` and prove it only
fills the goal — nothing is submitted until the learner presses the form's own action.

What this does NOT prove: that a live Desktop window lays the gallery out well. The rig frame set is
separate evidence; this is the copy and wiring half.
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

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

#: The shared stub draws Button as text only. This file reads the label and the example grouping,
#: so the one stub authority is extended in place rather than forked.
STUB = SDK_STUB.replace(
    "export const Button = (props) =>\n"
    "  el('button', {\n"
    "    type: 'button',\n"
    "    disabled: Boolean(props.disabled),\n"
    "    'data-variant': props.variant || null,\n"
    "    onClick: props.onClick\n"
    "  }, textOf(props))",
    "export const Button = (props) =>\n"
    "  el('button', {\n"
    "    type: 'button',\n"
    "    disabled: Boolean(props.disabled),\n"
    "    'data-variant': props.variant || null,\n"
    "    'aria-label': props['aria-label'] || null,\n"
    "    onClick: props.onClick\n"
    "  }, textOf(props))",
)

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { GoalGallery, GOAL_EXAMPLES, GOAL_PLACEHOLDER, TITLE_PLACEHOLDER } from './plugin.js'

const html = renderToStaticMarkup(
  React.createElement(GoalGallery, { onChoose: () => {} })
)

// Walk the pure element tree: every example is a Button whose onClick takes the example text.
const chosen = []
const tree = GoalGallery({ onChoose: (text) => chosen.push(text) })
const visit = (node) => {
  if (node === null || node === undefined || typeof node !== 'object') return
  if (Array.isArray(node)) { node.forEach(visit); return }
  if (node.props && typeof node.props.onClick === 'function' && node.props['aria-label']) {
    node.props.onClick()
  }
  if (node.props) visit(node.props.children)
}
visit(tree)

process.stdout.write(JSON.stringify({
  html,
  examples: GOAL_EXAMPLES,
  goalPlaceholder: GOAL_PLACEHOLDER,
  titlePlaceholder: TITLE_PLACEHOLDER,
  chosen
}))
"""


def _run() -> dict:
    modules = _desktop_node_modules()
    if modules is None:
        raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
    with tempfile.TemporaryDirectory(prefix="coursebook-h100-") as tmp:
        root = Path(tmp)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        # Private node_modules: the SDK stub must never be written through a
        # symlink into the host's shared install (H-208 cross-suite flake).
        stage_desktop_node_modules(root)
        write_sdk_stub(root, STUB)
        completed = subprocess.run(
            ["node", "harness.mjs"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if completed.returncode != 0:
            raise AssertionError(f"node harness failed:\n{completed.stdout}\n{completed.stderr}")
        return json.loads(completed.stdout)


SOURCE = PLUGIN_JS.read_text(encoding="utf-8")
BIKE = re.compile(r"\bbike|bicycle|inner tube|tube replacement", re.IGNORECASE)


class StarterCopySourceTest(unittest.TestCase):
    """The literal copy shipped in the plugin, readable without a node toolchain."""

    def test_no_bike_specific_copy_anywhere_in_the_plugin(self) -> None:
        for match in BIKE.finditer(SOURCE):
            line = SOURCE.count("\n", 0, match.start()) + 1
            self.fail(f"bike-specific copy at desktop/plugin.js:{line}: {match.group(0)!r}")

    def test_the_subject_hint_is_not_a_single_domain(self) -> None:
        self.assertNotIn("placeholder: 'e.g. bike repair", SOURCE)
        self.assertIn("e.g. Spanish, statistics, electrical safety", SOURCE)

    def test_the_gallery_sits_between_the_goal_and_the_course_name(self) -> None:
        goal_at = SOURCE.index("id: 'cb-goal'")
        gallery_at = SOURCE.index("jsx(GoalGallery, { onChoose: changeGoal })")
        title_at = SOURCE.index("id: 'cb-title'")
        self.assertLess(goal_at, gallery_at)
        self.assertLess(gallery_at, title_at)

    def test_choosing_an_example_only_fills_the_goal(self) -> None:
        # The gallery receives one callback, and the flow gives it changeGoal (which fills the goal
        # and derives the suggested name). No submit is reachable from an example: the form's own
        # action is still the only writer of a course.
        self.assertIn("jsx(GoalGallery, { onChoose: changeGoal })", SOURCE)
        self.assertNotIn("onChoose: submit", SOURCE)
        self.assertNotIn("onChoose: startLearnerPlan", SOURCE)

    def test_step_two_submit_lives_on_the_last_step_only(self) -> None:
        start = SOURCE.index("step === 2\n")
        end = SOURCE.index("step === 3\n", start)
        step_two = SOURCE[start:end]
        self.assertIn("data-cb-goal-examples", SOURCE)
        self.assertNotIn("onClick: submit", step_two)
        self.assertNotIn("onClick: () => submit", step_two)


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class GoalGalleryRenderTest(unittest.TestCase):
    """The shipped component, rendered and clicked through the real module."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.out = _run()

    def test_gallery_labels_itself_as_examples(self) -> None:
        html = self.out["html"]
        self.assertIn("data-cb-goal-examples", html)
        self.assertIn("Examples — press one to start from it, or write your own:", html)
        self.assertIn('role="group"', html)

    def test_at_least_three_distinct_domains_are_visible(self) -> None:
        domains = [example["domain"] for example in self.out["examples"]]
        self.assertGreaterEqual(len(set(domains)), 3, domains)
        self.assertEqual(len(domains), len(set(domains)), "each domain appears once")
        html = self.out["html"]
        for domain in domains:
            self.assertIn(f"{domain}: ", html, domain)

    def test_examples_cover_a_language_a_skill_and_a_concept(self) -> None:
        domains = {example["domain"] for example in self.out["examples"]}
        self.assertIn("Language", domains)
        self.assertIn("Skill", domains)
        self.assertIn("Concept", domains)
        text = " ".join(example["text"] for example in self.out["examples"]).lower()
        for topic in ("spanish", "lamp", "statistics"):
            self.assertIn(topic, text)

    def test_placeholders_are_marked_as_examples_and_prefill_nothing(self) -> None:
        self.assertTrue(self.out["goalPlaceholder"].startswith("e.g. "), self.out["goalPlaceholder"])
        self.assertTrue(self.out["titlePlaceholder"].startswith("e.g. "), self.out["titlePlaceholder"])
        for value in (self.out["goalPlaceholder"], self.out["titlePlaceholder"]):
            self.assertIsNone(BIKE.search(value), value)
        # A render of the gallery alone has no <input>/<textarea> carrying a value: the examples are
        # buttons, and the goal field itself is rendered empty by the flow (value: goal, state '').
        html = self.out["html"]
        self.assertNotIn("<textarea", html)
        self.assertNotIn("value=", html)

    def test_pressing_every_example_fills_only_the_goal_text(self) -> None:
        texts = [example["text"] for example in self.out["examples"]]
        self.assertEqual(self.out["chosen"], texts)

    def test_no_example_is_bike_specific(self) -> None:
        for example in self.out["examples"]:
            self.assertIsNone(BIKE.search(example["text"]), example["text"])
            self.assertIsNone(BIKE.search(example["domain"]), example["domain"])
            self.assertLessEqual(len(example["text"].split()), 12, example["text"])


if __name__ == "__main__":
    unittest.main()
