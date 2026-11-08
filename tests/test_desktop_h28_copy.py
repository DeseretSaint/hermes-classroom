"""H-28: the first-run, create, import and Parent Studio surfaces in a learner's words.

The plugin is one uncompiled ESM file, so these tests render the shipped components with
``react-dom/server`` and a stub ``@hermes/plugin-sdk`` — the same seam
``tests/test_desktop_lesson_views.py`` uses — and assert what a person reads, not what the source
intends. The payload side of the create flow (exact call sequence, idempotency keys, closed brief)
stays in ``tests/test_desktop_create_flow.py``; this file must not change it.

What this does NOT prove: that a live Desktop window shows these strings. The M4 visual audit and
the operator's frame set are separate evidence; this is the structural half.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

#: The SDK stub draws ListRow as nothing (other suites do not need it). This file does, so the one
#: stub authority is extended in place rather than forked: the row's title and description are what
#: a learner reads.
STUB = SDK_STUB.replace(
    "export const ListRow = () => null",
    "export const ListRow = (props) =>\n"
    "  el('div', { className: 'list-row' }, [\n"
    "    el('div', { key: 't', className: 'list-title' }, props.title),\n"
    "    el('div', { key: 'd', className: 'list-desc' }, props.description),\n"
    "    props.action\n"
    "  ])",
)

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  COURSE_SCOPES,
  CREATE_RESULT_COPY,
  CreateCourseFlow,
  FIRST_RUN_COPY,
  FirstRun,
  GOAL_EXAMPLES,
  GOAL_PLACEHOLDER,
  LIBRARY_COPY,
  RECIPE_COPY,
  TITLE_PLACEHOLDER,
  EVIDENCE_TARGET_OPTIONS,
  courseToolsVisible,
  dialLabel,
  enrollmentStatusLabel
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const text = (node) => {
  if (node === null || node === undefined || node === false) return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(text).join(' ')
  if (node.props && node.props.children !== undefined) return text(node.props.children)
  return ''
}

const copyBlocks = {
  FIRST_RUN_COPY,
  CREATE_RESULT_COPY,
  library: LIBRARY_COPY,
  scopes: COURSE_SCOPES,
  recipes: RECIPE_COPY,
  goalExamples: GOAL_EXAMPLES.map((example) => `${example.domain}: ${example.text}`),
  goalPlaceholder: GOAL_PLACEHOLDER,
  titlePlaceholder: TITLE_PLACEHOLDER,
  evidenceTargets: EVIDENCE_TARGET_OPTIONS.map((option) => option.label),
  dials: {
    pace: dialLabel('pace', 'light'),
    depth: dialLabel('depth', 'survey'),
    assessment: dialLabel('assessment', 'self_check'),
    autonomy: dialLabel('autonomy', 'guided')
  },
  status: {
    active: enrollmentStatusLabel('active'),
    archived: enrollmentStatusLabel('archived'),
    completed: enrollmentStatusLabel('completed')
  }
}

let html = null
if (payload.kind === 'first-run') {
  html = renderToStaticMarkup(
    React.createElement(FirstRun, {
      implemented: new Set(['course.create', 'pack.import']),
      onCreate: () => {},
      onBrowseLibrary: () => {},
      onRetry: () => {}
    })
  )
} else if (payload.kind === 'first-run-no-import') {
  html = renderToStaticMarkup(
    React.createElement(FirstRun, {
      implemented: new Set(['course.create']),
      onCreate: () => {},
      onBrowseLibrary: () => {},
      onRetry: () => {}
    })
  )
} else if (payload.kind === 'first-run-syllabus') {
  html = renderToStaticMarkup(
    React.createElement(FirstRun, {
      implemented: new Set(['course.create', 'pack.import', 'syllabus.intake.create']),
      onCreate: () => {},
      onSyllabus: () => {},
      onBrowseLibrary: () => {},
      onRetry: () => {}
    })
  )
} else if (payload.kind === 'first-run-nothing') {
  html = renderToStaticMarkup(
    React.createElement(FirstRun, {
      implemented: new Set([]),
      onCreate: () => {},
      onBrowseLibrary: () => {},
      onRetry: () => {}
    })
  )
} else if (payload.kind === 'first-run-unavailable') {
  html = renderToStaticMarkup(
    React.createElement(FirstRun, {
      implemented: new Set(['pack.import', 'syllabus.intake.create']),
      onCreate: () => {},
      onSyllabus: () => {},
      onBrowseLibrary: () => {},
      onRetry: () => {}
    })
  )
} else if (payload.kind === 'first-run-no-handler') {
  html = renderToStaticMarkup(
    React.createElement(FirstRun, {
      implemented: new Set(['course.create', 'pack.import']),
      onCreate: () => {}
    })
  )
} else if (payload.kind === 'first-run-offline') {
  // The plate reads `navigator.onLine`, the same signal the route header uses.
  Object.defineProperty(globalThis, 'navigator', { value: { onLine: false }, configurable: true })
  html = renderToStaticMarkup(
    React.createElement(FirstRun, {
      implemented: new Set(['course.create', 'pack.import', 'syllabus.intake.create']),
      onCreate: () => {},
      onSyllabus: () => {},
      onBrowseLibrary: () => {},
      onRetry: () => {}
    })
  )
} else if (payload.kind === 'create-step-one') {
  html = renderToStaticMarkup(React.createElement(CreateCourseFlow, { onCancel: () => {}, onCreated: () => {} }))
}

process.stdout.write(
  JSON.stringify({
    html,
    copy: copyBlocks,
    tools: {
      empty: courseToolsVisible({ total: 0, items: [] }),
      one: courseToolsVisible({ total: 1, items: [{}] }),
      unknown: courseToolsVisible(null)
    }
  })
)
"""


