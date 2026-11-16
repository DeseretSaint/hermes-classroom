"""catalog-sync.py must not leave pinned-entry temp files behind.

The cron runs it every few hours; a run that died before its exit used to leave one
``catalog-entry-*.yaml`` in the temp dir per attempt, and they accumulated in the scratch cache.
These cases pin the lifecycle: the file exists only while the process that wrote it lives, and
debris from an earlier dead run is pruned.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "catalog-sync.py"
ENTRY_REL = "plugin-catalog/coursebook.yaml"


def _load():
    spec = importlib.util.spec_from_file_location("catalog_sync_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fork_with_entry(root: Path) -> Path:
    """A throwaway git checkout carrying the catalog entry, so entry_at can read a real ref."""
    fork = root / "fork"
    (fork / "plugin-catalog").mkdir(parents=True)
    (fork / ENTRY_REL).write_text("name: coursebook\nsha: " + "a" * 40 + "\n")
    for cmd in (["git", "init", "-q"], ["git", "add", ENTRY_REL],
                ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "entry"]):
        subprocess.run(cmd, cwd=fork, check=True, capture_output=True)
    return fork


class CatalogSyncTempEntries(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.fork = _fork_with_entry(self.root)
        self._previous_tempdir = tempfile.tempdir
        tempfile.tempdir = str(self.root / "scratch")
        os.makedirs(tempfile.tempdir, exist_ok=True)

    def tearDown(self):
        tempfile.tempdir = self._previous_tempdir
        self._tmp.cleanup()

    def test_entry_name_comes_from_the_ref_not_the_checkout(self):
        gate = _load()
        (self.fork / ENTRY_REL).write_text("name: coursebook\nsha: " + "b" * 40 + "\n")
        entry = gate.entry_at(self.fork, "HEAD")
        try:
            assert entry.read_text().startswith("name: coursebook\nsha: " + "a" * 40), entry.read_text()
        finally:
            entry.unlink(missing_ok=True)
            gate.atexit.unregister(entry.unlink)

    def test_temp_entry_is_gone_when_the_process_exits(self):
        env = {**os.environ, "TMPDIR": str(self.root / "scratch")}
        probe = (
            "import importlib.util,pathlib\n"
            f"spec = importlib.util.spec_from_file_location('cs', {str(SCRIPT)!r})\n"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            f"print(m.entry_at(pathlib.Path({str(self.fork)!r}), 'HEAD'))\n"
        )
        done = subprocess.run([sys.executable, "-c", probe], check=False,
                              capture_output=True, text=True, env=env)
        self.assertEqual(0, done.returncode, done.stderr[-600:])
        written = Path(done.stdout.strip().splitlines()[-1])
        self.assertFalse(written.exists(), written)
        self.assertEqual([], list(Path(env["TMPDIR"]).glob("catalog-entry-*.yaml")))

    def test_stale_debris_is_pruned_and_a_live_file_is_kept(self):
        gate = _load()
        scratch = Path(tempfile.gettempdir())
        stale = scratch / "catalog-entry-stale.yaml"
        live = scratch / "catalog-entry-live.yaml"
        stale.write_text("sha: dead\n")
        live.write_text("sha: live\n")
        old = time.time() - gate._TEMP_ENTRY_STALE_SECONDS - 60
        os.utime(stale, (old, old))

        gate._prune_temp_entries()

        self.assertFalse(stale.exists(), "an hour-old pinned-entry temp file is debris")
        self.assertTrue(live.exists(), "a just-written file may belong to a concurrent run")


if __name__ == "__main__":
    unittest.main()
