"""The Desktop half mirrors contract enums; those copies must not drift.

`desktop/plugin.js` may not import the Python contract loader, so the small enum sets it needs to
render a form (recipe choices, dial filters, course dials) are written as literals. This test reads
those literals back out of the module and compares them with the frozen JSON contracts, so a
contract amendment fails here instead of shipping a form that offers a value the backend refuses.

The Workshop's Share tab is the same problem in a different shape: it is the one desktop surface
that posts outside this machine, and its route is a FastAPI endpoint in `dashboard/plugin_api.py`
rather than a cb.rpc method. Nothing in the release gate read either half of that pair, so this
file also pins the `/workshop/share` call (verb, request fields, response fields the tab reads), the
backend route and handler, and the Workshop tab that mounts it. `desktop/plugin.js` is the exact
concatenation of `desktop/src/*.js` (`tests/test_plugin_build.py`), so an assertion here cannot be
satisfied by a segment that no longer ships, or by a shipped route with no source segment.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "desktop" / "plugin.js"
PLUGIN_API = ROOT / "dashboard" / "plugin_api.py"
SUBMIT_COURSE = ROOT / "scripts" / "submit-course.py"


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
PENDING_CONTRACT_METHODS: set[str] = {
    # GM-001 froze this name for the Game Mode manifest; GM-003 registers it. The Home shelf reads
    # it per visible course for the mode badge and never guesses a mode when it is unwired.
    "world.read",
}

#: The three v5 surfaces this workspace depends on; asserted present so a rename cannot silently
#: turn a real control back into a permanently gated one.
LEARNING_WORKSPACE_METHODS = {"check.get", "course.outline", "lesson.assist"}

#: Every Workshop HTTP route the Desktop calls, the verb it calls it with, and the FastAPI handler
#: in `dashboard/plugin_api.py` that answers it. These are not cb.rpc methods, so a Desktop call with
#: no decorator here renders a control whose click can only fail.
WORKSHOP_ROUTES: dict[str, tuple[str, str]] = {
    "/workshop/catalog": ("get", "workshop_catalog"),
    "/workshop/install": ("post", "workshop_install"),
    "/workshop/share": ("post", "workshop_share"),
}

#: The fields the Share tab reads off a successful `/workshop/share` response. Every one must be a
#: key the store submission ledger in `scripts/submit-course.py` can actually produce; otherwise the
#: tab prints an `undefined` where a fact belongs.
SHARE_RESPONSE_FIELDS = {
    "status",
    "pack_id",
    "mode",
    "objectives",
    "world_plates",
    "content_hash",
    "pull_request",
}


def _flatten(text: str) -> str:
    """Whitespace-insensitive form of a source fragment, so an assertion survives re-indentation."""
    return " ".join(text.split())


def _matching_brace(source: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise AssertionError("unbalanced braces in the shipped module")


def _brace_block(source: str, marker: str) -> str:
    """The text from `marker` through the object literal it opens (or the arrow body it starts)."""
    start = source.index(marker)
    return source[start : _matching_brace(source, source.index("{", start)) + 1]


def _function_body(source: str, name: str) -> str:
    """The whole declaration of `function name(...) {...}` in the shipped module."""
    start = source.index(f"function {name}(")
    body_open = source.index(") {", start) + 2
    return source[start : _matching_brace(source, body_open) + 1]


def _rest_call(source: str, path: str) -> str:
    """The options object of `rest('<path>', {...})`, or "" when the call takes no options."""
    marker = f"rest('{path}'"
    start = source.index(marker)
    after = start + len(marker)
    while source[after].isspace():
        after += 1
    if source[after] == ")":
        return ""
    return _brace_block(source, marker)


def _submit_ledger_keys() -> set[str]:
    """String keys the submission ledger can carry: `submit`/`_counts` dicts and every ledger[...]."""
    tree = ast.parse(SUBMIT_COURSE.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in tree.body:
        # The ledger is built in `submit`/`_counts` and completed by `_publish_from_worktree`, which
        # mutates the same dict, so every `ledger["x"] =` in the module names a returned key.
        if isinstance(node, ast.FunctionDef) and node.name in {"submit", "_counts"}:
            for inner in ast.walk(node):
                if isinstance(inner, ast.Dict):
                    for key in inner.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            keys.add(key.value)
        for inner in ast.walk(node):
            if isinstance(inner, ast.Assign):
                for target in inner.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "ledger"
                        and isinstance(target.slice, ast.Constant)
                        and isinstance(target.slice.value, str)
                    ):
                        keys.add(target.slice.value)
    return keys


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
        # H-22 (a parent of H-28) froze the evidence-class labels to sentences: the parent's report is
        # named and explicitly not graded by Coursebook. Neither H-28 nor H-55 may soften it to a bare
        # noun.
        self.assertIn("parent_reported: 'Reported by the parent — not graded by Coursebook.'", source)
        # `observation.record` is H-21's control and H-55 wired it (cb.rpc v14). It is the only
        # observation write path: one call site, and no checkbox lane records evidence instead.
        self.assertEqual(source.count("call('observation.record'"), 1)
        self.assertIn("checkSlot: parentLed ? null : checkNode", source)


def _stage_node_harness(case: unittest.TestCase, prefix: str, harness: str) -> Path:
    """Copy the shipped module beside React and the SDK stub, and write a Node harness next to it.

    ``test_desktop_contracts`` runs inside ``scripts/validate-plugin.sh`` against a ``git archive``
    export, so nothing here may read a path outside the export except the host's own React install.
    """
    if shutil.which("node") is None:
        raise unittest.SkipTest("node is required to render a runtime desktop plugin")
    from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

    modules = _desktop_node_modules()
    if modules is None:
        raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
    tmp = tempfile.TemporaryDirectory(prefix=prefix)
    case.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    (root / "plugin.js").write_text(_source(), encoding="utf-8")
    (root / "harness.mjs").write_text(harness, encoding="utf-8")
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
    return root


class ParentObservationSurfaceTest(unittest.TestCase):
    """H-55: the parent-observation control — its envelope, its copy, and where it may not appear.

    ``docs/CHECKLIST-CONFIRMATION.md`` §6 names this as the only recording path for a parent-recipe
    objective. These cases run the shipped module with a recording rpc stub and the handler's own
    replay rule (same ``idempotency_key`` + payload returns the stored evidence), so a retry, a
    double click, a changed note and an over-long note are all asserted rather than described.

    What this does NOT prove: that a live backend answers. ``tests/test_kernel_transitions.py``
    drives the same payload through the registered handler against a real migrated database.
    """

    HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  OBSERVATION_NOTE_MAX,
  ParentObservation,
  ParentObservationRecorded,
  SectionPage,
  nextObservationSubmission,
  parentObservationPayload,
  recordParentObservation
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const ENR = 'enr_0123456789abcdef'
const OBJ = 'obj_0123456789abcdef'

/** A recording transport with the handler's replay rule: same key + payload returns the stored row. */
function transport({ fail = false } = {}) {
  const calls = []
  const stored = new Map()
  let written = 0
  const call = async (method, body, options = {}) => {
    calls.push({ method, payload: body, options })
    if (fail) {
      return {
        ok: false,
        contract_version: 14,
        operation_id: 'op_failed',
        error: { code: 'HOST_UNAVAILABLE', category: 'capability', message: 'The backend is not answering.', retryable: true }
      }
    }
    const key = options.idempotencyKey
    if (stored.has(key)) {
      return { ok: true, contract_version: 14, operation_id: 'op_replay', revision: 7, result: stored.get(key) }
    }
    written += 1
    const result = { evidence_id: `ev_0123456789abcde${written}`, evidence_class: body.evidence_class, revision: 7 }
    stored.set(key, result)
    return { ok: true, contract_version: 14, operation_id: 'op_write', revision: 7, result }
  }
  return { call, calls, written: () => written }
}

function sectionPage(recipe, withDocument = false) {
  const page = {
    enrollment_id: ENR,
    course: { course_id: 'course_0123456789abcdef', title: 'Lighting the stove safely' },
    section: {
      objective_id: OBJ,
      title: 'Light the burner',
      ordinal: 1,
      state: 'introduced',
      evidence_target: 'procedure',
      last_opened_at: null
    },
    runtime: {
      lesson_run_id: 'run_0123456789abcdef',
      binding_id: null,
      binding_status: 'active',
      session_state: 'live',
      last_active_at: null
    },
    revision: 7,
    document: null,
    segments: [],
    sources: [],
    attempts: [],
    notebook_entries: []
  }
  if (withDocument) {
    // A section whose lesson document exists but carries no blocks: LessonDocumentView's own empty
    // state. The observation must still be reachable — nothing was generated, but the parent saw the
    // thing happen.
    page.document = {
      schema_version: 1,
      document_id: 'doc_0123456789abcdef0123',
      content_hash: 'sha256:' + 'a'.repeat(64),
      section_title: 'Light the burner',
      objective_id: OBJ,
      state: 'textbook_only',
      view_note: 'Teaching content appears here after a lesson turn.',
      views: { textbook: true, guided: false, field_quest: false, field_notes: false },
      blocks: [],
      check_id: 'chk_0123456789abcdef',
      source_ids: []
    }
  }
  return React.createElement(SectionPage, {
    row: {
      enrollment_id: ENR,
      recipe,
      title: 'Lighting the stove safely',
      profile: 'default',
      next_step: { kind: 'resume_lesson', label: 'Continue this section' }
    },
    objectiveId: OBJ,
    page,
    pageStatus: 'ready',
    pageError: null,
    onRetryPage: () => {},
    implemented: new Set(['check.open', 'observation.record']),
    onBack: () => {},
    onChanged: () => {},
    review: null,
    targetBlockId: null
  })
}

let output
if (payload.kind === 'retry') {
  const t = transport()
  const first = nextObservationSubmission(null, { enrollmentId: ENR, objectiveId: OBJ, note: payload.note, nonce: 'nonce-one' })
  const retry = nextObservationSubmission(first, { enrollmentId: ENR, objectiveId: OBJ, note: payload.note, nonce: 'nonce-two' })
  const a = await recordParentObservation({ call: t.call, key: first.key, enrollmentId: ENR, objectiveId: OBJ, note: payload.note })
  const b = await recordParentObservation({ call: t.call, key: retry.key, enrollmentId: ENR, objectiveId: OBJ, note: payload.note })
  output = { first, retry, a, b, calls: t.calls, written: t.written() }
} else if (payload.kind === 'changed') {
  const first = nextObservationSubmission(null, { enrollmentId: ENR, objectiveId: OBJ, note: 'counted to ten', nonce: 'nonce-one' })
  const second = nextObservationSubmission(first, { enrollmentId: ENR, objectiveId: OBJ, note: 'wrote the kana', nonce: 'nonce-two' })
  const back = nextObservationSubmission(second, { enrollmentId: ENR, objectiveId: OBJ, note: 'counted to ten', nonce: 'nonce-three' })
  output = { first, second, back }
} else if (payload.kind === 'note') {
  const t = transport()
  const response = await recordParentObservation({
    call: t.call,
    key: 'cb-observation-key-one',
    enrollmentId: ENR,
    objectiveId: OBJ,
    note: payload.note
  })
  output = { response, calls: t.calls, payload: parentObservationPayload({ enrollmentId: ENR, objectiveId: OBJ, note: payload.note }) }
} else if (payload.kind === 'fail') {
  const t = transport({ fail: true })
  const response = await recordParentObservation({ call: t.call, key: 'cb-observation-key-one', enrollmentId: ENR, objectiveId: OBJ, note: 'lit the burner' })
  output = { response, calls: t.calls }
} else if (payload.kind === 'render') {
  output = {
    editing: renderToStaticMarkup(
      React.createElement(ParentObservation, { enrollmentId: ENR, objectiveId: OBJ, onRecorded: () => {} })
    ),
    recorded: renderToStaticMarkup(
      React.createElement(ParentObservationRecorded, {
        result: { evidence_id: 'ev_0123456789abcdef', evidence_class: 'parent_reported', revision: 7 }
      })
    ),
    noteMax: OBSERVATION_NOTE_MAX
  }
} else if (payload.kind === 'section') {
  output = { html: renderToStaticMarkup(sectionPage(payload.recipe, Boolean(payload.withDocument))) }
} else {
  throw new Error(`unknown case ${payload.kind}`)
}
process.stdout.write(JSON.stringify(output))
"""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        from tests.test_desktop_lesson_views import _desktop_node_modules

        if _desktop_node_modules() is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")

    def run_case(self, payload: dict) -> dict:
        if not hasattr(self, "_root"):
            self._root = _stage_node_harness(self, "coursebook-parent-observation-", self.HARNESS)
        case = self._root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self._root / "harness.mjs"), str(case)],
            cwd=self._root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return json.loads(result.stdout)

    # -- (a) the exact payload and envelope ------------------------------------------------
    def test_a_the_payload_is_the_frozen_request_and_note_is_null_when_absent(self) -> None:
        out = self.run_case({"kind": "note", "note": "   "})
        self.assertEqual(
            out["payload"],
            {
                "enrollment_id": "enr_0123456789abcdef",
                "objective_id": "obj_0123456789abcdef",
                "evidence_class": "parent_reported",
                "note": None,
            },
        )
        call = out["calls"][0]
        self.assertEqual(call["method"], "observation.record")
        self.assertEqual(call["payload"], out["payload"])
        # idempotency_key is an envelope field, and this append declares no revision fence.
        self.assertEqual(call["options"]["idempotencyKey"], "cb-observation-key-one")
        self.assertIsNone(call["options"]["expectedRevision"])
        self.assertNotIn("idempotency_key", call["payload"])
        self.assertNotIn("expected_revision", call["payload"])

    # -- (b) a retry of the same payload replays instead of writing twice ------------------
    def test_b_a_retry_reuses_the_key_and_records_one_observation(self) -> None:
        out = self.run_case({"kind": "retry", "note": "counted to ten without help"})
        self.assertEqual(out["first"]["key"], out["retry"]["key"], "the same payload keeps its key")
        self.assertEqual(len(out["calls"]), 2)
        self.assertEqual(out["calls"][0]["payload"], out["calls"][1]["payload"])
        self.assertEqual(
            out["calls"][0]["options"]["idempotencyKey"], out["calls"][1]["options"]["idempotencyKey"]
        )
        self.assertEqual(out["a"]["result"]["evidence_id"], out["b"]["result"]["evidence_id"])
        self.assertEqual(out["written"], 1, "a retried observation must not mint a second evidence row")
        self.assertEqual(out["a"]["result"]["evidence_class"], "parent_reported")
        # The response revision is the enrollment revision echoed unchanged: it is not progress.
        self.assertEqual(out["a"]["result"]["revision"], 7)

    # -- (c) a changed note is a different observation and gets its own key ----------------
    def test_c_a_changed_note_mints_a_new_key(self) -> None:
        out = self.run_case({"kind": "changed"})
        self.assertNotEqual(out["first"]["key"], out["second"]["key"])
        self.assertNotEqual(out["second"]["key"], out["back"]["key"])
        self.assertIn("enr_0123456789abcdef", out["first"]["key"])
        self.assertIn("obj_0123456789abcdef", out["first"]["key"])

    # -- (d) the note bound is the contract's, refused not truncated ----------------------
    def test_d_a_note_over_the_bound_is_refused_before_the_wire(self) -> None:
        out = self.run_case({"kind": "note", "note": "x" * 1001})
        self.assertEqual(out["calls"], [], "the control must not send a note the schema refuses")
        self.assertFalse(out["response"]["ok"])
        self.assertEqual(out["response"]["stage"], "note_too_long")
        self.assertEqual(out["response"]["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(out["payload"]["note"], "x" * 1001, "the function reports the refused payload, never a slice")

    def test_e_a_note_at_the_bound_is_accepted(self) -> None:
        out = self.run_case({"kind": "note", "note": "y" * 1000})
        self.assertEqual(len(out["calls"]), 1)
        self.assertEqual(len(out["calls"][0]["payload"]["note"]), 1000)

    # -- (e) an offline call is a contract error the control can retry --------------------
    def test_f_a_failed_call_returns_the_contract_error_and_keeps_the_payload(self) -> None:
        out = self.run_case({"kind": "fail"})
        self.assertFalse(out["response"]["ok"])
        self.assertEqual(out["response"]["error"]["code"], "HOST_UNAVAILABLE")
        self.assertEqual(out["calls"][0]["payload"]["evidence_class"], "parent_reported")
        self.assertEqual(out["calls"][0]["options"]["idempotencyKey"], "cb-observation-key-one")

    # -- (f) the copy names the parent and never claims a pass ---------------------------
    def test_g_the_control_and_the_recorded_state_are_never_a_pass(self) -> None:
        out = self.run_case({"kind": "render"})
        editing = out["editing"]
        self.assertIn("Parent observation", editing)
        self.assertIn("not independent evidence", editing)
        self.assertIn("What did you observe? (optional note)", editing)
        self.assertIn('for="cb-observation-note"', editing)
        self.assertIn("Record observation", editing)
        self.assertEqual(out["noteMax"], 1000)
        recorded = out["recorded"]
        self.assertIn("Reported by the parent — not graded by Coursebook.", recorded)
        self.assertIn('data-cb-parent-observation-recorded="ev_0123456789abcdef"', recorded)
        self.assertIn('role="status"', recorded)
        self.assertIn("does not complete this objective", recorded)
        for html in (editing, recorded):
            lowered = html.lower()
            self.assertNotIn(">passed<", lowered)
            self.assertNotIn("mastered", lowered)
            self.assertNotIn("graded by coursebook as", lowered)
            self.assertNotIn("this objective is complete", lowered)
        # The control's own wiring: a bounded field, a described help line, an announced state.
        source = _source()
        control = source[source.index("function ParentObservation("):source.index("function AttemptControls(")]
        self.assertIn("maxLength: OBSERVATION_NOTE_MAX", control)
        self.assertIn("'aria-describedby': 'cb-observation-help'", control)
        self.assertIn("'aria-invalid': overLimit ? 'true' : undefined", control)
        self.assertIn("statusRef.current?.focus({ preventScroll: true })", control)
        self.assertIn("disabled: phase === 'saving' || overLimit", control)

    # -- (g) absent on every learner recipe, present on a parent recipe -------------------
    def test_h_the_control_is_absent_on_a_learner_lesson_surface(self) -> None:
        for recipe in ("one_off", "casual", "committed", "companion"):
            with self.subTest(recipe=recipe):
                html = self.run_case({"kind": "section", "recipe": recipe})["html"]
                self.assertNotIn("data-cb-parent-observation", html)
                self.assertNotIn("Parent observation", html)
                self.assertNotIn("Record observation", html)
                self.assertIn("Current check", html, "a learner page still shows its check surface")

    def test_i_the_control_is_present_on_a_parent_lesson_surface(self) -> None:
        html = self.run_case({"kind": "section", "recipe": "parent"})["html"]
        self.assertIn('data-cb-parent-observation="obj_0123456789abcdef"', html)
        self.assertIn("Parent observation", html)
        self.assertIn("Record observation", html)
        self.assertNotIn("Current check", html, "a parent objective is observed, not answered")
        self.assertEqual(html.count("data-cb-parent-observation"), 1, "mounted once, never per block")

    def test_j_a_section_with_no_generated_blocks_still_lets_the_parent_record(self) -> None:
        # LessonDocumentView early-returns its own empty state when the document has no blocks. The
        # control used to live inside the document's check slot, so it vanished exactly when nothing
        # had been generated yet — the one case where the parent may still have seen the child do it.
        parent = self.run_case({"kind": "section", "recipe": "parent", "withDocument": True})["html"]
        self.assertIn('data-cb-parent-observation="obj_0123456789abcdef"', parent)
        # H-174: an empty generated document is named as incomplete and owned by the lessons job.
        self.assertIn("This lesson page is incomplete", parent)
        self.assertNotIn("Coursebook does not write it for you", parent)
        learner = self.run_case({"kind": "section", "recipe": "committed", "withDocument": True})["html"]
        self.assertNotIn("data-cb-parent-observation", learner)


class WorkshopShareContractTest(unittest.TestCase):
    """The Workshop's Share tab, its HTTP pair, and the tab that mounts it (H-196, CP-042).

    The Share tab is the one Desktop surface whose button leaves this machine: it posts one
    enrollment id to `POST /workshop/share`, which exports the course on the host, runs the store
    gate, pushes a branch and opens one pull request. Both halves were unasserted by the release
    gate, so a deleted route or a renamed response field would ship a dead or lying button.

    The evidence is the shipped text, not a live window: `desktop/plugin.js` (byte-for-byte the
    concatenation of `desktop/src/*.js`, enforced by `tests/test_plugin_build.py`),
    `dashboard/plugin_api.py` for the route, and `scripts/submit-course.py` for the ledger the
    response is built from.
    """

    def test_the_share_call_is_one_post_carrying_exactly_enrollment_and_confirm(self) -> None:
        source = _source()
        self.assertEqual(
            source.count("rest('/workshop/share'"),
            1,
            "one share call site; a second would bypass the confirmation gate",
        )
        # The options object, flattened: the verb and the whole request body.
        call = _flatten(_rest_call(source, "/workshop/share"))
        self.assertIn("method: 'POST'", call)
        self.assertIn("body: { enrollment_id: item.enrollment_id, confirm: true }", call)
        # The body keys are exactly these two: never a path, never a file to publish.
        body = call.split("body: {", 1)[1].split("}", 1)[0]
        self.assertEqual(re.findall(r"([a-z_]+):", body), ["enrollment_id", "confirm"])
        self.assertNotIn("path", call)
        # The id it posts is the enrollment the library row carries, not a title or an index.
        tab = _flatten(_function_body(source, "WorkshopShare"))
        self.assertIn("onClick: () => setPending(item)", tab)
        # `confirm: true` is only sent after the author pressed the dialog's publish control: the
        # row click opens the confirmation, and `publish` is reached from nowhere else.
        self.assertIn(
            "jsx(WorkshopShareConfirm, { item: pending, onConfirm: () => publish(pending), "
            "onCancel: () => setPending(null) })",
            tab,
        )
        self.assertEqual(
            tab.count("publish("),
            1,
            "publish( is called once, from the confirmation dialog",
        )
        self.assertNotIn("onClick: () => publish(", tab)

    def test_the_share_tab_reads_the_response_fields_that_carry_the_outcome(self) -> None:
        tab = _function_body(_source(), "WorkshopShare")
        flat = _flatten(tab)
        # A non-true `ok` is a refusal with a message, never a half-success.
        self.assertIn("response.ok !== true", flat)
        self.assertIn("response.message", flat)
        self.assertIn("setError(", flat)
        for field in sorted(SHARE_RESPONSE_FIELDS):
            with self.subTest(field=field):
                self.assertIn(f"outcome.{field}", flat, f"the Share tab must read {field} off the response")
        # The three outcomes the copy distinguishes: no-op, update, new.
        self.assertIn("outcome.status === 'already_present'", flat)
        self.assertIn("outcome.status === 'update'", flat)
        # The link is offered only when the host returned one, and it opens externally.
        self.assertIn("outcome.pull_request ? jsx('a', { href: outcome.pull_request", flat)
        self.assertIn("target: '_blank'", flat)
        self.assertIn("rel: 'noreferrer'", flat)
        # The button is disabled while its own row is in flight, so a double click cannot post twice.
        self.assertIn("disabled: busy === item.enrollment_id", flat)

    def test_every_share_response_field_is_one_the_submission_ledger_produces(self) -> None:
        # The tab renders whatever the host returns, so each field it reads must be a key the store
        # path can actually mint. This is the field half of the route contract.
        ledger = _submit_ledger_keys()
        self.assertEqual(
            sorted(SHARE_RESPONSE_FIELDS - ledger),
            [],
            "the Share tab reads a field the submission ledger never returns",
        )
        submit = SUBMIT_COURSE.read_text(encoding="utf-8")
        self.assertIn('"status": "already_present"', submit, "the no-op status the tab handles")
        self.assertIn('ledger["pull_request"] = node', submit, "the pull request link the tab offers")

    def test_every_workshop_call_in_the_module_has_its_backend_route(self) -> None:
        source = _source()
        api = PLUGIN_API.read_text(encoding="utf-8")
        called = set(re.findall(r"rest\('(/workshop/[a-z-]+)'", source))
        self.assertEqual(sorted(called - set(WORKSHOP_ROUTES)), [], "a Workshop call with no known route")
        self.assertEqual(sorted(set(WORKSHOP_ROUTES) - called), [], "a Workshop route the module never calls")
        for path, (verb, handler) in WORKSHOP_ROUTES.items():
            with self.subTest(path=path):
                self.assertRegex(
                    api,
                    rf'@router\.{verb}\("{re.escape(path)}"\)\s*async def {handler}\(',
                    f"{path} must be registered as {verb.upper()} on {handler}",
                )
                call = _flatten(_rest_call(source, path))
                if verb == "post":
                    self.assertIn("method: 'POST'", call, path)
                else:
                    self.assertNotIn("method:", call, f"{path} is a read and must use the GET default")

    def test_the_share_route_requires_confirm_and_never_accepts_a_path(self) -> None:
        api = PLUGIN_API.read_text(encoding="utf-8")
        self.assertIn('@router.post("/workshop/share")', api, "the share route must be registered")
        self.assertIn('@router.get("/packs/intake")', api, "the route that follows the share handler")
        share = api[api.index('@router.post("/workshop/share")') : api.index('@router.get("/packs/intake")')]
        # The confirmation gate: the author's explicit grant, or a dry run that writes nothing.
        self.assertIn('body.get("confirm") is not True', share)
        self.assertIn('body.get("dry_run") is not True', share)
        self.assertIn('"CONFIRMATION_REQUIRED"', share)
        self.assertIn('"share needs one enrollment_id"', share)
        # It exports through the contract, reading the reviewed hash first and fencing the write on it.
        self.assertIn('"method": "course.export.read"', share)
        self.assertIn('"method": "course.export"', share)
        self.assertIn('"expected_content_hash": content_hash', share)
        self.assertIn('f"share-{enrollment_id}-', share, "the export carries a per-course idempotency key")
        # The client can never hand this route a file to publish.
        self.assertNotIn('body.get("path")', share)
        self.assertNotIn('body["path"]', share)
        # Both answers are data: success is the ledger, refusal is a code plus a message.
        self.assertIn('return {"ok": True, **ledger}', share)
        self.assertRegex(share, r'"ok": False,\s*"code": "[A-Z_]+",\s*"message":')

    def test_the_workshop_tab_mounts_the_share_surface_on_the_coursebook_route(self) -> None:
        source = _source()
        tabs = _string_list(source, "const WORKSHOP_TABS = Object.freeze([")
        self.assertEqual(tabs, ["discover", "library", "provenance", "share"])
        self.assertIn(
            "{ id: 'share', label: 'Share to store' }",
            _flatten(source[source.index("const WORKSHOP_TABS") : source.index("const WORKSHOP_USER_CATEGORIES")]),
        )
        # The tab id has exactly one branch, and it mounts the Share component with no arguments.
        view = _flatten(_function_body(source, "WorkshopView"))
        self.assertEqual(view.count("tab === 'share'"), 1)
        self.assertIn("else if (tab === 'share') { body = jsx(WorkshopShare, {}) }", view)
        # The Workshop route itself: one page registration on ROUTE_PATH rendering CoursebookPage,
        # and the workshop destination mounting WorkshopView.
        self.assertIn("data: { path: ROUTE_PATH }", _flatten(source))
        self.assertIn("render: () => jsx(CoursebookPage, {})", _flatten(source))
        workshop_branch = _flatten(_brace_block(source, "else if (destination === 'workshop') {"))
        self.assertIn("body = jsx(WorkshopView, {", workshop_branch)
        self.assertEqual(source.count("jsx(WorkshopShare, {"), 1, "the Share surface is mounted once")


if __name__ == "__main__":
    unittest.main()
