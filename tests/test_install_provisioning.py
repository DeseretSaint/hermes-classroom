"""Provisioning checks: what a fresh user install must get right before a course can exist.

These run against the real checkout (that is the package a user installs) plus one deliberately
incomplete copy, so the findings prove the code reads the package rather than a fixture.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from coursebook import db, install_check

REPO = Path(__file__).resolve().parent.parent


class ProvisioningCheckTest(unittest.TestCase):
    def codes(self, findings) -> set[str]:
        return {finding.code for finding in findings}

    def test_the_shipped_checkout_provisions_cleanly(self) -> None:
        findings = install_check.inspect_provisioning(REPO)
        codes = self.codes(findings)
        for expected in ("SKILLS_OK", "TOOLS_OK", "CONTRACTS_OK", "DEPS_OK", "BUNDLED_PACKS_OK"):
            self.assertIn(expected, codes)
        self.assertFalse(
            [finding for finding in findings if finding.level == "error"],
            [finding.__dict__ for finding in findings],
        )

    def test_a_package_without_bundled_skills_is_an_error(self) -> None:
        work = tempfile.mkdtemp(prefix="cb-provisioning-")
        self.addCleanup(lambda: __import__("shutil").rmtree(work, True))
        source = Path(work)
        (source / "desktop").mkdir()
        (source / "plugin.yaml").write_text("name: coursebook\n", encoding="utf-8")
        findings = install_check.inspect_provisioning(source)
        self.assertIn("SKILLS_MISSING", self.codes(findings))

    def test_a_profile_database_must_match_this_builds_schema(self) -> None:
        home = tempfile.mkdtemp(prefix="cb-provisioning-home-")
        previous = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = home
        try:
            db.migrate()
        finally:
            if previous is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous
        self.addCleanup(lambda: __import__("shutil").rmtree(home, True))
        findings = install_check.inspect_provisioning(REPO, Path(home))
        self.assertIn("DB_SCHEMA_OK", self.codes(findings))

    def test_an_empty_home_reports_first_use_not_a_failure(self) -> None:
        home = tempfile.mkdtemp(prefix="cb-provisioning-empty-")
        self.addCleanup(lambda: __import__("shutil").rmtree(home, True))
        findings = install_check.inspect_provisioning(REPO, Path(home))
        self.assertIn("DB_NOT_CREATED", self.codes(findings))
        self.assertFalse([finding for finding in findings if finding.level == "error"])

    def test_the_cli_runs_provisioning_without_a_home(self) -> None:
        code = install_check.main(["--source", str(REPO), "--provisioning", "--quiet"])
        self.assertEqual(code, 0)
