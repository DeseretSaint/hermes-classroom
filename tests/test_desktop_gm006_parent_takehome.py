"""GM-006 — the Parent Studio take-home surfaces.

Two kinds of proof, both real:

* the backend half drives the shipped ``takehome.*`` handlers through ``api.dispatch`` against a
  real migrated SQLite database: a Game course and a Textbook course both open, the learner page
  carries no answer guide, the printed pages are real, and a full preview→create→approve→export
  cycle leaves the source course byte-for-byte unchanged;
* the desktop half renders the shipped module through React and asserts the composed DOM: the
  source shelf and picker, the print proof of actual page sheets (not a thumbnail), the
  parent-only answer guide, and the absence of XP, stars or ratings in the pack.

What this does not prove: live provider art, or that the pixels match the approved concept frames.
The isolated rig and ``docs/visual-review/gm-006/`` carry those.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from coursebook import db, domain, generation
from tests.kernel_support import KernelCase, criteria_with, numeric_spec
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules
from tests.test_gm_takehome import ANSWER_MARKER, GEN_HASH, LEARNER_MARKER, NOW, RUBRIC_MARKER, page_document

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

STATIC_HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'
import {
  TakeHomeShelf, TakeHomeSourcePanel, TakeHomeProof, TakeHomePackPanel,
  cbTakeHomeProofPages, cbTakeHomePageOrder
} from './plugin.js'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const quiet = () => {}
const out = (node) => process.stdout.write(renderToStaticMarkup(node))

if (payload.kind === 'shelf') {
  out(React.createElement(TakeHomeShelf, {
    rows: payload.rows, status: payload.status || 'ready', error: payload.error || null,
    onSelect: quiet, onRetry: quiet
  }))
} else if (payload.kind === 'source') {
  out(React.createElement(TakeHomeSourcePanel, {
    courseTitle: payload.courseTitle || 'Braising at home', source: payload.source,
    status: payload.status || 'ready', error: payload.error || null,
    onSelectObjective: quiet, onRetry: quiet, onBack: quiet
  }))
} else if (payload.kind === 'proof') {
  out(React.createElement(TakeHomeProof, {
    pages: payload.pages, audience: payload.audience || 'parent',
    title: payload.title || 'Braising at home', printProfile: payload.printProfile || null
  }))
} else if (payload.kind === 'pack') {
  out(React.createElement(TakeHomePackPanel, {
    courseTitle: payload.courseTitle || 'Braising at home', source: payload.source,
    objective: payload.objective, kind: payload.makeKind || 'print_pack',
    audience: payload.audience || 'parent', onKind: quiet, onAudience: quiet,
    preview: payload.preview || null, previewStatus: payload.previewStatus || 'idle',
    previewError: payload.previewError || null, onPreview: quiet, onRetryPreview: quiet,
    onBack: quiet, pack: payload.pack || null, busy: payload.busy || null,
    error: payload.error || null, exportError: payload.exportError || null,
    exported: payload.exported || null, artifact: payload.artifact || null,
    onSaveDraft: quiet, onApprove: quiet, onExport: quiet
  }))
} else if (payload.kind === 'helpers') {
  out(React.createElement('div', {
    'data-pages': String(cbTakeHomeProofPages({ pages: payload.pages, audience: payload.audience }).length),
    'data-order': cbTakeHomePageOrder(payload.pages).map((page) => page.role).join(',')
  }))
}
"""


class _RenderRig:
    """One node harness shared by every class in this module (built once, cleaned at exit)."""

    def __init__(self) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        self.tmp = tempfile.TemporaryDirectory(prefix="coursebook-gm006-")
        self.root = Path(self.tmp.name)
        (self.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (self.root / "static.mjs").write_text(STATIC_HARNESS, encoding="utf-8")
        node_modules = self.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

    def render(self, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "static.mjs"), str(case)],
            cwd=self.root, capture_output=True, text=True, timeout=240,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-4000:])
        return result.stdout


_RIG: _RenderRig | None = None


