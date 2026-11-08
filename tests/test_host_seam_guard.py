"""H-115-D4 — the one private host surface, guarded so an upgrade breaks loudly.

``coursebook/db.py`` opens the single-home pinned database through the host's *private*
``hermes_cli.sqlite_util.open_db``. That is the card's decision (b): keep the import (the documented
``plugin_db`` seam takes a filename and re-resolves the escaped profile), but make the coupling a
named constant, check it at the call site — module, attribute *and* keyword shape — and fail with
:class:`coursebook.db.HostSeamUnavailable`, whose message says exactly which surface moved and what
to do. These tests pin both halves: the seam still exists as called (the upgrade canary), and every
way it can disappear turns into that named failure instead of a mystery ``DatabaseUnavailable`` or
a silent fallback to the ambient profile's store.

Design rule these tests protect: a *coupling break* and an *I/O error* are different facts. Both are
``DatabaseUnavailable`` to existing callers, but only the first says "your Hermes build moved".
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from coursebook import db

try:  # ``single_home_pin`` needs the host anyway; absent = a bare checkout, not a drift
    import hermes_constants  # noqa: F401

    HAVE_HOST = True
except Exception:  # pragma: no cover - a bare checkout without the agent on sys.path
    HAVE_HOST = False


def _fake_module(**attrs: object) -> types.ModuleType:
    module = types.ModuleType(db.HOST_SEAM_MODULE)
    for name, value in attrs.items():
        setattr(module, name, value)
    return module


def _live_connection(path: Path, **_kwargs: object) -> sqlite3.Connection:
    """A stand-in opener that opens a real file, so ``connect()`` can finish its PRAGMA stack."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path, check_same_thread=False)


class SeamIsPresent(unittest.TestCase):
    """The upgrade canary: the host build on this machine still offers the surface as called."""

    @unittest.skipUnless(HAVE_HOST, "the Hermes agent is not on sys.path in this interpreter")
    def test_the_host_still_offers_open_db_with_the_keywords_we_pass(self) -> None:
        status = db.host_seam_status()
        self.assertTrue(
            status["available"],
            f"the private host seam moved: {status['module']}.{status['attribute']} — "
            f"{status['detail']}. Re-point coursebook/db.py::_host_open_db at the installed Hermes "
            f"build (last verified against {status['verified_against']}) and update "
            f"docs/ARCHITECTURE.md §'Host seam debt', or land the public open_db seam (H-115-D4 (a)).",
        )
        self.assertEqual(status["module"], "hermes_cli.sqlite_util")
        self.assertEqual(status["attribute"], "open_db")

    @unittest.skipUnless(HAVE_HOST, "the Hermes agent is not on sys.path in this interpreter")
    def test_status_reports_the_verified_host_build(self) -> None:
        """The recorded host build is a fact in one place, so an upgrade review can diff it."""
        self.assertIn("hermes-agent ", db.HOST_SEAM_VERIFIED)
        self.assertEqual(
            db.host_seam_status()["verified_against"], db.HOST_SEAM_VERIFIED
        )


