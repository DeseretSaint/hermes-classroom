"""H-02: the learner create flow really starts the plan job (Desktop half).

The module is one uncompiled ESM file, so the honest test imports the shipped functions and runs
them with a recording rpc stub: the exact call sequence, the exact payloads, the idempotency keys,
and the recovery shapes are asserted here rather than described in a comment.

What this does NOT prove: that a live backend is running. `tests/test_learner_plan_flow.py` drives
the same payloads through `coursebook.api.dispatch` against a real database, and the two files
together are the evidence that goal → plan job → review → approve → lessons is wired.
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


def _source() -> str:
    return PLUGIN_JS.read_text(encoding="utf-8")


HARNESS = """
import {
  COURSE_SCOPES,
  CB_USE_OPTIONS,
  CreateCourseFlow,
  courseCreatePayload,
  createStartStep,
  effectiveDepth,
  planJobBrief,
  planTimingCopy,
  scopeFacts,
  scopeSectionBand,
  SCOPE_MIN_DEPTH,
  startLearnerPlan,
  suggestedTitle
} from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const DECISION = {
  title: 'Coffee in Kyoto',
  goal: 'Order coffee and ask for the bill in Kyoto, politely.',
  recipe: 'committed',
  dials: { pace: 'steady', depth: 'working', assessment: 'graded', autonomy: 'guided' },
  locale: 'ja-JP',
  level: 'L0',
  subjectDomain: 'language',
  scope: 'short'
}

/** A recording transport. `fail` names the method that returns a typed failure instead. */
function transport({ fail = null, jobId = 'job_plan_1', idempotent = false } = {}) {
  const calls = []
  const jobsSeen = new Map()
  let jobsCreated = 0
  const call = async (method, body, options = {}) => {
    calls.push({ method, payload: body, options })
    if (fail === method) {
      return { ok: false, error: { code: 'PROVIDER_UNAVAILABLE', message: 'no provider bound' } }
    }
    if (method === 'course.create') {
      return { ok: true, result: { course_id: 'course_1', plan_id: 'plan_draft_1' } }
    }
    if (method === 'enrollment.create') {
      return { ok: true, result: { enrollment_id: 'enr_1' } }
    }
    if (method === 'jobs.create') {
      const key = options.idempotencyKey
      if (idempotent && jobsSeen.has(key)) {
        return { ok: true, result: { job_id: jobsSeen.get(key), state: 'queued' } }
      }
      jobsCreated += 1
      const id = `${jobId}_${jobsCreated}`
      if (idempotent) jobsSeen.set(key, id)
      return { ok: true, result: { job_id: id, state: 'queued' } }
    }
    throw new Error(`unexpected method ${method}`)
  }
  return { call, calls, jobsCreated: () => jobsCreated }
}

