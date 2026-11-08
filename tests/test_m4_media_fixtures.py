"""The M4 media gate must own its fixtures, not read a prunable scratch directory.

H-136: `scripts/m4v-audit.py` used to read `~/.hermes/cache/scratch/cb-media-image.png` and
`cb-media-audio.mp3`. The scratch janitor pruned them, so every honest re-pin of the M4 evidence
failed C-07/C-13 with `audio_elements: 0`. These tests hold the gate to committed, real media.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "media"
IMAGE = FIXTURES / "cb-media-image.png"
AUDIO = FIXTURES / "cb-media-audio.mp3"
AUDIT = ROOT / "audit" / "visual" / "m4-visual" / "audit.json"


class MediaFixtureTest(unittest.TestCase):
    def test_fixtures_are_committed_real_media(self) -> None:
        self.assertTrue(IMAGE.is_file(), "tests/fixtures/media/cb-media-image.png is missing")
        self.assertTrue(AUDIO.is_file(), "tests/fixtures/media/cb-media-audio.mp3 is missing")
        self.assertTrue(IMAGE.read_bytes().startswith(b"\x89PNG"), "image fixture is not a PNG")
        self.assertTrue(AUDIO.read_bytes().startswith(b"\xff\xf3"), "audio fixture is not an MPEG frame")

    def test_resolution_prefers_env_then_committed_fixture(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("m4v_audit", ROOT / "scripts" / "m4v-audit.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.IMAGE_PATH, IMAGE)
        self.assertEqual(module.AUDIO_PATH, AUDIO)
        fixtures = module.media_fixtures()
        self.assertEqual(fixtures["image"]["sha256"], hashlib.sha256(IMAGE.read_bytes()).hexdigest())
        self.assertEqual(fixtures["audio"]["sha256"], hashlib.sha256(AUDIO.read_bytes()).hexdigest())
        self.assertTrue(fixtures["image"]["magic_ok"] and fixtures["audio"]["magic_ok"])

    def test_the_committed_evidence_pins_the_committed_fixtures(self) -> None:
        if not AUDIT.is_file():
            self.skipTest("no M4 visual audit evidence committed")
        evidence = json.loads(AUDIT.read_text(encoding="utf-8"))
        fixtures = evidence["summary"]["media_fixtures"]
        self.assertEqual(fixtures["image"]["sha256"], hashlib.sha256(IMAGE.read_bytes()).hexdigest())
        self.assertEqual(fixtures["audio"]["sha256"], hashlib.sha256(AUDIO.read_bytes()).hexdigest())
        review = next(item for item in evidence["claims"] if item["id"] == "C-14")["evidence"]["independent_review"]
        self.assertEqual(review["artifact"], "tests/fixtures/media/cb-media-image.png")
        self.assertEqual(review["sha256"], hashlib.sha256(IMAGE.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
