"""The package is installable as one folder: manifest, registrations and both halves agree."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

import hermes_yaml as yaml

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = ROOT


class RecordingContext:
    """Mirrors the minimal PluginContext surface that register() uses."""

    plugin_config: dict = {}
    profile_name = "default"
    plugin_id = "coursebook_test"

    def __init__(self) -> None:
        self.tools: list[str] = []
        self.hooks: list[str] = []

    def register_tool(self, name, *args, **kwargs):  # noqa: ANN001 - mirrors the real signature loosely
        self.tools.append(str(name))

    def register_hook(self, hook_name, callback, *, hold_stream=False):  # noqa: ANN001
        self.hooks.append(str(hook_name))

    def get_config(self, key, default=None):  # noqa: ANN001
        return default


def load_plugin_package():
    name = "coursebook_plugin_manifest_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)]
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the coursebook plugin package")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8"))

    def test_required_admission_fields(self) -> None:
        for field in ("name", "version", "description"):
            self.assertTrue(self.manifest.get(field), f"plugin.yaml missing {field}")
        self.assertEqual(self.manifest["name"], "coursebook")
        self.assertEqual(self.manifest.get("manifest_version"), 2)

    def test_requires_hermes_is_a_parseable_spec(self) -> None:
        from hermes_cli.plugin_validate import _requires_hermes_spec_valid

        self.assertTrue(_requires_hermes_spec_valid(self.manifest["requires_hermes"]))

    def test_jsonschema_is_declared_explicitly(self) -> None:
        deps = self.manifest.get("python_dependencies") or []
        self.assertTrue(
            any(dep.split(">")[0].split("=")[0].strip() == "jsonschema" for dep in deps),
            "jsonschema must be a declared dependency: grading must not depend on an optional host package",
        )

    def test_no_secrets_or_env_requirements(self) -> None:
        self.assertFalse(self.manifest.get("requires_env"), "Coursebook stores no secrets")

    def test_declared_tools_and_hooks_match_register(self) -> None:
        module = load_plugin_package()
        ctx = RecordingContext()
        module.register(ctx)
        self.assertEqual(set(ctx.tools), set(self.manifest.get("provides_tools") or []))
        self.assertEqual(set(ctx.hooks), set(self.manifest.get("provides_hooks") or []))

    def test_register_is_idempotent_and_registers_every_hook_once(self) -> None:
        module = load_plugin_package()
        first, second = RecordingContext(), RecordingContext()
        module.register(first)
        module.register(second)
        self.assertEqual(sorted(first.hooks), sorted(second.hooks))
        self.assertEqual(len(first.hooks), len(set(first.hooks)))


class PackageLayoutTest(unittest.TestCase):
    def test_both_halves_exist_for_a_unified_package(self) -> None:
        self.assertTrue((PLUGIN_DIR / "__init__.py").is_file(), "agent half entry missing")
        self.assertTrue((PLUGIN_DIR / "desktop" / "plugin.js").is_file(), "desktop half missing")
        self.assertTrue((PLUGIN_DIR / "dashboard" / "plugin_api.py").is_file(), "backend routes missing")

    def test_dashboard_manifest_mounts_the_api(self) -> None:
        manifest = json.loads((PLUGIN_DIR / "dashboard" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "coursebook")
        self.assertEqual(manifest["api"], "plugin_api.py")
        self.assertTrue((PLUGIN_DIR / "dashboard" / manifest["api"]).is_file())
        # No web-dashboard tab: the UI ships in the Desktop half, so no tab/path may be advertised.
        self.assertTrue(manifest.get("tab", {}).get("hidden", False))

    def test_desktop_half_declares_the_same_id(self) -> None:
        source = (PLUGIN_DIR / "desktop" / "plugin.js").read_text(encoding="utf-8")
        self.assertIn("const PLUGIN_ID = 'coursebook'", source)
        self.assertIn("export default", source)

    def test_plugin_api_exposes_a_router(self) -> None:
        try:
            from fastapi import APIRouter  # noqa: F401
        except Exception:  # pragma: no cover - gateway always ships fastapi
            self.skipTest("fastapi unavailable in this interpreter")
        if str(PLUGIN_DIR) not in sys.path:
            sys.path.insert(0, str(PLUGIN_DIR))
        spec = importlib.util.spec_from_file_location(
            "coursebook_plugin_api_test", PLUGIN_DIR / "dashboard" / "plugin_api.py"
        )
        if spec is None or spec.loader is None:
            self.fail("cannot load dashboard/plugin_api.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        paths = {route.path for route in module.router.routes}
        self.assertEqual(
            paths,
            {
                "/health",
                "/schema",
                "/rpc",
                "/runtime",
                # CB-010: the only doors a local pack may enter or leave through.
                "/packs/intake",
                "/packs/grant",
                "/artifacts/{handle}",
                # M0: a bounded inline preview for the lesson renderer.
                "/media/{artifact_id}",
                # CB-013: the write half of binding.get — a stored session id is never an RPC field.
                "/sessions/bind",
            },
        )


if __name__ == "__main__":
    unittest.main()