def render(payload: dict) -> str:
    global _RIG
    if _RIG is None:
        _RIG = _RenderRig()
    return _RIG.render(payload)


# ── fixtures: a real course with one validated lesson per section ─────────────


class TakeHomeCase(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.work = Path(tempfile.mkdtemp(prefix="coursebook-gm006-fixture-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        with db.read() as connection:
            generation.ensure_schema(connection)

    def seed_course(
        self,
        *,
        title: str = "Braising at home",
        sections: int = 2,
        presentation_mode: str | None = None,
    ) -> dict:
        payload = {
            "title": title,
            "recipe": "committed",
            "goal": "Braise short ribs at home without a pressure cooker.",
            "locale": "en-US",
        }
        if presentation_mode:
            payload["presentation_mode"] = presentation_mode
        created = self.ok("course.create", payload)["result"]
        course_id = created["course_id"]
        plan_id = created["plan_id"]
        objective_ids: list[str] = []
        for ordinal in range(1, sections + 1):
            objective_ids.append(
                domain.record_objective(
                    plan_id,
                    title=f"Objective {ordinal}: sear and braise",
                    evidence_target="production",
                    criteria=criteria_with(numeric_spec()),
                )
            )
        for ordinal, objective_id in enumerate(objective_ids, start=1):
            self.execute(
                "UPDATE objectives SET evidence_criteria_json = ? WHERE id = ?",
                (
                    json.dumps([f"Criterion {ordinal}: browns the meat on every face"]),
                    objective_id,
                ),
            )
        enrollment_id = self.new_enrollment(course_id)
        self.approve(enrollment_id, plan_id, 0)
        seeded = {"course_id": course_id, "plan_id": plan_id, "objective_ids": objective_ids}
        self.seed_validated_lessons(seeded)
        return seeded

    def seed_validated_lessons(self, seeded: dict) -> None:
        plan_id = seeded["plan_id"]
        course_id = seeded["course_id"]
        objective_ids = seeded["objective_ids"]
        with db.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO gen_plan_documents (id, plan_id, course_id,"
                " request_fingerprint, plan_hash, document_json, research_json, generation_state,"
                " validation_id, result_json, created_at)"
                " VALUES (?, ?, ?, 'fp', ?, '{}', '{}', 'draft', NULL, '{}', ?)",
                (f"gpd_{plan_id}", plan_id, course_id, GEN_HASH, NOW),
            )
            for ordinal in range(1, len(objective_ids) + 1):
                section_id = f"sec_{ordinal}_{plan_id}"
                lesson_id = f"lsn_{ordinal}_{plan_id}"
                check_id = f"chk_{ordinal}_{plan_id}"
                title = f"Section {ordinal}: the sear"
                connection.execute(
                    "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
                    " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
                    " VALUES (?, ?, ?, ?, ?, 'Sear first, then braise.', ?, '[]', '[]')",
                    (section_id, plan_id, ordinal, GEN_HASH, title, f"[{ordinal}]"),
                )
                connection.execute(
                    "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
                    " page_json, media_json, parent_notes_json, rejection_reasons_json,"
                    " validation_id, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, 1, 'validated', ?, '[]', '{}', '[]', NULL, ?, ?)",
                    (lesson_id, plan_id, section_id, GEN_HASH, json.dumps(page_document(title)), NOW, NOW),
                )
                connection.execute(
                    "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
                    " rubric_json, reference_json, locale, audit_state, state, created_at)"
                    " VALUES (?, ?, 1, 'production', ?, ?, ?, 'en-US', 'passed', 'open', ?)",
                    (
                        check_id,
                        objective_ids[ordinal - 1],
                        json.dumps({"prompt": "When do the ribs go into the pan?", "format": "selection"}),
                        json.dumps({"criteria": [{"criterion": "b", "description": RUBRIC_MARKER}]}),
                        json.dumps({"reference_answer": ANSWER_MARKER, "accepted_answers": []}),
                        NOW,
                    ),
                )
                connection.execute(
                    "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref) VALUES (?, ?, ?)",
                    (lesson_id, check_id, ordinal),
                )

    def lesson_version(self, seeded: dict, index: int = 0) -> str:
        row = self.rows(
            "SELECT l.id AS lesson_id, l.version FROM gen_lessons l"
            " JOIN gen_plan_sections s ON s.id = l.section_id"
            " WHERE s.plan_id = ? ORDER BY s.ordinal LIMIT 1 OFFSET ?",
            (seeded["plan_id"], index),
        )[0]
        return f"{row['lesson_id']}:v{int(row['version'])}"

    def sources(self, seeded: dict) -> dict:
        return self.ok("takehome.sources", {"course_id": seeded["course_id"]})["result"]

    def preview(self, seeded: dict, *, audience: str = "parent", kind: str = "print_pack", index: int = 0) -> dict:
        return self.ok(
            "takehome.preview",
            {
                "course_id": seeded["course_id"],
                "objective_id": seeded["objective_ids"][index],
                "source_lesson_version": self.lesson_version(seeded, index),
                "audience": audience,
                "kind": kind,
            },
        )["result"]

    def create(self, seeded: dict, preview: dict, *, index: int = 0) -> dict:
        return self.ok(
            "takehome.create",
            {
                "course_id": seeded["course_id"],
                "objective_id": seeded["objective_ids"][index],
                "source_lesson_version": self.lesson_version(seeded, index),
                "audience": "parent",
                "kind": "print_pack",
                "title": "Take-home: searing",
            },
            expected_revision=0,
            idempotency_key=f"gm006-create-{seeded['course_id']}",
        )["result"]

    def page_text(self, preview: dict) -> dict[str, str]:
        return {page["role"]: page["text"] for page in preview["pages"]}


# ── backend: the source picker ────────────────────────────────────────────────


class SourcePickerTest(TakeHomeCase):
    def test_parent_source_picker_opens_game_and_textbook(self) -> None:
        game = self.seed_course(title="Replace a head gasket", presentation_mode="game")
        textbook = self.seed_course(title="Braising at home")

        game_source = self.sources(game)
        textbook_source = self.sources(textbook)
        self.assertEqual(game_source["presentation_mode"], "game")
        self.assertEqual(textbook_source["presentation_mode"], "textbook")
        self.assertTrue(game_source["objectives"][0]["available"])
        self.assertTrue(textbook_source["objectives"][0]["available"])
        self.assertEqual(game_source["objectives"][0]["lesson_version"], self.lesson_version(game))

        # The shelf is the same picker for both: one row per learner course, one door in.
        shelf = render(
            {
                "kind": "shelf",
                "rows": [
                    {"course_id": game["course_id"], "title": "Replace a head gasket", "recipe": "committed",
                     "provenance": {"source": "authored"}},
                    {"course_id": textbook["course_id"], "title": "Braising at home", "recipe": "committed",
                     "provenance": {"source": "bundled"}},
                    {"course_id": "crs_parent", "title": "My child's plan", "recipe": "parent",
                     "provenance": {"source": "authored"}},
                ],
            }
        )
        self.assertEqual(shelf.count("data-cb-source-course="), 2, "a parent plan leaked into the learner shelf")
        self.assertIn("Replace a head gasket", shelf)
        self.assertIn("Braising at home", shelf)
        self.assertIn("Choose this course", shelf)
        self.assertNotIn("My child's plan", shelf)

        for source, mode in ((game_source, "game"), (textbook_source, "textbook")):
            html = render({"kind": "source", "source": source})
            self.assertIn(f'data-cb-source-mode="{mode}"', html)
            self.assertIn("Preview this lesson", html)
            self.assertIn("Objective 1: sear and braise", html)
            self.assertIn("No child account and no child chat", html)
            self.assertIn("Back to courses", html)

    def test_parent_source_picker_names_a_blocked_lesson(self) -> None:
        seeded = self.seed_course()
        source = self.sources(seeded)
        source["objectives"][0]["available"] = False
        source["objectives"][0]["blocked_reason"] = "no generated lesson"
        html = render({"kind": "source", "source": source})
        self.assertIn('data-cb-source-available="false"', html)
        self.assertIn("Not printable yet", html)
        self.assertIn("The lesson for this objective has not been written yet.", html)

        failed = render(
            {"kind": "source", "source": None, "status": "error",
             "error": {"code": "NOT_FOUND", "message": "course crs_missing does not exist"}}
        )
        self.assertIn("This course’s lessons could not be read", failed)
        self.assertIn("Try again", failed)


# ── backend + desktop: the learner page and the answer guide ──────────────────


class LearnerPageTest(TakeHomeCase):
    def test_takehome_learner_page_has_no_answer_key(self) -> None:
        seeded = self.seed_course()
        preview = self.preview(seeded)
        text = self.page_text(preview)
        self.assertIn(LEARNER_MARKER, text["learner_page"])
        for secret in (ANSWER_MARKER, RUBRIC_MARKER):
            self.assertNotIn(secret, text["learner_page"], "the learner page carries the answer key")
            self.assertIn(secret, text["answer_guide"], "the answer guide lost the key")
        self.assertIn("Answer guide - parent only", text["answer_guide"])

        learner_proof = render({"kind": "proof", "pages": preview["pages"], "audience": "learner"})
        self.assertNotIn('data-cb-proof-page="answer_guide"', learner_proof)
        self.assertNotIn('data-cb-proof-page="parent_guide"', learner_proof)
        self.assertIn('data-cb-proof-page="learner_page"', learner_proof)
        self.assertIn("This page carries no answers.", learner_proof)
        for secret in (ANSWER_MARKER, RUBRIC_MARKER):
            self.assertNotIn(secret, learner_proof, "the learner copy leaked the answer key")

        parent_proof = render({"kind": "proof", "pages": preview["pages"], "audience": "parent"})
        self.assertIn('data-cb-proof-page="answer_guide"', parent_proof)
        self.assertIn('data-cb-proof-audience="parent"', parent_proof)
        self.assertIn("Parent only. Keep this page back.", parent_proof)
        self.assertIn(ANSWER_MARKER, parent_proof)
        self.assertLess(
            parent_proof.index('data-cb-proof-page="learner_page"'),
            parent_proof.index('data-cb-proof-page="answer_guide"'),
            "the answer guide must be the last sheet, never mixed into the learner page",
        )


# ── desktop + backend: the print proof is actual pages ───────────────────────


class PrintProofTest(TakeHomeCase):
    def test_takehome_print_proof_is_real_pages(self) -> None:
        seeded = self.seed_course()
        preview = self.preview(seeded)
        roles = [page["role"] for page in preview["pages"]]
        self.assertEqual(roles[:3], ["cover", "parent_guide", "learner_page"])
        self.assertEqual(roles[-1], "answer_guide")
        self.assertGreaterEqual(len(roles), 4)

        html = render({"kind": "proof", "pages": preview["pages"], "audience": "parent"})
        self.assertIn('data-cb-takehome-proof', html)
        self.assertEqual(html.count('data-cb-proof-page="'), len(roles), "a page is missing from the proof")
        self.assertIn("Print proof", html)
        self.assertIn("selectable text", html)
        self.assertIn(LEARNER_MARKER, html)
        self.assertIn("Choose the moment that actually sears the meat.", html)
        # Actual pages, not a thumbnail: no rasterized page preview anywhere.
        self.assertNotIn("<img", html)
        self.assertNotIn("data:image", html)
        self.assertNotIn("thumbnail", html.lower())
        for index in range(1, len(roles) + 1):
            self.assertIn(f'data-cb-proof-index="{index}"', html)

    def test_textbook_course_without_world_art_still_prints(self) -> None:
        seeded = self.seed_course(title="Textbook: braising")
        preview = self.preview(seeded)
        roles = [page["role"] for page in preview["pages"]]
        self.assertNotIn("plate", roles, "a course with no world art invented a plate")
        html = render({"kind": "proof", "pages": preview["pages"], "audience": "parent"})
        self.assertEqual(html.count('data-cb-proof-page="'), 4)
        self.assertIn("Textbook: braising", html)
        self.assertIn("Learner page", html)

    def test_a_captioned_world_plate_is_a_plate_not_lesson_prose(self) -> None:
        """When a source does carry world art, its plate prints as art with its caption.

        The plate is not lesson text and never carries the answer guide; the learner copy keeps
        the plate and its text alternative, which is the only honest way to print art.
        """
        seeded = self.seed_course()
        preview = self.preview(seeded)
        plate = {
            "role": "plate",
            "audience": "learner",
            "title": "Plate: a pan at shimmer",
            "text": "A pan at shimmer, ribs laid away from the cook.",
            "alt_text": "A dark pan on a hob; the oil shimmers across the surface.",
        }
        pages = [*preview["pages"], plate]
        learner = render({"kind": "proof", "pages": pages, "audience": "learner"})
        self.assertIn('data-cb-proof-page="plate"', learner)
        self.assertIn("A pan at shimmer, ribs laid away from the cook.", learner)
        self.assertIn("Text alternative: A dark pan on a hob", learner)
        self.assertNotIn('data-cb-proof-page="answer_guide"', learner)
        parent = render({"kind": "proof", "pages": pages, "audience": "parent"})
        self.assertIn('data-cb-proof-page="plate"', parent)
        self.assertIn('data-cb-proof-page="answer_guide"', parent)
        self.assertLess(
            parent.index('data-cb-proof-page="plate"'),
            parent.index('data-cb-proof-page="answer_guide"'),
            "the plate printed after the parent-only answer guide",
        )


# ── backend: the pack never mutates its source ───────────────────────────────


class SourceMutationTest(TakeHomeCase):
    def test_parent_pack_does_not_mutate_source(self) -> None:
        seeded = self.seed_course()
        snapshot_sql = {
            "courses": "SELECT * FROM courses ORDER BY id",
            "plans": "SELECT * FROM plans ORDER BY id",
            "objectives": "SELECT * FROM objectives ORDER BY id",
            "gen_plan_documents": "SELECT * FROM gen_plan_documents ORDER BY id",
            "gen_plan_sections": "SELECT * FROM gen_plan_sections ORDER BY id",
            "gen_lessons": "SELECT * FROM gen_lessons ORDER BY id",
            "checks": "SELECT * FROM checks ORDER BY id",
            "attempts": "SELECT * FROM attempts ORDER BY id",
            "evidence": "SELECT * FROM evidence ORDER BY id",
        }
        before = {name: self.rows(sql) for name, sql in snapshot_sql.items()}

        preview = self.preview(seeded)
        created = self.create(seeded, preview)
        self.ok(
            "takehome.approve",
            {"pack_id": created["pack_id"], "preview_hash": preview["preview_hash"]},
            expected_revision=created["revision"],
            idempotency_key=f"gm006-approve-{seeded['course_id']}",
        )
        self.ok(
            "takehome.export",
            {"pack_id": created["pack_id"]},
            expected_revision=created["revision"] + 1,
            idempotency_key=f"gm006-export-{seeded['course_id']}",
        )

        after = {name: self.rows(sql) for name, sql in snapshot_sql.items()}
        for name in snapshot_sql:
            self.assertEqual(before[name], after[name], f"the take-home pack rewrote {name}")

        stored = self.ok("takehome.read", {"pack_id": created["pack_id"]})["result"]["pack"]
        source_row = self.rows(
            "SELECT * FROM gen_lessons l JOIN gen_plan_sections s ON s.id = l.section_id"
            " WHERE s.plan_id = ? ORDER BY s.ordinal LIMIT 1",
            (seeded["plan_id"],),
        )[0]
        self.assertEqual(stored["source_course_id"], seeded["course_id"])
        self.assertEqual(stored["source_objective_id"], seeded["objective_ids"][0])
        self.assertEqual(stored["source_lesson_version"], self.lesson_version(seeded))
        self.assertEqual(stored["content_hash"], preview["content_hash"])
        # The pack did not clone or re-enroll the source: one course, one enrollment.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses"), 1)
        self.assertIsNotNone(source_row["id"])

        # The panel says the same thing in words, so the promise is visible where it matters.
        html = render(
            {
                "kind": "pack",
                "source": self.sources(seeded),
                "objective": self.sources(seeded)["objectives"][0],
                "preview": preview,
            }
        )
        self.assertIn("Printing this pack does not change the course, its plan or its approval.", html)


# ── desktop + backend: no XP, stars or invented scores ───────────────────────


class NoFakeScoreTest(TakeHomeCase):
    FORBIDDEN = ("XP", "five-star", "5-star", "star rating", "stars", "score", "mastery", "leaderboard")

    def test_parent_pack_no_xp_or_rating(self) -> None:
        seeded = self.seed_course()
        preview = self.preview(seeded)
        pack_text = json.dumps(preview).lower()
        for word in ("xp", "rating", "stars", "mastery", "points", "leaderboard"):
            self.assertNotIn(word, pack_text, f"the pack JSON contains {word}")
        body = "\n".join(page["text"] for page in preview["pages"]).lower()
        for word in ("xp", "rating", "stars", "mastery", "leaderboard"):
            self.assertNotIn(word, body, f"a printed page contains {word}")

        source = self.sources(seeded)
        html = render(
            {
                "kind": "pack",
                "source": source,
                "objective": source["objectives"][0],
                "preview": preview,
            }
        )
        proof = render({"kind": "proof", "pages": preview["pages"], "audience": "parent"})
        for surface in (html, proof):
            for word in self.FORBIDDEN:
                self.assertNotIn(word, surface, f"the take-home surface shows {word}")
            self.assertNotIn("data-cb-xp", surface)

    def test_export_failure_is_named(self) -> None:
        seeded = self.seed_course()
        preview = self.preview(seeded)
        source = self.sources(seeded)
        html = render(
            {
                "kind": "pack",
                "source": source,
                "objective": source["objectives"][0],
                "preview": preview,
                "pack": {"pack_id": "thp_1", "state": "draft", "revision": 0},
                "exportError": {"code": "POLICY_VIOLATION", "message": "refused",
                                "details": {"reason": "approval_stale"}},
            }
        )
        self.assertIn('data-cb-takehome-export-error="approval_stale"', html)
        self.assertIn("Approve the pages you can see again.", html)
        self.assertNotIn("Download the print-ready PDF", html)


# ── backend + desktop: the exported pack answers a real download ─────────────


class ExportDownloadTest(TakeHomeCase):
    def test_exported_pack_resolves_a_download_handle(self) -> None:
        """The export gate advances the revision and the artifact answers a fetchable handle.

        This is the regression pin for the take-home PDF: the export writes its artifact with
        provenance bound to the source lesson, and `artifact.get` validates that provenance
        against the contract's identifier pattern. A lesson *version* (`<lesson_id>:v<n>`)
        carries a colon, so binding it verbatim made `artifact.get` return INTERNAL_ERROR and
        the Download control never appear. The pack still binds the exact version — in notes.
        """
        seeded = self.seed_course()
        preview = self.preview(seeded)
        created = self.create(seeded, preview)
        self.assertEqual(created["revision"], 0)
        approved = self.ok(
            "takehome.approve",
            {"pack_id": created["pack_id"], "preview_hash": preview["preview_hash"]},
            expected_revision=created["revision"],
            idempotency_key=f"gm006-dl-approve-{seeded['course_id']}",
        )
        exported = self.ok(
            "takehome.export",
            {"pack_id": created["pack_id"]},
            expected_revision=created["revision"] + 1,
            idempotency_key=f"gm006-dl-export-{seeded['course_id']}",
        )["result"]
        self.assertEqual(exported["state"], "exported")
        self.assertEqual(exported["pack_id"], created["pack_id"])
        self.assertTrue(exported["artifact_id"].startswith("art_"))
        # Approval is one revision; export is the next one. The gate is not skipped.
        self.assertEqual(approved["result"].get("state"), "approved")

        artifact = self.ok("artifact.get", {"artifact_id": exported["artifact_id"]})["result"]
        self.assertEqual(artifact["kind"], "pdf")
        self.assertEqual(artifact["mime"], "application/pdf")
        self.assertGreater(artifact["bytes"], 0)
        self.assertRegex(artifact["content_hash"], r"^sha256:[0-9a-f]{64}$")
        download = artifact["download"]
        self.assertRegex(download["url"], r"^/api/plugins/coursebook/artifacts/[A-Za-z0-9_-]+$")
        self.assertEqual(download["method"], "GET")
        self.assertTrue(download["requires_session"])
        for source_id in artifact["provenance"]["source_ids"]:
            self.assertRegex(source_id, r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
        # The exact version the pack is bound to is still readable, just not as an identifier.
        self.assertIn(self.lesson_version(seeded), artifact["provenance"]["notes"] or "")

        stored = self.ok("takehome.read", {"pack_id": created["pack_id"]})["result"]["pack"]
        self.assertEqual(stored["state"], "exported")
        self.assertEqual(stored["export"]["artifact_id"], exported["artifact_id"])
        self.assertEqual(stored["export"]["mime"], "application/pdf")
        self.assertGreater(stored["export"]["bytes"], 0)

        # The panel offers the file it just proved, not a placeholder: the anchor is the
        # backend's session-bound route and is named as a PDF.
        html = render(
            {
                "kind": "pack",
                "source": self.sources(seeded),
                "objective": self.sources(seeded)["objectives"][0],
                "preview": preview,
                "pack": {"pack_id": created["pack_id"], "state": "exported", "revision": 2,
                         "approved_at": "now", "approval_hash": "sha256:" + "0" * 64},
                "exported": exported,
                "artifact": artifact,
            }
        )
        self.assertIn(f'data-cb-takehome-exported="{exported["artifact_id"]}"', html)
        self.assertIn("Download the print-ready PDF", html)
        self.assertIn(f'href="{download["url"]}"', html)
        self.assertIn('download="take-home-pack.pdf"', html)


class LegacyArtifactProvenanceTest(TakeHomeCase):
    def test_artifact_get_reads_a_versioned_source_id(self) -> None:
        """A row written before the identifier rule still answers a download handle.

        The artifact store dedupes by bytes, so re-exporting an identical pack keeps the first
        row's provenance. `artifact.get` therefore has to normalize a bound lesson version
        (`lsn_…:v1`) at the contract boundary instead of returning INTERNAL_ERROR for it.
        """
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO artifacts (id, course_id, kind, content_hash, path, bytes, mime,"
                " provenance_json, ref_count, created_at)"
                " VALUES ('art_legacy_gm006', NULL, 'pdf', ?, '/tmp/legacy.pdf', 42,"
                " 'application/pdf', ?, 1, ?)",
                (
                    "a" * 64,
                    json.dumps({
                        "generator": "coursebook.takehome",
                        "notes": "take-home pack PDF; source lesson lsn_1_pln_x:v3",
                        "source_ids": ["lsn_1_pln_x:v3", "bad id with spaces", "src_cited_1"],
                    }),
                    NOW,
                ),
            )
        result = self.ok("artifact.get", {"artifact_id": "art_legacy_gm006"})["result"]
        self.assertEqual(result["provenance"]["source_ids"], ["lsn_1_pln_x", "src_cited_1"])
        self.assertIn("lsn_1_pln_x:v3", result["provenance"]["notes"])
        self.assertRegex(result["download"]["url"], r"^/api/plugins/coursebook/artifacts/")


if __name__ == "__main__":
    unittest.main()
