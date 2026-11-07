"""The Desktop half mirrors contract enums; those copies must not drift.

`desktop/plugin.js` may not import the Python contract loader, so the small enum sets it needs to
render a form (recipe choices, dial filters, course dials) are written as literals. This test reads
those literals back out of the module and compares them with the frozen JSON contracts, so a
contract amendment fails here instead of shipping a form that offers a value the backend refuses.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "desktop" / "plugin.js"


def _source() -> str:
    return PLUGIN.read_text(encoding="utf-8")


def _contract(name: str) -> dict:
    return json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))


def _latest_rpc() -> dict:
    """The newest frozen cb.rpc document on disk (`rpc.v5.json` today)."""
    versions = sorted((ROOT / "contracts").glob("rpc.v*.json"), key=lambda path: int(re.findall(r"v(\d+)", path.name)[0]))
    return json.loads(versions[-1].read_text(encoding="utf-8"))


#: Methods the Desktop gates on that the frozen contract does not define. Empty since cb.rpc v5
#: (CB-026, Atlas) froze `course.outline`, `check.get` and `lesson.assist`: the gate on each is now
#: a runtime gate — `/runtime.implemented_methods` decides, and the honest "not in this build" state
#: expires by itself when Cinder's handlers land. Keeping the (now empty) allowlist means a typo in
#: a gated method name still fails here.
PENDING_CONTRACT_METHODS: set[str] = set()

#: The three v5 surfaces this workspace depends on; asserted present so a rename cannot silently
#: turn a real control back into a permanently gated one.
LEARNING_WORKSPACE_METHODS = {"check.get", "course.outline", "lesson.assist"}


def _string_list(source: str, marker: str) -> list[str]:
    """The single-quoted string literals of the array literal that follows `marker`."""
    start = source.index(marker)
    end = source.index("]", start)
    return re.findall(r"'([a-z_]+)'", source[start:end])


def _dial_options(source: str, dial: str) -> list[str]:
    start = source.index(f"{dial}: {{")
    end = source.index("]", start)
    return re.findall(r"id: '([a-z_]+)'", source[start:end])


class DesktopContractMirrorTest(unittest.TestCase):
    def test_recipes_match_the_vocabulary(self) -> None:
        vocabulary = _contract("vocabulary.v1.json")
        expected = vocabulary["$defs"]["recipe"]["enum"]
        self.assertEqual(_string_list(_source(), "const RECIPES = ["), expected)

    def test_dial_options_match_course_create(self) -> None:
        rpc = _contract("rpc.v2.json")
        request = rpc["$defs"]["methods"]["properties"]["course.create"]["request"]
        dials = request["properties"]["dials"]["properties"]
        source = _source()
        for dial, schema in dials.items():
            with self.subTest(dial=dial):
                self.assertEqual(_dial_options(source, dial), schema["enum"])

    def test_library_filters_match_the_request_enum(self) -> None:
        rpc = _contract("rpc.v2.json")
        request = rpc["$defs"]["methods"]["properties"]["library.list"]["request"]
        expected = request["properties"]["filter"]["enum"]
        self.assertEqual(_string_list(_source(), "const FILTERS = ["), expected)

    def test_filtered_empty_accounts_for_a_search_query(self) -> None:
        # With courses on the profile, an empty result set caused by the search box must render the
        # filtered-empty state (which offers Clear search), never first-run. `applied_filter` alone
        # missed the search case and told a learner with courses that they had none.
        source = _source()
        start = source.index("const filteredEmpty =")
        block = source[start : source.index("\n\n", start)]
        self.assertIn("applied_filter", block)
        self.assertIn("query", block, "the search term must count as a filter")

    def test_navigation_uses_the_contributed_route_and_one_segment(self) -> None:
        source = _source()
        self.assertIn("const ROUTE_PATH = '/coursebook'", source)
        # One static segment: no nested or parameterised coursebook route literal.
        self.assertNotRegex(source, r"'/coursebook[/:]")

    def test_the_learning_workspace_methods_are_frozen(self) -> None:
        # cb.rpc v5 (CB-026) froze the three surfaces this workspace was originally built to gate.
        methods = set(_latest_rpc()["$defs"]["method"]["enum"])
        self.assertEqual(sorted(LEARNING_WORKSPACE_METHODS - methods), [])

    def test_every_gated_control_names_a_contract_method(self) -> None:
        # A control gated on a method that the contract does not define could never light up —
        # except for the explicitly filed forward amendments, which render an honest gated state.
        rpc = _latest_rpc()
        methods = set(rpc["$defs"]["method"]["enum"])
        source = _source()
        named = set(re.findall(r"supports\('([a-z_]+\.[a-z_]+)'\)", source))
        named |= set(re.findall(r"implemented\.has\('([a-z_]+\.[a-z_]+)'\)", source))
        named |= set(re.findall(r"backendSupports\('([a-z_]+\.[a-z_]+)'\)", source))
        self.assertTrue(named, "no gated controls found")
        self.assertEqual(sorted(named - methods - PENDING_CONTRACT_METHODS), [])
        # Every pending gate must still be used, so the allowlist cannot rot into dead weight.
        self.assertEqual(sorted(PENDING_CONTRACT_METHODS - named), [])


class ChecklistConfirmationSurfaceTest(unittest.TestCase):
    """The confirmation checklist as the pane really renders and answers it (H-35).

    ``docs/CHECKLIST-CONFIRMATION.md`` §9 freezes this surface: a served ``format: "verification"``
    stimulus with declared items is ticked, answered with ``kind: "selection"`` over the item ids,
    and its result is labelled self-reported in the frozen words. These cases render the shipped
    module through ``react-dom/server`` with the SDK stub, so a checkbox that disappears, a payload
    that reverts to text/labels, or a softened claim fails here.
    """

    HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  AttemptControls,
  AttemptVerdict,
  checklistAnswer,
  SELF_REPORTED_CONFIRM_COPY,
  SELF_REPORTED_EVIDENCE_COPY
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
let html
if (payload.kind === 'check') {
  html = renderToStaticMarkup(
    React.createElement(AttemptControls, {
      enrollmentId: 'enr_0123456789abcdef',
      objectiveId: 'obj_0123456789abcdef',
      check: payload.check,
      revision: 3,
      implemented: new Set(['check.get']),
      bindingState: payload.bindingState || 'active',
      parentLed: Boolean(payload.parentLed),
      onCommitted: () => {}
    })
  )
} else {
  html = renderToStaticMarkup(
    React.createElement(AttemptVerdict, {
      result: payload.result,
      criteria: payload.criteria,
      checklist: payload.checklist,
      onResumeChecklist: () => {},
      onNewExample: () => {},
      onExplain: () => {}
    })
  )
}
process.stdout.write(
  JSON.stringify({
    html,
    answer: checklistAnswer(payload.ids || []),
    confirm: SELF_REPORTED_CONFIRM_COPY,
    evidence: SELF_REPORTED_EVIDENCE_COPY
  })
)
"""

    ITEMS = [
        {"id": "step-open-app", "label": "Open the settings panel"},
        {"id": "step-enable-mode", "label": "Turn on the accessibility mode"},
        {"id": "step-check-contrast", "label": "Confirm the text is readable"},
    ]

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-checklist-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(_source(), encoding="utf-8")
        (root / "harness.mjs").write_text(cls.HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler"):
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

    def render(self, payload: dict) -> dict:
        case = Path(self.tmp.name) / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(Path(self.tmp.name) / "harness.mjs"), str(case)],
            cwd=self.tmp.name,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return json.loads(result.stdout)

    def verification_check(self) -> dict:
        return {
            "check_id": "chk_0123456789abcdef",
            "check_version": 4,
            "evidence_target": "procedure",
            "state": "open",
            "stimulus": {
                "prompt": "Set up the accessibility mode and confirm each step you actually did.",
                "format": "verification",
                "choices": [],
                "items": self.ITEMS,
            },
        }

    # -- (a) the served items are checkboxes carrying the served ids ---------------------------
    def test_a_verification_stimulus_renders_one_checkbox_per_item(self) -> None:
        out = self.render({"kind": "check", "check": self.verification_check()})
        html = out["html"]
        self.assertIn('data-cb-check-items-mode="selection"', html)
        for item in self.ITEMS:
            self.assertIn(f'data-cb-check-tick="{item["id"]}"', html)
            self.assertIn(f'data-cb-check-item="{item["id"]}"', html)
            self.assertEqual(html.count(item["id"]), 2, item["id"])
        self.assertEqual(html.count('type="checkbox"'), len(self.ITEMS))
        self.assertEqual(html.count("checked"), 0, "nothing is ticked before the learner ticks it")
        # The ticked value is never the label: a label must not appear where an id belongs.
        for item in self.ITEMS:
            self.assertNotIn(f'data-cb-check-tick="{item["label"]}"', html)
        # The written-answer field is not offered for a checklist.
        self.assertNotIn("cb-attempt-answer", html)
        self.assertIn('data-cb-answer-kind="selection"', html)

    # -- (b) the submitted payload is kind:selection over the checked ids ----------------------
    def test_b_selection_answer_carries_ids_not_labels(self) -> None:
        out = self.render(
            {"kind": "verdict", "result": {}, "criteria": [], "checklist": [], "ids": [self.ITEMS[0]["id"], self.ITEMS[2]["id"]]}
        )
        self.assertEqual(out["answer"], {"kind": "selection", "selection": ["step-open-app", "step-check-contrast"]})
        self.assertNotIn("text", out["answer"])
        self.assertNotIn("settings panel", json.dumps(out["answer"]))
        # The component's submit path hands the ticked ids to that builder, not the labels or text.
        source = _source()
        controls = source[source.index("function AttemptControls"):]
        submit = controls[controls.index("const submit = useCallback") : controls.index("const retryGrading")]
        self.assertIn("checklistAnswer(ticked)", submit)
        self.assertIn("attemptAnswer(text.trim())", submit)

    # -- (c) Submit is disabled with zero ticks ------------------------------------------------
    def test_c_submit_is_disabled_until_something_is_ticked(self) -> None:
        html = self.render({"kind": "check", "check": self.verification_check()})["html"]
        submit = re.search(r"<button[^>]*>Submit confirmation</button>", html)
        self.assertIsNotNone(submit, html[-1500:])
        self.assertIn("disabled", submit.group(0))
        clear = re.search(r"<button[^>]*>Clear ticks</button>", html)
        self.assertIsNotNone(clear)
        self.assertIn("disabled", clear.group(0))

    # -- (d) a self-reported pass renders the two frozen sentences -----------------------------
    def test_d_self_reported_pass_renders_the_frozen_copy(self) -> None:
        out = self.render(
            {
                "kind": "verdict",
                "result": {"verdict": "pass", "evidence_class": "self_reported", "next_action": "review_objective"},
                "criteria": [{"id": item["id"], "observed": "ticked", "met": True} for item in self.ITEMS],
                "checklist": self.ITEMS,
            }
        )
        html = out["html"]
        self.assertIn("You confirmed every step. This is your own report, not an independent check.", html)
        self.assertIn("data-cb-self-reported=\"confirmation\"", html)
        self.assertEqual(html.count('type="checkbox"'), len(self.ITEMS))
        self.assertEqual(html.count('checked=""'), len(self.ITEMS), "every criterion reads as ticked")
        self.assertNotIn(">Passed<", html)
        self.assertNotIn("mastered", html.lower())
        self.assertNotIn("verified", html.lower())
        self.assertNotIn("passed independently", html.lower())
        self.assertNotIn("This objective is complete", html)
        self.assertIn("not an independent check", html)

    def test_d_evidence_class_always_carries_the_self_reported_notice(self) -> None:
        out = self.render(
            {
                "kind": "verdict",
                "result": {"verdict": "pass", "evidence_class": "self_reported", "next_action": "complete_objective"},
                "criteria": [{"id": item["id"], "observed": "ticked", "met": True} for item in self.ITEMS],
                "checklist": self.ITEMS,
            }
        )
        self.assertEqual(
            out["evidence"], "Self-reported — you told us. It cannot count as independent evidence."
        )
        # Rendered wherever an evidence class is shown, not only inside the verdict panel.
        self.assertIn("'data-cb-evidence-notice': value", _source())
        self.assertIn("SELF_REPORTED_EVIDENCE_COPY", _source())

    def test_partial_keeps_the_check_open_and_invites_the_rest(self) -> None:
        out = self.render(
            {
                "kind": "verdict",
                "result": {"verdict": "partial", "evidence_class": "self_reported", "next_action": "retry_attempt"},
                "criteria": [{"id": item["id"], "observed": "ticked", "met": index < 2} for index, item in enumerate(self.ITEMS)],
                "checklist": self.ITEMS,
            }
        )
        html = out["html"]
        self.assertIn("You confirmed 2 of 3 steps", html)
        self.assertIn("Tick the remaining steps", html)
        self.assertNotIn("data-cb-self-reported", html)
        self.assertEqual(html.count('checked=""'), 2)

    def test_a_parent_led_check_renders_no_tick_list(self) -> None:
        html = self.render({"kind": "check", "check": self.verification_check(), "parentLed": True})["html"]
        self.assertNotIn('type="checkbox"', html)
        self.assertNotIn("data-cb-check-items", html)
        self.assertNotIn("data-cb-check-item", html)
        self.assertIn("cb-attempt-answer", html, "a parent-led card keeps the written-answer path")

    def test_a_text_stimulus_keeps_the_written_answer_path(self) -> None:
        check = self.verification_check()
        check["stimulus"] = {"prompt": "Explain why contrast matters.", "format": "text", "choices": []}
        html = self.render({"kind": "check", "check": check})["html"]
        self.assertNotIn('type="checkbox"', html)
        self.assertIn('data-cb-answer-kind="text"', html)
        self.assertIn("Submit answer", html)

    def test_the_parent_observation_label_exists_and_no_parent_control_ticks(self) -> None:
        source = _source()
        self.assertIn("parent_reported: 'Parent reported'", source)
        # `observation.record` is H-21's control; this card must not grow a second observation path.
        self.assertNotIn("observation.record", source)


if __name__ == "__main__":
    unittest.main()
