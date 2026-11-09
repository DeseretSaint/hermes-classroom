"""H-208: render harnesses own the ``@hermes/plugin-sdk`` stub they write.

The host install's ``node_modules`` is shared by every worktree and every agent
process on the machine. A harness that symlinks its whole ``node_modules`` to the
host tree and then writes the stub through that symlink mutates another running
suite's dependency; H-208 saw ``ToggleRow`` vanish from the SDK mid-suite this way.

These tests pin the fix: the staging helper builds a private tree, two harness
roots cannot see each other's stub, and the host install's bytes are untouched.
A source guard keeps new harnesses from reintroducing the whole-tree symlink.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.desktop_node_modules import (
    desktop_node_modules,
    stage_desktop_node_modules,
    write_sdk_stub,
)

TESTS_DIR = Path(__file__).resolve().parent


def _digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _host_sdk_snapshot(modules: Path) -> dict[str, str | None]:
    sdk = modules / "@hermes" / "plugin-sdk"
    return {
        "index.js": _digest(sdk / "index.js"),
        "package.json": _digest(sdk / "package.json"),
    }


class PrivateNodeModulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = desktop_node_modules()
        if cls.modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        assert cls.modules is not None

    def test_node_modules_is_a_directory_the_harness_owns(self) -> None:
        with tempfile.TemporaryDirectory(prefix="coursebook-nm-private-") as tmp:
            root = Path(tmp)
            sdk = stage_desktop_node_modules(root)
            self.assertIsNotNone(sdk)
            self.assertFalse((root / "node_modules").is_symlink())
            assert sdk is not None
            self.assertFalse(sdk.is_symlink())
            self.assertTrue(Path(os.path.realpath(sdk)).is_relative_to(Path(os.path.realpath(root))))
            self.assertTrue((sdk / "package.json").is_file())

    def test_imported_packages_resolve_through_the_private_tree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="coursebook-nm-private-") as tmp:
            root = Path(tmp)
            stage_desktop_node_modules(root)
            self.assertTrue((root / "node_modules" / "react").is_dir())
            self.assertTrue((root / "node_modules" / "react-dom" / "server.js").is_file())

    def test_two_harness_roots_do_not_share_the_stub(self) -> None:
        with tempfile.TemporaryDirectory(prefix="coursebook-nm-a-") as a, \
                tempfile.TemporaryDirectory(prefix="coursebook-nm-b-") as b:
            stage_desktop_node_modules(a)
            stage_desktop_node_modules(b)
            write_sdk_stub(a, "export const Sender = 'a'\n")
            write_sdk_stub(b, "export const Sender = 'b'\n")
            index_a = Path(a) / "node_modules" / "@hermes" / "plugin-sdk" / "index.js"
            index_b = Path(b) / "node_modules" / "@hermes" / "plugin-sdk" / "index.js"
            self.assertNotEqual(os.path.realpath(index_a), os.path.realpath(index_b))
            self.assertIn("'a'", index_a.read_text(encoding="utf-8"))
            self.assertIn("'b'", index_b.read_text(encoding="utf-8"))

    def test_stub_write_does_not_touch_the_host_install(self) -> None:
        before = _host_sdk_snapshot(self.modules)
        with tempfile.TemporaryDirectory(prefix="coursebook-nm-host-") as tmp:
            stage_desktop_node_modules(tmp)
            write_sdk_stub(tmp, "export const Button = () => null\n")
        self.assertEqual(_host_sdk_snapshot(self.modules), before)

    def test_staging_skips_when_the_host_install_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="coursebook-nm-none-") as tmp:
            with mock.patch("tests.desktop_node_modules.desktop_node_modules", return_value=None):
                self.assertIsNone(stage_desktop_node_modules(tmp))


class NoWholeTreeSymlinkGuardTest(unittest.TestCase):
    """No test module may symlink its whole ``node_modules`` to the host tree."""

    WHOLE_TREE = re.compile(
        r"""\(\s*[^()]*?/\s*["']node_modules["']\s*\)\s*\.symlink_to\("""
    )

    def test_no_test_module_symlinks_the_shared_node_modules(self) -> None:
        offenders = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            for match in self.WHOLE_TREE.finditer(source):
                line = source.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.name}:{line}")
        self.assertEqual(offenders, [], "these harnesses symlink the host node_modules tree")


if __name__ == "__main__":
    unittest.main()