class SeamDriftIsNamed(unittest.TestCase):
    """Every way the seam can vanish is a typed coupling break with an actionable message."""

    def _assert_names_the_surface(self, error: BaseException) -> None:
        message = str(error)
        self.assertIn("hermes_cli.sqlite_util.open_db", message)
        self.assertIn(db.SINGLE_HOME_FLAG, message)
        self.assertIn("last verified that surface against", message)
        self.assertIn("Refusing to fall back", message)

    def test_missing_module(self) -> None:
        def missing() -> object:
            raise ModuleNotFoundError("No module named 'hermes_cli.sqlite_util'")

        with mock.patch.object(db, "_host_module", missing):
            with self.assertRaises(db.HostSeamUnavailable) as caught:
                db._host_open_db(Path("unused/data.db"))
        self._assert_names_the_surface(caught.exception)
        self.assertIn("not importable", str(caught.exception))

    def test_module_present_but_the_attribute_moved(self) -> None:
        with mock.patch.object(db, "_host_module", lambda: _fake_module(connect=lambda path: path)):
            with self.assertRaises(db.HostSeamUnavailable) as caught:
                db._host_open_db(Path("unused/data.db"))
        self._assert_names_the_surface(caught.exception)
        self.assertIn("no callable open_db", str(caught.exception))

    def test_attribute_present_but_renamed_keywords(self) -> None:
        """A refactor that keeps the name and drops ``db_label`` breaks the pinned open just the same."""

        def open_db(path: Path) -> sqlite3.Connection:  # noqa: ARG001 - signature is the point
            raise AssertionError("the guard must refuse before calling a drifted opener")

        with mock.patch.object(db, "_host_module", lambda: _fake_module(open_db=open_db)):
            with self.assertRaises(db.HostSeamUnavailable) as caught:
                db._host_open_db(Path("unused/data.db"))
        self._assert_names_the_surface(caught.exception)
        for name in db.HOST_SEAM_KWARGS:
            self.assertIn(name, str(caught.exception))

    def test_module_identity_drift_is_named(self) -> None:
        """The literal the lint reports and the constant the messages name cannot diverge silently."""
        elsewhere = types.ModuleType("hermes_cli.somewhere_else")
        elsewhere.open_db = _live_connection  # type: ignore[attr-defined]
        with mock.patch.object(db, "_host_module", lambda: elsewhere):
            with self.assertRaises(db.HostSeamUnavailable) as caught:
                db._host_open_db(Path("unused/data.db"))
        self.assertIn("hermes_cli.somewhere_else", str(caught.exception))
        self.assertIn(db.HOST_SEAM_MODULE, str(caught.exception))

    def test_opener_that_takes_kwargs_is_accepted(self) -> None:
        """The guard must not false-positive on the host's own ``**kwargs`` spellings."""
        calls: list[tuple[Path, dict]] = []

        def open_db(path: Path, **kwargs: object) -> sqlite3.Connection:
            calls.append((Path(path), kwargs))
            return _live_connection(path)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data.db"
            with mock.patch.object(db, "_host_module", lambda: _fake_module(open_db=open_db)):
                connection = db._host_open_db(target)
            connection.close()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], target)
        self.assertEqual(
            calls[0][1],
            {"db_label": "plugin-data/coursebook/data.db", "foreign_keys": True,
             "check_same_thread": False},
        )

    def test_an_opener_error_is_io_not_a_coupling_break(self) -> None:
        """A permission or disk error must not be reported as "your Hermes build moved"."""

        def denied(path: Path, **_kwargs: object) -> sqlite3.Connection:
            raise PermissionError(f"no write access to {path}")

        with tempfile.TemporaryDirectory() as tmp:
            launch, escaped = Path(tmp) / "launch-home", Path(tmp) / "default-home"
            launch.mkdir()
            escaped.mkdir()
            homes = [
                mock.patch("hermes_constants.get_process_hermes_home", lambda: launch),
                mock.patch("hermes_constants.get_hermes_home", lambda: escaped),
            ]
            for patch in homes:
                patch.start()
            try:
                # distinct homes are irrelevant here: the opener refuses before any path matters
                with mock.patch.dict(os.environ, {db.SINGLE_HOME_FLAG: "1"}), \
                        mock.patch.object(
                            db, "_host_module", lambda: _fake_module(open_db=denied)):
                    with self.assertRaises(db.DatabaseUnavailable) as caught:
                        db.connect()
            finally:
                for patch in reversed(homes):
                    patch.stop()
        self.assertNotIsInstance(caught.exception, db.HostSeamUnavailable)
        self.assertIn("no write access", str(caught.exception))


