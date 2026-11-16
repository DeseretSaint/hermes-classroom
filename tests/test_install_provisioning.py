"""Provisioning checks: what a fresh user install must get right before a course can exist.

These run against the real checkout (that is the package a user installs) plus one deliberately
incomplete copy, so the findings prove the code reads the package rather than a fixture.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coursebook import db, install_check

REPO = Path(__file__).resolve().parent.parent


class ProvisioningCheckTest(unittest.TestCase):
    def codes(self, findings) -> set[str]:
        return {finding.code for finding in findings}

    def test_an_absent_optional_dependency_degrades_its_lane_and_still_reports_DEPS_OK(self) -> None:
        """A supported install without `json_repair` is not an incomplete package.

        The product has a typed degraded path for every optional wheel (docs/INSTALL.md): the
        malformed-answer repair is skipped and the answer is refused as before. `DEPS_OK` must
        therefore survive a warning-level miss, carrying the caveat, or a legal install is
        reported as broken — which is exactly how `test_the_shipped_checkout_provisions_cleanly`
        failed on a venv that simply lacked `json_repair` (t_3a77c891).
        """
        with mock.patch.object(
            install_check, "_dependency_importable",
            side_effect=lambda module: module != "json_repair",
        ):
            findings = install_check.inspect_provisioning(REPO)
        codes = self.codes(findings)
        self.assertIn("DEPS_OK", codes, [finding.__dict__ for finding in findings])
        missing = [finding for finding in findings if finding.code == "DEP_MISSING"]
        self.assertEqual(len(missing), 1, [finding.__dict__ for finding in findings])
        self.assertEqual(missing[0].level, "warning")
        self.assertIn("json_repair", missing[0].message)
        self.assertIn("requirements-dev.txt", missing[0].fix or "")
        deps_ok = next(finding for finding in findings if finding.code == "DEPS_OK")
        self.assertIn("3 of 4", deps_ok.message)
        self.assertIn("optional wheel", deps_ok.message)
        self.assertFalse([finding for finding in findings if finding.level == "error"])

    def test_an_absent_required_dependency_withholds_DEPS_OK_and_fails_the_check(self) -> None:
        """`jsonschema` is graded as an error; without it `DEPS_OK` must not be emitted."""
        with mock.patch.object(
            install_check, "_dependency_importable",
            side_effect=lambda module: module != "jsonschema",
        ):
            findings = install_check.inspect_provisioning(REPO)
        self.assertNotIn("DEPS_OK", self.codes(findings))
        errors = [finding for finding in findings if finding.level == "error"]
        self.assertEqual([finding.code for finding in errors], ["DEP_MISSING"])
        self.assertIn("jsonschema", errors[0].message)

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
