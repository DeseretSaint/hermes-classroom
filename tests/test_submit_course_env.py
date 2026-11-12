"""Every ``git``/``gh`` child gets an explicit allowlisted environment.

The Hermes process carries model-provider keys. A child that fetches, commits, pushes or forks
does not need them, so ``scripts/submit-course.py`` passes its own minimal environment. SSH and
https must keep working: ``SSH_AUTH_SOCK``, every ``GIT_*`` (including ``GIT_SSH_COMMAND``) and
both proxy spellings survive.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SUBMIT = ROOT / "scripts" / "submit-course.py"


def _load_submit():
    spec = importlib.util.spec_from_file_location("cb_submit_course_env_under_test", SUBMIT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SubmitCourseEnvTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_submit()

    def test_provider_keys_do_not_reach_a_git_child(self) -> None:
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/learner",
            "LANG": "en_GB.UTF-8",
            "ANTHROPIC_API_KEY": "sk-ant-secret",
            "OPENAI_API_KEY": "sk-openai-secret",
            "HERMES_HOME": "/home/learner/.hermes",
            "GIT_SSH_COMMAND": "ssh -i /home/learner/.ssh/id_ed25519",
            "GIT_AUTHOR_NAME": "Learner",
            "SSH_AUTH_SOCK": "/run/user/1000/ssh-agent.sock",
            "HTTPS_PROXY": "http://proxy.invalid:3128",
            "CB_STORE_ROOT": "/tmp/unreviewed-worktree",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            clean = self.module._clean_env()
            extended = self.module._clean_env({"GH_TOKEN": "ghs_explicit"})

        self.assertEqual(clean["PATH"], "/usr/bin:/bin")
        self.assertEqual(clean["HOME"], "/home/learner")
        self.assertEqual(clean["LANG"], "en_GB.UTF-8")
        self.assertEqual(clean["SSH_AUTH_SOCK"], "/run/user/1000/ssh-agent.sock")
        self.assertEqual(clean["HTTPS_PROXY"], "http://proxy.invalid:3128")
        self.assertEqual(clean["GIT_SSH_COMMAND"], "ssh -i /home/learner/.ssh/id_ed25519")
        self.assertEqual(clean["GIT_AUTHOR_NAME"], "Learner")
        self.assertNotIn("ANTHROPIC_API_KEY", clean)
        self.assertNotIn("OPENAI_API_KEY", clean)
        self.assertNotIn("HERMES_HOME", clean)
        self.assertNotIn("CB_STORE_ROOT", clean)
        self.assertEqual(extended["GH_TOKEN"], "ghs_explicit")

    def test_git_and_run_pass_the_clean_environment(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin", "OPENAI_API_KEY": "sk-nope"}, clear=True):
            with mock.patch.object(self.module.subprocess, "run", return_value=completed) as run:
                self.module._git(ROOT, "status", "--short")
                git_env = run.call_args.kwargs["env"]
                self.module._run(["gh", "api", "user"], cwd=ROOT)
                run_env = run.call_args.kwargs["env"]
        for env in (git_env, run_env):
            self.assertEqual(env["PATH"], "/usr/bin")
            self.assertNotIn("OPENAI_API_KEY", env)


if __name__ == "__main__":
    unittest.main()
