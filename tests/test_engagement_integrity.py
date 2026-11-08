"""Engagement integrity (H-155): the shipped copy and the shipped projections carry evidence, not theater.

This is the executable half of `docs/ENGAGEMENT-AUDIT.md`. It runs the real `desktop/plugin.js`
through Node and asserts what a learner can actually read and see:

* no user-facing string literal claims XP, a streak, a league, a leaderboard, hearts, energy, gems,
  coins, loot, a mastery percentage or "on a roll" pressure — except in an explicit negation
  ("there is no percentage to show"), which is a disclaimer and not a claim;
* the shelf path, the desk facts and the progress sentence print counts that equal the backend
  fields they were given, never a percentage;
* the objective state words the UI maps are the contract's own vocabulary
  (`contracts/vocabulary.v1.json`), so no invented state can appear.

Known defects are pinned with `expectedFailure` and the finding id from the audit, so the defect is
reproducible and its fix flips the test back to a normal pass.

Run: python3 -m unittest tests.test_engagement_integrity -v
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
VOCABULARY = ROOT / "contracts" / "vocabulary.v1.json"

HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  cbCoursePathSegments,
  cbCoursePathCaption,
  buildDeskModel,
  objectiveProgress,
  progressStatement,
  CoursePath
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const out = {}

const zero = {
  enrollment_id: 'enr_zero',
  course_id: 'crs_zero',
  title: 'Zero evidence course',
  evidence_summary: { independent: 0, review_due: 0, total_objectives: 4 }
}
out.zero = { segments: cbCoursePathSegments(zero), caption: cbCoursePathCaption(zero) }
out.zeroHtml = renderToStaticMarkup(React.createElement(CoursePath, { row: zero }))

const one = { ...zero, evidence_summary: { independent: 1, review_due: 1, total_objectives: 4 } }
out.one = { segments: cbCoursePathSegments(one), caption: cbCoursePathCaption(one) }

const empty = { ...zero, evidence_summary: { independent: 0, review_due: 0, total_objectives: 0 } }
out.empty = { segments: cbCoursePathSegments(empty), caption: cbCoursePathCaption(empty) }

const hostile = { ...zero, evidence_summary: { independent: 999, review_due: -3, total_objectives: 4 } }
out.hostile = { segments: cbCoursePathSegments(hostile), caption: cbCoursePathCaption(hostile) }

const unreadable = { ...zero, evidence_summary: { independent: 'x', review_due: null, total_objectives: undefined } }
out.unreadable = { segments: cbCoursePathSegments(unreadable), caption: cbCoursePathCaption(unreadable) }

out.desk = buildDeskModel({
  library: { items: [{ ...zero, next_step: { kind: 'start_lesson', label: 'Start section 1' }, updated_at: '2026-11-07T00:00:00+00:00' }] },
  outline: {
    total: 4,
    objectives: [
      { objective_id: 'o1', ordinal: 1, title: 'One', state: 'not_started', independent: false },
      { objective_id: 'o2', ordinal: 2, title: 'Two', state: 'not_started', independent: false },
      { objective_id: 'o3', ordinal: 3, title: 'Three', state: 'review_due', independent: false },
      { objective_id: 'o4', ordinal: 4, title: 'Four', state: 'independent_evidence', independent: true }
    ]
  },
  estimate: null
})
out.deskFields = {
  total: out.desk.total,
  settled: out.desk.settled,
  dueCount: out.desk.dueCount,
  sectionLabel: out.desk.sectionLabel,
  estimateLabel: out.desk.estimateLabel
}
out.progress = objectiveProgress(out.desk.objectives, out.desk.total)
out.statementZero = progressStatement(0, 4)
out.statementEmpty = progressStatement(0, 0)

process.stdout.write(JSON.stringify(out))
"""

