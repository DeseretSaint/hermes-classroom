"""H-182/D6 — the job reaper must run in the same store scope as the RPC, and never spam.

The defect (tree ``300d00b``, ``~/.hermes/coursebook-test-h182/home/logs/errors.log``): in a fresh
Desktop profile on a remote backend (``hermes serve --isolated :44290``) the reaper failed every
five seconds with ``sqlite3.OperationalError: no such table: jobs`` from
``coursebook/job_service.py:1000`` inside ``executor._reaper_loop``, so H-66 expired-lease
reconciliation never ran in that topology.

Two mechanisms produced it, and each has a test here against a **real** SQLite store and the
**real** reaper thread:

1. the reaper thread has no request scope, so it resolved ``get_hermes_home()`` from whatever
   context the plugin loader left behind instead of the scope the RPC resolves; ``start_tick`` now
   snapshots that scope with :func:`coursebook.db.store_scope` and pins the thread
   (:class:`ReaperStoreScopeTest`);
2. the reaper starts at plugin registration, *before* the first Coursebook action has migrated
   anything, and opening the file then created an empty database and raised every pass; a store with
   no schema is now a quiet skip (:class:`ReaperBeforeFirstMigrationTest`).

Run only these with::

    python3 -m unittest tests.test_h182_reaper_scope -v
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from coursebook import db, executor, job_service
from tests.kernel_support import KernelCase

try:  # ``single_home_pin`` needs the host's home resolver; a bare checkout has no host
    import hermes_constants  # noqa: F401

    HAVE_HOST = True
except Exception:  # pragma: no cover - environment guard
    HAVE_HOST = False

#: Far enough in the past that the lease is certainly expired for a real "now".
EXPIRED = datetime.now(timezone.utc) - timedelta(hours=2)


def _store(home: Path) -> Path:
    """The store root a home resolves to, without asking the host."""
    return home / "plugin-data" / "coursebook"


def _job_state(store: Path, job_id: str) -> str:
    with db.use_store_scope(store):
        return str(job_service._view(job_id)["state"])


def _seed_expired_job(store: Path, goal: str) -> str:
    """Create, claim and abandon one job so its lease is past due. Returns its id."""
    with db.use_store_scope(store):
        db.migrate()
        job_id = job_service.create("plan", {"goal": goal, "brief_version": 1})["job_id"]
        job_service.claim(job_id, owner="dead-worker", now=EXPIRED)
    return job_id


@unittest.skipUnless(HAVE_HOST, "hermes_constants is not importable in this interpreter")
class ReaperStoreScopeTest(KernelCase):
    """The reaper reads the store the RPC would read — not the ambient home of its thread."""

    def setUp(self) -> None:
        super().setUp()  # self.home is a migrated launch home (KernelCase)
        self.root = Path(tempfile.mkdtemp(prefix="coursebook-reaper-homes-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.launch = Path(self.home)
        self.escaped = self.root / "escaped-profile"
        self.escaped.mkdir()
        #: Which home an *unpinned* ``get_hermes_home()`` answers from. Flipped after start.
        self.active = Path(self.launch)
        self._patches = [
            mock.patch("hermes_constants.get_process_hermes_home", lambda: Path(self.launch)),
            # resolved at call time, so the flip below reaches the thread
            mock.patch("hermes_constants.get_hermes_home", lambda: Path(self.active)),
        ]
        for patch in self._patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self) -> None:  # noqa: N802 - unittest API
        executor.stop()
        for thread in (executor._REAPER_THREAD, executor._TICK_THREAD):
            if thread is not None and callable(getattr(thread, "join", None)):
                thread.join(5.0)
        executor._STOP.clear()
        executor._REAPER_THREAD = None
        executor._TICK_THREAD = None
        executor._TICK_TASK = None
        super().tearDown()

    def _start_and_drift(self, *, single_home: bool) -> tuple[str, str]:
        """Start the real reaper, then move the ambient home out from under it."""
        launch_job = _seed_expired_job(_store(self.launch), "launch")
        escaped_job = _seed_expired_job(_store(self.escaped), "escaped")
        env = {db.SINGLE_HOME_FLAG: "1"} if single_home else {}
        with mock.patch.dict(os.environ, env), self.assertLogs("coursebook.executor", level="INFO") as logs:
            executor._STOP.clear()
            executor._start_reaper(0.5)
            # The thread has started with the registering scope. Now an unrequested context — a
            # multiplexed call, a profile switch, a stale loader context — answers from elsewhere.
            self.active = Path(self.escaped)
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline and _job_state(_store(self.launch), launch_job) == "running":
                time.sleep(0.05)
            time.sleep(1.1)  # give a wrongly-scoped reaper a second pass to touch the other store
        errors = [record for record in logs.records if record.levelno >= 40]
        self.assertEqual(errors, [], f"the reaper logged an error: {[r.getMessage() for r in errors]}")
        return launch_job, escaped_job

    def test_single_home_backend_reconciles_the_launch_store(self) -> None:
        """The reported topology: the flag is set, the thread has no request scope."""
        launch_job, escaped_job = self._start_and_drift(single_home=True)
        self.assertEqual(_job_state(_store(self.launch), launch_job), "interrupted_requires_retry")
        self.assertEqual(
            _job_state(_store(self.escaped), escaped_job),
            "running",
            "the reaper touched a home the pane never serves",
        )

    def test_the_pin_holds_without_the_single_home_flag(self) -> None:
        """Multi-profile hosting: the reaper keeps the scope it was registered in."""
        launch_job, escaped_job = self._start_and_drift(single_home=False)
        self.assertEqual(_job_state(_store(self.launch), launch_job), "interrupted_requires_retry")
        self.assertEqual(_job_state(_store(self.escaped), escaped_job), "running")


@unittest.skipUnless(HAVE_HOST, "hermes_constants is not importable in this interpreter")
class ReaperBeforeFirstMigrationTest(KernelCase):
    """Before the first Coursebook action there is no store: skip quietly, provision nothing."""

    def setUp(self) -> None:
        super().setUp()
        self.empty = Path(tempfile.mkdtemp(prefix="coursebook-reaper-empty-"))
        self.addCleanup(shutil.rmtree, self.empty, True)
        self._patches = [
            mock.patch("hermes_constants.get_process_hermes_home", lambda: Path(self.empty)),
            mock.patch("hermes_constants.get_hermes_home", lambda: Path(self.empty)),
        ]
        for patch in self._patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self) -> None:  # noqa: N802 - unittest API
        executor.stop()
        thread = executor._REAPER_THREAD
        if thread is not None and callable(getattr(thread, "join", None)):
            thread.join(5.0)
        executor._STOP.clear()
        executor._REAPER_THREAD = None
        super().tearDown()

    def test_an_unmigrated_store_is_a_skip_not_an_error(self) -> None:
        self.assertFalse(_store(self.empty).exists())
        self.assertEqual(
            job_service.reconcile_expired(),
            {
                "interrupted": 0,
                "cancelled": 0,
                "skipped": True,
                "reason": "database has no schema yet",
            },
        )
        self.assertFalse(
            _store(self.empty).exists(),
            "a read created the store: absent must not become provisioned",
        )

    def test_the_reaper_thread_survives_and_stays_quiet(self) -> None:
        with self.assertLogs("coursebook.executor", level="INFO") as logs:
            executor._STOP.clear()
            thread = executor._start_reaper(0.5)
            time.sleep(1.6)  # at least two passes
            self.assertTrue(thread.is_alive(), "the reaper died on an unmigrated store")
        errors = [record for record in logs.records if record.levelno >= 40]
        self.assertEqual(errors, [], f"the reaper logged an error: {[r.getMessage() for r in errors]}")
        self.assertFalse(
            _store(self.empty).exists(),
            "the reaper provisioned a store that no Coursebook action has created",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