let output
if (payload.kind === 'sequence') {
  const t = transport({ idempotent: Boolean(payload.idempotent) })
  const first = await startLearnerPlan({ call: t.call, key: 'cb-course-create-key1', ...DECISION })
  const second = payload.retry
    ? await startLearnerPlan({ call: t.call, key: 'cb-course-create-key1', ...DECISION })
    : null
  output = { first, second, calls: t.calls, jobsCreated: t.jobsCreated() }
} else if (payload.kind === 'fail') {
  const t = transport({ fail: payload.fail })
  const result = await startLearnerPlan({ call: t.call, key: 'cb-course-create-key1', ...DECISION })
  output = { result, calls: t.calls }
} else if (payload.kind === 'brief') {
  output = {
    brief: planJobBrief({
      courseId: 'course_1',
      enrollmentId: 'enr_1',
      goal: DECISION.goal,
      recipe: DECISION.recipe,
      dials: DECISION.dials,
      ...(payload.optional || {})
    }),
    course: courseCreatePayload({
      title: DECISION.title,
      recipe: DECISION.recipe,
      goal: DECISION.goal,
      dials: DECISION.dials,
      ...(payload.optional || {})
    })
  }
} else if (payload.kind === 'copy') {
  output = {
    scopes: COURSE_SCOPES,
    copy: Object.fromEntries(COURSE_SCOPES.map((scope) => [scope.id, planTimingCopy(scope.id)])),
    fallback: planTimingCopy(null),
    // H-179: the shape each card states and the one track of uses.
    facts: Object.fromEntries(COURSE_SCOPES.map((scope) => [scope.id, scopeFacts(scope.id)])),
    bands: Object.fromEntries(COURSE_SCOPES.map((scope) => [scope.id, scopeSectionBand(scope.id)])),
    uses: CB_USE_OPTIONS,
    trails: Object.fromEntries(COURSE_SCOPES.map((scope) => [scope.id, scope.trail]))
  }
} else if (payload.kind === 'render') {
  // H-179: a real render of the shape step and the trailhead preview, so the primary count is
  // read from markup rather than counted in the source.
  const React = (await import('react')).default
  const { renderToStaticMarkup } = await import('react-dom/server')
  const seed = payload.step === 2
    ? { goal: DECISION.goal }
    : { goal: DECISION.goal, scope: payload.scope || 'short', title: 'Coffee in Kyoto', dials: DECISION.dials, recipe: 'casual' }
  const html = renderToStaticMarkup(React.createElement(CreateCourseFlow, {
    seed,
    onCancel: () => {},
    onCreated: () => {}
  }))
  output = { html }
} else if (payload.kind === 'step') {
  output = {
    fresh: createStartStep(null),
    emptyGoal: createStartStep({ goal: '   ', scope: 'short' }),
    goalOnly: createStartStep({ goal: 'Wire a lamp safely' }),
    goalAndScope: createStartStep({ goal: 'Wire a lamp safely', scope: 'single' }),
    titles: {
      empty: suggestedTitle(''),
      plain: suggestedTitle('Hold a six-minute conversation in Spanish'),
      firstSentence: suggestedTitle('Order coffee in Kyoto. Then ask for the bill.'),
      whitespace: suggestedTitle('  Wire   a lamp   safely  '),
      long: suggestedTitle('x'.repeat(100))
    }
  }
} else if (payload.kind === 'depth') {
  output = {
    floor: SCOPE_MIN_DEPTH,
    cases: [
      ['single', 'survey'],
      ['short', 'survey'],
      ['full', 'survey'],
      ['full', 'working'],
      ['single', 'deep'],
      ['full', 'deep'],
      ['short', null]
    ].map(([scope, depth]) => ({ scope, depth, effective: effectiveDepth(depth, scope) }))
  }
} else {
  throw new Error(`unknown case ${payload.kind}`)
}
process.stdout.write(JSON.stringify(output))
"""


class CreateFlowSequenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to run the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-create-flow-")
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

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_case(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return json.loads(result.stdout)

    # ── the sequence ────────────────────────────────────────────────────────
    def test_the_flow_is_course_then_enrollment_then_one_plan_job(self) -> None:
        out = self.run_case({"kind": "sequence"})
        methods = [call["method"] for call in out["calls"]]
        self.assertEqual(methods, ["course.create", "enrollment.create", "jobs.create"])
        self.assertTrue(out["first"]["ok"])
        self.assertEqual(out["first"]["jobId"], "job_plan_1_1")

    def test_each_step_carries_its_own_idempotency_key(self) -> None:
        out = self.run_case({"kind": "sequence"})
        keys = [call["options"].get("idempotencyKey") for call in out["calls"]]
        self.assertEqual(keys[0], "cb-course-create-key1")
        self.assertEqual(keys[1], "cb-course-create-key1-enroll")
        self.assertEqual(keys[2], "cb-course-create-key1-plan")
        # course.create explicitly has no prior revision; it is not a fenced mutation.
        self.assertIsNone(out["calls"][0]["options"].get("expectedRevision"))

    def test_the_job_brief_carries_every_declared_input(self) -> None:
        out = self.run_case({"kind": "sequence"})
        brief = out["calls"][2]["payload"]["brief"]
        self.assertEqual(out["calls"][2]["payload"]["kind"], "plan")
        self.assertEqual(brief["stage"], "plan")
        self.assertEqual(brief["course_id"], "course_1")
        self.assertEqual(brief["enrollment_id"], "enr_1")
        self.assertEqual(brief["goal"], "Order coffee and ask for the bill in Kyoto, politely.")
        self.assertEqual(brief["recipe"], "committed")
        self.assertEqual(brief["dials"]["assessment"], "graded")
        self.assertEqual(brief["locale"], "ja-JP")
        self.assertEqual(brief["level"], "L0")
        self.assertEqual(brief["subject_domain"], "language")
        self.assertEqual(brief["scope"], "short")

    def test_the_course_create_payload_carries_the_same_decision(self) -> None:
        out = self.run_case({"kind": "sequence"})
        payload = out["calls"][0]["payload"]
        self.assertEqual(payload["level"], "L0")
        self.assertEqual(payload["subject_domain"], "language")
        self.assertEqual(payload["scope"], "short")
        self.assertEqual(payload["locale"], "ja-JP")
        self.assertNotIn("stage", payload)

    def test_a_retry_with_the_same_key_spawns_no_second_job(self) -> None:
        out = self.run_case({"kind": "sequence", "retry": True, "idempotent": True})
        self.assertEqual(out["first"]["jobId"], out["second"]["jobId"])
        self.assertEqual(out["jobsCreated"], 1)
        self.assertEqual([call["method"] for call in out["calls"]].count("jobs.create"), 2)

    # ── failure and recovery ────────────────────────────────────────────────
    def test_a_failed_plan_job_keeps_the_draft_recoverable(self) -> None:
        out = self.run_case({"kind": "fail", "fail": "jobs.create"})
        result = out["result"]
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "jobs.create")
        self.assertEqual(result["courseId"], "course_1")
        self.assertEqual(result["enrollmentId"], "enr_1")
        self.assertEqual(result["error"]["code"], "PROVIDER_UNAVAILABLE")
        self.assertEqual([call["method"] for call in out["calls"]], ["course.create", "enrollment.create", "jobs.create"])

    def test_a_failed_course_create_stops_before_enrolling(self) -> None:
        out = self.run_case({"kind": "fail", "fail": "course.create"})
        self.assertEqual([call["method"] for call in out["calls"]], ["course.create"])

    def test_a_failed_enrollment_does_not_queue_a_job(self) -> None:
        out = self.run_case({"kind": "fail", "fail": "enrollment.create"})
        self.assertEqual([call["method"] for call in out["calls"]], ["course.create", "enrollment.create"])
        self.assertEqual(out["result"]["stage"], "enrollment.create")
        self.assertEqual(out["result"]["courseId"], "course_1")

    # ── payload shape ───────────────────────────────────────────────────────
    def test_absent_optional_inputs_are_omitted_not_emptied(self) -> None:
        out = self.run_case({"kind": "brief"})
        self.assertEqual(
            set(out["brief"]),
            {"stage", "course_id", "enrollment_id", "goal", "recipe", "dials"},
        )
        self.assertEqual(set(out["course"]), {"title", "recipe", "goal", "dials", "presentation_mode"})
        # GM-004: the create flow always states its mode. Game is the intent the chooser shows
        # preselected, so an unset choice is recorded as `game`, not sent as an empty null.
        self.assertEqual(out["course"]["presentation_mode"], "game")

    def test_the_closed_brief_has_no_field_outside_the_contract(self) -> None:
        allowed = {
            "goal", "brief", "title", "recipe", "dials", "locale", "level", "subject_domain",
            "scope", "course_id", "enrollment_id", "plan_id", "stage",
        }
        out = self.run_case({"kind": "brief", "optional": {"locale": "ja-JP", "level": "L0",
                                                           "subjectDomain": "language", "scope": "short"}})
        self.assertLessEqual(set(out["brief"]), allowed)

    def test_scope_options_are_the_contract_enum(self) -> None:
        out = self.run_case({"kind": "copy"})
        contract = json.loads((ROOT / "contracts" / "rpc.v10.json").read_text(encoding="utf-8"))
        scope = contract["$defs"]["methods"]["properties"]["course.create"]["request"]["properties"]["scope"]
        self.assertEqual(
            [item["id"] for item in out["scopes"]],
            [value for value in scope["enum"] if value is not None],
        )

    def test_the_time_expectation_invents_no_minutes(self) -> None:
        out = self.run_case({"kind": "copy"})
        for scope, copy in out["copy"].items():
            self.assertNotRegex(copy, r"\d+\s*(min|minute|hour)", scope)
            self.assertIn("several minutes", copy.lower(), scope)
        self.assertNotRegex(out["fallback"], r"\d+\s*(min|minute|hour)")

    # ── H-170: goal → size → review ─────────────────────────────────────────
    def test_a_fresh_form_opens_on_the_goal_step(self) -> None:
        out = self.run_case({"kind": "step"})
        self.assertEqual(out["fresh"], 1)

    def test_a_seed_opens_on_the_first_step_still_missing_an_answer(self) -> None:
        out = self.run_case({"kind": "step"})
        # A blanked goal is still a missing goal, even if a scope survived.
        self.assertEqual(out["emptyGoal"], 1)
        self.assertEqual(out["goalOnly"], 2)
        # Both answers present: Review, where Create is still a press.
        self.assertEqual(out["goalAndScope"], 3)

    def test_the_title_is_suggested_from_the_goal_and_needs_no_invention(self) -> None:
        out = self.run_case({"kind": "step"})
        titles = out["titles"]
        self.assertEqual(titles["empty"], "")
        self.assertEqual(titles["plain"], "Hold a six-minute conversation in Spanish")
        self.assertEqual(titles["firstSentence"], "Order coffee in Kyoto")
        self.assertEqual(titles["whitespace"], "Wire a lamp safely")
        self.assertLessEqual(len(titles["long"]), 64)
        self.assertTrue(titles["long"].endswith("…"))

    # ── H-168: the depth default mirrors the research floor ─────────────────
    def test_the_depth_floor_matches_the_backend_by_scope(self) -> None:
        out = self.run_case({"kind": "depth"})
        self.assertEqual(out["floor"], {"single": "working", "short": "working", "full": "deep"})
        by_case = {(row["scope"], row["depth"]): row["effective"] for row in out["cases"]}
        self.assertEqual(by_case[("single", "survey")], "working")
        self.assertEqual(by_case[("short", "survey")], "working")
        self.assertEqual(by_case[("full", "survey")], "deep")
        self.assertEqual(by_case[("full", "working")], "deep")
        # A deeper pick is never lowered, and a missing depth is raised to the floor.
        self.assertEqual(by_case[("single", "deep")], "deep")
        self.assertEqual(by_case[("full", "deep")], "deep")
        self.assertEqual(by_case[("short", None)], "working")

    def test_submit_sends_the_four_dials_at_no_less_than_the_floor(self) -> None:
        source = _source()
        start = source.index("function CreateCourseFlow")
        submit_at = source.index("const outcome = await startLearnerPlan({", start)
        block = source[submit_at : start + 8000]
        self.assertIn("dials: { ...dials, depth: effectiveDepth(dials.depth, scope) }", block)
        # The payload keeps the closed four-dial object: no key is dropped or renamed here.
        for key in ("pace", "depth", "assessment", "autonomy"):
            self.assertIn(f"{key}:", source[source.index("const DIALS = {"):source.index("const DIALS = {") + 900])

    # ── H-179: the shape chooser ────────────────────────────────────────────
    def test_the_section_band_is_the_backend_scope_table(self) -> None:
        """A card's number is the backend's own band, not a UI guess."""
        out = self.run_case({"kind": "copy"})
        generation = (ROOT / "coursebook" / "generation.py").read_text(encoding="utf-8")
        block = generation[generation.index("SCOPE_EXPECTATIONS"):]
        block = block[: block.index("\n}\n")]
        expected = {}
        for scope in ("single", "short", "full"):
            body = block[block.index(f'"{scope}":'):]
            body = body[: body.index('"note"')]
            band = re.search(r'"blueprint_objectives":\s*\((\d+),\s*(\d+)\)', body)
            self.assertIsNotNone(band, scope)
            expected[scope] = [int(band.group(1)), int(band.group(2))]
        self.assertEqual({row["id"]: row["sections"] for row in out["scopes"]}, expected)
        # The words match the numbers: one section, a band, a band.
        self.assertEqual(out["bands"]["single"], "1 section")
        self.assertEqual(out["bands"]["short"], f"{expected['short'][0]}–{expected['short'][1]} sections")
        self.assertEqual(out["bands"]["full"], f"{expected['full'][0]}–{expected['full'][1]} sections")

    def test_each_shape_states_its_sections_and_research_floor(self) -> None:
        out = self.run_case({"kind": "copy"})
        for scope in ("single", "short", "full"):
            facts = out["facts"][scope]
            self.assertIn(out["bands"][scope], facts)
            self.assertIn("research depth", facts)
            self.assertIn("several minutes", facts.lower())
            # No invented minute count anywhere on a card.
            self.assertNotRegex(facts, r"\d+\s*(min|minute|hour)")

    def test_the_trail_preview_stays_a_schematic(self) -> None:
        out = self.run_case({"kind": "copy"})
        self.assertEqual(out["trails"], {"single": 1, "short": 3, "full": 6})
        # The dot count never claims more than the band's floor, and only open bands get a tail.
        for row in out["scopes"]:
            self.assertLessEqual(row["trail"], row["sections"][1], row["id"])
            self.assertEqual(row["trail"] > 1, row["sections"][1] > row["sections"][0], row["id"])

    def test_the_use_choice_is_four_plain_options_and_no_parent(self) -> None:
        out = self.run_case({"kind": "copy"})
        ids = [option["id"] for option in out["uses"]]
        self.assertEqual(ids, ["one_off", "casual", "committed", "companion"])
        self.assertNotIn("parent", ids)
        for option in out["uses"]:
            self.assertNotIn(option["id"], option["label"])
            self.assertLessEqual(len(option["label"]), 18, option["label"])

    def test_the_flow_keeps_exactly_one_primary(self) -> None:
        # Rendered markup, not a source count: step 2 (the shape) and step 3 (the trailhead) each
        # paint exactly one filled action, and Cancel is a tertiary control in the same row.
        for step in (2, 3):
            html = self.run_case({"kind": "render", "step": step})["html"]
            self.assertEqual(html.count('data-cb-action="primary"'), 1, f"step {step}")
            self.assertIn('data-cb-action="tertiary"', html, f"step {step}")
            self.assertIn("Cancel", html, f"step {step}")

    def test_the_review_step_is_a_trailhead_not_a_status_wall(self) -> None:
        source = _source()
        step3 = source[source.index("      step === 3\n"):source.index("      jsxs('div', {\n        className: 'flex flex-wrap items-center gap-2 border-t")]
        self.assertNotIn("StatusRow", step3)
        self.assertIn("'data-cb-create-preview': ''", step3)
        self.assertIn("THE TRAILHEAD", step3)
        self.assertIn("First stop", step3)
        self.assertIn("data-cb-create-facts", source)
        self.assertIn("no lesson is written until you do", step3)
        # The name that will be created is the preview's title.
        self.assertIn("children: displayTitle", step3)
        # And the render says the same thing a learner reads.
        html = self.run_case({"kind": "render", "step": 3})["html"]
        self.assertIn("THE TRAILHEAD", html)
        self.assertIn("Coffee in Kyoto", html)
        self.assertIn("Short course", html)
        self.assertIn("First stop", html)
        self.assertIn("no lesson is written until you do", html)
        self.assertIn("Create course", html)
        self.assertIn("data-cb-create-preview-shape", html)

    def test_the_name_is_optional_and_never_blocks_continue(self) -> None:
        source = _source()
        self.assertIn("children: 'Name (optional)'", source)
        self.assertIn("'data-cb-title-disclosure': ''", source)
        self.assertIn("const canAdvance = step === 1 ? goal.trim().length > 0 : Boolean(scope)", source)
        # An empty name still sends a title the contract accepts: the suggestion, never invention.
        self.assertIn("title: title.trim() || suggestedTitle(goal),", source)

    def test_the_shape_step_offers_no_learner_parent_path(self) -> None:
        source = _source()
        block = source[source.index("function CreateCourseFlow"):source.index("// ══ H-27")]
        self.assertNotIn("RECIPES.filter", block)
        self.assertNotIn("Preparing lessons for a child", block)
        self.assertNotIn("What kind of course is this?", block)


class CreateFlowWiringTest(unittest.TestCase):
    """Source-level gates that a Node stub cannot see (which surface renders what)."""

    def test_the_dead_end_copy_is_gone(self) -> None:
        source = _source()
        self.assertNotIn("generation is not wired in this build", source)
        self.assertNotIn("plan generation is not part of this build", source)

    def test_the_flow_uses_the_one_orchestrator(self) -> None:
        source = _source()
        start = source[source.index("function CreateCourseFlow"):source.index("// ══ H-27")]
        self.assertIn("startLearnerPlan({", start)
        self.assertNotIn("'course.create',\n      {", start)

    def test_the_plan_tab_renders_the_learner_review_surface(self) -> None:
        source = _source()
        plan_view = source[source.index("} else if (view === 'plan') {"):]
        plan_view = plan_view[: plan_view.index("} else if (view === 'evidence')")]
        self.assertIn("jsx(LearnerPlanView", plan_view)
        self.assertIn("onStartLesson", plan_view)

    def test_the_learner_surface_hides_parent_only_authoring(self) -> None:
        source = _source()
        self.assertIn("const learner = surface === 'learner'", source)
        self.assertRegex(source, r"(?s)isDraft && !editing && !learner\s*\?.*?children: 'Edit plan'")
        self.assertRegex(source, r"(?s)!isDraft && !editing && !learner\s*\?.*?children: 'Start a new plan version'")

    def test_the_learner_surface_approves_with_the_kernel_digest(self) -> None:
        """`course.outline` echoes the generation digest; approval must send the recomputed one."""
        source = _source()
        approve = source[source.index("const approvePlan = useCallback"):]
        approve = approve[: approve.index("const generateLessons")]
        self.assertIn("const fresh = await rpc('parent.blueprint.read'", approve)
        self.assertIn("plan_hash: hash", approve)
        learner = source[source.index("function LearnerPlanView"):source.index("function StudioBlueprintView")]
        self.assertIn("jsx(StudioPlanView", learner)
        self.assertIn("surface: 'learner'", learner)

    def test_the_lessons_job_is_keyed_by_plan_version(self) -> None:
        source = _source()
        self.assertIn("idempotencyKey: `cb-lessons-${plan.plan_id}`", source)

    def test_no_fake_percentage_on_the_job_surface(self) -> None:
        source = _source()
        job_line = source[source.index("function JobStateText"):source.index("function useStudioJob")]
        self.assertNotIn("%", job_line)
        self.assertNotIn("percent", job_line.lower())

    def test_the_job_line_cancels_and_reports_a_typed_failure(self) -> None:
        source = _source()
        job_line = source[source.index("function StudioJobLine"):source.index("function StudioList")]
        self.assertIn("rpc('jobs.cancel', { job_id: jobId })", job_line)
        self.assertIn("if (!response.ok) setError(response.error)", job_line)
        self.assertIn("describeError(error)", job_line)
        # Failure reasons come from the job's own error object, never a made-up sentence.
        self.assertIn("job.error", source)
        self.assertIn("error.message", job_line + source[source.index("function JobStateText"):source.index("function useStudioJob")])


    def test_the_empty_plan_job_line_uses_the_settled_handler(self) -> None:
        """A bare `onSettled` here threw ReferenceError and replaced the route (H-95/H-143)."""
        source = _source()
        plan_view = source[source.index("function StudioPlanView"):source.index("function StudioBlueprintView")]
        self.assertNotIn("onSettled, onRunAgain", plan_view)
        self.assertIn("onSettled: onJobSettled", plan_view)


# The shared stub renders `Input`/`Textarea` as null, which is right for markup tests but hides the
# one field these cases read back. The create form's own fields become real elements here so the
# prefilled goal is read from the DOM rather than from a prop.
FORM_SDK_STUB = SDK_STUB.replace(
    "export const Input = () => null",
    "export const Input = (props) => el('input', { ...props })",
).replace(
    "export const Textarea = () => null",
    "export const Textarea = (props) => el('textarea', { ...props })",
)
assert FORM_SDK_STUB != SDK_STUB, "the shared SDK stub changed shape; update the form stub"

#: CREATE-2/CREATE-5: the form is mounted in jsdom and pressed the way a learner presses it. The
#: transport is a recording `ctx.rest`, so the payloads come from the shipped component, not from a
#: copy of its logic.
FORM_HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.MouseEvent = dom.window.MouseEvent
globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.__CB_TEST_WIDTH__ = '1049'
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

const calls = []
const responses = payload.responses || {}
const generic = { items: [], entries: [], objectives: [], jobs: [], total: 0 }
const fakeRest = async (path, options) => {
  const body = (options && options.body) || {}
  const base = String(path).split('?')[0]
  if (base === '/rpc') {
    calls.push({ method: body.method, payload: body.payload || {}, key: body.idempotency_key || null })
    const result = Object.prototype.hasOwnProperty.call(responses, body.method) ? responses[body.method] : generic
    return { ok: true, contract_version: 26, operation_id: 'test-operation', result }
  }
  if (base === '/runtime') {
    return {
      wire_version: 26,
      contract_version: 26,
      implemented_methods: payload.implemented || [],
      single_home_host: false
    }
  }
  if (base === '/health') {
    return { ok: true, contract_version: 26, result: { db: { ready: true }, plugin_version: 'test', contract_version: 26 } }
  }
  return { ok: true, result: {} }
}

mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => {
    const handle = window.setTimeout(fn, ms)
    return () => window.clearTimeout(handle)
  },
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))

const flush = async (ms = 40) => {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) })
}
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const byText = (selector, wanted) =>
  [...document.querySelectorAll(selector)].find((node) => text(node) === wanted) || null
const levelState = () =>
  [...document.querySelectorAll('[data-cb-level-option]')].map((node) => ({
    id: node.getAttribute('data-cb-level-option'),
    token: node.getAttribute('data-cb-level-token'),
    pressed: node.getAttribute('aria-pressed'),
    selected: node.getAttribute('data-cb-level-selected'),
    label: text(node)
  }))
const press = async (node, what) => {
  if (!node) throw new Error(`nothing to press: ${what}`)
  await act(async () => {
    node.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }))
  })
  await flush(25)
}
// React tracks a field's own value; writing through the prototype setter and firing `input` is
// how a person's keystroke reaches a controlled field in this DOM.
const type = async (node, value) => {
  if (!node) throw new Error('nothing to type into')
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(node), 'value').set
  await act(async () => {
    setter.call(node, value)
    node.dispatchEvent(new window.Event('input', { bubbles: true }))
  })
  await flush(15)
}
const stepMarker = () => {
  const found = [...document.querySelectorAll('div')].find((node) => /^Step [123] of 3$/.test(text(node)))
  return found ? text(found) : null
}
const levelField = () => document.querySelector('[data-cb-create-level]')

await act(async () => {
  root.render(React.createElement(mod.CreateCourseFlow, {
    seed: payload.kind === 'choices' ? null : payload.seed || null,
    onCancel: () => {},
    onCreated: () => {}
  }))
})
await flush(80)

if (payload.kind === 'choices') {
  const output = {
    step: stepMarker(),
    freeTextLevel: Boolean(document.querySelector('#cb-level')),
    levels: levelState(),
    help: text(document.querySelector('#cb-level-help')),
    groupLabel: text(document.querySelector('#cb-level-label'))
  }
  process.stdout.write(JSON.stringify(output))
} else {
  await type(document.querySelector('#cb-goal'), payload.goal)
  await press(
    [...document.querySelectorAll('[data-cb-level-option]')].find(
      (node) => node.getAttribute('data-cb-level-option') === (payload.pick || 'none')
    ),
    'a level choice'
  )
  const afterPick = levelState()
  await press(byText('button', 'Continue'), 'Continue from the goal step')
  await press(document.querySelector('[data-cb-scope-option="short"]'), 'the short shape')
  await press(byText('button', 'Continue'), 'Continue from the shape step')
  const previewNode = document.querySelector('[data-cb-create-preview-level]')
  const previewLevel = previewNode ? text(previewNode) : null
  const stepAtReview = stepMarker()
  await press(byText('button', 'Create course'), 'Create course')
  await flush(200)

  const course = calls.find((call) => call.method === 'course.create')
  const job = calls.find((call) => call.method === 'jobs.create')
  const rejectNode = document.querySelector('[data-cb-plan-reject]')
  const changeGoal = byText('button', 'Change the goal')
  const before = {
    reject: rejectNode ? rejectNode.getAttribute('data-cb-plan-reject') : null,
    rejectAction: rejectNode ? rejectNode.getAttribute('data-cb-plan-reject-action') : null,
    changeGoalOffered: Boolean(changeGoal),
    scolds: document.body.textContent.includes('not reachable from this surface')
  }

  let after = null
  if (changeGoal && payload.followChangeGoal !== false) {
    await press(changeGoal, 'Change the goal')
    await flush(80)
    const goalField = document.querySelector('#cb-goal')
    after = {
      step: stepMarker(),
      heading: text(document.querySelector('h2')),
      goal: goalField ? goalField.value : null,
      level: levelField() ? levelField().getAttribute('data-cb-create-level') : null,
      levels: levelState(),
      scolds: document.body.textContent.includes('not reachable from this surface'),
      stillHasResult: Boolean(document.querySelector('[data-cb-create-receipt]'))
    }
  }

  process.stdout.write(JSON.stringify({
    afterPick,
    previewLevel,
    stepAtReview,
    coursePayload: course ? course.payload : null,
    brief: job && job.payload && job.payload.brief ? job.payload.brief : null,
    before,
    after
  }))
}
"""

