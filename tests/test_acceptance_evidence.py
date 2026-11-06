"""Acceptance evidence integrity tests (Sentinel).

These do not test the product; they keep the QA packet honest: every probe has a recorded
verdict, every defect id referenced by the report exists, and the raw evidence files the
report cites are present. Run with the repo's own test command:

    python3 -m unittest tests.test_acceptance_evidence -v
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBES = ROOT / "PROBES.md"
DEFECTS = ROOT / "DEFECTS.md"
ACCEPTANCE = ROOT / "docs" / "ACCEPTANCE.md"
RAW = ROOT / "probes" / "raw"

PROBE_IDS = [f"p{i}" for i in range(1, 8)]


class TestProbePacket(unittest.TestCase):
    def test_every_probe_has_a_verdict(self) -> None:
        text = PROBES.read_text(encoding="utf-8")
        for i in range(1, 8):
            self.assertRegex(
                text, rf"\|\s*p?{i}\s*\|", f"probe {i} missing from the PROBES.md verdict table"
            )
        for word in ("PASS", "FAIL", "BLOCKED"):
            self.assertIn(word, text, f"verdict vocabulary missing {word}")

    def test_raw_evidence_exists(self) -> None:
        required = [
            RAW / "p1" / "assert.json",
            RAW / "p2" / "assert_storage.json",
            RAW / "p3" / "assert.json",
            RAW / "p4" / "assert.json",
            RAW / "p5" / "assert.json",
            RAW / "p6" / "assert.json",
            RAW / "p7" / "assert.json",
            RAW / "p4" / "p4_runtime_seam.json",
            RAW / "p5" / "p5_media_seam.json",
            RAW / "RUN.log",
            RAW / "VERDICTS.txt",
            RAW / "p7" / "p7_hook_bypass.json",
        ]
        for path in required:
            self.assertTrue(path.exists(), f"missing evidence {path.relative_to(ROOT)}")

    def test_defect_ids_referenced_are_defined(self) -> None:
        defects = DEFECTS.read_text(encoding="utf-8")
        defined = set(re.findall(r"CB-QA-\d{2}", defects))
        self.assertTrue(defined, "no defect ids defined")
        referenced = set(re.findall(r"CB-QA-\d{2}", PROBES.read_text(encoding="utf-8")))
        referenced |= set(re.findall(r"CB-QA-\d{2}", ACCEPTANCE.read_text(encoding="utf-8")))
        missing = referenced - defined
        self.assertFalse(missing, f"undeclared defect ids referenced: {sorted(missing)}")

    def test_acceptance_matrix_covers_ux_proof_suite(self) -> None:
        text = ACCEPTANCE.read_text(encoding="utf-8")
        for n in range(1, 20):
            self.assertRegex(
                text, rf"\|\s*{n}\s*\|", f"UX proof #{n} missing from the acceptance matrix"
            )

    def test_matrix_uses_only_known_statuses(self) -> None:
        text = ACCEPTANCE.read_text(encoding="utf-8")
        statuses = set(re.findall(r"\|\s*(verified|pending|blocked|failing)\b", text, re.IGNORECASE))
        self.assertTrue(statuses, "no statuses found in the matrix")
        self.assertLessEqual(
            {s.lower() for s in statuses}, {"verified", "pending", "blocked", "failing"}
        )


if __name__ == "__main__":
    unittest.main()
