"""The release gate must read the tree's live wire-contract version, not the record's.

`docs/release-evidence.json` can name any `cb.rpc` version it likes. Before this test
existed, `check_contracts()` opened `contracts/rpc.v<recorded>.json` and asserted that
file's method count, so a record pinned to v25 passed on a tree that shipped v26. These
tests plant a throwaway git tree and run the real script as a subprocess: the gate must
derive `WIRE_CONTRACT_VERSION` from `coursebook/contracts.py`, fail when it disagrees
with the record, and fail when a newer `contracts/rpc.v*.json` sits on disk than the
record names — while still counting methods against the live contract file.

    python3 -m unittest tests.test_check_docs_truth -v
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-docs-truth.py"

DB_VERSION = 14


def _rpc_contract(methods: int) -> dict:
    return {"methods": {"type": "object", "properties": {f"m{i}": {"type": "string"} for i in range(methods)}}}


def _plant_tree(
    root: Path,
    *,
    recorded_version: int | str,
    live_version: int,
    contracts: dict[int, int],
    recorded_methods: int | None = None,
) -> Path:
    """A minimal git tree the gate can run against: one live constant, N contract files."""
    (root / "scripts").mkdir(parents=True)
    shutil.copyfile(SCRIPT, root / "scripts" / "check-docs-truth.py")

    (root / "coursebook").mkdir()
    (root / "coursebook" / "contracts.py").write_text(
        f'WIRE_CONTRACT_ID = "cb.rpc"\nWIRE_CONTRACT_VERSION = {live_version}\n',
        encoding="utf-8",
    )
    (root / "coursebook" / "db.py").write_text(
        f"DB_SCHEMA_VERSION = {DB_VERSION}\n", encoding="utf-8"
    )
    # check_prompt_versions() reads this module unconditionally; the gate must reach the
    # contract checks without a traceback, so plant the constants it parses.
    (root / "coursebook" / "generation.py").write_text(
        "PLAN_PROMPT_VERSION = \"plan-prompt.v11\"\n"
        "PLAN_PROMPT_VERSION_V2 = \"plan-prompt.v10\"\n"
        "UNIT_SECTIONS_PROMPT_VERSION = \"unit-sections-prompt.v1\"\n"
        "LESSON_PROMPT_VERSION = \"lesson-prompt.v10\"\n"
        "VALIDATION_PROMPT_VERSION = \"validation-prompt.v5\"\n",
        encoding="utf-8",
    )

    (root / "contracts").mkdir()
    for version, methods in contracts.items():
        (root / "contracts" / f"rpc.v{version}.json").write_text(
            json.dumps(_rpc_contract(methods)), encoding="utf-8"
        )
    (root / "contracts" / f"db.v{DB_VERSION}.json").write_text(
        json.dumps({"schema_version": DB_VERSION}), encoding="utf-8"
    )

    (root / "docs").mkdir()
    (root / "desktop").mkdir()
    module = root / "desktop" / "plugin.js"
    module.write_text("// planted module\n", encoding="utf-8")
    evidence = {
        "measured_commit": "0" * 40,
        "plugin": {
            "path": "desktop/plugin.js",
            "sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        },
        "rpc": {
            "contract": "cb.rpc",
            "version": recorded_version,
            "declared_methods": (
                recorded_methods
                if recorded_methods is not None
                else contracts.get(recorded_version, 0)  # type: ignore[arg-type]
            ),
        },
        "db": {"contract": "cb.db", "version": DB_VERSION, "schema_version": DB_VERSION},
    }
    (root / "docs" / "release-evidence.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )

    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    return root


def _commit(root: Path, message: str) -> str:
    """Commit the planted tree and return the new HEAD sha."""
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c", "user.name=qa",
            "-c", "user.email=qa@example.invalid",
            "commit", "-q", "-m", message,
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _set_measured_commit(root: Path, commit: str) -> None:
    path = root / "docs" / "release-evidence.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    evidence["measured_commit"] = commit
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")


def _run(root: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "check-docs-truth.py"),
            "--skip-tests",
            "--json",
            *(extra or []),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )


def _failures(proc: subprocess.CompletedProcess) -> list[str]:
    try:
        return json.loads(proc.stdout)["failures"]
    except (json.JSONDecodeError, KeyError) as exc:  # pragma: no cover - diagnostics aid
        raise AssertionError(f"gate did not emit a JSON result: {proc.stdout!r} {proc.stderr!r}") from exc


class LiveWireVersionTest(unittest.TestCase):
    def test_stale_record_version_exits_1_and_names_both_versions(self) -> None:
        """Record says v25, tree ships v26: the gate must fail, not open v25 and pass."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _plant_tree(
                Path(tmp), recorded_version=25, live_version=26, contracts={25: 93, 26: 93}
            )
            proc = _run(root)

        self.assertEqual(proc.returncode, 1, f"{proc.stdout}\n{proc.stderr}")
        named = [
            f
            for f in _failures(proc)
            if "WIRE_CONTRACT_VERSION" in f and "v25" in f and "26" in f
        ]
        self.assertEqual(len(named), 1, _failures(proc))

    def test_matching_versions_do_not_trip_the_version_check(self) -> None:
        # The real tree's shape: v25 is immutable history on disk, v26 is live and recorded.
        with tempfile.TemporaryDirectory() as tmp:
            root = _plant_tree(
                Path(tmp), recorded_version=26, live_version=26, contracts={25: 93, 26: 93}
            )
            proc = _run(root)

        failures = _failures(proc)
        self.assertFalse(
            [f for f in failures if "WIRE_CONTRACT_VERSION" in f or "is newer than" in f],
            failures,
        )
        # The method count is still asserted, and against the live contract file.
        self.assertIn("rpc.v26.json declares 93 methods", json.loads(proc.stdout)["notes"])

    def test_newer_contract_on_disk_than_the_record_fails(self) -> None:
        """An on-disk amendment cannot land while the record still names the old version."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _plant_tree(
                Path(tmp), recorded_version=26, live_version=26, contracts={26: 93, 27: 93}
            )
            proc = _run(root)

        self.assertEqual(proc.returncode, 1, f"{proc.stdout}\n{proc.stderr}")
        newer = [f for f in _failures(proc) if "rpc.v27.json" in f and "v26" in f]
        self.assertEqual(len(newer), 1, _failures(proc))

    def test_method_count_is_counted_off_the_live_contract_not_the_record(self) -> None:
        """Record v25 declares 93; live v26 declares 94. Both holes must show."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _plant_tree(
                Path(tmp),
                recorded_version=25,
                live_version=26,
                contracts={25: 93, 26: 94},
                recorded_methods=93,
            )
            proc = _run(root)

        failures = _failures(proc)
        self.assertEqual(proc.returncode, 1, f"{proc.stdout}\n{proc.stderr}")
        self.assertTrue(
            [f for f in failures if "rpc.v26.json declares 94" in f], failures
        )
        self.assertFalse(
            [f for f in failures if "rpc.v25.json declares" in f], failures
        )

    def test_matching_version_but_wrong_method_count_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _plant_tree(
                Path(tmp),
                recorded_version=26,
                live_version=26,
                contracts={26: 94},
                recorded_methods=93,
            )
            proc = _run(root)

        self.assertEqual(proc.returncode, 1, f"{proc.stdout}\n{proc.stderr}")
        self.assertTrue(
            [f for f in _failures(proc) if "rpc method count" in f and "94" in f],
            _failures(proc),
        )


    def test_non_integer_recorded_version_fails_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _plant_tree(
                Path(tmp), recorded_version="26", live_version=26, contracts={26: 93}
            )
            proc = _run(root)

        self.assertEqual(proc.returncode, 1, f"{proc.stdout}\n{proc.stderr}")
        self.assertNotIn("Traceback", proc.stderr)
        self.assertTrue(
            [f for f in _failures(proc) if "is not an integer" in f], _failures(proc)
        )

    def test_missing_live_constant_fails_instead_of_passing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _plant_tree(
                Path(tmp), recorded_version=26, live_version=26, contracts={25: 93, 26: 93}
            )
            (root / "coursebook" / "contracts.py").write_text(
                'WIRE_CONTRACT_ID = "cb.rpc"\n', encoding="utf-8"
            )
            proc = _run(root)

        self.assertEqual(proc.returncode, 1, f"{proc.stdout}\n{proc.stderr}")
        self.assertTrue(
            [f for f in _failures(proc) if "no WIRE_CONTRACT_VERSION" in f],
            _failures(proc),
        )


