"""A declared setting must have a reader: the schema and the code move together."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import hermes_yaml as yaml

from coursebook import tools

ROOT = Path(__file__).resolve().parent.parent


class ConfigSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(tools.configure, None)
        self.manifest = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))

    def test_every_declared_key_has_a_reader(self) -> None:
        declared = set((self.manifest.get("config_schema") or {}).keys())
        self.assertTrue(declared, "config_schema should declare the settings this build reads")
        self.assertEqual(
            declared,
            set(tools.CONFIG_KEYS),
            "plugin.yaml config_schema and coursebook.tools.CONFIG_KEYS must not drift",
        )

    def test_declared_types_are_admission_valid(self) -> None:
        from hermes_cli.plugin_validate import ValidationReport, _check_config_spec

        report = ValidationReport()
        _check_config_spec(report, self.manifest)
        self.assertTrue(report.ok, report.failures)

    def test_declared_defaults_match_the_reader_defaults(self) -> None:
        entry = self.manifest["config_schema"]["status_include_contracts"]
        self.assertEqual(entry["type"], "bool")
        self.assertEqual(entry["default"], tools.DEFAULT_STATUS_INCLUDE_CONTRACTS)


class StatusToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(tools.configure, None)

    def test_contract_summary_is_included_by_default(self) -> None:
        tools.configure(None)
        payload = tools.status_handler()
        self.assertIn('"contracts"', payload)
        self.assertIn('"implemented_methods"', payload)

    def test_setting_removes_the_block_it_names(self) -> None:
        tools.configure(lambda key, default: False if key == "status_include_contracts" else default)
        payload = tools.status_handler()
        self.assertNotIn('"contracts"', payload)
        # The rest of the status payload is unaffected.
        self.assertIn('"db"', payload)

    def test_broken_reader_falls_back_to_the_default_instead_of_raising(self) -> None:
        def broken(key, default):
            raise RuntimeError("config.yaml is unreadable")

        tools.configure(broken)
        payload = tools.status_handler()
        self.assertIn('"contracts"', payload)

    def test_register_wires_the_context_reader(self) -> None:
        from tests.test_manifest import RecordingContext, load_plugin_package

        class SettingsContext(RecordingContext):
            def get_config(self, key, default=None):
                return False if key == "status_include_contracts" else default

        module = load_plugin_package()
        module.register(SettingsContext())
        # The privately-loaded package owns its own module objects; read through it.
        self.assertNotIn('"contracts"', module.tools.status_handler())


class StatusToolDispatchTest(unittest.TestCase):
    """Dispatch the registered handler the way the host does, not as a bare call.

    ``tools/registry.py::dispatch`` invokes ``entry.handler(args, **kwargs)`` — the model's
    argument dict arrives **positionally**. A handler declared ``(**_kwargs)`` therefore raises
    ``TypeError`` on every real invocation while ``plugins doctor`` (import/registration only)
    stays green. This class pins the registry call shape.
    """

    def setUp(self) -> None:
        self.addCleanup(tools.configure, None)
        tools.configure(None)

    def _registry(self):
        from tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(
            name=tools.STATUS_TOOL_NAME,
            toolset="coursebook",
            schema=tools.status_schema(),
            handler=tools.status_handler,
            description=tools.STATUS_TOOL_DESCRIPTION,
        )
        return registry

    def test_registry_dispatch_returns_the_health_payload(self) -> None:
        raw = self._registry().dispatch(tools.STATUS_TOOL_NAME, {})
        self.assertIsInstance(raw, str)
        payload = json.loads(raw)
        self.assertEqual(payload["plugin_version"], tools.__version__)
        self.assertIn("db", payload)
        self.assertIn("implemented_methods", payload)

    def test_handler_accepts_the_argument_dict_positionally(self) -> None:
        # The exact shape that used to raise: status_handler({}) -> TypeError.
        payload = json.loads(tools.status_handler({}))
        self.assertIn("plugin_version", payload)

    def test_handler_accepts_forwarded_context_kwargs(self) -> None:
        payload = json.loads(tools.status_handler({}, task_id="t-1", session_id="s-1"))
        self.assertIn("db", payload)


if __name__ == "__main__":
    unittest.main()
