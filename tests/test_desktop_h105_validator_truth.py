"""H-105: plan review shows who checked the plan, and never claims more.

The validator records `model_assessed` when it ran on the author model, and `independent` only when
a host-configured second model actually ran. Plan review must show that record as one plain line:
"Checked by the same model" vs "Checked by a second model". The technical provenance
(`outcome`/`independence` enums, both model identities, the backend warning) belongs in the
disclosure, and the copy "independently validated" is reserved for a genuinely independent pass.

The shipped model and the shipped component are imported with React and rendered, so the copy,
the disclosure and the data attributes are asserted where they are written. A small source test
proves the wiring the model cannot express (a revisit reads the finished job's checkpoint; the
learner surface passes the hint through).

What this does NOT prove: that a real provider reports two distinct model identities. That is
`tests/test_validator_independence.py` (backend, scripted fakes) and the live plan probe.
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
const { planValidationView, PlanValidationLine, PLAN_VALIDATION_LINES } = await import('./plugin.js')

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const model = planValidationView({
  job: payload.job || null,
  jobHint: payload.jobHint || null,
  plan: payload.plan || null,
  reading: Boolean(payload.reading),
  learner: Boolean(payload.learner)
})

let output = { model, lines: PLAN_VALIDATION_LINES }
if (payload.kind === 'render') {
  output.html = renderToStaticMarkup(
    React.createElement(PlanValidationLine, {
      job: payload.job || null,
      jobHint: payload.jobHint || null,
      plan: payload.plan || null,
      reading: Boolean(payload.reading),
      learner: Boolean(payload.learner)
    })
  )
}
process.stdout.write(JSON.stringify(output))
"""


def plan_job(validation: dict | None, *, plan_id: str = "plan_1", verdict: str = "pass", state: str = "completed"):
    checkpoint = {
        "plan_id": plan_id,
        "generation_state": "draft",
        "objectives": 4,
        "validation_verdict": verdict,
        "validation": validation,
    }
    return {
        "job_id": "job_plan_1",
        "kind": "plan",
        "state": state,
        "brief": {"stage": "plan", "goal": "Hold a six-minute conversation in Spanish", "scope": "short"},
        "checkpoint": checkpoint,
        "error": None,
    }


def same_model_validation():
    """The empty `validator_model` config: validation ran on the author model."""
    return {
        "outcome": "model_assessed",
        "verdict": "pass",
        "independence": "same_model",
        "independent": False,
        "generator": {"provider": "nous", "model": "deepseek-v4.1", "known": True},
        "validator": {"provider": "nous", "model": "deepseek-v4.1", "known": True},
        "facts_unverified": False,
        "warning": (
            "model assessed, not independent: the validator ran on the same model that wrote the "
            "artifact. Treat the pass as a second prompt, not a second opinion."
        ),
    }


def second_model_validation(**overrides):
    validation = {
        "outcome": "independently_validated",
        "verdict": "pass",
        "independence": "independent",
        "independent": True,
        "generator": {"provider": "nous", "model": "deepseek-v4.1", "known": True},
        "validator": {"provider": "anthropic", "model": "claude-sonnet-4", "known": True},
        "facts_unverified": False,
        "warning": None,
    }
    validation.update(overrides)
    return validation


class PlanValidationModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to run the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h105-")
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

    # ── the three provenance outcomes the card names ─────────────────────────

    def test_empty_validator_config_is_the_same_model_not_independence(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(same_model_validation()),
            }
        )
        self.assertEqual(out["model"]["state"], "same_model")
        self.assertEqual(out["model"]["line"], "Checked by the same model")
        self.assertIn("Checked by the same model", out["html"])
        self.assertNotIn("independently validated", out["html"].lower())
        self.assertNotIn("second model", out["html"].lower())

    def test_the_identity_is_shown_when_the_runtime_reported_it(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(same_model_validation()),
            }
        )
        self.assertEqual(out["model"]["validatorModel"], "nous/deepseek-v4.1")
        self.assertIn("Checking model: nous/deepseek-v4.1", out["html"])

    def test_unidentified_identity_is_never_upgraded(self) -> None:
        validation = same_model_validation()
        validation["independence"] = "unidentified"
        validation["validator"] = {"provider": "nous", "model": None, "known": False}
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(validation),
            }
        )
        self.assertEqual(out["model"]["state"], "unidentified")
        self.assertEqual(out["model"]["line"], "Checked by a model that could not be identified")
        self.assertIsNone(out["model"]["validatorModel"])
        self.assertIn("The runtime did not report the checking model.", out["html"])

    def test_a_cross_model_pass_names_the_second_model(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(second_model_validation()),
            }
        )
        self.assertEqual(out["model"]["state"], "independent")
        self.assertEqual(out["model"]["line"], "Checked by a second model")
        self.assertIn("Checked by a second model", out["html"])
        self.assertIn("anthropic/claude-sonnet-4", out["html"])

    def test_a_second_model_with_unchecked_facts_is_not_factual_verification(self) -> None:
        validation = second_model_validation(
            outcome="model_assessed",
            facts_unverified=True,
            warning="facts unverified, no sources: research was unavailable.",
        )
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(validation),
            }
        )
        self.assertEqual(out["model"]["state"], "independent")
        self.assertTrue(out["model"]["factsUnverified"])
        self.assertIn("not factual verification", out["html"])
        self.assertNotIn("independently validated", out["html"].lower())

    # ── no record, no claim ──────────────────────────────────────────────────

    def test_a_plan_with_no_record_claims_nothing(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "approved"},
                "job": None,
            }
        )
        self.assertEqual(out["model"]["state"], "unrecorded")
        self.assertIn("No validator record is stored for this version", out["html"])
        self.assertNotIn("Checked by a second model", out["html"])
        self.assertNotIn("Checked by the same model", out["html"])

    def test_a_pending_read_shows_nothing_rather_than_no_record(self) -> None:
        out = self.run_case(
            {
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": None,
                "reading": True,
            }
        )
        self.assertIsNone(out["model"])

    def test_a_record_bound_to_another_version_is_not_borrowed(self) -> None:
        carried = plan_job(second_model_validation(), plan_id="plan_old")
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_new", "version": 2, "state": "draft"},
                "job": carried,
            }
        )
        self.assertEqual(out["model"]["state"], "unrecorded")
        self.assertIn("earlier version", out["html"])
        self.assertNotIn("Checked by a second model", out["html"])

    def test_the_finished_job_hint_reaches_a_revisit(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "approved"},
                "job": None,
                "jobHint": plan_job(same_model_validation(), state="completed"),
            }
        )
        self.assertEqual(out["model"]["state"], "same_model")
        self.assertIn("Checked by the same model", out["html"])

    # ── technical provenance stays in the disclosure ────────────────────────

    def test_the_raw_record_stays_behind_a_disclosure(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(same_model_validation()),
                "learner": False,
            }
        )
        html = out["html"]
        self.assertIn("<details", html)
        self.assertIn("Technical detail", html)
        self.assertIn("Writing model: nous/deepseek-v4.1.", html)
        self.assertIn("docs/GENERATION.md", html)
        self.assertIn("docs/HARNESS-STATUS.md", html)
        # The visible statement is one line; the enum tokens never appear as user copy. They remain
        # as data attributes for the tests and for a developer inspecting the DOM.
        visible = " ".join([out["model"]["line"]] + list(out["model"]["detail"]))
        self.assertNotIn("model_assessed", visible)
        self.assertNotIn("same_model", visible)
        for token in ("model_assessed", "independence", "independently_validated"):
            self.assertNotIn(token, out["model"]["line"])

    def test_a_learner_surface_does_not_show_a_repository_path(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(same_model_validation()),
                "learner": True,
            }
        )
        self.assertIn("Checked by the same model", out["html"])
        self.assertNotIn("docs/GENERATION.md", out["html"])

    # ── H-167: every recorded state has one exact line, and same-model has no fresh-eyes copy ──

    def test_each_recorded_state_maps_to_its_exact_line(self) -> None:
        out = self.run_case({"kind": "render", "plan": None, "job": None})
        self.assertEqual(
            out["lines"],
            {
                "independent": "Checked by a second model",
                "same_model": "Checked by the same model",
                "unidentified": "Checked by a model that could not be identified",
                "unrecorded": "No validator record is stored for this version",
            },
        )

    def test_a_missing_record_maps_to_the_unrecorded_line(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "approved"},
                "job": None,
            }
        )
        self.assertEqual(out["model"]["line"], "No validator record is stored for this version")
        self.assertFalse(out["model"]["configure"])

    def test_same_model_review_names_the_setting_that_would_change_it(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(same_model_validation()),
            }
        )
        self.assertEqual(out["model"]["line"], "Checked by the same model")
        self.assertTrue(out["model"]["configure"])
        html = out["html"]
        self.assertIn("plugins.entries.coursebook.settings.validator_model", html)
        self.assertIn("validator_provider", html)
        self.assertIn("plugins.entries.coursebook.llm.allow_model_override", html)
        self.assertIn("allow_provider_override", html)
        self.assertIn("coursebook_status", html)
        for banned in ("fresh eyes", "subagent", "independently validated", "second model"):
            self.assertNotIn(banned, html.lower())

    def test_an_unidentified_pass_also_names_the_setting(self) -> None:
        validation = same_model_validation()
        validation["independence"] = "unidentified"
        validation["validator"] = {"provider": "nous", "model": None, "known": False}
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(validation),
            }
        )
        self.assertTrue(out["model"]["configure"])
        self.assertIn("plugins.entries.coursebook.settings.validator_model", out["html"])

    def test_an_independent_pass_has_no_configure_hint(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(second_model_validation()),
            }
        )
        self.assertFalse(out["model"]["configure"])
        self.assertNotIn("coursebook_status", out["html"])
        self.assertNotIn("validator_model", out["html"])

    def test_a_learner_surface_never_shows_the_host_setting(self) -> None:
        out = self.run_case(
            {
                "kind": "render",
                "plan": {"plan_id": "plan_1", "version": 1, "state": "draft"},
                "job": plan_job(same_model_validation()),
                "learner": True,
            }
        )
        self.assertIn("Checked by the same model", out["html"])
        self.assertFalse(out["model"]["configure"])
        self.assertNotIn("validator_model", out["html"])
        self.assertNotIn("allow_model_override", out["html"])