SDK_STUB = """
import React from 'react'

const el = (tag, props, children) => React.createElement(tag, props, children)

export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export const PANES_AREA = 'panes'
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const SETTINGS_PLUGINS_AREA = 'settings.plugins'
export const TOOL_MEDIA_RENDERER_AREA = 'tool.media'
export const useValue = (atom) => (atom && typeof atom.get === 'function' ? atom.get() : atom)
export const useTheme = () => ({ renderedMode: 'light', resolvedMode: 'light' })
export const Button = (props) => el('button', { type: 'button', 'aria-label': props['aria-label'], onClick: props.onClick }, props.children)
export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, props.children)
export const Codicon = (props) => el('span', { className: 'codicon', 'data-icon': props.name }, null)
export const ListRow = (props) => el('div', { className: 'list-row' }, [props.title, props.description, props.action])
export const SegmentedControl = () => null
export const SearchField = () => null
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const EmptyState = (props) => el('div', { className: 'empty-state' }, [props.title, props.description])
export const ErrorState = (props) => el('div', { className: 'error-state' }, [props.title, props.description, props.children])
export const PanelEmpty = () => null
export const PanelSectionLabel = () => null
export const Input = () => null
export const Textarea = () => null
export const ConfirmDialog = () => null
export const DropdownMenu = () => null
export const DropdownMenuItem = () => null
export const DropdownMenuTrigger = () => null
export const DropdownMenuContent = () => null
export const Select = () => null
export const SelectTrigger = () => null
export const SelectValue = () => null
export const SelectContent = () => null
export const SelectItem = () => null
export const Tabs = () => null
export const Tip = () => null
export const SandboxedFrame = () => null
export const MessageTextContent = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null

const atom = (value) => ({ get: () => value })
export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    viewport: atom({ width: 1280, height: 900, narrow: false })
  },
  profileRoutes: async () => [{ connectionId: 'local', mode: 'local', profile: 'default', targetProfile: 'default' }],
  navigate: () => {},
  notify: () => {},
  openSession: async () => ({ ok: true }),
  newChat: async () => ({ ok: true })
}
"""

#: The mechanics the engagement evidence refuses. 'level', 'badge', 'points', 'ring', 'lock' and
#: 'checkpoint' are deliberately absent: each has a legitimate informational use in this product
#: (reading level, a host state chip, syllabus grade weight, a current-position halo, a submit
#: busy state, the document's own check node). They are audited by hand in the audit table.
BANNED = re.compile(
    r"\bXP\b"
    r"|streak"
    r"|leaderboard|league"
    r"|\bhearts?\b|\blives\b"
    r"|\benergy\b|\bgems?\b|\bcoins?\b|\bloot\b|\bcurrency\b"
    r"|\bmastery\b|\bmastered\b"
    r"|percent"
    r"|on a roll|days in a row|keep it up|spin to win|don'?t lose",
    re.IGNORECASE,
)
#: A disclaimer negates the mechanic; it is the opposite of a violation.
NEGATION = re.compile(r"\bno\b|\bnot\b|\bnever\b|\bnothing\b|\bcannot\b|\bwithout\b|isn't|aren't", re.IGNORECASE)

LITERAL = re.compile(r"'((?:[^'\\]|\\.)*)'")
#: Inline style values are not copy. CSS shorthand has no space after the property colon; prose
#: does ("Next: open the section…"), so the space is what keeps the filter from eating copy.
CSSISH = re.compile(
    r"^(?:[\d.]+(?:rem|px|em|%|s|ms|fr|vh|vw)?|#[0-9a-fA-F]{3,8}|(?:var|calc|rgb|rgba|hsl)\(.*"
    r"|[a-z-]+:[^ ].*"
    r"|[a-z0-9-]+(?:\s+[a-z0-9-]+){0,3}|[a-z][a-z0-9_-]*)$",
    re.IGNORECASE,
)


