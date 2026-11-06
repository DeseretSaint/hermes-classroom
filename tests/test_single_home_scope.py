"""An isolated backend serves ONE home, so the pane must read that home's cb.db (CB-013).

The Desktop half reports ``sharedRemote`` and appends ``?profile=<launch profile>`` to every
plugin request. On an isolated backend the host's profile scope then resolves
``plugins.plugin_storage`` against the *default* home (``~/.hermes``) — outside this process's
launch home — and the renderer lists an empty library while the seeded course sits in the launch
home. ``coursebook.db.single_home_pin`` fixes that under an explicit flag.

These tests drive the real storage seam: the host's ``plugin_data_dir``/``plugin_db`` and the real
migrations. Only the two home lookups are patched, to two throwaway directories — which is exactly
the pair of answers a scoped request produces in a real gateway.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coursebook import db, pack_flow

try:  # the host module is present when the agent is importable, which is how the gateway runs
    import hermes_constants  # noqa: F401

    HAVE_HOST = True
except Exception:  # pragma: no cover - a bare checkout without the agent on sys.path
    HAVE_HOST = False


def _two_homes(root: Path) -> tuple[Path, Path]:
    """A launch home and a different profile home (what ``?profile=default`` resolves to)."""
    launch = root / "launch-home"
    escaped = root / "default-home"
    launch.mkdir()
    escaped.mkdir()
    return launch, escaped


@unittest.skipUnless(HAVE_HOST, "hermes_constants is not importable in this interpreter")
class SingleHomeScope(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.launch, self.escaped = _two_homes(self.root)
        patched = {
            "get_process_hermes_home": lambda: self.launch,
            "get_hermes_home": lambda: self.escaped,
        }
        self._patches = [mock.patch(f"hermes_constants.{name}", fn) for name, fn in patched.items()]
        for patch in self._patches:
            patch.start()
        self._env = mock.patch.dict(os.environ, {db.SINGLE_HOME_FLAG: "1"})
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        for patch in reversed(self._patches):
            patch.stop()
        self._tmp.cleanup()

    # ── the pin ──────────────────────────────────────────────────────────

    def test_default_scope_reads_the_launch_home(self) -> None:
        """``?profile=default`` escaping the launch home still reads the launch home's cb.db."""
        self.assertEqual(db.single_home_pin(), self.launch)
        self.assertEqual(
            db.database_path(),
            self.launch / "plugin-data" / "coursebook" / "data.db",
        )
        self.assertFalse((self.escaped / "plugin-data").exists(), "the escaped home was touched")

    def test_write_lands_in_the_launch_home_and_nowhere_else(self) -> None:
        """A real migrated write through the pinned connection never reaches the escaped home."""
        db.ensure_schema()
        with db.transaction() as connection:
            connection.execute("CREATE TABLE cb013_probe (value TEXT NOT NULL)")
            connection.execute("INSERT INTO cb013_probe VALUES ('launch-home')")
        launch_db = self.launch / "plugin-data" / "coursebook" / "data.db"
        self.assertTrue(launch_db.is_file())
        with sqlite3.connect(launch_db) as check:
            self.assertEqual(check.execute("SELECT value FROM cb013_probe").fetchone()[0],
                             "launch-home")
        self.assertFalse((self.escaped / "plugin-data" / "coursebook").exists(),
                         "a write landed in the escaped (root-profile) home")

    def test_pack_roots_agree_with_the_database_root(self) -> None:
        """Staging, library and the sqlite file resolve to the same single home."""
        self.assertEqual(pack_flow.data_root(), db.data_root())
        self.assertEqual(pack_flow.library_root(), db.data_root() / "pack-library")
        self.assertEqual(pack_flow.staging_root(), db.data_root() / "pack-staging")

    # ── behaviour that must NOT change ───────────────────────────────────

    def test_flag_off_keeps_the_host_resolution(self) -> None:
        """Without the flag, multi-profile hosting is untouched: the scope wins."""
        os.environ.pop(db.SINGLE_HOME_FLAG)
        self.assertIsNone(db.single_home_pin())
        self.assertIn(self.escaped, db.database_path().parents)

    def test_a_profile_inside_the_launch_home_keeps_its_own_database(self) -> None:
        """A real child profile of the launch home is not flattened onto the launch home."""
        child = self.launch / "profiles" / "cbqa"
        child.mkdir(parents=True)
        with mock.patch("hermes_constants.get_hermes_home", lambda: child):
            self.assertIsNone(db.single_home_pin())
            self.assertIn(child, db.database_path().parents)

    def test_pin_is_off_while_the_scope_is_the_launch_home(self) -> None:
        """An unscoped request resolves exactly as the host would."""
        with mock.patch("hermes_constants.get_hermes_home", lambda: self.launch):
            self.assertIsNone(db.single_home_pin())
            self.assertEqual(db.database_path(),
                             self.launch / "plugin-data" / "coursebook" / "data.db")


class DesktopSingleHomeScope(unittest.TestCase):
    """The Desktop half must not let the app guess a profile on a single-home backend.

    Source-level on purpose (like ``test_desktop_surface``): the failure this guards against is a
    NEW REST call site that bypasses the scope-aware door and silently reads another home.
    """

    def setUp(self) -> None:
        self.source = (Path(__file__).resolve().parent.parent / "desktop" / "plugin.js").read_text(
            encoding="utf-8"
        )

    def test_every_plugin_rest_call_uses_the_scope_aware_helper(self) -> None:
        direct = [
            line.strip()
            for line in self.source.splitlines()
            if ".rest(" in line and not line.lstrip().startswith("*")
        ]
        self.assertEqual(len(direct), 2, f"a REST call bypasses rest(): {direct}")
        self.assertTrue(any("rest(scopePath(path)" in line for line in direct))
        self.assertTrue(any("/runtime?profile=" in line for line in direct))

    def test_scope_is_stated_only_for_a_single_home_host(self) -> None:
        self.assertIn("if (!backendWire.singleHome || !target) return target", self.source)
        self.assertIn("parsed.searchParams.set('profile', '')", self.source)
        self.assertIn("single_home_host", self.source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
