"""H-26: the student syllabus path — bounded intake, deterministic parse, anchors, alignment.

These are backend/RPC cases over the real ``coursebook.api.dispatch`` path and a real migrated
SQLite database. No provider is called: the parse and align stages are deterministic, and the one
plan job in this file runs on the repository's scripted offline provider (``FakeLLM``), which is
labelled as such wherever it is used. No Japanese pack is involved; the fixtures are the three
syllabi in ``tests/fixtures/syllabi/``.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from coursebook import api, contracts, db, domain, executor, generation
from coursebook import syllabus as syllabus_mod

from tests.blueprint_support import blueprint_plan
from tests.kernel_support import KernelCase
from tests.test_generation import (
    FakeLLM,
    FakeSearch,
    fixture,
    plan_fixture,
    response,
    source_ids_from,
    validation_from_fixture,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "syllabi"

#: Objective/section titles that the deterministic title-token rule can place against the CS and
#: biology fixtures. They are authored content for the *plan*, never copied from the syllabus.
CS_TITLES = (
    "Relational model",
    "SQL queries",
    "Joins and aggregation",
    "Normalization from functional dependencies",
)


def cs_plan(titles=CS_TITLES, units=None):
    """A scripted ``coursebook.plan.v2`` response with CS titles.

    The plan is unit-shaped because H-21's blueprint is the only plan the backend authors for a
    scoped brief; the script never falls back to the pre-blueprint v1 document.
    """

    def build(request: generation.LLMRequest) -> generation.LLMResponse:
        payload = json.loads(request.input_text)
        scope = str(payload.get("scope") or "short")
        count = len(titles)
        unit_count = int(units or (1 if scope != "full" else 2))
        if scope == "full":
            unit_count = max(2, unit_count)
        per_unit = max(1, -(-count // unit_count))
        if scope == "full":
            per_unit = max(2, per_unit)
        document = blueprint_plan(
            scope=scope, units=unit_count, objectives_per_unit=per_unit, recipe="companion"
        )
        document["title"] = "CS 340 companion"
        document["learner_outcome"] = (
            "Explain the relational model, write SQL against a normalized schema and diagnose a "
            "slow query, in support of the learner's own CS 340 class."
        )
        document["context_needs"] = ["course readings", "worked SQL examples"]
        document["exclusions"] = ["No claim of official course content."]
        for index, objective in enumerate(document["objectives"]):
            objective["title"] = titles[index % len(titles)]
        for index, unit in enumerate(document["units"]):
            unit["title"] = f"Unit {index + 1}: {titles[index % len(titles)]}"
        return response(document)

    return build


class SyllabusCase(KernelCase):
    # ── helpers ─────────────────────────────────────────────────────────────
    def intake(self, *, name="cs340-databases.md", text=None, raw=None, mime="text/markdown",
               supersedes=None, key=None):
        payload = {"file_name": name, "mime_hint": mime}
        if text is not None:
            payload["pasted_text"] = text
        elif raw is not None:
            import base64

            payload["content_base64"] = base64.b64encode(raw).decode("ascii")
        if supersedes:
            payload["supersedes_syllabus_id"] = supersedes
        response_body = self.dispatch("syllabus.intake.create", payload, idempotency_key=key)
        return response_body

    def intake_ok(self, **kwargs):
        body = self.intake(**kwargs)
        self.assertTrue(body["ok"], body.get("error"))
        return body["result"]["syllabus_id"], body["result"]["revision"]

    def parse_now(self, syllabus_id, revision):
        job = self.ok(
            "syllabus.parse",
            {"syllabus_id": syllabus_id, "revision": revision, "egress_acknowledged": True},
        )["result"]
        views = executor.pump_once()
        state = next((v["state"] for v in views if v["job_id"] == job["job_id"]), None)
        self.assertEqual(state, "completed", views)
        return job["job_id"]

    def companion_course(self, syllabus_id, revision, *, scope="short", titles=CS_TITLES,
                         units=None, recipe="companion", llm_script=None):
        created = self.ok(
            "course.create",
            {
                "title": "CS 340 companion",
                "recipe": recipe,
                "goal": "Support my own CS 340 databases class",
                "scope": scope,
                "syllabus_id": syllabus_id,
                "syllabus_revision": revision,
            },
            idempotency_key=f"cb-companion-{syllabus_id}",
        )["result"]
        enrollment_id = self.ok(
            "enrollment.create",
            {"course_id": created["course_id"], "learner_label": "Student"},
        )["result"]["enrollment_id"]
        brief = {
            "stage": "plan",
            "course_id": created["course_id"],
            "enrollment_id": enrollment_id,
            "goal": "Support my own CS 340 databases class",
            "recipe": recipe,
            "scope": scope,
            "syllabus_id": syllabus_id,
            "syllabus_revision": revision,
        }
        job = self.ok(
            "jobs.create", {"kind": "plan", "brief": brief},
            idempotency_key=f"cb-companion-plan-{syllabus_id}",
        )["result"]
        script = llm_script or {
            "coursebook.plan.generate": cs_plan(titles, units),
            "coursebook.plan.validate": validation_from_fixture(),
        }
        llm = FakeLLM(script)
        search = FakeSearch()
        views = executor.pump_once(llm=llm, search=search)
        state = next((v["state"] for v in views if v["job_id"] == job["job_id"]), None)
        self.assertEqual(state, "completed", views)
        plans = self.ok("course.get", {"course_id": created["course_id"]})["result"]["course"]["plans"]
        authored = max(plans, key=lambda item: item["version"])
        return {
            "course_id": created["course_id"],
            "draft_plan_id": created["plan_id"],
            "plan_id": authored["plan_id"],
            "enrollment_id": enrollment_id,
            "brief": brief,
            "llm": llm,
            "search": search,
        }

    def align_now(self, syllabus_id, revision, course_id, plan_id):
        job = self.ok(
            "syllabus.align",
            {"syllabus_id": syllabus_id, "revision": revision,
             "course_id": course_id, "plan_id": plan_id},
        )["result"]
        views = executor.pump_once()
        state = next((v["state"] for v in views if v["job_id"] == job["job_id"]), None)
        self.assertEqual(state, "completed", views)
        return self.ok(
            "syllabus.alignment.get",
            {"syllabus_id": syllabus_id, "revision": revision, "course_id": course_id},
        )["result"]

    def review_all(self, syllabus_id, revision, course_id, alignment):
        decisions = []
        for item in alignment["items"]:
            if item["state"] == "conflict":
                decisions.append({"item_id": item["item_id"], "action": "accept_divergence"})
            elif item["state"] == "partial":
                decisions.append({"item_id": item["item_id"], "action": "accept_partial"})
            elif item["state"] == "unmatched":
                decisions.append({"item_id": item["item_id"], "action": "accept_unmatched"})
        if not decisions:
            return None
        return self.ok(
            "syllabus.alignment.review",
            {"syllabus_id": syllabus_id, "revision": revision, "course_id": course_id,
             "alignment_revision": alignment["alignment_revision"], "decisions": decisions},
        )["result"]


class ContractDeltaTest(KernelCase):
    def test_v12_publishes_the_seven_syllabus_commands_and_no_path_field(self) -> None:
        # v12's delta is measured against its own snapshot; the live wire has since moved to v13
        # (H-08's authored-course export appended two methods and left these seven unchanged).
        v12 = json.loads((contracts.CONTRACT_DIR / "rpc.v12.json").read_text(encoding="utf-8"))
        self.assertEqual(v12["x-contract-version"], 12)
        self.assertEqual(v12["$id"], "https://contracts.coursebook.hermes/rpc/v12")
        for method in ("syllabus.intake.create", "syllabus.get", "syllabus.parse",
                       "syllabus.align", "syllabus.alignment.get",
                       "syllabus.alignment.review", "syllabus.delete"):
            self.assertIn(method, contracts.method_names())
        intake = contracts.method_schema("syllabus.intake.create")["request"]
        self.assertNotIn("path", intake["properties"])
        self.assertNotIn("url", intake["properties"])
        self.assertIs(intake["additionalProperties"], False)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_db_v8_adds_eight_tables_and_keeps_the_old_inventory(self) -> None:
        v7 = json.loads((contracts.CONTRACT_DIR / "db.v7.json").read_text(encoding="utf-8"))
        # The v8 snapshot, not the live inventory: cb.db has since moved to v9 for H-53's nullable
        # `evidence.note`, so this stays a v7-vs-v8 check on the file that shipped.
        current = json.loads((contracts.CONTRACT_DIR / "db.v8.json").read_text(encoding="utf-8"))
        self.assertEqual(current["schema_version"], 8)
        self.assertEqual(current["x-contract-version"], 8)
        added = set(current["tables"]) - set(v7["tables"])
        self.assertEqual(added, {
            "syllabus_series", "syllabi", "syllabus_files", "syllabus_blocks",
            "syllabus_parse_runs", "syllabus_items", "course_syllabi", "syllabus_alignments",
        })
        for table in v7["tables"]:
            self.assertEqual(current["tables"][table], v7["tables"][table], table)
        migration = [entry for entry in current["migration_plan"] if entry["version"] == 8]
        self.assertEqual(len(migration), 1)
        self.assertEqual(migration[0]["migration"], "0008_syllabus_intake.sql")
        self.assertTrue(any("Additive only" in line for line in migration[0]["impact"]))
        self.assertTrue(any("No backfill" in line for line in migration[0]["impact"]))
        sql = (ROOT / "coursebook" / "migrations" / migration[0]["migration"]).read_text(encoding="utf-8")
        for table in added:
            self.assertIn(f"CREATE TABLE {table}", sql)

    def test_errors_v4_adds_only_the_typed_syllabus_refusals(self) -> None:
        v3 = json.loads((contracts.CONTRACT_DIR / "errors.v3.json").read_text(encoding="utf-8"))
        current = contracts.contract("cb.errors")
        self.assertEqual(current["x-contract-version"], 4)
        added = set(current["code_catalog"]) - set(v3["code_catalog"])
        self.assertEqual(added, {
            "SYLLABUS_REJECTED", "SYLLABUS_NO_TEXT_LAYER", "SYLLABUS_STALE",
            "SYLLABUS_UNREVIEWED", "SYLLABUS_IN_USE", "PARSER_UNAVAILABLE",
            "BLUEPRINT_UNAVAILABLE",
        })
        # Syllabus intake needs cb.db v8 or later; H-53 took the inventory to v9 without touching
        # any syllabus table, so the requirement is a floor, not an equality.
        self.assertGreaterEqual(db.target_schema_version(), 8)
        self.assertGreaterEqual(db.applied_schema_version() or 0, 7)


class IntakeTest(SyllabusCase):
    def test_exactly_one_of_bytes_or_pasted_text(self) -> None:
        both = {"file_name": "x.md", "mime_hint": "text/markdown",
                "pasted_text": "x", "content_base64": "eA=="}
        self.assertEqual(self.err("syllabus.intake.create", both)["code"], "VALIDATION_FAILED")
        self.assertEqual(self.err("syllabus.intake.create",
                                  {"file_name": "x.md", "mime_hint": "text/markdown"})["code"],
                         "VALIDATION_FAILED")

    def test_magic_bytes_decide_not_the_filename(self) -> None:
        docx = (FIXTURES / "hist210-early-modern-europe.docx").read_bytes()
        # A DOCX uploaded under a Markdown name is still parsed as a DOCX, never as text.
        sid, rev = self.intake_ok(name="history.md", raw=docx, mime="text/markdown")
        row = self.rows("SELECT source_kind, mime FROM syllabi WHERE id = ?", (sid,))[0]
        self.assertEqual(row["source_kind"], "docx")

    def test_text_caps_are_enforced_before_anything_is_written(self) -> None:
        error = self.err("syllabus.intake.create", {
            "file_name": "big.txt", "mime_hint": "text/plain",
            "pasted_text": "A" * (syllabus_mod.MAX_TEXT_CHARS + 1),
        })
        self.assertEqual(error["code"], "SYLLABUS_REJECTED")
        self.assertEqual(error["details"]["reason"], "too_large")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM syllabi"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM syllabus_files"), 0)

    def test_non_utf8_and_nul_text_are_refused(self) -> None:
        import base64

        error = self.err("syllabus.intake.create", {
            "file_name": "x.txt", "mime_hint": "text/plain",
            "content_base64": base64.b64encode(b"\xff\xfe\x00bad").decode(),
        })
        self.assertEqual(error["code"], "SYLLABUS_REJECTED")
        error = self.err("syllabus.intake.create", {
            "file_name": "x.txt", "mime_hint": "text/plain", "pasted_text": "abc\x00def",
        })
        self.assertEqual(error["code"], "SYLLABUS_REJECTED")

    def test_encrypted_pdf_and_active_content_are_refused_without_storing(self) -> None:
        encrypted = (FIXTURES / "syllabus-encrypted.pdf").read_bytes()
        error = self.err("syllabus.intake.create", {
            "file_name": "enc.pdf", "mime_hint": "application/pdf",
            "content_base64": __import__("base64").b64encode(encrypted).decode(),
        })
        self.assertEqual(error["code"], "SYLLABUS_REJECTED")
        self.assertEqual(error["details"]["reason"], "active_content")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM syllabi"), 0)

    def test_pdf_refuses_honestly_when_the_extractor_is_missing_or_the_page_has_no_text(self) -> None:
        import base64

        raw = (FIXTURES / "scanned-no-text-layer.pdf").read_bytes()
        error = self.err("syllabus.intake.create", {
            "file_name": "scan.pdf", "mime_hint": "application/pdf",
            "content_base64": base64.b64encode(raw).decode(),
        })
        # Two honest answers, both typed: no extractor installed, or no text layer in the page.
        self.assertIn(error["code"], {"PARSER_UNAVAILABLE", "SYLLABUS_NO_TEXT_LAYER"})
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM syllabi"), 0)

    def test_parser_unavailable_is_named_when_pypdf_is_absent(self) -> None:
        if syllabus_mod._pdf_module() is not None:
            self.skipTest("pypdf is installed in this environment")
        import base64

        header = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
        error = self.err("syllabus.intake.create", {
            "file_name": "x.pdf", "mime_hint": "application/pdf",
            "content_base64": base64.b64encode(header).decode(),
        })
        self.assertEqual(error["code"], "PARSER_UNAVAILABLE")

    def test_same_content_replay_is_one_document(self) -> None:
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text(),
                                  key="cb-intake-1")
        again = self.ok("syllabus.intake.create", {
            "file_name": "cs340-databases.md", "mime_hint": "text/markdown",
            "pasted_text": (FIXTURES / "cs340-databases.md").read_text(),
        }, idempotency_key="cb-intake-1")["result"]
        self.assertEqual(again["syllabus_id"], sid)
        again_different_key = self.intake_ok(
            text=(FIXTURES / "cs340-databases.md").read_text(), supersedes=sid)
        # Same bytes for the same series: no second revision is minted.
        self.assertEqual(again_different_key, (sid, rev))


class ParseTest(SyllabusCase):
    def test_anchors_survive_and_unknown_is_not_invented(self) -> None:
        text = (FIXTURES / "cs340-databases.md").read_text()
        sid, rev = self.intake_ok(text=text)
        self.parse_now(sid, rev)
        document = self.ok("syllabus.get", {"syllabus_id": sid, "include_blocks": True})["result"]
        self.assertEqual(document["syllabus"]["state"], "parsed")
        self.assertTrue(document["blocks"])
        by_kind: dict[str, list[dict]] = {}
        for item in document["items"]:
            by_kind.setdefault(item["kind"], []).append(item)
        # Every extracted item cites a real block and a quote that is verbatim in it.
        blocks = {block["block_id"]: block["text"] for block in document["blocks"]}
        for item in document["items"]:
            if item["state"] != "extracted":
                continue
            self.assertTrue(item["anchors"], item["kind"])
            for anchor in item["anchors"]:
                self.assertIn(anchor["block_id"], blocks)
                self.assertIn(" ".join(anchor["quote"].split()), " ".join(blocks[anchor["block_id"]].split()))
        self.assertEqual(by_kind["course_code"][0]["value"], "CS 340")
        self.assertEqual(by_kind["course_title"][0]["value"], "Introduction to Databases")
        self.assertEqual(by_kind["instructor"][0]["value"], "Dr. Ada Lovelace")
        # The "TBD" reading is unknown, with no value and no invented chapter.
        readings = by_kind["reading"]
        unknown = [item for item in readings if item["state"] == "unknown"]
        self.assertEqual(len(unknown), 1)
        self.assertIsNone(unknown[0]["value"])
        self.assertEqual(unknown[0]["anchors"], [])
        self.assertTrue(any(item["value"] == "Chapter 1" for item in readings))
        # Weights are stored as written: percentages here, and no normalization into points.
        assessments = by_kind["assessment"]
        midterm = next(item for item in assessments if item["value"] == "Midterm exam")
        self.assertEqual(midterm["value"], "Midterm exam")
        self.assertEqual(len(by_kind["policy"]), 4)
        # Dates that are stated are exact; nothing is computed from the term start.
        starts = by_kind["term_start"]
        self.assertEqual(starts[0]["value"], "2026-08-24")
        self.assertEqual(starts[0]["derivation"], "explicit")

    def test_docx_headings_become_section_anchors_and_missing_dates_stay_unknown(self) -> None:
        raw = (FIXTURES / "hist210-early-modern-europe.docx").read_bytes()
        sid, rev = self.intake_ok(name="hist210.docx", raw=raw,
                                  mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.parse_now(sid, rev)
        document = self.ok("syllabus.get", {"syllabus_id": sid, "include_blocks": True})["result"]
        self.assertTrue(any(block["label"] and "Week 1" in block["label"] for block in document["blocks"]))
        by_kind: dict[str, list[dict]] = {}
        for item in document["items"]:
            by_kind.setdefault(item["kind"], []).append(item)
        # No term start in the file: unknown, not inferred from "Week 1".
        self.assertEqual(by_kind["term_start"][0]["state"], "unknown")
        # A "date TBA" deadline is unknown with derivation unknown.
        midterm = next(item for item in by_kind["assessment"] if item["value"] == "Midterm exam")
        self.assertEqual(midterm["state"], "extracted")  # the title is stated
        # The due item itself is unknown; no date was produced.
        unknown_due = [item for item in by_kind["assessment"] if item["state"] == "unknown"]
        self.assertTrue(unknown_due)

    def test_points_are_not_normalized_to_percentages(self) -> None:
        sid, rev = self.intake_ok(text=(FIXTURES / "bio150l-general-biology-lab.md").read_text())
        self.parse_now(sid, rev)
        document = self.ok("syllabus.get", {"syllabus_id": sid})["result"]
        assessments = [item for item in document["items"] if item["kind"] == "assessment"]
        report = next(item for item in assessments if item["value"] == "Lab report 1")
        row = self.rows(
            "SELECT value_json FROM syllabus_items WHERE syllabus_id = ? AND title = ?",
            (sid, "Lab report 1"),
        )[0]
        self.assertEqual(row["value_json"] and json.loads(row["value_json"])["state"], "extracted")
        # weight_unit is points; the number is stored as points, never converted.
        items = self.rows(
            "SELECT title, value_json FROM syllabus_items WHERE syllabus_id = ? AND kind = 'assessment'",
            (sid,),
        )
        self.assertTrue(items)
        self.assertNotIn("100%", json.dumps(document))

    def test_a_stated_due_date_and_weight_are_served_with_their_anchors(self) -> None:
        # H-26b: the parse built due/weight but v13 only persisted the title, so a stated deadline
        # and weight were unrecoverable from syllabus.get. The v13 H-26b amendment persists them as
        # `fields`.
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text())
        self.parse_now(sid, rev)
        document = self.ok("syllabus.get", {"syllabus_id": sid, "include_blocks": True})["result"]
        blocks = {block["block_id"]: block["text"] for block in document["blocks"]}
        assessments = [item for item in document["items"] if item["kind"] == "assessment"]
        quiz = next(item for item in assessments if item["value"] == "Quiz 1")
        self.assertEqual(quiz["state"], "extracted")
        fields = quiz["fields"]
        self.assertEqual(set(fields), {"due", "weight", "weight_unit"})
        # The due date is the stated one, with a verbatim anchor, not a computed date.
        self.assertEqual(fields["due"]["value"], "2026-09-01")
        self.assertEqual(fields["due"]["state"], "extracted")
        self.assertEqual(fields["due"]["derivation"], "explicit")
        self.assertTrue(fields["due"]["anchors"])
        for anchor in fields["due"]["anchors"]:
            self.assertIn(" ".join(anchor["quote"].split()),
                          " ".join(blocks[anchor["block_id"]].split()))
        # The weight is stored as written: 5 percent, never converted.
        self.assertEqual(fields["weight"]["value"], 5)
        self.assertEqual(fields["weight"]["state"], "extracted")
        self.assertTrue(fields["weight"]["anchors"])
        self.assertEqual(fields["weight_unit"], "percent")
        # Every assessment item (title row) carries the same shape; the unknown-due placeholder
        # row has none, because it is the due item itself.
        for item in assessments:
            if item["value"] and item["value"].endswith("(due)"):
                self.assertNotIn("fields", item)
            elif item["state"] == "extracted":
                self.assertIn("fields", item)
        self.assertNotIn("2026-09-01", json.dumps(
            [item for item in assessments if item["state"] == "unknown"]))

    def test_an_unknown_due_date_keeps_its_placeholder_row_and_says_unknown(self) -> None:
        raw = (FIXTURES / "hist210-early-modern-europe.docx").read_bytes()
        sid, rev = self.intake_ok(
            name="hist210.docx", raw=raw,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.parse_now(sid, rev)
        document = self.ok("syllabus.get", {"syllabus_id": sid})["result"]
        assessments = [item for item in document["items"] if item["kind"] == "assessment"]
        midterm = next(item for item in assessments if item["value"] == "Midterm exam")
        self.assertEqual(midterm["fields"]["due"]["state"], "unknown")
        self.assertIsNone(midterm["fields"]["due"]["value"])
        self.assertEqual(midterm["fields"]["due"]["anchors"], [])
        # The v13 `<title> (due)` placeholder row is still emitted for an unknown date.
        self.assertTrue(any(item["title"] == "Midterm exam (due)" for item in assessments))
        # The field object is always present; only a stated weight is extracted, and the unit is
        # one of the three contract values, never an invented conversion.
        self.assertIn(midterm["fields"]["weight_unit"], ("percent", "points", "unknown"))
        if midterm["fields"]["weight_unit"] == "unknown":
            self.assertEqual(midterm["fields"]["weight"]["state"], "unknown")

    def test_anchor_verification_downgrades_a_fabricated_quote(self) -> None:
        blocks = [{"id": "b1", "ordinal": 1, "kind": "paragraph", "label": None, "page": None,
                   "line_start": 1, "line_end": 1, "text": "CS 101 — Real text"}]
        document = {
            "_items": [{"kind": "course_code", "title": None, "week_ordinal": None,
                        "item": {"value": "CS 999", "state": "extracted", "derivation": "explicit",
                                 "anchors": [{"block_id": "b1", "quote": "CS 999 — Invented"}]}}],
            "weeks": [], "assessments": [], "learning_outcomes": [], "policies": [],
        }
        verdict = syllabus_mod.verify_anchors(document, {"b1": blocks[0]})
        self.assertEqual(verdict["anchor_mismatches"], 1)
        self.assertEqual(document["_items"][0]["item"]["state"], "unknown")
        self.assertIsNone(document["_items"][0]["item"]["value"])

    def test_not_a_syllabus_is_refused_by_the_parse_stage(self) -> None:
        sid, rev = self.intake_ok(text="A grocery list\nMilk\nBread\n")
        job = self.ok("syllabus.parse", {
            "syllabus_id": sid, "revision": rev, "egress_acknowledged": True,
        })["result"]
        executor.pump_once()
        job_row = self.rows("SELECT state, error_json FROM jobs WHERE id = ?", (job["job_id"],))[0]
        self.assertEqual(job_row["state"], "failed")
        self.assertEqual(json.loads(job_row["error_json"])["code"], "SYLLABUS_REJECTED")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM syllabus_parse_runs"), 0)

    def test_parse_requires_the_egress_acknowledgement(self) -> None:
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text())
        error = self.err("syllabus.parse", {"syllabus_id": sid, "revision": rev,
                                             "egress_acknowledged": False})
        self.assertEqual(error["code"], "VALIDATION_FAILED")


class AlignmentTest(SyllabusCase):
    def test_mapping_states_are_deterministic_and_anchored(self) -> None:
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text())
        self.parse_now(sid, rev)
        flow = self.companion_course(sid, rev)
        first = self.align_now(sid, rev, flow["course_id"], flow["plan_id"])
        # A second align request replays the same job key: the mapping is not rebuilt twice.
        again = self.ok("syllabus.align", {
            "syllabus_id": sid, "revision": rev,
            "course_id": flow["course_id"], "plan_id": flow["plan_id"],
        })["result"]
        self.assertEqual(again["alignment_revision"], first["alignment_revision"])
        executor.pump_once()
        second = self.ok("syllabus.alignment.get", {
            "syllabus_id": sid, "revision": rev, "course_id": flow["course_id"],
        })["result"]
        states = {(item["kind"], item["title"], item["state"]) for item in first["items"]}
        self.assertEqual(states, {(item["kind"], item["title"], item["state"]) for item in second["items"]})
        self.assertEqual(second["alignment_revision"], first["alignment_revision"])
        self.assertGreaterEqual(first["counts"].get("aligned", 0), 4)
        self.assertGreater(first["counts"].get("unmatched", 0), 0)
        self.assertGreaterEqual(first["counts"].get("unknown", 0), 1)
        for item in first["items"]:
            if item["state"] in ("aligned", "partial", "conflict"):
                self.assertTrue(item["evidence"]["deterministic"])
                self.assertTrue(item["evidence"]["syllabus_sha256"].startswith("sha256:"))
                self.assertTrue(item["anchors"])

    def test_conflict_blocks_approval_and_acceptance_unblocks_it(self) -> None:
        text = (
            "CS 900 — Testing\n"
            "Instructor: Dr. Test\n"
            "## Schedule\n"
            "### Week 1: Linear algebra\n"
            "Midterm exam due 2027-02-01 (20%)\n"
            "### Week 4: Linear algebra review\n"
            "Final exam due 2027-03-01 (20%)\n"
        )
        sid, rev = self.intake_ok(text=text)
        self.parse_now(sid, rev)
        flow = self.companion_course(sid, rev, units=2,
                                     titles=("Linear algebra", "Linear algebra review",
                                             "Vectors", "Midterm exam"))
        alignment = self.align_now(sid, rev, flow["course_id"], flow["plan_id"])
        conflict = next(item for item in alignment["items"] if item["state"] == "conflict")
        self.assertEqual(conflict["reason_code"], "scheduled_after_deadline")
        # An unreviewed alignment can never be approved.
        self.assertEqual(self.err("plan.approve", {
            "enrollment_id": flow["enrollment_id"], "plan_id": flow["plan_id"],
            "plan_hash": domain.plan_hash(flow["plan_id"]),
        }, expected_revision=0)["code"], "SYLLABUS_UNREVIEWED")
        reviewed = self.ok("syllabus.alignment.review", {
            "syllabus_id": sid, "revision": rev, "course_id": flow["course_id"],
            "alignment_revision": alignment["alignment_revision"],
            "decisions": [{"item_id": conflict["item_id"], "action": "accept_divergence"}],
        })["result"]
        self.assertEqual(reviewed["reviewed_revision"], rev)
        self.assertFalse(reviewed["plan_replan_required"])
        # Other pending conflicts still block; accept them one by one.
        remaining = [item for item in alignment["items"] if item["state"] == "conflict"
                     and item["item_id"] != conflict["item_id"]]
        if remaining:
            self.ok("syllabus.alignment.review", {
                "syllabus_id": sid, "revision": rev, "course_id": flow["course_id"],
                "alignment_revision": alignment["alignment_revision"],
                "decisions": [{"item_id": item["item_id"], "action": "accept_divergence"}
                              for item in remaining],
            })
        approved = self.ok("plan.approve", {
            "enrollment_id": flow["enrollment_id"], "plan_id": flow["plan_id"],
            "plan_hash": domain.plan_hash(flow["plan_id"]),
        }, expected_revision=0)
        self.assertTrue(approved["ok"])

    def test_a_revision_marks_prior_alignments_stale_and_blocks_the_old_plan(self) -> None:
        rev1_text = (FIXTURES / "bio150l-general-biology-lab.md").read_text()
        sid, rev = self.intake_ok(text=rev1_text)
        self.parse_now(sid, rev)
        flow = self.companion_course(sid, rev)
        alignment = self.align_now(sid, rev, flow["course_id"], flow["plan_id"])
        self.review_all(sid, rev, flow["course_id"], alignment)

        revised = rev1_text.replace("### Lab 14: Practical exam", "### Lab 13: Practical exam")
        new_sid, new_rev = self.intake_ok(text=revised, supersedes=sid)
        self.assertNotEqual(new_sid, sid)
        self.assertEqual(new_rev, rev + 1)
        old = self.rows("SELECT content_sha256, superseded_at FROM syllabi WHERE id = ?", (sid,))[0]
        new_sha = self.scalar("SELECT content_sha256 FROM syllabi WHERE id = ?", (new_sid,))
        self.assertNotEqual(old["content_sha256"], new_sha)
        self.assertIsNotNone(old["superseded_at"])
        stale = self.scalar(
            "SELECT COUNT(*) FROM syllabus_alignments WHERE course_id = ? AND stale = 1",
            (flow["course_id"],),
        )
        self.assertGreater(stale, 0)
        # The approved-plan gate now refuses against the old revision, and writes nothing.
        error = self.err("plan.approve", {
            "enrollment_id": flow["enrollment_id"], "plan_id": flow["plan_id"],
            "plan_hash": domain.plan_hash(flow["plan_id"]),
        }, expected_revision=0)
        self.assertEqual(error["code"], "SYLLABUS_STALE")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM transitions"), 0)
        # A new authoring job for the old revision is refused by the plan stage, typed.
        self.assertEqual(self.err("course.create", {
            "title": "stale", "recipe": "companion", "goal": "g", "scope": "short",
            "syllabus_id": sid, "syllabus_revision": rev,
        })["code"], "SYLLABUS_STALE")

    def test_full_scope_plans_through_the_unit_blueprint(self) -> None:
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text())
        self.parse_now(sid, rev)
        titles = tuple(f"Semester topic {index}" for index in range(1, 13))
        flow = self.companion_course(sid, rev, scope="full", titles=titles, units=2)
        course = self.ok("course.get", {"course_id": flow["course_id"]})["result"]["course"]
        self.assertEqual(course["scope"], "full")
        self.assertEqual(course["recipe"], "companion")
        # The plan is a v2 document with real units; it is not a truncated v1 plan.
        with db.transaction() as connection:
            units = connection.execute(
                "SELECT ordinal, title FROM plan_units WHERE plan_id = ? ORDER BY ordinal",
                (flow["plan_id"],),
            ).fetchall()
            schema = connection.execute(
                "SELECT document_json FROM gen_plan_documents WHERE plan_id = ?",
                (flow["plan_id"],),
            ).fetchone()
        self.assertEqual([int(row["ordinal"]) for row in units], [1, 2])
        document = json.loads(schema["document_json"])
        plan = document["plan"] if "plan" in document else document
        self.assertEqual(plan["plan_schema"], generation.PLAN_SCHEMA_V2_NAME)
        self.assertEqual(plan["scope"], "full")
        self.assertGreaterEqual(len(plan["objectives"]), 12)

    def test_an_all_aligned_mapping_reviews_with_empty_decisions_and_approves(self) -> None:
        # H-26b gap 2: a mapping the deterministic aligner resolved entirely to `aligned` had no
        # legal decision (decisions minItems 1, every action targeting a non-aligned state), so
        # reviewed_revision could never be set and plan.approve refused SYLLABUS_UNREVIEWED.
        # The four assessment titles carry two or more of a unit's own tokens, and none sits under
        # a week heading, so the deterministic rule resolves every row to `aligned` with no
        # schedule conflict.
        text = (
            "CS 900 — Testing\n"
            "Instructor: Dr. Test\n"
            "Homework relational model due 2027-02-01 (20%)\n"
            "Homework sql queries due 2027-02-08 (20%)\n"
            "Homework joins aggregation due 2027-02-15 (20%)\n"
            "Homework normalization functional dependencies due 2027-02-22 (20%)\n"
        )
        sid, rev = self.intake_ok(text=text)
        self.parse_now(sid, rev)
        flow = self.companion_course(sid, rev, titles=CS_TITLES, units=2)
        alignment = self.align_now(sid, rev, flow["course_id"], flow["plan_id"])
        self.assertEqual(alignment["counts"]["aligned"], 4)
        self.assertEqual(alignment["counts"]["unmatched"], 0)
        self.assertEqual(alignment["counts"]["partial"], 0)
        self.assertEqual(alignment["counts"]["conflict"], 0)
        needing = [item for item in alignment["items"]
                   if item["state"] in ("partial", "unmatched", "conflict", "stale")]
        self.assertEqual(needing, [])
        approve = {
            "enrollment_id": flow["enrollment_id"], "plan_id": flow["plan_id"],
            "plan_hash": domain.plan_hash(flow["plan_id"]),
        }
        self.assertEqual(self.err("plan.approve", approve, expected_revision=0)["code"],
                         "SYLLABUS_UNREVIEWED")
        # Empty decisions = "I reviewed it and accepted the aligned rows"; the backend verifies
        # the claim because every row is aligned.
        reviewed = self.ok("syllabus.alignment.review", {
            "syllabus_id": sid, "revision": rev, "course_id": flow["course_id"],
            "alignment_revision": alignment["alignment_revision"], "decisions": [],
        })["result"]
        self.assertEqual(reviewed["reviewed_revision"], rev)
        self.assertFalse(reviewed["plan_replan_required"])
        approved = self.ok("plan.approve", approve, expected_revision=0)
        self.assertTrue(approved["ok"])

    def test_empty_decisions_is_refused_when_a_row_still_needs_a_decision(self) -> None:
        # The guard Atlas required: minItems 0 must not let a caller claim review while an
        # unmatched/partial/conflict row has never been acknowledged.
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text())
        self.parse_now(sid, rev)
        flow = self.companion_course(sid, rev)
        alignment = self.align_now(sid, rev, flow["course_id"], flow["plan_id"])
        self.assertGreater(alignment["counts"]["unmatched"], 0)
        error = self.err("syllabus.alignment.review", {
            "syllabus_id": sid, "revision": rev, "course_id": flow["course_id"],
            "alignment_revision": alignment["alignment_revision"], "decisions": [],
        })
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(error["details"]["unmatched"], alignment["counts"]["unmatched"])
        self.assertEqual(error["details"]["alignment_revision"], alignment["alignment_revision"])
        after = self.ok("syllabus.alignment.get", {
            "syllabus_id": sid, "revision": rev, "course_id": flow["course_id"],
        })["result"]
        self.assertIsNone(after["reviewed_revision"])


class CompanionCourseTest(SyllabusCase):
    def test_course_create_is_companion_and_never_a_pack(self) -> None:
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text())
        self.parse_now(sid, rev)
        flow = self.companion_course(sid, rev)
        course = self.ok("course.get", {"course_id": flow["course_id"]})["result"]["course"]
        self.assertEqual(course["recipe"], "companion")
        self.assertIsNone(course["pack_id"])
        self.assertEqual(course["syllabus"]["syllabus_id"], sid)
        self.assertEqual(course["syllabus"]["revision"], rev)
        self.assertIsNone(course["syllabus"]["reviewed_revision"])
        # No pack row and no pack provenance: the course is authored, not imported.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM packs"), 0)
        provenance = self.ok("library.list", {})["result"]["items"][0]["provenance"]
        self.assertEqual(provenance["source"], "authored")
        self.assertIsNone(provenance["pack_id"])

    def test_the_planner_receives_validated_items_and_the_recipe_is_unchanged(self) -> None:
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text())
        self.parse_now(sid, rev)
        flow = self.companion_course(sid, rev)
        plan_request = next(
            request for request in flow["llm"].requests
            if request.purpose == "coursebook.plan.generate"
        )
        self.assertIn("UNTRUSTED-SYLLABUS-DATA", plan_request.input_text)
        self.assertIn("Relational model", plan_request.input_text)
        course = self.ok("course.get", {"course_id": flow["course_id"]})["result"]["course"]
        self.assertEqual(course["recipe"], "companion")
        self.assertEqual(course["scope"], "short")
        self.assertEqual(course["dials"], {})
        # Research queries are derived from the syllabus outcomes, not the generic companion suffix.
        self.assertTrue(flow["search"].queries)
        self.assertFalse(any(query.endswith("course outline exam") for query in flow["search"].queries))

    def test_review_then_approve_and_no_official_claim(self) -> None:
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text())
        self.parse_now(sid, rev)
        flow = self.companion_course(sid, rev)
        alignment = self.align_now(sid, rev, flow["course_id"], flow["plan_id"])
        reviewed = self.review_all(sid, rev, flow["course_id"], alignment)
        self.assertEqual(reviewed["reviewed_revision"], rev)
        approved = self.ok("plan.approve", {
            "enrollment_id": flow["enrollment_id"], "plan_id": flow["plan_id"],
            "plan_hash": domain.plan_hash(flow["plan_id"]),
        }, expected_revision=0)["result"]
        self.assertEqual(approved["revision"], 1)
        surface = json.dumps([
            self.ok("syllabus.alignment.get", {
                "syllabus_id": sid, "revision": rev, "course_id": flow["course_id"],
            })["result"],
            self.ok("course.get", {"course_id": flow["course_id"]})["result"],
        ]).lower()
        for forbidden in ("official week", "your professor", "required by your course",
                          "counts toward your grade", "accredited", "registered student"):
            self.assertNotIn(forbidden, surface)
        self.assertNotIn("enrolled", surface)

    def test_delete_refuses_while_a_course_is_bound_then_removes_every_row(self) -> None:
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text())
        self.parse_now(sid, rev)
        flow = self.companion_course(sid, rev)
        self.align_now(sid, rev, flow["course_id"], flow["plan_id"])
        error = self.err("syllabus.delete", {"syllabus_id": sid})
        self.assertEqual(error["code"], "SYLLABUS_IN_USE")
        self.execute("UPDATE courses SET status = 'archived' WHERE id = ?", (flow["course_id"],))
        self.ok("syllabus.delete", {"syllabus_id": sid})
        for table in ("syllabi", "syllabus_files", "syllabus_blocks", "syllabus_parse_runs",
                      "syllabus_items", "syllabus_alignments"):
            self.assertEqual(self.scalar(f"SELECT COUNT(*) FROM {table}"), 0, table)
        # Coursebook evidence is untouched by a syllabus deletion.
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM plans"), 2)

    def test_rejections_are_typed_and_write_nothing(self) -> None:
        sid, rev = self.intake_ok(text=(FIXTURES / "cs340-databases.md").read_text())
        self.parse_now(sid, rev)
        # A companion course with a non-companion recipe is refused.
        self.assertEqual(self.err("course.create", {
            "title": "x", "recipe": "committed", "goal": "g",
            "syllabus_id": sid, "syllabus_revision": rev,
        })["code"], "VALIDATION_FAILED")
        # Half a binding is refused.
        self.assertEqual(self.err("course.create", {
            "title": "x", "recipe": "companion", "goal": "g", "syllabus_id": sid,
        })["code"], "VALIDATION_FAILED")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM course_syllabi"), 0)


class HostileInputTest(SyllabusCase):
    def test_a_syllabus_is_data_and_cannot_change_policy(self) -> None:
        text = (FIXTURES / "hostile-injection.txt").read_text()
        sid, rev = self.intake_ok(text=text)
        self.parse_now(sid, rev)
        flow = self.companion_course(sid, rev, titles=CS_TITLES)
        course = self.ok("course.get", {"course_id": flow["course_id"]})["result"]["course"]
        self.assertEqual(course["recipe"], "companion")
        self.assertEqual(course["scope"], "short")
        self.assertEqual(course["dials"], {})
        # No URL from the syllabus was fetched, and no tool was called for it.
        self.assertFalse(any("example.invalid" in url for url in flow["search"].fetches))
        self.assertFalse(any("example.invalid" in query for query in flow["search"].queries))
        # The instruction-like sentence is inert text: it is not a policy item outside a policy
        # section, and it never appears as an instruction the harness executes.
        document = self.ok("syllabus.get", {"syllabus_id": sid})["result"]
        policies = [item for item in document["items"] if item["kind"] == "policy"]
        self.assertEqual(len(policies), 1)
        self.assertIn("Academic integrity", policies[0]["value"])
        self.assertEqual(document["parse_run"]["provider"], None)
        self.assertEqual(document["parse_run"]["model"], None)


if __name__ == "__main__":
    unittest.main()
