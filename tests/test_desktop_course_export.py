"""H-08: the normal course surface has a real export action (Desktop half).

The backend proof lives in ``tests/test_course_export.py``. This module asserts the shipped module's
half: the write call carries the reviewed content hash and an idempotency key and nothing else, the
course view list actually offers Export, and every backend refusal reason has human copy instead of
a raw code. A live Desktop window is not required for any of those facts.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = """
import {
  courseExportRequest,
  courseExportRepair,
  COURSE_EXPORT_BLOCKED_COPY,
  COURSE_EXPORT_PRIVATE_ROWS,
  COURSE_EXPORT_REPAIR,
  LEARNING_VIEWS
} from './plugin.js'

const row = { enrollment_id: 'enr_course_export', course_id: 'crs_course_export' }
const hash = 'sha256:' + 'a'.repeat(64)
const first = courseExportRequest(row, hash)
const second = courseExportRequest(row, hash)
process.stdout.write(
  JSON.stringify({
    first,
    second,
    reasons: Object.keys(COURSE_EXPORT_BLOCKED_COPY),
    copy: COURSE_EXPORT_BLOCKED_COPY,
    private_rows: COURSE_EXPORT_PRIVATE_ROWS,
    repair: COURSE_EXPORT_REPAIR,
    repairs: Object.keys(COURSE_EXPORT_BLOCKED_COPY).map((reason) => [reason, courseExportRepair(reason)]),
    views: LEARNING_VIEWS
  })
)
"""


class CourseExportSurfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to run the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-course-export-ui-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.root = root
        result = subprocess.run(
            ["node", str(root / "harness.mjs")],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-2000:])
        cls.out = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_the_write_call_carries_the_reviewed_hash_and_a_key_only(self) -> None:
        first = self.out["first"]
        self.assertEqual(first["method"], "course.export")
        self.assertEqual(
            first["payload"], {"enrollment_id": "enr_course_export", "expected_content_hash": "sha256:" + "a" * 64}
        )
        self.assertTrue(first["options"]["idempotencyKey"].startswith("cb-course-export-"))
        # A double click must be a replay, not a second archive: each call mints its own key.
        self.assertNotEqual(first["options"]["idempotencyKey"], self.out["second"]["options"]["idempotencyKey"])

    def test_the_course_view_list_offers_export(self) -> None:
        views = {item["id"]: item["label"] for item in self.out["views"]}
        self.assertEqual(views.get("export"), "Export")
        # The existing tabs are untouched and still ordered before it.
        self.assertEqual(
            [item["id"] for item in self.out["views"]],
            ["overview", "textbook", "notebook", "quizzes", "plan", "evidence", "sources", "export"],
        )

    def test_every_backend_refusal_has_human_copy(self) -> None:
        for reason in (
            "plan_not_approved",
            "lessons_not_validated",
            "no_generated_content",
            "changes_need_review",
            "export_not_exportable",
            "export_write_failed",
            "course_pack_backed",
        ):
            with self.subTest(reason=reason):
                self.assertIn(reason, self.out["reasons"])
                self.assertGreater(len(self.out["copy"][reason]), 40)

    def test_the_pack_backed_copy_points_at_pack_export(self) -> None:
        self.assertIn("pack surface", self.out["copy"]["course_pack_backed"])
        # A pack-backed course's one repair is the Library, where pack export lives.
        self.assertEqual(self.out["repair"]["course_pack_backed"]["target"], "library")

    def test_every_refusal_that_has_a_repair_points_at_a_real_surface(self) -> None:
        repairs = {reason: repair for reason, repair in self.out["repairs"]}
        for reason in (
            "plan_not_approved",
            "lessons_not_validated",
            "no_generated_content",
            "changes_need_review",
            "export_not_exportable",
        ):
            with self.subTest(reason=reason):
                self.assertIsNotNone(repairs[reason], reason)
                self.assertEqual(repairs[reason]["target"], "plan")
                self.assertGreater(len(repairs[reason]["label"]), 10)
        # A write failure has no repair but trying again, so it is not silently given a fake one.
        self.assertIsNone(repairs["export_write_failed"])

    def test_the_preview_names_what_stays_behind(self) -> None:
        rows = self.out["private_rows"]
        self.assertGreaterEqual(len(rows), 4)
        labels = " ".join(row["label"] for row in rows).lower()
        for needle in ("attempt", "notebook", "observation", "provider", "enrollment"):
            self.assertIn(needle, labels)
        # The panel is a statement, not a list of files: none of its rows may name an archive file.
        self.assertFalse(any(row["value"] for row in rows if ".md" in row["value"]))

    def test_the_surface_is_wired_into_the_course_detail(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn("jsx(CourseExportView, {", source)
        self.assertIn("onRepair: () => selectView('plan')", source)
        self.assertIn("'Export this course'", source)
        self.assertIn("'course.export.read'", source)
        # The no-upload statement and the rights line are the backend's text, printed verbatim.
        self.assertIn("read.no_upload", source)
        self.assertIn("read.rights", source)
        # No fake artifact: the surface only offers a download when the backend named one.
        self.assertIn("artifact.download.url", source)
        # H-121: the stays/goes preview and the one-repair action are stable handles for a live probe.
        self.assertIn("'data-cb-export-leaves': ''", source)
        self.assertIn("'data-cb-export-blocked':", source)
        self.assertIn("'data-cb-export-repair':", source)
        self.assertIn("data-cb-export-hash", source)
        self.assertIn("data-cb-export-done", source)
        self.assertIn("data-cb-export-portable", source)

    def test_the_import_confirmation_keeps_pack_and_enrollment_identity_apart(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn("Pack (shared content)", source)
        self.assertIn("Enrollment (this profile)", source)
        self.assertIn("data-cb-import-done", source)
        self.assertIn("data-cb-import-identity", source)
        self.assertIn("setMode(mode)", source)


if __name__ == "__main__":
    unittest.main()
