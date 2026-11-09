"""A declared setting must have a reader: the schema and the code move together."""

from __future__ import annotations

import json
import types
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


class ValidatorStatusTest(unittest.TestCase):
    """H-167: the status block is the honest answer to "is a different model configured?"."""

    def setUp(self) -> None:
        from coursebook import generation

        self.generation = generation
        self.addCleanup(tools.configure, None)
        self.addCleanup(generation.bind_validator_llm, None, provider="", model="")
        generation.bind_validator_llm(None, provider="", model="")

    def _block(self) -> dict:
        return json.loads(tools.status_handler({}))["validator"]

    def test_an_empty_install_reports_no_validator_route(self) -> None:
        block = self._block()
        self.assertEqual(set(block), {"configured", "provider", "model", "reason", "output_bound"})
        self.assertIs(block["configured"], False)
        self.assertIsNone(block["provider"])
        self.assertIsNone(block["model"])
        # H-192c: the declared output cap is reported, and not registered on an unbound host.
        self.assertIs(block["output_bound"]["registered"], False)
        reason = block["reason"]
        self.assertIn("plugins.entries.coursebook.settings.validator_model", reason)
        self.assertIn("plugins.entries.coursebook.settings.validator_provider", reason)
        self.assertIn("plugins.entries.coursebook.llm.allow_model_override", reason)
        self.assertIn("allow_provider_override", reason)
        self.assertIn("model_assessed", reason)
        # It reports configuration; it never claims a check ran.
        self.assertIn("never independent", reason)

    def test_a_bound_route_reports_provider_and_model_without_any_secret(self) -> None:
        self.generation.bind_validator_llm(
            types.SimpleNamespace(complete_structured=lambda **kwargs: None),
            provider="anthropic",
            model="claude-sonnet-4",
        )
        raw = tools.status_handler({})
        block = json.loads(raw)["validator"]
        self.assertEqual(
            block,
            {
                "configured": True,
                "provider": "anthropic",
                "model": "claude-sonnet-4",
                "reason": block["reason"],
                "output_bound": block["output_bound"],
            },
        )
        self.assertIn("not that it answered", block["reason"])
        self.assertEqual(block["output_bound"]["completion_cap"], self.generation.VALIDATION_OUTPUT_TOKENS)
        for forbidden in ("api_key", "apikey", "token", "secret", "credential", "password"):
            self.assertNotIn(forbidden, raw.lower())

    def test_settings_without_a_bound_host_route_stay_unconfigured(self) -> None:
        self.generation.bind_validator_llm(None, provider="anthropic", model="claude-sonnet-4")
        block = self._block()
        self.assertIs(block["configured"], False)
        self.assertEqual(block["provider"], "anthropic")
        self.assertEqual(block["model"], "claude-sonnet-4")
        self.assertIn("no host LLM route is bound", block["reason"])

    def test_a_broken_config_read_is_unconfigured_not_a_crash(self) -> None:
        def broken():
            raise RuntimeError("settings unreadable")

        original = self.generation.validator_config
        self.generation.validator_config = broken
        self.addCleanup(setattr, self.generation, "validator_config", original)
        block = self._block()
        self.assertIs(block["configured"], False)
        self.assertIn("could not be read", block["reason"])


if __name__ == "__main__":
    unittest.main()
