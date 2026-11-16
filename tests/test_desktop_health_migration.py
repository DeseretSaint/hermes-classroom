"""H-114 F11 — the pane must never call a *failed* migration "not migrated".

``health.get`` provisions the store on first contact, so its migration can fail for a real reason
(disk I/O, a locked or corrupt store) on a profile that *has* course data. Before the ``cb.rpc``
health amendment that answer was wire-identical to a never-migrated profile, and the Desktop
rendered "The course database is not migrated yet … this profile has no course tables" — a
confident, wrong statement about the user's own data. These tests mount the real shipped
``desktop/plugin.js`` in Node:

* ``healthStatus`` maps the wire block to the pane's state, and a failed store is ``failed``;
* ``MigrationFailedBody`` renders the bounded error, the target schema and one retry;
* the words "not migrated" / "no course tables" do not appear anywhere in that body;
* the unmigrated branch still owns those words, so the fix is a split rather than a deletion;
* a failed startup reconciliation is rendered, not only logged.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from coursebook import contracts
from tests.test_desktop_field_desk import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
WIRE = contracts.WIRE_CONTRACT_VERSION

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { DegradedBody, MigrationFailedBody, ReconciliationNote, healthStatus } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const noop = () => {}
const out = { statuses: {}, bodies: {} }

for (const [name, result] of Object.entries(payload.statuses || {})) {
  out.statuses[name] = healthStatus(result)
}
if (payload.failed) {
  out.bodies.failed = renderToStaticMarkup(
    React.createElement(MigrationFailedBody, { result: payload.failed, reload: noop })
  )
}
if (payload.degraded) {
  out.bodies.degraded = renderToStaticMarkup(
    React.createElement(DegradedBody, { result: payload.degraded, reload: noop })
  )
}
if (payload.reconciliation) {
  out.bodies.reconciliation = renderToStaticMarkup(
    React.createElement(ReconciliationNote, { result: payload.reconciliation })
  )
}
process.stdout.write(JSON.stringify(out))
"""


def failed_health(**overrides) -> dict:
    """A `health.get` result for a store whose migration raised."""
    result = {
        "plugin_version": "0.1.0",
        "contract_version": WIRE,
        "backend": "python",
        "db": {
            "ready": False,
            "schema_version": 9,
            "state": "failed",
            "target_schema_version": 10,
            "error": {
                "type": "OperationalError",
                "message": "disk I/O error",
                "target_schema_version": 10,
            },
        },
        "reconciliation": {"state": "ok", "error": None, "message": None},
    }
    result.update(overrides)
    return result


def unmigrated_health() -> dict:
    return {
        "plugin_version": "0.1.0",
        "contract_version": WIRE,
        "backend": "python",
        "db": {"ready": False, "schema_version": None, "state": "unmigrated", "target_schema_version": 10},
        "reconciliation": {"state": "ok", "error": None, "message": None},
    }


class HealthPaneRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-health-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
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
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_harness(self, payload: dict) -> dict:
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

    # -- the state split --------------------------------------------------------------------
    def test_a_failed_migration_is_its_own_state_not_degraded(self) -> None:
        observed = self.run_harness(
            {
                "statuses": {
                    "failed": failed_health(),
                    "unmigrated": unmigrated_health(),
                    "healthy": {
                        "db": {
                            "ready": True,
                            "schema_version": 10,
                            "state": "ready",
                            "target_schema_version": 10,
                        }
                    },
                    # An older backend that reports the failure without `state` still never renders
                    # as "not migrated": the error's presence is enough to refuse that claim.
                    "error_without_state": {
                        "db": {
                            "ready": False,
                            "schema_version": None,
                            "error": {
                                "type": "OperationalError",
                                "message": "disk I/O error",
                                "target_schema_version": 10,
                            },
                        }
                    },
                }
            }
        )
        self.assertEqual(observed["statuses"]["failed"], "failed")
        self.assertEqual(observed["statuses"]["unmigrated"], "degraded")
        self.assertEqual(observed["statuses"]["healthy"], "ready")
        self.assertEqual(observed["statuses"]["error_without_state"], "failed")

    # -- the failed body --------------------------------------------------------------------
    def test_the_failed_body_names_the_error_and_offers_a_retry(self) -> None:
        html = self.run_harness({"failed": failed_health()})["bodies"]["failed"]
        self.assertIn("The course database could not be prepared", html)
        self.assertIn("OperationalError", html)
        self.assertIn("disk I/O error", html)
        self.assertIn("schema v10", html)
        self.assertIn("Retry migration", html)
        self.assertIn('data-cb-health="migration-failed"', html)

    def test_the_failed_body_never_claims_the_profile_has_no_tables(self) -> None:
        html = self.run_harness({"failed": failed_health()})["bodies"]["failed"].lower()
        self.assertNotIn("not migrated", html)
        self.assertNotIn("no course tables", html)
        self.assertNotIn("nothing honest to list", html)
        # It says what is actually true: the store exists and preparation failed.
        self.assertIn("the store exists", html)

    def test_the_unmigrated_branch_still_carries_its_own_copy(self) -> None:
        html = self.run_harness({"degraded": unmigrated_health()})["bodies"]["degraded"]
        self.assertIn("The course database is not migrated yet", html)
        self.assertIn("No course tables exist for this profile yet.", html)

    # -- reconciliation visibility ----------------------------------------------------------
    def test_a_failed_startup_reconciliation_is_rendered_not_only_logged(self) -> None:
        result = failed_health(
            reconciliation={
                "state": "failed",
                "error": "OperationalError",
                "message": "orphaned artifact staging unreadable",
            }
        )
        html = self.run_harness({"reconciliation": result})["bodies"]["reconciliation"]
        self.assertIn('data-cb-reconciliation="failed"', html)
        self.assertIn("OperationalError", html)
        self.assertIn("orphaned artifact staging unreadable", html)

    def test_a_healthy_reconciliation_renders_nothing(self) -> None:
        html = self.run_harness({"reconciliation": failed_health()})["bodies"]["reconciliation"]
        self.assertEqual(html, "")


if __name__ == "__main__":
    unittest.main()