class RequireHeadTest(unittest.TestCase):
    """--require-head is opt-in: default mode must not change, release mode must be sharp."""

    def test_stale_record_against_head_fails_naming_both_shas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _plant_tree(
                Path(tmp), recorded_version=26, live_version=26, contracts={26: 93}
            )
            measured = _commit(root, "the measured tree")
            _set_measured_commit(root, measured)
            (root / "later.txt").write_text("a merge landed after the measurement\n")
            head = _commit(root, "merge after the measurement")

            default = _run(root)
            strict = _run(root, ["--require-head"])

        self.assertFalse(
            [f for f in _failures(default) if f.startswith("--require-head")],
            "default mode changed behaviour",
        )
        self.assertEqual(strict.returncode, 1, f"{strict.stdout}\n{strict.stderr}")
        named = [
            f for f in _failures(strict)
            if f.startswith("--require-head:") and measured in f and head in f
        ]
        self.assertEqual(len(named), 1, _failures(strict))

    def test_record_that_names_head_passes_the_freshness_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _plant_tree(
                Path(tmp), recorded_version=26, live_version=26, contracts={26: 93}
            )
            head = _commit(root, "planted tree")
            # The record names the commit it describes; the working tree is dirty after the
            # rewrite, which is exactly a pre-commit release run.
            _set_measured_commit(root, head)
            proc = _run(root, ["--require-head"])

        self.assertFalse(
            [f for f in _failures(proc) if f.startswith("--require-head")], _failures(proc)
        )
        self.assertIn(
            "--require-head: 1 recorded commit(s) all name HEAD",
            "\n".join(json.loads(proc.stdout)["notes"]),
        )


    def test_stale_module_pin_fails_under_require_head(self) -> None:
        """The record can name HEAD and still quote an older build's module hash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _plant_tree(
                Path(tmp), recorded_version=26, live_version=26, contracts={26: 93}
            )
            head = _commit(root, "planted tree")
            _set_measured_commit(root, head)
            stored = json.loads((root / "docs" / "release-evidence.json").read_text())
            recorded_pin = stored["plugin"]["sha256"]

            (root / "desktop" / "plugin.js").write_text("// rebuilt module\n", encoding="utf-8")
            actual_pin = hashlib.sha256((root / "desktop" / "plugin.js").read_bytes()).hexdigest()
            strict = _run(root, ["--require-head"])

        self.assertEqual(strict.returncode, 1, f"{strict.stdout}\n{strict.stderr}")
        stale = [
            f for f in _failures(strict)
            if f.startswith("--require-head:") and recorded_pin in f and actual_pin in f
        ]
        self.assertEqual(len(stale), 1, _failures(strict))


if __name__ == "__main__":
    unittest.main()
