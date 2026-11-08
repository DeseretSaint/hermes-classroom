"""Tests for the install/doctor seam: stale Desktop copy detection, refresh, socket cleanup."""

from __future__ import annotations

import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from coursebook import install_check

MARKER = install_check.MARKER


class InstallCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="cb-install-check-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.home = self.root / "home"
        self.source = self.root / "pkg"
        (self.source / "desktop").mkdir(parents=True)
        (self.source / "plugin.yaml").write_text("name: coursebook\n", encoding="utf-8")
        (self.source / "scripts").mkdir()
        (self.source / "scripts" / "install-local.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        self.source_plugin = self.source / "desktop" / "plugin.js"
        self.source_plugin.write_text("// source build\n", encoding="utf-8")

        (self.home / "plugins").mkdir(parents=True)
        os.symlink(self.source, self.home / "plugins" / "coursebook")
        target = self.home / "desktop-plugins" / "coursebook"
        target.mkdir(parents=True)
        (target / "plugin.js").write_text("// source build\n", encoding="utf-8")
        (target / MARKER).write_text(json.dumps({
            "package": "coursebook",
            "source": str(self.source / "desktop"),
            "sourceMtimeMs": install_check.mtime_ms(self.source_plugin.stat()),
            "linked": True,
        }), encoding="utf-8")

    # -- the check ---------------------------------------------------------

    def test_fresh_install_is_current(self) -> None:
        report = install_check.inspect_install(self.home, self.source)
        self.assertTrue(report.ok, [f.message for f in report.findings])
        self.assertIn("DESKTOP_CURRENT", {f.code for f in report.findings})
        self.assertIsNone(report.fix_command)

    def test_stale_copy_names_both_shas_and_one_fix_command(self) -> None:
        installed = install_check.installed_plugin(self.home)
        installed.write_text("// stale build\n", encoding="utf-8")

        report = install_check.inspect_install(self.home, self.source)
        self.assertFalse(report.ok)
        stale = next(f for f in report.findings if f.code == "DESKTOP_STALE")
        source_sha = install_check.sha256_file(self.source_plugin)
        installed_sha = install_check.sha256_file(installed)
        self.assertIn(source_sha[:12], stale.message)
        self.assertIn(installed_sha[:12], stale.message)
        self.assertIn(str(installed), stale.message)

        expected = (f"bash {self.source}/scripts/install-local.sh "
                    f"--home {self.home} --refresh-desktop")
        self.assertEqual(stale.fix, expected)
        self.assertEqual(report.fix_command, expected)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = install_check.main(["--home", str(self.home), "--source", str(self.source)])
        self.assertEqual(code, 1)
        self.assertIn("Fix it with one command:", out.getvalue())
        self.assertIn("--refresh-desktop", out.getvalue())

    def test_missing_desktop_copy_is_named(self) -> None:
        install_check.installed_plugin(self.home).unlink()
        report = install_check.inspect_install(self.home, self.source)
        self.assertFalse(report.ok)
        self.assertIn("DESKTOP_MISSING", {f.code for f in report.findings})
        self.assertIn("--refresh-desktop", report.fix_command or "")

    def test_marker_that_names_the_file_is_reported(self) -> None:
        marker = self.home / "desktop-plugins" / "coursebook" / MARKER
        marker.write_text(json.dumps({
            "package": "coursebook",
            "source": str(self.source_plugin),  # the old install-local.sh bug
            "sourceMtimeMs": 0,
        }), encoding="utf-8")
        report = install_check.inspect_install(self.home, self.source)
        self.assertIn("MARKER_NAMES_FILE", {f.code for f in report.findings})

    # -- the repair --------------------------------------------------------

    def test_refresh_repairs_the_copy_and_writes_a_directory_marker(self) -> None:
        installed = install_check.installed_plugin(self.home)
        installed.write_text("// stale build\n", encoding="utf-8")

        target = install_check.refresh_desktop(self.home, self.source)
        self.assertEqual(target, self.home / "desktop-plugins" / "coursebook")
        self.assertEqual(install_check.sha256_file(installed),
                         install_check.sha256_file(self.source_plugin))

        marker = json.loads((target / MARKER).read_text(encoding="utf-8"))
        self.assertEqual(marker["source"], str(self.source / "desktop"))
        self.assertTrue(Path(marker["source"]).is_dir(),
                        "the marker must name a directory: Hermes resolves it as one")
        self.assertTrue(marker["linked"])
        self.assertTrue(install_check.inspect_install(self.home, self.source).ok)

    def test_refresh_does_not_replace_an_unowned_directory(self) -> None:
        target = self.home / "desktop-plugins" / "coursebook"
        (target / MARKER).unlink()
        with self.assertRaises(install_check.Refused):
            install_check.refresh_desktop(self.home, self.source)

    def test_refresh_refuses_the_machine_level_home(self) -> None:
        with self.assertRaises(install_check.Refused):
            install_check.refresh_desktop(self.home, self.source, root=self.home)
        target = install_check.refresh_desktop(self.home, self.source, root=self.home, force=True)
        self.assertTrue((target / MARKER).is_file())

    # -- live-worker guard -------------------------------------------------

    def _proc_root(self, pid: int, cmdline: str, home: Path, *, name: str = "proc") -> Path:
        proc = self.root / name
        entry = proc / str(pid)
        entry.mkdir(parents=True)
        (entry / "cmdline").write_bytes(
            cmdline.replace("{home}", str(home)).replace(" ", "\0").encode() + b"\0")
        (entry / "environ").write_bytes(b"PATH=/usr/bin\0")
        return proc

    def test_live_worker_detection_matches_only_hermes_processes(self) -> None:
        home = self.root / "live-home"
        home.mkdir()
        proc = self._proc_root(4242, "hermes serve --profile x", home)
        (proc / "4242" / "cmdline").write_bytes(
            f"/usr/bin/hermes\0serve\0--port\044219\0".encode())
        (proc / "4242" / "environ").write_bytes(
            f"HERMES_HOME={home}".encode() + b"\0")
        self.assertEqual(install_check.live_worker_pids(home, proc), [4242])

        editor = self._proc_root(5252, "vi {home}/notes.md", home, name="proc-editor")
        self.assertEqual(install_check.live_worker_pids(home, editor), [])

    def test_refresh_refuses_beside_a_live_worker_unless_forced(self) -> None:
        proc = self._proc_root(4343, "hermes gateway --home {home}", self.home)
        with self.assertRaises(install_check.Refused) as caught:
            install_check.refresh_desktop(self.home, self.source, proc_root=proc)
        self.assertIn("4343", str(caught.exception))

        install_check.refresh_desktop(self.home, self.source, proc_root=proc, force=True)
        self.assertTrue(install_check.inspect_install(self.home, self.source).ok)

    # -- stale test sockets ------------------------------------------------

    def _dead_pid(self) -> int:
        process = subprocess.Popen(["true"])
        process.wait()
        return process.pid

    def _chromium_profile(self, path: Path, pid: int) -> None:
        path.mkdir(parents=True)
        os.symlink(f"somehost-{pid}", path / "SingletonLock")
        os.symlink("123456", path / "SingletonCookie")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(path / "SingletonSocket"))
        finally:
            sock.close()

    def test_clean_removes_dead_sockets_and_keeps_live_ones(self) -> None:
        # AF_UNIX paths are capped at ~108 bytes, so use a short directory for the socket.
        short = Path(tempfile.mkdtemp(prefix="cbs-", dir="/tmp"))
        self.addCleanup(lambda: __import__("shutil").rmtree(short, ignore_errors=True))
        dead = short / "audit" / "visual" / "m4" / ".chromium"
        self._chromium_profile(dead, self._dead_pid())
        live = short / ".worktrees" / "t_x" / "audit" / "visual" / "m2" / ".chromium"
        self._chromium_profile(live, os.getpid())
        (dead / "Preferences").write_text("{}", encoding="utf-8")

        actions = install_check.clean_stale_sockets(short)
        by_profile = {action["profile"]: action for action in actions}
        self.assertEqual(by_profile[str(dead)]["action"], "removed")
        self.assertEqual(by_profile[str(dead)]["entries"],
                         ["SingletonCookie", "SingletonLock", "SingletonSocket"])
        self.assertTrue((dead / "Preferences").is_file(), "only Singleton* entries may go")
        self.assertFalse((dead / "SingletonSocket").exists())
        self.assertEqual(by_profile[str(live)]["action"], "kept")
        self.assertTrue((live / "SingletonSocket").exists())

    def test_dry_run_lists_stale_sockets_without_removing_them(self) -> None:
        short = Path(tempfile.mkdtemp(prefix="cbs-", dir="/tmp"))
        self.addCleanup(lambda: __import__("shutil").rmtree(short, ignore_errors=True))
        profile = short / "audit" / "visual" / "m1" / ".chromium"
        self._chromium_profile(profile, self._dead_pid())

        actions = install_check.clean_stale_sockets(short, apply=False)
        self.assertEqual([action["action"] for action in actions], ["would_remove"])
        self.assertTrue((profile / "SingletonSocket").exists())

    def test_no_sockets_is_not_an_error(self) -> None:
        self.assertEqual(install_check.clean_stale_sockets(self.root), [])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = install_check.main(["--home", str(self.home), "--source", str(self.source),
                                       "--clean-sockets"])
        self.assertEqual(code, 0)
        self.assertIn("No Chromium Singleton* entries found.", out.getvalue())


if __name__ == "__main__":
    unittest.main()