def _run(payload: dict) -> dict:
    modules = _desktop_node_modules()
    if modules is None:
        raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
    with tempfile.TemporaryDirectory(prefix="coursebook-h28-") as tmp:
        root = Path(tmp)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        (root / "node_modules").symlink_to(modules, target_is_directory=True)
        sdk_dir = root / "node_modules" / "@hermes" / "plugin-sdk"
        sdk_dir.mkdir(parents=True, exist_ok=True)
        index_js = sdk_dir / "index.js"
        index_js_original = index_js.read_text(encoding="utf-8") if index_js.exists() else None
        index_js.write_text(STUB, encoding="utf-8")
        payload_path = root / "payload.json"
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            completed = subprocess.run(
                ["node", "harness.mjs", str(payload_path)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=180,
            )
        finally:
            if index_js_original is None:
                index_js.unlink(missing_ok=True)
            else:
                index_js.write_text(index_js_original, encoding="utf-8")
        if completed.returncode != 0:
            raise AssertionError(f"node harness failed:\n{completed.stdout}\n{completed.stderr}")
        return json.loads(completed.stdout)


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class FirstRunCopyTest(unittest.TestCase):
    """H-153: one start plate — one headline, one short what-happens line, one primary, and at most
    one secondary door. The three-step explainer, the progress paragraph and the capability
    inventory are gone; every entry is gated on the command that serves it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.out = _run({"kind": "first-run"})

    def test_one_primary_action_and_at_most_one_secondary(self) -> None:
        html = self.out["html"]
        self.assertIn("Start with a goal", html)
        self.assertIn("Use a course I already have", html)
        # The primary is a default-variant button: the only filled control on the screen.
        self.assertEqual(html.count('data-variant="default"'), 1, html)
        self.assertEqual(html.count('data-variant="secondary"'), 1, html)
        self.assertEqual(html.count("<button"), 2, html)

    def test_the_plate_is_one_headline_and_one_what_happens_line(self) -> None:
        html = self.out["html"]
        self.assertIn("What do you want to be able to do?", html)
        self.assertIn(
            "Name one goal, review the plan, then learn. Nothing is created until you approve the plan.",
            html,
        )
        self.assertEqual(html.count("data-cb-first-run-line"), 1, html)
        # No numbered path, no second "next" sentence, no progress paragraph.
        self.assertNotIn("data-cb-first-run-path", html)
        self.assertNotIn("Next you choose how big the course is.", html)
        self.assertNotIn("Nothing is marked complete without a check you can see.", html)

    def test_the_support_and_inventory_note_is_gone(self) -> None:
        for kind in ("first-run", "first-run-no-import", "first-run-syllabus", "first-run-nothing"):
            html = _run({"kind": kind})["html"]
            for banned in ("Not in this", "backend build", "sample data", "pack preview", "plan generation jobs"):
                self.assertNotIn(banned, html, kind)

    def test_the_plate_carries_no_seal_or_decorative_mark(self) -> None:
        # H-176 (FINAL-POLISH-SPEC §3) amends H-28: first-run carries one deterministic,
        # `aria-hidden` contour ghost so the empty trailhead still reads as a place. It is not a
        # seal, a monogram cover or an avatar image, and it is never the only identity on screen.
        html = self.out["html"]
        self.assertNotIn("data-cb-seal", html)
        self.assertNotIn("<img", html)
        self.assertEqual(html.count("data-cb-first-run-contour"), 1, html)
        self.assertEqual(html.count("<svg"), 1, html)
        self.assertIn('data-cb-first-run-contour="" aria-hidden="true"', html)
        self.assertIn('data-cb-course-contour', html)

    def test_no_tour_no_sample_course_no_praise(self) -> None:
        html = self.out["html"]
        for banned in ('role="dialog"', "Step 1 of 3", "Welcome", "ready to go", "You're all set"):
            self.assertNotIn(banned, html)

    def test_the_secondary_opens_the_library_only_when_a_door_is_mounted(self) -> None:
        # Import (pack.import) and college syllabus (syllabus.intake.create) are the Library's two
        # doors. With neither mounted the secondary is absent, not a dead control.
        out = _run({"kind": "first-run-nothing"})
        html = out["html"]
        self.assertNotIn("Use a course I already have", html)
        self.assertNotIn("<button", html)
        self.assertIn("cannot create or add a course yet", html)

    def test_a_build_without_course_create_says_so_and_keeps_the_library(self) -> None:
        out = _run({"kind": "first-run-unavailable"})
        html = out["html"]
        self.assertIn("cannot create a course yet", html)
        self.assertNotIn("data-cb-first-run-primary", html)
        self.assertIn("Use a course I already have", html)
        self.assertNotIn("Not in this", html)

    def test_offline_is_a_state_with_one_action(self) -> None:
        out = _run({"kind": "first-run-offline"})
        html = out["html"]
        self.assertIn('data-cb-first-run-state="offline"', html)
        self.assertIn("paused while this profile is offline", html)
        self.assertIn("Try again", html)
        self.assertNotIn("Start with a goal", html)
        self.assertEqual(html.count('data-variant="default"'), 1, html)

    def test_the_secondary_is_still_gated_by_its_handler(self) -> None:
        # A caller that cannot route to the Library gets no door (the harness above always can).
        out = _run({"kind": "first-run-no-handler"})
        self.assertNotIn("Use a course I already have", out["html"])
        self.assertIn("Start with a goal", out["html"])

    def test_governance_vocabulary_is_gone(self) -> None:
        html = self.out["html"]
        for banned in ("governed learning", "real evidence", "nothing advances on its own"):
            self.assertNotIn(banned.lower(), html.lower())


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class LearnerVocabularyTest(unittest.TestCase):
    """UX-02/UX-09: no banned word and no raw enum in the default learner-facing copy."""

    BANNED = ("recipe", "cold", "discrimination", "provenance")
    BANNED_WORDS = (re.compile(r"\bl0\b", re.IGNORECASE),)
    RAW_ENUMS = ("one_off", "casual", "committed", "companion", "self_check", "independent_evidence")

    @classmethod
    def setUpClass(cls) -> None:
        cls.out = _run({"kind": "copy"})

    def _strings(self, node):
        if isinstance(node, str):
            yield node
        elif isinstance(node, dict):
            for value in node.values():
                yield from self._strings(value)
        elif isinstance(node, list):
            for value in node:
                yield from self._strings(value)

    def test_no_banned_word_in_the_copy_blocks(self) -> None:
        for value in self._strings(self.out["copy"]):
            lowered = value.lower()
            for banned in self.BANNED:
                self.assertNotIn(banned, lowered, f"banned word {banned!r} in {value!r}")
            for pattern in self.BANNED_WORDS:
                self.assertIsNone(pattern.search(value), f"banned word in {value!r}")

    def test_no_raw_enum_reaches_a_label(self) -> None:
        for value in self._strings(self.out["copy"]):
            for raw in self.RAW_ENUMS:
                self.assertNotIn(raw, value, f"raw enum {raw!r} in {value!r}")

    def test_no_invented_progress_or_time_claim(self) -> None:
        for value in self._strings(self.out["copy"]):
            self.assertNotRegex(value, r"\d+\s*%")
            self.assertNotRegex(value.lower(), r"\b\d+\s*(minute|min|hour)s?\b")

    def test_scope_answers_explain_a_consequence(self) -> None:
        scopes = self.out["copy"]["scopes"]
        self.assertEqual([scope["id"] for scope in scopes], ["single", "short", "full"])
        labels = [scope["label"] for scope in scopes]
        self.assertEqual(
            labels,
            ["A single lesson", "A short course (a few sessions)", "A full course (weeks or months)"],
        )
        for scope in scopes:
            self.assertTrue(scope["consequence"].strip(), scope["id"])
            self.assertTrue(scope["consequence"].endswith("."), scope["id"])

    def test_one_off_is_a_task_not_a_quiz(self) -> None:
        one_off = self.out["copy"]["recipes"]["one_off"]
        self.assertIn("task", one_off["title"].lower())
        self.assertIn("not a quiz", one_off["description"].lower())

    def test_default_examples_are_topic_diverse(self) -> None:
        # H-100 replaced the bike-repair starter with a neutral gallery: a language, a practical
        # skill, an academic concept and an everyday skill. No single domain owns the form.
        examples = " ".join(self.out["copy"]["goalExamples"]).lower()
        for topic in ("spanish", "lamp", "statistics", "nutrition"):
            self.assertIn(topic, examples)
        self.assertNotIn("bike", examples)
        self.assertNotIn("register", examples)
        self.assertNotIn("friend", examples)
        self.assertNotIn("manager", examples)
        self.assertNotIn("bike", self.out["copy"]["goalPlaceholder"].lower())
        self.assertNotIn("bike", self.out["copy"]["titlePlaceholder"].lower())
        self.assertNotIn("japanese", self.out["copy"]["titlePlaceholder"].lower())

    def test_parent_language_uses_plain_words(self) -> None:
        labels = self.out["copy"]["evidenceTargets"]
        self.assertIn("Tell the difference", labels)
        self.assertNotIn("Discrimination", labels)

    def test_dials_and_status_are_humanised(self) -> None:
        dials = self.out["copy"]["dials"]
        self.assertEqual(dials["pace"], "Light")
        self.assertEqual(dials["assessment"], "Self-check")
        self.assertEqual(self.out["copy"]["status"]["active"], "Active")

    def test_library_copy_moves_the_absence_into_a_disclosure(self) -> None:
        library = self.out["copy"]["library"]
        self.assertNotIn("provenance", library["lead"].lower())
        # H-150: the lead must not claim every pack was made by someone else — bundled packs are
        # on the same shelf. It names both provenances the filters actually return.
        self.assertIn("ship with Coursebook", library["lead"])
        self.assertIn("from someone else", library["lead"])
        self.assertIn("no marketplace ranking and no verified badge", library["whatWeDoNotCheck"].lower())
        self.assertIn("What we check", library["whatWeCheck"])
        self.assertIn("hashes", library["whatWeCheck"].lower())

    def test_create_result_leads_with_the_promise(self) -> None:
        lead = self.out["copy"]["CREATE_RESULT_COPY"]["lead"]
        self.assertIn("Your plan is being researched", lead)
        self.assertIn("leave this page", lead)


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class CreateFlowCompositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.out = _run({"kind": "create-step-one"})

    def test_first_step_asks_for_the_goal(self) -> None:
        html = self.out["html"]
        self.assertIn("What do you want to be able to do?", html)
        self.assertIn('for="cb-goal"', html)
        self.assertIn('for="cb-title"', html)
        self.assertIn("Name this course (required)", html)

    def test_the_flow_states_the_step_and_what_happens_next(self) -> None:
        html = self.out["html"]
        self.assertIn("Step 1 of 3", html)
        self.assertIn("data-cb-create-spine", html)
        self.assertIn('aria-current="step"', html)
        self.assertIn("Next: choose how much course you want.", html)
        self.assertNotIn("STEP 1 OF 3", html)

    def test_step_one_has_no_scope_options_and_no_recipe_choice(self) -> None:
        html = self.out["html"]
        self.assertNotIn("data-cb-scope-option", html)
        self.assertNotIn("A single lesson", html)
        self.assertNotIn("Recipe", html)
        self.assertNotIn("STEP 2 OF 3", html)

    def test_continue_is_present_and_creation_is_not(self) -> None:
        html = self.out["html"]
        self.assertIn("Continue", html)
        self.assertNotIn("Create course", html)


class CreateFlowSourceTest(unittest.TestCase):
    """The parts a static render cannot reach: step order, disclosures, and the header rule."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_the_goal_is_asked_before_the_size(self) -> None:
        """H-170: the first-run promise is "name one goal", so the goal step comes first."""
        source = self.source
        start = source.index("const CREATE_STEP_SPINE")
        block = source[start : source.index("])", start)]
        self.assertLess(block.index("name: 'Goal'"), block.index("name: 'Size'"), block)
        self.assertLess(block.index("name: 'Size'"), block.index("name: 'Review'"), block)
        # The goal field is authored before the scope options, and the flow opens on it.
        self.assertLess(source.index("id: 'cb-goal'"), source.index("'data-cb-scope-option'"))
        self.assertIn("useState(createStartStep(seed))", source)

    def test_tuning_fields_are_behind_a_disclosure(self) -> None:
        source = self.source
        self.assertIn("data-cb-tune", source)
        self.assertIn("Help me tune it (optional)", source)
        tune_at = source.index("data-cb-tune")
        level_at = source.index("id: 'cb-level'")
        self.assertLess(tune_at, level_at)

    def test_create_receipt_is_a_disclosure(self) -> None:
        source = self.source
        self.assertIn("data-cb-create-receipt", source)
        self.assertIn("Details and job state", source)

    def test_library_trust_moves_into_a_disclosure(self) -> None:
        source = self.source
        self.assertIn("data-cb-pack-trust", source)
        self.assertIn("What we check / what we do not check", source)

    def test_header_new_course_yields_to_the_welcome(self) -> None:
        source = self.source
        self.assertIn("&& canCreate && !coursesEmpty", source)

    def test_empty_course_list_hides_search_and_filters(self) -> None:
        source = self.source
        self.assertIn("const showTools = courseToolsVisible(data)", source)
        self.assertNotIn("Packs installed on this profile, by where they came from", source)

    def test_no_duplicate_header_brief_button(self) -> None:
        self.assertNotIn("New lesson brief", self.source)
        self.assertIn("New lesson plan", self.source)


if __name__ == "__main__":
    unittest.main()
