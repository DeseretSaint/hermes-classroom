"""H-103: a rejected plan is explained, and has exactly one repair action.

The runtime plugin is one uncompiled ESM file. These tests import the shipped model and render the
shipped panel with React, so the copy, the action choice and the disclosure are asserted where they
are written. The four required refusals are covered: an empty plan, an unsourced plan, a structural
reject and a provider failure. A source-level section proves the wiring the model cannot express:
approval is withheld, the zero-objective path keeps the draft on screen, and a retry carries a key
derived from the rejected job.

What this does NOT prove: that a live provider rejects a real topic. `tests/test_executor_plan_checkpoint.py`
proves the reasons the backend recorded reach the job checkpoint; the live plan probe remains the
integration gate.
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
const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const { planRejectView, PlanRejectPanel } = await import('./plugin.js')

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const model = planRejectView({
  job: payload.job,
  plan: payload.plan || null,
  objectiveCount: payload.objectiveCount || 0,
  surface: payload.surface || 'learner',
  goal: payload.goal || null,
  title: payload.title || null
})

let output
if (payload.kind === 'render') {
  output = {
    model,
    html: renderToStaticMarkup(
      React.createElement(PlanRejectPanel, {
        model,
        busy: false,
        error: null,
        onAction: () => {}
      })
    )
  }
} else {
  output = { model }
}
process.stdout.write(JSON.stringify(output))
"""


def completed_reject(reasons, *, verdict="reject", outcome="rejected", independence="same_model"):
    return {
        "job_id": "job_plan_rejected",
        "kind": "plan",
        "state": "completed",
        "brief": {
            "stage": "plan",
            "goal": "Order coffee and ask for the bill in Kyoto, politely.",
            "recipe": "casual",
            "dials": {"pace": "steady"},
            "scope": "short"
        },
        "checkpoint": {
            "plan_id": "plan_draft_1",
            "generation_state": "needs_review",
            "objectives": 3,
            "rejection_reasons": reasons,
            "validation_verdict": verdict,
            "validation": {
                "outcome": outcome,
                "independence": independence,
                "research_status": "available"
            }
        },
        "error": None
    }


class PlanRejectModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to run the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-plan-reject-")
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

    # ── the four refusals, each with one named action ───────────────────────

    def test_empty_plan_names_changing_the_goal(self) -> None:
        out = self.run_case(
            {
                "kind": "model",
                "job": completed_reject(["plan: no objectives were authored"]),
                "objectiveCount": 0,
                "plan": {"plan_id": "plan_draft_1", "version": 1, "state": "draft"},
                "surface": "learner",
            }
        )
        model = out["model"]
        self.assertEqual(model["kind"], "empty")
        self.assertEqual(model["action"]["label"], "Change the goal")
        self.assertTrue(model["draftKept"])
        self.assertIn("nothing to approve", model["title"].lower() + " " + model["body"].lower())

    def test_unsourced_plan_names_trying_again(self) -> None:
        out = self.run_case(
            {
                "kind": "model",
                "job": completed_reject(
                    ['objective 2: claims "sourced" support without a ledger source']
                ),
                "objectiveCount": 3,
                "plan": {"plan_id": "plan_draft_1", "version": 1, "state": "draft"},
            }
        )
        model = out["model"]
        self.assertEqual(model["kind"], "unsourced")
        self.assertEqual(model["action"]["label"], "Try again")
        self.assertTrue(model["draftKept"])
        self.assertIn("source", model["body"].lower())

    def test_structural_reject_lets_a_parent_edit_the_plan(self) -> None:
        out = self.run_case(
            {
                "kind": "model",
                "job": completed_reject(["objective ordinals must be contiguous starting at 1"]),
                "objectiveCount": 3,
                "plan": {"plan_id": "plan_draft_1", "version": 1, "state": "draft"},
                "surface": "parent",
            }
        )
        model = out["model"]
        self.assertEqual(model["kind"], "structural")
        self.assertEqual(model["action"]["label"], "Edit the plan")
        self.assertIn("outline", model["title"].lower())

    def test_structural_reject_on_a_learner_surface_names_trying_again(self) -> None:
        """A learner cannot call `parent.plan.edit`, so the action must be one they can take."""
        out = self.run_case(
            {
                "kind": "model",
                "job": completed_reject(["objective ordinals must be contiguous starting at 1"]),
                "objectiveCount": 3,
                "plan": {"plan_id": "plan_draft_1", "version": 1, "state": "draft"},
                "surface": "learner",
            }
        )
        self.assertEqual(out["model"]["kind"], "structural")
        self.assertEqual(out["model"]["action"]["label"], "Try again")

    def test_provider_failure_names_trying_again_and_keeps_the_brief(self) -> None:
        out = self.run_case(
            {
                "kind": "model",
                "job": {
                    "job_id": "job_provider_failed",
                    "kind": "plan",
                    "state": "failed",
                    "brief": {"stage": "plan", "goal": "Hold a six-minute conversation in Spanish"},
                    "checkpoint": {},
                    "error": {"code": "ProviderFailure", "message": "the provider did not answer"},
                },
                "objectiveCount": 0,
            }
        )
        model = out["model"]
        self.assertEqual(model["kind"], "provider")
        self.assertEqual(model["action"]["label"], "Try again")
        self.assertIn("brief is saved", model["body"])
        self.assertFalse(model["draftKept"])

    def test_a_stopped_run_that_already_wrote_a_draft_keeps_it_on_screen(self) -> None:
        out = self.run_case(
            {
                "kind": "model",
                "job": {
                    "job_id": "job_cancelled",
                    "kind": "plan",
                    "state": "cancelled",
                    "brief": {"stage": "plan", "goal": "Take a water sample"},
                    "checkpoint": {},
                    "error": None,
                },
                "objectiveCount": 1,
                "plan": {"plan_id": "plan_draft_2", "version": 2, "state": "draft"},
            }
        )
        model = out["model"]
        self.assertEqual(model["kind"], "cancelled")
        self.assertTrue(model["draftKept"])
        self.assertIn("stays here", model["body"])
        self.assertEqual(model["action"]["label"], "Try again")

    def test_a_usable_draft_has_no_rejection_panel(self) -> None:
        job = completed_reject([])
        job["checkpoint"].update(
            {"validation_verdict": "pass", "validation": {"outcome": "model_assessed"}}
        )
        out = self.run_case({"kind": "model", "job": job, "objectiveCount": 3})
        self.assertIsNone(out["model"])

    # ── visible copy and disclosure ─────────────────────────────────────────

    def test_visible_copy_never_shows_a_bare_contract_enum(self) -> None:
        for payload in (
            {
                "job": completed_reject(["plan: no objectives were authored"]),
                "objectiveCount": 0,
                "plan": {"plan_id": "plan_draft_1", "version": 1, "state": "draft"},
            },
            {
                "job": completed_reject(
                    ["objective 2: claims 'sourced' support without a ledger source"]
                ),
                "objectiveCount": 3,
                "plan": {"plan_id": "plan_draft_1", "version": 1, "state": "draft"},
            },
        ):
            model = self.run_case({"kind": "model", **payload})["model"]
            visible = " ".join([model["title"], model["body"], model["where"]])
            for token in ("reject", "model_assessed", "validation_verdict", "objective_alignment", "needs_review"):
                self.assertNotIn(token, visible, f"{token} leaked into the visible explanation")

    def test_the_raw_check_stays_behind_a_disclosure(self) -> None:
        payload = {
            "kind": "render",
            "job": completed_reject(["objective 2: claims 'sourced' support without a ledger source"]),
            "objectiveCount": 3,
            "plan": {"plan_id": "plan_draft_1", "version": 1, "state": "draft"},
        }
        out = self.run_case(payload)
        html = out["html"]
        self.assertIn("<details", html)
        self.assertIn("Technical detail", html)
        self.assertIn("source", html.lower())
        # The disclosure explains the record; it still does not print the raw enum token.
        self.assertNotIn("objective_alignment", html)

    def test_the_panel_has_exactly_one_action(self) -> None:
        payload = {
            "kind": "render",
            "job": completed_reject(["objective ordinals must be contiguous starting at 1"]),
            "objectiveCount": 3,
            "plan": {"plan_id": "plan_draft_1", "version": 1, "state": "draft"},
            "surface": "parent",
        }
        out = self.run_case(payload)
        html = out["html"]
        self.assertEqual(html.count("<button"), 1, html)
        self.assertIn("Edit the plan", html)
        self.assertIn('data-cb-plan-reject="structural"', html)
        self.assertIn('data-cb-plan-reject-draft="kept"', html)


