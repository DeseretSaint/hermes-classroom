"""The catalog probe's parser, exercised without a network call.

`scripts/catalog-live-check.py` is a by-hand probe, not part of the offline gate:
importing this module and calling `evaluate()` must never fetch anything. These
tests build index dicts in memory and assert the three outcomes the probe exists
to report — entry present at the recorded pin, entry absent, and pin drift.

    python3 -m unittest tests.test_catalog_live_check -v
"""
from __future__ import annotations

import importlib.util
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "catalog-live-check.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("catalog_live_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load_probe()

PIN = "14a2dbb6870e81044dfb644964257fe9ccba992b"


def _index(*, entries: list[dict], generated_at: str = "2026-11-20T06:42:55.630891+00:00") -> dict:
    return {"generated_at": generated_at, "entries": entries, "removed": []}


def _entry(**overrides) -> dict:
    row = {
        "name": "coursebook",
        "version": "0.2.1",
        "sha": PIN,
        "tier": "community",
        "category": "desktop",
    }
    row.update(overrides)
    return row


class EvaluateTest(unittest.TestCase):
    def test_entry_present_at_recorded_pin_passes(self) -> None:
        index = _index(entries=[_entry(name="other"), _entry()])
        result = probe.evaluate(index)

        self.assertTrue(result["ok"], result["reason"])
        self.assertEqual(result["entry_count"], 2)
        self.assertEqual(result["matches"], 1)
        self.assertEqual(result["entry"]["name"], "coursebook")
        self.assertEqual(result["entry"]["sha"], PIN)
        self.assertEqual(result["entry"]["version"], "0.2.1")
        self.assertEqual(result["entry"]["tier"], "community")
        # The rotating value is reported, never compared.
        self.assertEqual(result["generated_at"], "2026-11-20T06:42:55.630891+00:00")

    def test_entry_absent_fails(self) -> None:
        index = _index(entries=[_entry(name="other"), _entry(name="another")])
        result = probe.evaluate(index)

        self.assertFalse(result["ok"])
        self.assertEqual(result["matches"], 0)
        self.assertIsNone(result["entry"])
        self.assertIn("no entry named 'coursebook'", result["reason"])
        self.assertIn("2 entries", result["reason"])

    def test_pin_drift_fails_and_names_both_shas(self) -> None:
        moved = "0123456789abcdef0123456789abcdef01234567"
        index = _index(entries=[_entry(sha=moved)])
        result = probe.evaluate(index)

        self.assertFalse(result["ok"])
        self.assertEqual(result["matches"], 1)
        self.assertEqual(result["entry"]["sha"], moved)
        self.assertIn("sha drift", result["reason"])
        self.assertIn(moved, result["reason"])
        self.assertIn(PIN, result["reason"])

    def test_expected_pin_is_a_parameter(self) -> None:
        index = _index(entries=[_entry(sha="0000000")])
        self.assertTrue(probe.evaluate(index, expect_sha="0000000")["ok"])
        self.assertFalse(probe.evaluate(index)["ok"])

    def test_duplicate_names_are_ambiguous_not_ok(self) -> None:
        result = probe.evaluate(_index(entries=[_entry(), _entry()]))
        self.assertFalse(result["ok"])
        self.assertEqual(result["matches"], 2)
        self.assertIn("exactly one", result["reason"])

    def test_default_expect_sha_is_the_recorded_pin(self) -> None:
        self.assertEqual(probe.DEFAULT_EXPECT_SHA, PIN)


class NoNetworkTest(unittest.TestCase):
    def test_evaluate_never_touches_the_network(self) -> None:
        with mock.patch.object(
            urllib.request, "urlopen", side_effect=AssertionError("network call in a parser test")
        ):
            result = probe.evaluate(_index(entries=[_entry()]))
        self.assertTrue(result["ok"])

    def test_shape_errors_are_reported_as_catalog_errors(self) -> None:
        for bad in ({}, {"entries": []}, {"generated_at": "x"}, [], {"generated_at": "x", "entries": {}}):
            with self.subTest(bad=bad):
                with self.assertRaises(probe.CatalogError):
                    probe.evaluate(bad)


if __name__ == "__main__":
    unittest.main()
