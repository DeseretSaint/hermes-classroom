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
  courseCreatePayload,
  planJobBrief,
  planTimingCopy,
  startLearnerPlan
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
    fallback: planTimingCopy(null)
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
        self.assertEqual(set(out["course"]), {"title", "recipe", "goal", "dials"})

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


class CreateFlowWiringTest(unittest.TestCase):
    """Source-level gates that a Node stub cannot see (which surface renders what)."""

    def test_the_dead_end_copy_is_gone(self) -> None:
        source = _source()
        self.assertNotIn("generation is not wired in this build", source)
        self.assertNotIn("plan generation is not part of this build", source)

    def test_the_flow_uses_the_one_orchestrator(self) -> None:
        source = _source()
        start = source[source.index("function CreateCourseFlow"):source.index("function CreateCourseFlow") + 6000]
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


if __name__ == "__main__":
    unittest.main()
