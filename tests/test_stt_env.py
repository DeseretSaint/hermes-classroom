"""The ffmpeg decoder gets an explicit minimal environment, never the host's.

``stt.py`` runs a host binary on a learner's audio. That child has no business seeing the
model-provider keys the Hermes process carries, so the decode call passes its own allowlist. The
test checks the helper and the actual subprocess call, with no audio and no ffmpeg binary needed.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from coursebook import stt


class SttCleanEnvTest(unittest.TestCase):
    def test_helper_drops_provider_keys_and_keeps_the_decoder_names(self) -> None:
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/learner",
            "LANG": "en_GB.UTF-8",
            "OPENAI_API_KEY": "sk-openai-secret",
            "ANTHROPIC_API_KEY": "sk-ant-secret",
            "HERMES_HOME": "/home/learner/.hermes",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            clean = stt._clean_env()
        self.assertEqual(clean["PATH"], "/usr/bin:/bin")
        self.assertEqual(clean["HOME"], "/home/learner")
        self.assertEqual(clean["LANG"], "en_GB.UTF-8")
        self.assertNotIn("OPENAI_API_KEY", clean)
        self.assertNotIn("ANTHROPIC_API_KEY", clean)
        self.assertNotIn("HERMES_HOME", clean)

    def test_decode_passes_the_clean_environment_to_ffmpeg(self) -> None:
        done = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"\x00\x00", stderr=b"")
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin", "OPENAI_API_KEY": "sk-nope"}, clear=True):
            with mock.patch.object(stt.shutil, "which", return_value="/usr/bin/ffmpeg"):
                with mock.patch.object(stt.subprocess, "run", return_value=done) as run:
                    pcm = stt.LocalWhisperAdapter()._decode(Path("/tmp/take.wav"))
        self.assertEqual(pcm, b"\x00\x00")
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertEqual(run.call_args.args[0][0], "/usr/bin/ffmpeg")


if __name__ == "__main__":
    unittest.main()