GOAL = "Replace the head gasket on a 1998 Civic without stripping the block"


def _rejected_plan() -> dict:
    return {
        "plan_id": "plan_draft_1",
        "version": 1,
        "state": "draft",
        "validation": {
            "approvable": False,
            "source": None,
            "verdict": "reject",
            "outcome": "rejected",
            "independence": "same_model",
            "facts_unverified": False,
            "reasons": ["plan: no objectives were authored"],
            "reason": None,
            "detail": None,
            "manual_authoring": False,
        },
    }


def _rejected_job() -> dict:
    return {
        "job_id": "job_plan_1",
        "kind": "plan",
        "state": "completed",
        "brief": {
            "stage": "plan",
            "course_id": "course_1",
            "enrollment_id": "enr_1",
            "goal": GOAL,
            "recipe": "casual",
            "dials": {"pace": "light", "depth": "working", "assessment": "self_check", "autonomy": "guided"},
            "level": "none",
            "subject_domain": "auto repair",
            "scope": "short",
        },
        "checkpoint": {
            "plan_id": "plan_draft_1",
            "objectives": 0,
            "rejection_reasons": ["plan: no objectives were authored"],
            "validation_verdict": "reject",
            "validation": {"outcome": "rejected", "independence": "same_model", "research_status": "available"},
        },
        "error": None,
    }


