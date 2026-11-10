"""The v3 audit is a real gate, not a document: run it, pin it, and refuse a fabricated PASS.

``scripts/m4v-audit.py`` keeps its v2 claims (C-01 … C-15) because they are written against the v2
tokens and v2 screens. This module exercises the v3 audit the same way the v2 evidence gate is
reviewed: black-box, through its own command line, reading the JSON it writes.

Ungated (runs today):

  * the static audit exits 0 and writes a parseable audit with all twelve v3 claims;
  * the contract claims (V-01 contract shape, V-02 the 30 contrast gates, V-03 text placements) are
    PASS and are recomputed from ``contracts/cb.tokens.v3.json``;
  * the **module sha pin** holds: ``plugin_sha256`` and ``contract_sha256`` equal the hashes of the
    files on disk, so an audit cannot be inherited from a different build;
  * while the v3 material is absent, the paint claims are ``NOT-BUILT`` and never ``PASS`` — the
    audit may not claim what it did not measure;
  * ``--full`` refuses (exit 3) in **both** material states, naming the unimplemented paint phase —
    literals plus a browser plus ``cp-capture.mjs`` are not a measurement, so the phase may not
    succeed until it reads a frame and a stamp.

Gated by ``V3_REQUIRED`` (CP-020a flips it): every v3 claim must be PASS and the audit must report
``surfaces_built``. That is the RED the card hands over.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "v3-audit.py"
PLUGIN = ROOT / "desktop" / "plugin.js"
CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"

#: CP-020a flips this to True together with tests/test_desktop_tokens_v3.py.
V3_REQUIRED = False

CLAIMS = [f"V-{index:02d}" for index in range(1, 13)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_audit(full: bool = False) -> tuple[subprocess.CompletedProcess, dict | None]:
    tmp = tempfile.TemporaryDirectory(prefix="coursebook-v3audit-")
    out = Path(tmp.name)
    command = [sys.executable, str(SCRIPT), "--out", str(out)]
    if full:
        command.append("--full")
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
    audit = out / "audit.json"
    payload = json.loads(audit.read_text(encoding="utf-8")) if audit.is_file() else None
    tmp.cleanup()
    return result, payload


class V3AuditStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result, cls.audit = run_audit()

    def test_the_audit_runs_and_writes_parseable_evidence(self) -> None:
        self.assertEqual(self.result.returncode, 0, self.result.stderr[-3000:])
        self.assertIsNotNone(self.audit, "the audit wrote no audit.json")
        assert self.audit is not None
        self.assertEqual([item["id"] for item in self.audit["claims"]], CLAIMS)
        for item in self.audit["claims"]:
            self.assertTrue(item["claim"], item["id"])
            self.assertIn(item["status"], ("PASS", "FAIL", "NOT-BUILT"), item["id"])
            self.assertIsInstance(item["evidence"], dict, item["id"])

    def test_the_contract_claims_pass_and_are_recomputed(self) -> None:
        assert self.audit is not None
        statuses = self.audit["summary"]["claims"]
        for ident in ("V-01", "V-02", "V-03"):
            self.assertEqual(statuses[ident], "PASS", f"{ident} is {statuses[ident]}")
        gate_claim = next(item for item in self.audit["claims"] if item["id"] == "V-02")
        self.assertEqual(gate_claim["evidence"]["gates"], 60, "30 gates in two modes")
        self.assertEqual(gate_claim["evidence"]["failures"], [])
        self.assertIsNotNone(gate_claim["evidence"]["tightest"])

    def test_the_module_sha_pin_matches_the_files_on_disk(self) -> None:
        assert self.audit is not None
        summary = self.audit["summary"]
        self.assertEqual(summary["plugin_sha256"], sha256(PLUGIN),
                         "the audit was produced from a different plugin.js")
        self.assertEqual(summary["contract_sha256"], sha256(CONTRACT),
                         "the audit was produced from a different contract")
        self.assertEqual(len(summary["plugin_sha256"]), 64)
        self.assertTrue(summary["commit"], "the audit records no commit")

    def test_absent_v3_material_is_not_built_never_pass(self) -> None:
        assert self.audit is not None
        summary = self.audit["summary"]
        if summary["surfaces_built"]:
            self.skipTest("v3 material exists; the gated class owns the PASS assertions")
        gated = [f"V-{index:02d}" for index in range(4, 13)]
        for ident in gated:
            self.assertEqual(summary["claims"][ident], "NOT-BUILT", ident)
        for item in self.audit["claims"]:
            if item["status"] == "NOT-BUILT":
                self.assertIn("reason", item["evidence"], item["id"])

    def test_full_phase_refuses_instead_of_inventing_frames(self) -> None:
        # Not material-conditional: this assertions holds whether or not CP-020a has landed the
        # literals. The paint phase reads no frame and verifies no stamp, so it must never exit 0
        # while that is true — the old skip let an exit-0 "painted audit" through.
        result, payload = run_audit(full=True)
        self.assertEqual(result.returncode, 3, result.stdout[-2000:] + result.stderr[-2000:])
        self.assertIn("refused", result.stderr.lower())
        self.assertIn("unimplemented", result.stderr.lower())
        self.assertIn("stamp", result.stderr.lower())
        # No PASS may be written by a phase that did not measure anything.
        if payload is not None and not payload["summary"]["surfaces_built"]:
            self.assertTrue(payload["summary"]["not_built"])


@unittest.skipUnless(V3_REQUIRED, "CP-020a flips V3_REQUIRED; see tests/test_desktop_tokens_v3.py")
class V3AuditBuiltTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result, cls.audit = run_audit()

    def test_every_v3_claim_passes_once_the_material_exists(self) -> None:
        self.assertIsNotNone(self.audit, self.result.stderr[-3000:])
        assert self.audit is not None
        summary = self.audit["summary"]
        self.assertTrue(summary["surfaces_built"], summary)
        self.assertEqual(summary["failed"], [], summary["failed"])
        self.assertEqual(summary["not_built"], [], summary["not_built"])
        self.assertEqual(self.result.returncode, 0, self.result.stderr[-3000:])


def load_audit_module():
    """Import ``scripts/v3-audit.py`` by path so a control can replay ``static_claims``."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("coursebook_v3_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V3AuditNormalisationTest(unittest.TestCase):
    """D5: the audit's banned-token scans must see the CSS a browser sees.

    The gate and the audit are separate implementations of the same claims (§3 promises they agree),
    so a fix in only one of them would pass its own tests and leave the other reporting green on a
    glass blur, a raw shadow or a 900 ms transition. This control replays the audit's own
    ``static_claims`` on the same compliant/mutated stylesheets ``V3GateBitesTest`` uses.
    """

    def setUp(self) -> None:
        from tests.test_desktop_gate_scope import V3GateBitesTest

        self.audit = load_audit_module()
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.builder = V3GateBitesTest("test_a_compliant_v3_block_passes_every_gated_claim")

    def statuses(self, css: str) -> dict[str, str]:
        _, summary = self.audit.static_claims(self.contract, self.builder.module_text(css=css))
        return summary["claims"]

    def test_the_compliant_block_passes_every_static_v3_claim(self) -> None:
        statuses = self.statuses(self.builder.good_css())
        for index in range(4, 13):
            ident = f"V-{index:02d}"
            self.assertEqual(statuses[ident], "PASS", f"{ident} on the compliant block")

    def test_the_banned_token_scans_are_case_and_vendor_normalised(self) -> None:
        good = self.builder.good_css()
        cases = (
            ("V-06", "Backdrop-Filter: Blur(8px);",
             good.replace("container-type: inline-size;", "Backdrop-Filter: Blur(8px);")),
            ("V-07", "-webkit-box-shadow",
             good.replace("box-shadow: var(--cb3-elev-1);",
                          "-webkit-box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);")),
            ("V-11", "900MS",
             good.replace("transition: opacity var(--cb3-dur-route);", "transition: opacity 900MS;")),
            ("V-11", "ANIMATION: spin INFINITE",
             good.replace("container-type: inline-size;", "ANIMATION: spin INFINITE;")),
        )
        for ident, mutation, css in cases:
            with self.subTest(claim=ident, mutation=mutation):
                self.assertNotEqual(css, good, "the mutation did not apply")
                self.assertEqual(
                    self.statuses(css)[ident], "FAIL",
                    f"{ident} reported PASS on {mutation!r}: the audit does not normalise the scan",
                )

    def test_css_number_spellings_fail_their_claim(self) -> None:
        # D6: the audit's V-11/V-12 must read the same legal `<number>` spellings the gate does
        # (leading dot, scientific notation); otherwise both report PASS on an out-of-table
        # duration or a viewport measurement.
        good = self.builder.good_css()
        cases = (
            ("V-11", "transition: opacity .9s",
             good.replace("transition: opacity var(--cb3-dur-route);", "transition: opacity .9s;")),
            ("V-11", "transition: opacity 1e3ms",
             good.replace("transition: opacity var(--cb3-dur-route);", "transition: opacity 1e3ms;")),
            ("V-11", "transition-duration: .4s",
             good.replace("transition: opacity var(--cb3-dur-route);", "transition-duration: .4s;")),
            ("V-12", "padding: .5vw",
             good.replace("container-type: inline-size;", "padding: .5vw;")),
            # CP-003c (R1): units are ASCII case-insensitive, so the audit's V-12 must see
            # `100VW` / `1E3VW` exactly like `100vw`. Without the flag it reported PASS.
            ("V-12", "padding: 100VW",
             good.replace("container-type: inline-size;", "padding: 100VW;")),
            ("V-12", "padding: 100Vw",
             good.replace("container-type: inline-size;", "padding: 100Vw;")),
            ("V-12", "padding: 1E3VW",
             good.replace("container-type: inline-size;", "padding: 1E3VW;")),
        )
        for ident, mutation, css in cases:
            with self.subTest(claim=ident, mutation=mutation):
                self.assertNotEqual(css, good, "the mutation did not apply")
                self.assertEqual(
                    self.statuses(css)[ident], "FAIL",
                    f"{ident} reported PASS on {mutation!r}: the audit cannot parse the number",
                )


if __name__ == "__main__":
    unittest.main()
