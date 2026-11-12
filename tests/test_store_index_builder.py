"""``store/index.json`` is rebuilt by the installed builder, not the fetched tree's copy.

``scripts/store_index.py`` resolves its own checkout and inserts it on ``sys.path`` before
importing ``coursebook``. Running the fetched worktree's copy — or passing ``CB_STORE_ROOT``,
which the builder treats the same way — would execute code from outside the reviewed pin on the
author's machine. The publish path runs this checkout's script with ``--root <worktree>``, which
moves only the data root after the import has come from the installed copy.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBMIT = ROOT / "scripts" / "submit-course.py"


def _load_submit():
    spec = importlib.util.spec_from_file_location("cb_submit_course_index_under_test", SUBMIT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StoreIndexBuilderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_submit()

    def test_builder_is_the_installed_copy_with_root_not_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cb-fetched-worktree-") as temporary:
            work = Path(temporary)
            command = self.module._index_command(work)

        installed = (ROOT / "scripts" / "store_index.py").resolve()
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(Path(command[1]).resolve(), installed,
                         "the index builder is not this checkout's script")
        self.assertNotEqual(Path(command[1]).resolve(), (work / "scripts" / "store_index.py").resolve())
        self.assertIn("--root", command)
        self.assertEqual(command[command.index("--root") + 1], str(work))

    def test_publish_runs_the_index_command_from_the_fetched_worktree(self) -> None:
        """The invocation the publish path makes is exactly ``_index_command(work)``."""
        source = SUBMIT.read_text(encoding="utf-8")
        self.assertIn("_run(_index_command(work), cwd=work)", source)
        self.assertNotIn('str(work / "scripts" / "store_index.py")', source)
        self.assertNotIn("CB_STORE_ROOT=", source)


if __name__ == "__main__":
    unittest.main()