def copy_literals(source: str):
    """Every user-facing string literal, excluding comments. Yields (line, literal)."""
    for number, line in enumerate(source.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        for match in LITERAL.finditer(line):
            value = match.group(1)
            if len(value) < 8 or " " not in value or not re.search(r"[A-Za-z]", value):
                continue
            if CSSISH.match(value):
                continue
            yield number, value


def _desktop_node_modules() -> Path | None:
    candidates = [
        os.environ.get("HERMES_DESKTOP_APP"),
        str(Path.home() / ".hermes" / "hermes-agent" / "apps" / "desktop"),
        str(Path.home() / ".hermes" / "hermes-agent"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        react = Path(candidate) / "node_modules" / "react"
        server = Path(candidate) / "node_modules" / "react-dom" / "server.js"
        if react.is_dir() and server.is_file():
            return Path(candidate) / "node_modules"
    return None


class EngagementIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to execute the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-engagement-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.root = root
        payload = root / "payload.json"
        payload.write_text("{}", encoding="utf-8")
        result = subprocess.run(
            ["node", str(root / "harness.mjs"), str(payload)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise AssertionError(f"node harness failed:\n{result.stderr}")
        cls.out = json.loads(result.stdout)
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # ── copy ────────────────────────────────────────────────────────────────

    def test_user_copy_never_claims_a_refused_mechanic(self):
        """No string a learner can read claims XP, streaks, leagues, hearts, mastery or pressure."""
        claims = []
        for number, value in copy_literals(self.source):
            if not BANNED.search(value):
                continue
            if NEGATION.search(value):
                continue  # "there is no percentage to show" is a disclaimer
            claims.append((number, value))
        self.assertEqual([], claims, f"refused mechanics appear as claims in user copy: {claims}")

    def test_copy_scan_actually_sees_the_copy(self):
        """Guard against a silent scanner: the extraction must find the product's own copy."""
        literals = [value for _, value in copy_literals(self.source)]
        self.assertGreater(len(literals), 500)
        self.assertTrue(any("independent evidence" in value for value in literals))
        # Prose with a colon must not be mistaken for an inline style and skipped.
        self.assertTrue(any(value.startswith("Next: open the section") for value in literals))

    def test_disclaimers_are_present_where_a_percentage_could_be_misread(self):
        """Where a number could read as a score, the build says it is not one."""
        joined = "\n".join(value for _, value in copy_literals(self.source))
        for phrase in (
            "there is no percentage to show",
            "not an independent check",
            "not a graded score",
            "not mastery of the whole course",
        ):
            self.assertIn(phrase, joined.lower())

    # ── projections ─────────────────────────────────────────────────────────

    def test_course_path_caption_is_counts_never_percentage(self):
        for case in ("zero", "one", "empty", "hostile"):
            caption = self.out[case]["caption"]
            self.assertNotIn("%", caption)
            self.assertRegex(caption, r"^(No sections yet|\d+ of \d+ with evidence( · \d+ due)?)$")

    def test_course_path_clamps_unreadable_and_hostile_summaries(self):
        hostile = self.out["hostile"]["segments"]
        self.assertEqual(4, sum(1 for segment in hostile if segment["state"] == "done"))
        self.assertEqual("4 of 4 with evidence", self.out["hostile"]["caption"])
        unreadable = self.out["unreadable"]
        self.assertEqual({"empty"}, {segment["state"] for segment in unreadable["segments"]})
        self.assertEqual("No sections yet", unreadable["caption"])

    @unittest.expectedFailure
    def test_zero_evidence_path_paints_no_reached_segment(self):
        """ENG-D1: at zero evidence the first of four shelf segments is painted `--cb-accent`
        (state `current`, opacity 1) while the caption says "0 of 4 with evidence". One filled
        segment of four reads as 25% reached. Fix (H-148): at zero evidence every segment is
        `empty`/`quiet`, and `current` is not painted as a completed part."""
        segments = self.out["zero"]["segments"]
        painted = [s for s in segments if s["state"] in ("done", "current", "due")]
        self.assertEqual([], painted)
        self.assertNotIn("background:var(--cb-accent);opacity:1", self.out["zeroHtml"])

    def test_desk_counts_equal_the_outline_fields(self):
        desk = self.out["deskFields"]
        self.assertEqual(4, desk["total"])
        self.assertEqual(1, desk["settled"])
        self.assertEqual(1, desk["dueCount"])
        self.assertEqual("Section 1 of 4", desk["sectionLabel"])

    def test_progress_sentence_is_counts_and_says_so_when_empty(self):
        statement = self.out["progress"]["statement"]
        self.assertEqual("1 of 4 objectives have independent evidence", statement)
        self.assertNotIn("%", statement)
        self.assertEqual("No objectives recorded yet", self.out["statementEmpty"])

    # ── vocabulary ──────────────────────────────────────────────────────────

    def test_ui_state_words_are_the_contract_vocabulary(self):
        """The path may not render a state the backend cannot store."""
        vocabulary = json.loads(VOCABULARY.read_text(encoding="utf-8"))
        allowed = set(vocabulary["$defs"]["objective_state"]["enum"])
        block = self.source.split("const SECTION_STATE_SEMANTIC = {", 1)[1].split("\n}", 1)[0]
        keys = set(re.findall(r"^\s{2}([a-z_]+):", block, re.MULTILINE))
        self.assertEqual(allowed, keys, "the UI state map drifted from contracts/vocabulary.v1.json")
        self.assertNotIn("mastered", allowed)


if __name__ == "__main__":
    unittest.main()
