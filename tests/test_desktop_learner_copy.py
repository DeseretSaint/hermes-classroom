"""E2E U1/U6/U7 — the wide card keeps the keyboard, one vocabulary, one question.

Three findings, one contract:

  * **U1** — at a route width of 1200 px or more every Home course card was an `<article>` with
    only `onClick`, while the same card below that width was a real `sdk.RowButton`. Keyboard
    access disappeared exactly when the window was wider. The wide card now carries a real
    `<button>` overlay, so Tab reaches it and Enter/Space open the course natively.
  * **U6** — one section printed as "Section 2 of 6", "Checkpoint 3" and "STOP 7", and Studio
    called it "Objective"; `independent_evidence` was "Evidence", "Independent evidence" and
    "Complete" on three surfaces. Every learner-facing noun, state word and check word now comes
    from `CB_COPY` (desktop/src/00-header.js), which the module exports.
  * **U7** — create step 1 asked "What do you want to be able to do?" and repeated the sentence as
    the field label 60 px below; step 3 asked the same question again. Step 1's visible label is
    gone (its accessible name is a `sr-only` label), and step 3 asks what would prove the goal.

The map test is deliberately hostile: it scans the source for a *second* place a state word is
written, not merely for the shipped map's wording, so a new literal on a new surface fails here
rather than drifting silently.
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "desktop" / "src"
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

IMPORT_HARNESS = r"""
import fs from 'node:fs'

const { CB_COPY } = await import('./plugin.js')
const payload = {
  frozen: Object.isFrozen(CB_COPY),
  state: Object.values(CB_COPY.state),
  check: Object.values(CB_COPY.checkState),
  sectionOne: CB_COPY.section.one,
  sectionMany: CB_COPY.section.many,
  label: [CB_COPY.sectionLabel(2, 6), CB_COPY.sectionLabel(3), CB_COPY.sectionLabel(null, 6)],
  stateWord: [CB_COPY.stateWord('independent_evidence'), CB_COPY.stateWord('unknown_state')],
  checkWord: [CB_COPY.checkWord('closed'), CB_COPY.checkWord('unknown')]
}
fs.writeFileSync(process.argv[3], JSON.stringify(payload))
"""

HOME_HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
globalThis.__CB_TEST_WIDTH__ = String(payload.width)
const { CoursebookHome } = await import('./plugin.js')

const rows = (payload.rows || []).map((row, index) => ({
  enrollment_id: `enr_${index}`,
  course_id: `crs_${index}`,
  title: row.title,
  subtitle: null,
  recipe: 'committed',
  level_label: null,
  locale: null,
  learner_label: null,
  enrollment_status: 'active',
  course_status: 'active',
  provenance: { source: 'authored', pack_id: null, pack_version: null },
  next_step: { kind: 'resume_lesson', label: 'Resume lesson' },
  evidence_summary: { independent: 0, review_due: 0, total_objectives: 4, current_objective_id: 'obj' },
  warning: null,
  updated_at: '2026-11-01T18:00:00.000000+00:00',
  revision: 0,
  sections_total: row.sections_total,
  sections_done: row.sections_done
}))

const html = renderToStaticMarkup(
  React.createElement(CoursebookHome, {
    library: {
      status: 'ready',
      data: { items: rows, next_cursor: null, total: rows.length, empty_reason: null, applied_filter: 'all' },
      error: null,
      stale: false
    },
    modes: {},
    modesSupported: true,
    online: true,
    canCreate: true,
    onStartCreate: () => {},
    onBrowseLibrary: () => {},
    onOpenCourse: () => {},
    onShowAll: () => {},
    onRetry: () => {}
  })
)
fs.writeFileSync(process.argv[3], JSON.stringify({ html }))
"""

ROWS = [
    {"title": "Auto Repair Fundamentals", "sections_total": 8, "sections_done": 5},
    {"title": "Japanese Cafe Basics", "sections_total": 4, "sections_done": 2},
    {"title": "Astronomy", "sections_total": 6, "sections_done": 1},
    {"title": "Sourdough", "sections_total": 3, "sections_done": 0},
]

#: The words a learner must never read on a coursebook surface (U6).
BANNED_LEARNER_WORDS = ("Checkpoint", "STOP", "Objective")

#: Every state word the product used to spell in more than one place.
STATE_WORDS = (
    "Not started",
    "Started",
    "Independent evidence",
    "Delayed evidence",
    "Review due",
    "Needs review",
    "Moved on without a grade",
    "No check yet",
    "Check open",
    "Check closed",
    "Check replaced",
)

COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)

#: A counted section label — ``Section 2``, ``Section 2 of 6``, ``Sections 6`` — is authored by
#: ``CB_COPY.sectionLabel`` and nowhere else. The pattern deliberately catches template
#: interpolations, numeric literals and quote-then-concat forms, so a surface cannot rebuild the
#: count by hand even when it never types the finished sentence.
COUNTED_SECTION_RE = re.compile(r"\bSections?\s+(?:\$\{|[0-9]|['\"]\s*\+)")


def strip_comments(source: str) -> str:
    """Comments are prose about the words; only rendered strings are the contract."""
    source = COMMENT_RE.sub("", source)
    return re.sub(r"(?m)^\s*//.*$", "", source)


def segments() -> dict[str, str]:
    return {path.name: strip_comments(path.read_text(encoding="utf-8")) for path in sorted(SRC.glob("*.js"))}


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class DesktopHarness(unittest.TestCase):
    HARNESS = IMPORT_HARNESS

    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-e2e-u167-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(cls.HARNESS, encoding="utf-8")
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

    def run_node(self, payload) -> dict:
        case = self.root / "case.json"
        out = self.root / "out.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case), str(out)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=240,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(out.read_text(encoding="utf-8"))


class LearnerCopyMapTest(DesktopHarness):
    """U6 — one exported map is the only source of learner nouns and state words."""

    def test_the_map_is_exported_frozen_and_complete(self) -> None:
        out = self.run_node({})
        self.assertTrue(out["frozen"], "CB_COPY must be frozen")
        self.assertIn("Independent evidence", out["state"])
        self.assertNotIn("Evidence", out["state"], "the independent state must not be called just 'Evidence'")
        self.assertEqual(out["sectionOne"], "Section")
        self.assertEqual(out["label"][0], "Section 2 of 6")
        self.assertEqual(out["label"][1], "Section 3")
        self.assertEqual(out["label"][2], "Section")
        self.assertEqual(out["stateWord"][0], "Independent evidence")
        self.assertEqual(out["stateWord"][1], "State not recorded")
        self.assertEqual(out["checkWord"][0], "Check closed")
        self.assertEqual(out["checkWord"][1], "Check state not recorded")

    def test_every_state_word_is_written_once_and_only_in_the_map(self) -> None:
        files = segments()
        header = files["00-header.js"]
        for word in STATE_WORDS:
            sites = [name for name, body in files.items() if f"'{word}'" in body]
            self.assertEqual(sites, ["00-header.js"], f"{word!r} is spelled outside the one map: {sites}")
            self.assertEqual(header.count(f"'{word}'"), 1, f"{word!r} is written twice in the map")

    def test_no_file_declares_a_second_state_map(self) -> None:
        files = segments()
        canonical = {
            "independent_evidence": "Independent evidence",
            "review_due": "Review due",
            "needs_review": "Needs review",
            "delayed_evidence": "Delayed evidence",
            "not_started": "Not started",
            "introduced": "Started",
        }
        for name, body in files.items():
            if name == "00-header.js":
                continue
            for key, word in canonical.items():
                for match in re.finditer(re.escape(key) + r"\s*:\s*'([^']*)'", body):
                    if match.group(1) == word:
                        self.fail(f"{name} maps {key!r} to its own copy of {word!r} at offset {match.start()}")
        self.assertIn("const CB_COPY", files["00-header.js"])

    def test_counted_section_labels_are_authored_only_by_the_map(self) -> None:
        """The noun the finding is about may not be re-counted by hand on any surface."""
        files = segments()
        for name, body in files.items():
            if name == "00-header.js":
                continue
            for match in COUNTED_SECTION_RE.finditer(body):
                start = max(0, match.start() - 40)
                self.fail(
                    f"{name} spells a counted section label instead of CB_COPY.sectionLabel: "
                    f"{body[start:match.end() + 60]!r}"
                )

    def test_every_counted_section_surface_reads_the_map(self) -> None:
        files = segments()
        for name in ("30-home.js", "80-components.js", "90-course.js", "99-tutor.js"):
            self.assertIn(
                "CB_COPY.sectionLabel(", files[name], f"{name} does not route its section label through the map"
            )
        self.assertEqual(
            files["00-header.js"].count("sectionLabel(ordinal, total)"),
            1,
            "the map must define exactly one counted-section helper",
        )

    def test_banned_internal_words_are_not_rendered_as_copy(self) -> None:
        files = segments()
        for name, body in files.items():
            for word in BANNED_LEARNER_WORDS:
                for pattern in (f"'{word}'", f"'{word} ", f"`{word}", f'"{word}"'):
                    self.assertNotIn(pattern, body, f"{name} still renders the internal word {word!r}")


