"""Desktop half loads as a real ESM module and wires the documented SDK surfaces.

The runtime loader refuses relative imports and JSX, so the honest test is the loader's own
constraint: evaluate the file as plain ESM with only the three allowed specifiers resolvable,
then inspect what ``register(ctx)`` actually registered. Node does the resolution; the stubs
implement exactly the SDK surface the plugin uses, so a missing/misspelled export fails here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

SDK_STUB = textwrap.dedent(
    """
    const atom = (value) => ({ get: () => value })
    const calls = []
    export const ROUTES_AREA = 'routes'
    export const SIDEBAR_NAV_AREA = 'sidebar.nav'
    export const PANES_AREA = 'panes'
    export const PALETTE_AREA = 'palette'
    export const KEYBINDS_AREA = 'keybinds'
    export const useValue = (a) => a.get()
    export const Button = 'Button'
    export const Badge = 'Badge'
    export const ErrorState = 'ErrorState'
    export const Loader = 'Loader'
    export const PanelEmpty = 'PanelEmpty'
    export const PanelSectionLabel = 'PanelSectionLabel'
    export const host = {
      state: {
        focusedSessionId: atom(null),
        focusedStoredSessionId: atom(null),
        focusedSessionProfile: atom('default'),
        profile: atom('default')
      },
      profileRoutes: () => [],
      navigate: (path) => calls.push(['navigate', path]),
      notify: (payload) => calls.push(['notify', payload]),
      openSession: (id, options) => calls.push(['openSession', id, options]),
      newChat: (profile) => calls.push(['newChat', profile]),
      calls
    }
    """
)

HARNESS = textwrap.dedent(
    """
    import plugin from './plugin.js'
    import { host } from '@hermes/plugin-sdk'

    const registrations = []
    const settingsPages = []
    const restCalls = []
    const disposers = []

    const ctx = {
      source: 'plugin:coursebook',
      register: (contribution) => {
        registrations.push({ id: contribution.id, area: contribution.area, data: contribution.data || null })
        return () => {}
      },
      registerSettingsPage: (page) => {
        settingsPages.push({ id: page.id, title: page.title })
        return () => {}
      },
      rest: async (path, options) => {
        restCalls.push({ path, options: options || null })
        if (path === '/runtime') {
          return {
            wire_contract: 'cb.rpc',
            wire_version: 2,
            implemented_methods: ['health.get', 'schema.get', 'binding.get'],
            contract_problems: []
          }
        }
        return { ok: true, contract_version: 2, operation_id: 'op', revision: 0, result: {} }
      },
      onDispose: (fn) => disposers.push(fn),
      runAction: () => ({ ok: true }),
      storage: { get: (k, d) => d, set: () => {}, remove: () => {} }
    }

    plugin.register(ctx)
    await new Promise((resolve) => setTimeout(resolve, 25))

    const module = await import('./plugin.js')
    console.log(JSON.stringify({
      id: module.default.id,
      name: module.default.name,
      registrations,
      settingsPages,
      restCalls,
      disposers: disposers.length,
      hostCalls: host.calls
    }))
    """
)


def node_available() -> bool:
    return shutil.which("node") is not None


@unittest.skipUnless(node_available(), "node is required to evaluate a runtime desktop plugin")
class DesktopRegistrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-desktop-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        sdk_dir = root / "node_modules" / "@hermes" / "plugin-sdk"
        sdk_dir.mkdir(parents=True)
        (sdk_dir / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk_dir / "index.js").write_text(SDK_STUB, encoding="utf-8")

        react_dir = root / "node_modules" / "react"
        react_dir.mkdir(parents=True)
        (react_dir / "package.json").write_text(
            json.dumps(
                {
                    "name": "react",
                    "type": "module",
                    "exports": {".": "./index.js", "./jsx-runtime": "./jsx-runtime.js"},
                }
            ),
            encoding="utf-8",
        )
        (react_dir / "index.js").write_text(
            "export const useCallback = (fn) => fn\n"
            "export const useEffect = () => {}\n"
            "export const useState = (initial) => [initial, () => {}]\n",
            encoding="utf-8",
        )
        (react_dir / "jsx-runtime.js").write_text(
            "export const jsx = (type, props) => ({ type, props })\n"
            "export const jsxs = (type, props) => ({ type, props })\n",
            encoding="utf-8",
        )
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")

        cls.result = subprocess.run(
            ["node", "harness.mjs"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if cls.result.returncode != 0:
            raise AssertionError(f"node harness failed:\n{cls.result.stdout}\n{cls.result.stderr}")
        cls.payload = json.loads(cls.result.stdout.strip().splitlines()[-1])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_module_identity(self) -> None:
        self.assertEqual(self.payload["id"], "coursebook")
        self.assertEqual(self.payload["name"], "Coursebook")

    def test_registers_every_documented_surface(self) -> None:
        areas = {entry["area"] for entry in self.payload["registrations"]}
        self.assertEqual(areas, {"routes", "sidebar.nav", "panes", "palette", "keybinds"})
        ids = {entry["id"] for entry in self.payload["registrations"]}
        self.assertEqual(ids, {"page", "nav", "pane", "open", "focus"})

    def test_route_and_nav_agree_on_the_path(self) -> None:
        by_id = {entry["id"]: entry for entry in self.payload["registrations"]}
        self.assertEqual(by_id["page"]["data"], {"path": "/coursebook"})
        self.assertEqual(by_id["nav"]["data"]["path"], "/coursebook")

    def test_palette_and_keybind_target_the_route(self) -> None:
        by_id = {entry["id"]: entry for entry in self.payload["registrations"]}
        self.assertEqual(by_id["open"]["data"]["id"], "coursebook.open")
        self.assertEqual(by_id["focus"]["data"]["defaults"], ["mod+shift+k"])
        self.assertEqual(by_id["focus"]["data"]["category"], "Coursebook")

    def test_registers_a_settings_page(self) -> None:
        self.assertEqual([page["id"] for page in self.payload["settingsPages"]], ["coursebook-settings"])

    def test_reads_the_backend_registry_at_register_time(self) -> None:
        paths = [call["path"] for call in self.payload["restCalls"]]
        self.assertIn("/runtime", paths, "the client must read the mounted wire version + method registry")

    def test_wire_version_is_taken_from_the_backend_not_hardcoded(self) -> None:
        # A v2 contract must not require a Desktop edit.
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn("contractVersion: backendWire.contractVersion", source)
        self.assertIn("implemented_methods", source)

    def test_disposers_are_available(self) -> None:
        self.assertGreaterEqual(self.payload["disposers"], 1)


@unittest.skipUnless(node_available(), "node is required to evaluate a runtime desktop plugin")
class SessionIdDisciplineTest(unittest.TestCase):
    """The source must never convert a runtime id into a stored one, or pick by recency."""

    def setUp(self) -> None:
        self.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_binding_is_read_by_the_stored_id(self) -> None:
        self.assertIn("loadBinding({ storedSessionId: storedId })", self.source)
        self.assertIn("host.state.focusedStoredSessionId", self.source)

    def test_no_recency_or_title_lookup(self) -> None:
        lowered = self.source.lower()
        for forbidden in ("latest_session", "most_recent", "order by updated_at", "sort((a, b) => b"):
            self.assertNotIn(forbidden, lowered)

    def test_runtime_id_is_never_sent_to_binding_get(self) -> None:
        self.assertNotIn("loadBinding({ storedSessionId: runtimeId })", self.source)
        self.assertNotIn("session_id: runtimeId", self.source)
        self.assertNotIn("session_id: host.state.focusedSessionId", self.source)

    def test_resume_requires_a_stored_session_id(self) -> None:
        self.assertIn("binding.stored_session_id", self.source)
        self.assertIn("host.openSession(binding.stored_session_id", self.source)

    def test_scope_is_explicit(self) -> None:
        self.assertIn("focusedSessionProfile", self.source)
        self.assertIn("profileRoutes", self.source)


if __name__ == "__main__":
    unittest.main()