class PlanRejectWiringTest(unittest.TestCase):
    """The model cannot prove a button is withheld; the shipped render path can."""

    def test_approval_is_withheld_while_a_rejection_is_shown(self) -> None:
        source = _source()
        header = source[source.index("children: shownRejection && !editing"):]
        self.assertIn("Approve plan", header)
        self.assertLess(header.index("children: shownRejection && !editing"), header.index("Approve plan"))

    def test_a_zero_objective_reject_does_not_fall_through_to_the_empty_state(self) -> None:
        source = _source()
        branch = source[source.index("if (!plan || objectives.length === 0) {"):]
        self.assertIn("if (shownRejection) {", branch[:900])
        self.assertIn("data-cb-plan-draft", branch[:1200])
        self.assertIn("A rejected draft is never replaced by a blank", branch[:400])

    def test_retry_uses_a_key_derived_from_the_rejected_job(self) -> None:
        source = _source()
        self.assertIn("`cb-plan-retry-${source.job_id}`", source)
        self.assertIn("retryPlanKey.current = { jobId: response.result.job_id, key: null }", source)

    def test_a_rejection_is_not_auto_navigated_away(self) -> None:
        source = _source()
        panel = source[source.index("function PlanRejectPanel"):source.index("function StudioPlanView")]
        self.assertNotIn("host.navigate", panel)
        self.assertNotIn("openSession", panel)
        self.assertNotIn("setTimeout", panel)

    def test_a_stopped_plan_job_still_reaches_plan_review(self) -> None:
        """Objectives can exist when a run is cancelled or rejected; the job id must still travel."""
        source = _source()
        self.assertIn("const planRunStopped", source)
        self.assertIn("planJob.checkpoint.validation_verdict === 'reject'", source)
        self.assertIn("!JOB_TERMINAL_STATES.has(planJob.state) || planRunStopped", source)

    def test_both_surfaces_pass_the_repair_callback(self) -> None:
        source = _source()
        self.assertGreaterEqual(source.count("onChangeGoal,"), 3)
        self.assertIn("beginCreate(seed || null)", source)
        self.assertIn("seed: createSeed", source)


if __name__ == "__main__":
    unittest.main()