class PlanValidationWiringTest(unittest.TestCase):
    """The model cannot prove where the record is read; the shipped render path can."""

    def test_plan_review_renders_the_line(self) -> None:
        source = _source()
        self.assertIn("jsx(PlanValidationLine, {", source)
        block = source[source.index("jsx(PlanValidationLine, {"):]
        self.assertIn("job: planRun", block[:600])
        self.assertIn("jobHint: planJobHint", block[:600])

    def test_the_learner_surface_passes_the_finished_job_hint(self) -> None:
        source = _source()
        learner = source[source.index("function LearnerPlanView"):]
        self.assertIn("planJobHint: planJob", learner[:9000])

    def test_the_hint_is_declared_where_the_view_is_defined(self) -> None:
        source = _source()
        view = source[source.index("function StudioPlanView"):source.index("function StudioPlanView") + 600]
        self.assertIn("planJobHint", view)

    def test_the_plan_validation_line_is_exported(self) -> None:
        source = _source()
        exports = source[source.index("export {"):source.index("export default {")]
        self.assertIn("planValidationView", exports)
        self.assertIn("PlanValidationLine", exports)
        self.assertIn("PLAN_VALIDATION_LINES", exports)

    def test_the_copy_never_says_independently_validated_for_a_same_model_pass(self) -> None:
        source = _source()
        copy = source[source.index("const PLAN_VALIDATION_LINES"):source.index("})", source.index("const PLAN_VALIDATION_LINES"))]
        self.assertNotIn("validated", copy)
        self.assertIn("Checked by the same model", copy)


if __name__ == "__main__":
    unittest.main()