class WideCardKeyboardTest(DesktopHarness):
    """U1 — the wide Home card is reachable by Tab and opened by Enter."""

    HARNESS = HOME_HARNESS

    def render(self, width: int) -> str:
        return self.run_node({"width": width, "rows": ROWS})["html"]

    @staticmethod
    def cards(html: str) -> list[str]:
        return re.findall(r"<article[^>]*data-cb-home-scene-card.*?</article>", html, re.S)

    def test_every_wide_card_carries_a_real_button(self) -> None:
        html = self.render(1344)
        cards = self.cards(html)
        self.assertEqual(len(cards), 4, "the scene did not render four cards")
        for card in cards:
            self.assertIn("<button", card, "a wide card has no control a keyboard can reach")
            button = re.search(r"<button[^>]*data-cb-home-scene-open[^>]*>", card)
            self.assertIsNotNone(button, "the control is not the card's open button")
            self.assertIn('type="button"', button.group(0))
            self.assertRegex(button.group(0), r'aria-label="Open [^"]+"', "the button has no accessible name")

    def test_the_card_itself_is_a_list_item_not_the_control(self) -> None:
        html = self.render(1344)
        for card in self.cards(html):
            opening = card[: card.index(">")]
            self.assertIn('role="listitem"', opening)
            self.assertNotIn("tabindex", opening.lower(), "the list item must not be a second tab stop")

    def test_the_narrow_home_still_renders_its_own_control(self) -> None:
        html = self.render(1049)
        self.assertNotIn("data-cb-home-scene", html)
        self.assertIn("data-cb-home-card", html)

    def test_the_scene_stylesheet_rings_the_card_control(self) -> None:
        source = (SRC / "76-v3-scope.js").read_text(encoding="utf-8")
        self.assertIn("[data-cb-v3] :focus-visible", source, "the identity lost its keyboard ring")
        match = re.search(r"\[data-cb-v3\] \[data-cb-home-scene-open\]:focus-visible\s*\{([^}]*)\}", source)
        self.assertIsNotNone(match, "the card button has no ring inside the clipped card")
        self.assertIn("outline-offset", match.group(1))


class CreateQuestionsTest(unittest.TestCase):
    """U7 — step 1 asks once, and step 3 asks what would prove the goal."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = strip_comments((SRC / "50-create.js").read_text(encoding="utf-8"))

    @staticmethod
    def constant(source: str, name: str) -> str:
        match = re.search(rf"const {name} = '([^']*)'", source)
        if match is None:
            raise AssertionError(f"{name} is not a single-quoted constant")
        return match.group(1)

    def test_step_three_does_not_repeat_the_step_one_question(self) -> None:
        heading = re.search(r"goal: '([^']*)'", self.source).group(1)
        question = self.constant(self.source, "OUTCOME_QUESTION")
        ratio = difflib.SequenceMatcher(None, heading.lower(), question.lower()).ratio()
        self.assertLess(ratio, 0.6, f"step 3 repeats step 1 ({heading!r} ~ {question!r}, ratio {ratio:.2f})")
        self.assertIn("prove", question.lower(), "step 3 must ask what would prove the goal")
        self.assertNotEqual(question, heading)

    def test_step_three_asks_for_the_proof_in_its_subtitle_and_field(self) -> None:
        subtitle = self.constant(self.source, "OUTCOME_SUBTITLE")
        self.assertIn("proof", subtitle.lower())
        self.assertIn("The proof you want, in your own words", self.source)
        self.assertIn('name: \'Proof\'', self.source)

    def test_step_one_heading_is_not_repeated_as_a_visible_label(self) -> None:
        heading = "What do you want to be able to do?"
        self.assertEqual(self.source.count(heading), 1, "step 1's question is still printed twice")
        label = re.search(r"jsx\('label', \{ className: 'sr-only', htmlFor: 'cb-goal'[^}]*children: '([^']*)'", self.source)
        self.assertIsNotNone(label, "the goal field lost its accessible name")
        self.assertNotEqual(label.group(1), heading)


if __name__ == "__main__":
    unittest.main()