class PinnedOpenGoesThroughTheGuard(unittest.TestCase):
    """The single-home path opens the launch home's file through the guarded seam, once."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.launch = root / "launch-home"
        self.escaped = root / "default-home"
        self.launch.mkdir()
        self.escaped.mkdir()
        self._patches = [
            mock.patch("hermes_constants.get_process_hermes_home", lambda: self.launch),
            mock.patch("hermes_constants.get_hermes_home", lambda: self.escaped),
        ]
        for patch in self._patches:
            patch.start()
        self._env = mock.patch.dict(os.environ, {db.SINGLE_HOME_FLAG: "1"})
        self._env.start()
        self.calls: list[Path] = []

        def opener(path: Path, **kwargs: object) -> sqlite3.Connection:
            self.calls.append(Path(path))
            return _live_connection(path, **kwargs)

        self._module = mock.patch.object(db, "_host_module", lambda: _fake_module(open_db=opener))
        self._module.start()

    def tearDown(self) -> None:
        self._module.stop()
        self._env.stop()
        for patch in reversed(self._patches):
            patch.stop()
        self._tmp.cleanup()

    def test_connect_opens_the_launch_home_through_the_guarded_seam(self) -> None:
        connection = db.connect()
        try:
            self.assertEqual(
                self.calls, [self.launch / "plugin-data" / "coursebook" / "data.db"]
            )
            self.assertEqual(connection.row_factory, sqlite3.Row)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.isolation_level, None)
        finally:
            connection.close()
        self.assertFalse((self.escaped / "plugin-data").exists(), "the escaped home was touched")

    def test_a_drifted_seam_fails_the_pinned_connect_loudly(self) -> None:
        """Flag set + seam gone = ``DatabaseUnavailable`` naming the flag, never the ambient store."""
        with mock.patch.object(db, "_host_module", lambda: _fake_module()):
            with self.assertRaises(db.DatabaseUnavailable) as caught:
                db.connect()
        self.assertIn(db.SINGLE_HOME_FLAG, str(caught.exception))
        self.assertIn("hermes_cli.sqlite_util.open_db", str(caught.exception))
        self.assertFalse((self.escaped / "plugin-data").exists(), "the escaped home was touched")


class DoctorReportsTheCouplingBreak(unittest.TestCase):
    """``install_check`` answers "why can't the pinned backend open its store?" before a request."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.launch = root / "launch-home"
        self.escaped = root / "default-home"
        self.launch.mkdir()
        self.escaped.mkdir()
        self._patches = [
            mock.patch("hermes_constants.get_process_hermes_home", lambda: self.launch),
            mock.patch("hermes_constants.get_hermes_home", lambda: self.escaped),
        ]
        for patch in self._patches:
            patch.start()
        self._env = mock.patch.dict(os.environ, {db.SINGLE_HOME_FLAG: "1"})
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        for patch in reversed(self._patches):
            patch.stop()
        self._tmp.cleanup()

    def _finding(self):
        from coursebook import install_check

        finding = install_check._scope_finding()
        self.assertIsNotNone(finding, "the single-home flag must yield a scope finding")
        return finding

    def test_available_seam_is_an_ok_pinned_finding(self) -> None:
        with mock.patch.object(db, "_host_module", lambda: _fake_module(open_db=_live_connection)):
            finding = self._finding()
        self.assertEqual(finding.level, "ok")
        self.assertEqual(finding.code, "SCOPE_PINNED")
        self.assertIn("hermes_cli.sqlite_util.open_db", finding.message)

    def test_moved_seam_is_an_error_finding_with_a_fix(self) -> None:
        with mock.patch.object(db, "_host_module", lambda: _fake_module()):
            finding = self._finding()
        self.assertEqual(finding.level, "error")
        self.assertEqual(finding.code, "HOST_SEAM_UNAVAILABLE")
        self.assertIn(db.HOST_SEAM_VERIFIED, finding.message)
        self.assertIsNotNone(finding.fix)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