class CreateFormInteractionTest(unittest.TestCase):
    """CREATE-2/CREATE-5: the shipped form, pressed in jsdom, against a recording transport."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to run the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-create-form-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(FORM_HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(FORM_SDK_STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_case(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return json.loads(result.stdout)

    def submit(self, pick: str, **payload) -> dict:
        responses = {
            "course.create": {"course_id": "course_1", "plan_id": "plan_draft_1", "revision": 0},
            "enrollment.create": {"enrollment_id": "enr_1", "revision": 0},
            "jobs.create": {"job_id": "job_plan_1", "state": "queued"},
            "jobs.get": {"job": _rejected_job()},
            "jobs.list": {"jobs": [_rejected_job()]},
            "course.outline": {"plan": _rejected_plan(), "objectives": []},
            "parent.blueprint.read": {"plan": _rejected_plan(), "tabs": {}, "sources": []},
        }
        return self.run_case(
            {
                "kind": "submit",
                "pick": pick,
                "goal": GOAL,
                "implemented": [
                    "course.create", "enrollment.create", "jobs.create", "jobs.get",
                    "jobs.list", "course.outline", "parent.blueprint.read",
                ],
                "responses": responses,
                **payload,
            }
        )

    # ── CREATE-2: the level is a question ──────────────────────────────────
    def test_the_level_is_three_one_tap_choices_and_no_free_text(self) -> None:
        out = self.run_case({"kind": "choices"})
        self.assertEqual(out["step"], "Step 1 of 3")
        self.assertFalse(out["freeTextLevel"], "the free-text level box must be gone")
        self.assertEqual([row["id"] for row in out["levels"]], ["none", "some", "confident"])
        self.assertEqual([row["token"] for row in out["levels"]], ["none", "some", "confident"])
        for row, label in zip(out["levels"], ("None", "Some", "Confident")):
            self.assertTrue(row["label"].startswith(label), row["label"])
        # Nothing is preselected: an unanswered level is a real answer.
        self.assertTrue(all(row["pressed"] == "false" for row in out["levels"]))
        self.assertIn("Where are you starting from?", out["groupLabel"])

    def test_one_tap_none_is_the_token_the_generation_rule_reads(self) -> None:
        """The token that reaches the plan is the rule's own vocabulary, proven in Python."""
        out = self.submit("none")
        self.assertEqual([row["id"] for row in out["afterPick"] if row["pressed"] == "true"], ["none"])
        brief = out["brief"]
        self.assertIsNotNone(brief)
        self.assertEqual(out["stepAtReview"], "Step 3 of 3")
        self.assertEqual(out["coursePayload"]["level"], "none")
        self.assertEqual(brief["level"], "none")
        # The level is the one the deterministic beginner rule accepts, and it is the same value
        # the course row stores for the same decision.
        from coursebook import generation

        self.assertTrue(generation.is_beginner_level(brief["level"]))
        self.assertIn("Starting from: None", out["previewLevel"])

    def test_one_tap_some_is_recorded_and_is_not_a_beginner_claim(self) -> None:
        out = self.submit("some")
        brief = out["brief"]
        self.assertEqual(brief["level"], "some")
        from coursebook import generation

        self.assertFalse(generation.is_beginner_level(brief["level"]))
        self.assertIn("Starting from: Some", out["previewLevel"])

    # ── CREATE-5: change the goal really returns to the form ───────────────
    def test_change_the_goal_returns_to_the_prefilled_form(self) -> None:
        out = self.submit("none")
        before = out["before"]
        self.assertEqual(before["reject"], "empty")
        self.assertEqual(before["rejectAction"], "change_goal")
        self.assertTrue(before["changeGoalOffered"], "the empty-plan refusal must offer a real control")
        self.assertFalse(before["scolds"])
        after = out["after"]
        self.assertIsNotNone(after)
        self.assertEqual(after["step"], "Step 1 of 3")
        self.assertEqual(after["heading"], "What do you want to be able to do?")
        # The brief the plan actually ran is prefilled, including the level and the subject.
        self.assertEqual(after["goal"], GOAL)
        self.assertEqual(after["level"], "none")
        self.assertEqual([row["id"] for row in after["levels"] if row["pressed"] == "true"], ["none"])
        self.assertFalse(after["scolds"])
        self.assertFalse(after["stillHasResult"], "the result screen is gone, not stacked under the form")


if __name__ == "__main__":
    unittest.main()
