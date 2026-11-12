"""Lesson media generation: host adapter, cache, fallback, projection and preview."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path

from coursebook import artifacts, db, generation, media

from tests.kernel_support import KernelCase

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"x" * 32
MP3 = b"\xff\xfb\x90\x00" + b"x" * 32
NOW = "2026-11-06T12:00:00Z"
HASH = "sha256:" + "a" * 64


class FakeHost:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.images: list[str] = []
        self.speeches: list[str] = []
        #: The ratio each image call asked for. Item 30: geometry is the caller's decision, so the
        #: test double records it instead of defaulting it.
        self.aspect_ratios: list[str] = []

    def image(self, prompt: str, *, aspect_ratio: str = "landscape"):
        self.images.append(prompt)
        self.aspect_ratios.append(aspect_ratio)
        if self.fail:
            raise media.MediaGenerationError("image provider offline")
        return PNG, "image/png"

    def speech(self, text: str, *, voice=None, language=None, instructions=None):
        self.speeches.append(text)
        if self.fail:
            raise media.MediaGenerationError("tts provider offline")
        return MP3, "audio/mpeg"


class MediaGenerationTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.course_id, self.plan_id = self.new_course()
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        self.objective_id = self.seed_objective(self.plan_id)
        self.enrollment_id = self.new_enrollment(self.course_id)
        # The canonical store the preview route reads from, not a fixture-local root: the route
        # refuses any path outside ``<plugin data>/artifacts``, so a test store elsewhere would be
        # testing a layout production never has.
        self.store = artifacts.ArtifactStore()
        self.execute(
            "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint, plan_hash,"
            " document_json, research_json, generation_state, validation_id, result_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, '{}', 'validated', NULL, '{}', ?)",
            ("gen_doc_1", self.plan_id, self.course_id, "fp-1", HASH, json.dumps({"locale": "ja"}), NOW),
        )
        self.execute(
            "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
            " objective_refs_json, context_needs_json, source_ids_json)"
            " VALUES (?, ?, 1, ?, ?, ?, ?, '[]', '[]')",
            ("sec_1", self.plan_id, HASH, "Greeting", "Say hello", json.dumps([1])),
        )
        self.media_items = [
            {
                "kind": "visual",
                "role": "illustration",
                "purpose": "See the workshop bench",
                "spec": "An editorial illustration of a workshop bench with a torque wrench",
                "text_equivalent": "A workshop bench with a torque wrench.",
            },
            {
                "kind": "audio",
                "role": "narration",
                "purpose": "Hear the greeting",
                "spec": "A slow, clear Japanese greeting",
                "text_equivalent": "こんにちは",
                "transcript": "こんにちは",
                "language": "ja-JP",
                "voice": "default",
            },
        ]
        self.lesson_id = "gen_lesson_1"
        self.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json,"
            " media_json, parent_notes_json, rejection_reasons_json, validation_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 1, 'validated', '{}', ?, '{}', '[]', NULL, ?, ?)",
            (self.lesson_id, self.plan_id, "sec_1", HASH, json.dumps(self.media_items), NOW, NOW),
        )

    def generate(self, host, *, lesson_ids=None):
        with db.read() as connection:
            return media.generate_for_lessons(
                connection,
                lesson_ids=lesson_ids or [self.lesson_id],
                job_id="job_media_1",
                host=host,
                store=self.store,
                now=datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc),
            )

    def stored_media(self) -> list[dict]:
        row = self.rows("SELECT media_json FROM gen_lessons WHERE id = ?", (self.lesson_id,))[0]
        return json.loads(row["media_json"])

    def test_generates_images_and_audio_and_attaches_artifacts(self) -> None:
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.generated, 2)
        self.assertEqual(len(host.images), 1)
        self.assertEqual(len(host.speeches), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 2)
        stored = self.stored_media()
        self.assertTrue(all(item.get("artifact_id") for item in stored))
        self.assertEqual({item["mime"] for item in stored}, {"image/png", "audio/mpeg"})
        self.assertTrue(all(item.get("label") for item in stored))

    def test_second_run_reuses_cached_artifacts_without_provider_calls(self) -> None:
        self.generate(FakeHost())
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.reused, 2)
        self.assertEqual(summary.generated, 0)
        self.assertEqual(host.images, [])
        self.assertEqual(host.speeches, [])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 2)

    # ── Item 30: geometry fits the job ───────────────────────────────────────────

    def set_media(self, items: list[dict]) -> None:
        self.execute(
            "UPDATE gen_lessons SET media_json = ? WHERE id = ?",
            (json.dumps(items), self.lesson_id),
        )

    def provenance_of(self, artifact_id: str) -> dict:
        return json.loads(
            str(self.scalar("SELECT provenance_json FROM artifacts WHERE id = ?", (artifact_id,)))
        )

    def test_an_illustration_is_requested_at_four_by_three_and_records_its_geometry(self) -> None:
        host = FakeHost()
        self.generate(host)
        # The caller chose the plate; the old code passed nothing and took the provider default.
        self.assertEqual(host.aspect_ratios, ["4:3"])
        visual = next(item for item in self.stored_media() if item["kind"] == "visual")
        provenance = self.provenance_of(visual["artifact_id"])
        self.assertEqual(provenance["aspect_ratio"], "4:3")
        self.assertEqual(provenance["min_width_px"], 1024)
        self.assertEqual(provenance["min_width_px"], media.MIN_FIGURE_WIDTH_PX)
        # The provider saw the built request, and provenance records its hash and version.
        spec = media._media_spec(self.media_items[0], locale="ja")
        built = media.lesson_illustration_prompt(spec)
        self.assertEqual(host.images[0], built.prompt)
        self.assertEqual(provenance["prompt_hash"], built.prompt_hash)
        self.assertEqual(provenance["prompt_version"], media.ILLUSTRATION_PROMPT_VERSION)
        # The same geometry reaches the reader through the preview route.
        preview = media.preview_artifact(visual["artifact_id"])
        self.assertEqual(preview["aspect_ratio"], "4:3")
        self.assertEqual(preview["min_width_px"], 1024)

    def test_a_portrait_subject_is_requested_at_three_by_four(self) -> None:
        self.set_media(
            [
                dict(
                    self.media_items[0],
                    spec="A portrait of a mechanic at the workshop bench",
                    text_equivalent="A mechanic stands at the bench.",
                )
            ]
        )
        host = FakeHost()
        self.generate(host)
        self.assertEqual(host.aspect_ratios, ["3:4"])
        self.assertIn("vertical composition", host.images[0])
        item = self.stored_media()[0]
        self.assertEqual(self.provenance_of(item["artifact_id"])["aspect_ratio"], "3:4")

    def test_a_schematic_records_four_by_three_and_the_width_floor(self) -> None:
        self.set_media(
            [
                {
                    "kind": "visual",
                    "role": "schematic",
                    "purpose": "Carry the torque sequence",
                    "spec": "Deterministic torque table",
                    "text_equivalent": "Bolt 1 to 20 Nm in the numbered order.",
                    "facts": {"rows": [{"label": "Bolt 1", "value": "20 Nm"}]},
                }
            ]
        )
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.generated, 1)
        # A schematic is deterministic: it never asks a provider for a picture or a ratio...
        self.assertEqual(host.images, [])
        self.assertEqual(host.aspect_ratios, [])
        item = self.stored_media()[0]
        self.assertEqual(item["mime"], "image/svg+xml")
        provenance = self.provenance_of(item["artifact_id"])
        self.assertEqual(provenance["aspect_ratio"], "4:3")
        self.assertEqual(provenance["min_width_px"], 1024)
        # ...and the bytes carry the width floor its record claims.
        svg = Path(
            str(self.scalar("SELECT path FROM artifacts WHERE id = ?", (item["artifact_id"],)))
        ).read_bytes()
        self.assertIn(b'width="1024"', svg)

    def test_audio_records_no_plate_geometry(self) -> None:
        self.generate(FakeHost())
        audio = next(item for item in self.stored_media() if item["kind"] == "audio")
        provenance = self.provenance_of(audio["artifact_id"])
        self.assertNotIn("aspect_ratio", provenance)
        self.assertNotIn("min_width_px", provenance)
        self.assertIsNone(media.preview_artifact(audio["artifact_id"])["aspect_ratio"])

    # ── H-169: a model_assessed page is readable, so its media is content ───────────────

    def set_lesson_state(self, state: str) -> None:
        self.execute("UPDATE gen_lessons SET state = ? WHERE id = ?", (state, self.lesson_id))

    def test_model_assessed_lesson_generates_visual_and_audio(self) -> None:
        self.set_lesson_state("model_assessed")
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.generated, 2)
        self.assertEqual(summary.skipped, 0)
        self.assertEqual(len(host.images), 1)
        self.assertEqual(len(host.speeches), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 2)
        stored = self.stored_media()
        self.assertEqual({item["mime"] for item in stored}, {"image/png", "audio/mpeg"})
        self.assertTrue(all(item.get("artifact_id") for item in stored))
        # The page's own provenance travels with each artifact it produced: a model-assessed
        # page never yields bytes that read as independently validated.
        for item in stored:
            provenance = json.loads(
                str(self.scalar("SELECT provenance_json FROM artifacts WHERE id = ?", (item["artifact_id"],)))
            )
            self.assertEqual(provenance["lesson_state"], "model_assessed")
            self.assertFalse(provenance["independent"])
            self.assertNotIn("independently validated", str(item["label"]).casefold())
        # The preview route exposes the same judgement, not just the bytes.
        visual = next(item for item in stored if item["kind"] == "visual")
        preview = media.preview_artifact(visual["artifact_id"])
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["lesson_state"], "model_assessed")
        self.assertFalse(preview["independent"])

    def test_model_assessed_lesson_reuses_cached_artifacts(self) -> None:
        self.set_lesson_state("model_assessed")
        self.generate(FakeHost())
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.reused, 2)
        self.assertEqual(summary.generated, 0)
        self.assertEqual(host.images, [])
        self.assertEqual(host.speeches, [])
        stored = self.stored_media()
        self.assertTrue(all(item.get("artifact_id") for item in stored))

    def test_needs_review_lesson_generates_no_media_and_stays_text_complete(self) -> None:
        self.set_lesson_state("needs_review")
        host = FakeHost()
        summary = self.generate(host)
        self.assertEqual(summary.generated, 0)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(host.images, [])
        self.assertEqual(host.speeches, [])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)
        stored = self.stored_media()
        self.assertTrue(all(item["text_equivalent"] for item in stored))
        self.assertTrue(all(not item.get("artifact_id") for item in stored))

    def test_model_assessed_learner_page_carries_artifact_mime_equivalent_and_warning(self) -> None:
        self.set_lesson_state("model_assessed")
        self.generate(FakeHost())
        with db.read() as connection:
            page = generation.learner_page(connection, self.lesson_id)
        self.assertEqual(page["provenance"]["outcome"], "model_assessed")
        self.assertTrue(page["provenance"]["check_enabled"])
        self.assertFalse(page["provenance"]["independent"])
        self.assertIn("not independently validated", page["provenance"]["warning"])
        media = page["media"]
        self.assertEqual(len(media), 2)
        self.assertEqual({item["mime"] for item in media}, {"image/png", "audio/mpeg"})
        self.assertTrue(all(item.get("artifact_id") for item in media))
        self.assertTrue(all(item.get("text_equivalent") for item in media))
        # The projected document attaches the same artifacts to a teaching block.
        children = [child for block in page["document"]["blocks"] for child in block["media"]]
        self.assertEqual(
            {child["artifact_id"] for child in children},
            {item["artifact_id"] for item in media},
        )

    def test_provider_failure_keeps_text_equivalent_and_marks_degraded(self) -> None:
        summary = self.generate(FakeHost(fail=True))
        self.assertEqual(summary.generated, 0)
        self.assertEqual(summary.degraded, 2)
        stored = self.stored_media()
        self.assertTrue(all(item["degraded"] for item in stored))
        self.assertTrue(all(item.get("reason") for item in stored))
        self.assertTrue(all(item["text_equivalent"] for item in stored))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)

    def test_authored_media_is_projected_into_the_lesson_run(self) -> None:
        self.generate(FakeHost())
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0, ?, ?, ?)",
            ("run_media_1", self.enrollment_id, self.objective_id, NOW, NOW, NOW),
        )
        with db.transaction() as connection:
            count = media.seed_authored_media(
                connection,
                lesson_run_id="run_media_1",
                objective_id=self.objective_id,
                now=NOW,
            )
        self.assertEqual(count, 2)
        segments = self.rows("SELECT kind, text, artifact_id FROM lesson_segments ORDER BY ordinal")
        self.assertEqual([row["kind"] for row in segments], ["media", "media"])
        self.assertTrue(all(row["artifact_id"] for row in segments))
        self.assertIn("こんにちは", [row["text"] for row in segments])

    def test_authored_media_is_projected_into_a_model_assessed_lesson_run(self) -> None:
        self.set_lesson_state("model_assessed")
        self.generate(FakeHost())
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0, ?, ?, ?)",
            ("run_media_2", self.enrollment_id, self.objective_id, NOW, NOW, NOW),
        )
        with db.transaction() as connection:
            count = media.seed_authored_media(
                connection,
                lesson_run_id="run_media_2",
                objective_id=self.objective_id,
                now=NOW,
            )
        self.assertEqual(count, 2)
        segments = self.rows(
            "SELECT kind, text, artifact_id FROM lesson_segments WHERE lesson_run_id = ? ORDER BY ordinal",
            ("run_media_2",),
        )
        self.assertEqual([row["kind"] for row in segments], ["media", "media"])
        self.assertTrue(all(row["artifact_id"] for row in segments))

    def test_preview_returns_a_verified_data_url_and_rejects_unknown(self) -> None:
        self.generate(FakeHost())
        visual = next(item for item in self.stored_media() if item["kind"] == "visual")
        preview = media.preview_artifact(visual["artifact_id"])
        self.assertTrue(preview["ok"])
        self.assertTrue(preview["data_url"].startswith("data:image/png;base64,"))
        self.assertEqual(media.preview_artifact("art_missing")["code"], "NOT_FOUND")

    def test_preview_passes_the_artifacts_permission_and_sources_to_the_reader(self) -> None:
        self.generate(FakeHost())
        visual = next(item for item in self.stored_media() if item["kind"] == "visual")
        provenance = json.loads(
            str(
                self.scalar(
                    "SELECT provenance_json FROM artifacts WHERE id = ?", (visual["artifact_id"],)
                )
            )
        )
        preview = media.preview_artifact(visual["artifact_id"])
        self.assertEqual(preview["permission"], provenance["permission"])
        self.assertEqual(preview["source_ids"], provenance["source_ids"])
        self.assertIn("permission", preview)

    # ── H-115-D2: a row is a record, not a warrant ────────────────────────
    # The route used to serve whatever path an ``artifacts`` row named, with the row's declared
    # MIME. These three tests are the probe's T3a/T3c reproduced as suite tests.

    def insert_row(self, artifact_id: str, *, path: Path, mime: str, data: bytes, kind: str = "visual") -> None:
        self.execute(
            "INSERT INTO artifacts (id, course_id, kind, content_hash, path, bytes, mime,"
            " provenance_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                artifact_id,
                self.course_id,
                kind,
                hashlib.sha256(data).hexdigest(),
                str(path),
                len(data),
                mime,
                json.dumps({"label": "probe"}),
                NOW,
            ),
        )

    def test_preview_refuses_a_row_pointing_outside_the_artifact_store(self) -> None:
        outside = Path(self.home) / "outside.png"
        outside.write_bytes(PNG)
        self.insert_row("art_outside0000000000000000000000001", path=outside, mime="image/png", data=PNG)
        preview = media.preview_artifact("art_outside0000000000000000000000001")
        self.assertFalse(preview["ok"])
        self.assertEqual(preview["code"], "NOT_FOUND")
        self.assertNotIn("data_url", preview)
        # The refusal never echoes the path it refused.
        self.assertNotIn(str(outside), json.dumps(preview))

    def test_preview_refuses_a_symlink_that_escapes_the_artifact_store(self) -> None:
        outside = Path(self.home) / "outside-target.png"
        outside.write_bytes(PNG)
        store = artifacts.read_root()
        store.mkdir(parents=True, exist_ok=True)
        link = store / "escape.png"
        link.symlink_to(outside)
        self.insert_row("art_symlink000000000000000000000001", path=link, mime="image/png", data=PNG)
        preview = media.preview_artifact("art_symlink000000000000000000000001")
        self.assertFalse(preview["ok"])
        self.assertEqual(preview["code"], "NOT_FOUND")

    def test_preview_refuses_html_bytes_declared_as_svg(self) -> None:
        payload = b"<html><script>alert(document.domain)</script></html>"
        store = artifacts.read_root()
        store.mkdir(parents=True, exist_ok=True)
        target = store / "mime-confusion.bin"
        target.write_bytes(payload)
        self.insert_row(
            "art_mimeconfusion00000000000000000001", path=target, mime="image/svg+xml", data=payload
        )
        preview = media.preview_artifact("art_mimeconfusion00000000000000000001")
        self.assertFalse(preview["ok"])
        self.assertEqual(preview["code"], "UNSAFE_MEDIA")
        self.assertNotIn("data_url", preview)

    def test_preview_still_serves_a_genuine_svg_from_the_store(self) -> None:
        svg = artifacts.make_schematic_svg("Torque order", [{"label": "Step 1", "value": "20 Nm"}])
        store = artifacts.read_root()
        store.mkdir(parents=True, exist_ok=True)
        target = store / "schematic.svg"
        target.write_bytes(svg)
        self.insert_row("art_goodsvg00000000000000000000000001", path=target, mime="image/svg+xml", data=svg)
        preview = media.preview_artifact("art_goodsvg00000000000000000000000001")
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["mime"], "image/svg+xml")
        self.assertTrue(preview["data_url"].startswith("data:image/svg+xml;base64,"))


    # ── item 31: a required cited reference is delivered or flagged ──────────
    # The defect: a ``sourced_technical`` spec had no producer, so every source-analysis lesson
    # degraded to a generic text paragraph. The lesson was graded on an image the learner never
    # received, and nothing on the page said the reference was missing.

    SOURCED_ITEM = {
        "kind": "visual",
        "role": "sourced_technical",
        "purpose": "The poster the analysis is performed on",
        "spec": "A wartime recruitment poster photograph",
        "text_equivalent": "A recruitment poster reading 'Your country needs you'.",
        "source_ids": ["src_poster"],
        "permission": "public_domain",
    }

    def seed_sourced_reference(self, *, image: str = "required", recorded: bool = True) -> None:
        """Give the lesson a cited-reference spec and the capability decision that judges it."""
        page: dict = {"locale": "en"}
        if recorded:
            page["policy"] = {
                "recipe": "committed",
                "evidence_target": "transfer",
                "check_angle": "analysis",
                "rubric_profile": "source_analysis",
                "image": image,
                "image_role": "sourced_reference",
                "audio": "none",
                "audio_role": None,
            }
        self.execute(
            "UPDATE gen_lessons SET page_json = ?, media_json = ? WHERE id = ?",
            (json.dumps(page), json.dumps([dict(self.SOURCED_ITEM)]), self.lesson_id),
        )

    def test_a_required_sourced_reference_is_flagged_media_incomplete_not_silently_text(self) -> None:
        self.seed_sourced_reference(image="required")
        host = FakeHost()
        summary = self.generate(host)
        # No provider was invented to fill the gap, and nothing was stored as the reference.
        self.assertEqual(host.images, [])
        self.assertEqual(summary.generated, 0)
        self.assertEqual(summary.degraded, 0)
        self.assertEqual(summary.incomplete, 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)
        item = self.stored_media()[0]
        self.assertEqual(item["media_status"], artifacts.MEDIA_STATE_INCOMPLETE)
        # The text equivalent really is what the learner gets, so the renderer's fallback flag is
        # true; the named state is what separates this from an optional provider hiccup.
        self.assertTrue(item["degraded"])
        self.assertFalse(item.get("artifact_id"))
        self.assertIn("src_poster", item["reason"])
        self.assertIn("public_domain", item["reason"])
        self.assertIn("not the reference", item["reason"])
        self.assertEqual(item["label"], artifacts.INCOMPLETE_REFERENCE_LABEL)
        self.assertEqual(item["missing"]["source_ids"], ["src_poster"])
        self.assertIsNone(item["missing"]["asset"])
        # The stage reports it: the job checkpoint names the lesson and the source it lacks.
        checkpoint = summary.as_checkpoint()
        self.assertEqual(checkpoint["incomplete"], 1)
        self.assertEqual(checkpoint["incomplete_items"][0]["lesson_id"], self.lesson_id)
        self.assertEqual(checkpoint["incomplete_items"][0]["source_ids"], ["src_poster"])

    def test_an_unbound_host_still_flags_a_required_reference(self) -> None:
        # A cited reference never needed a provider, so a profile with no media seam must not ship
        # a source-analysis lesson that looks complete.
        self.seed_sourced_reference(image="required")
        previous = media._HOST_MEDIA
        media._HOST_MEDIA = None
        try:
            with db.read() as connection:
                summary = media.generate_for_lessons(
                    connection,
                    lesson_ids=[self.lesson_id],
                    job_id="job_media_1",
                    store=self.store,
                    now=datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc),
                )
        finally:
            media._HOST_MEDIA = previous
        self.assertEqual(summary.incomplete, 1)
        item = self.stored_media()[0]
        self.assertEqual(item["media_status"], artifacts.MEDIA_STATE_INCOMPLETE)
        self.assertIn("src_poster", item["reason"])

    def test_the_flagged_reference_reaches_the_learner_page_as_a_named_reason(self) -> None:
        self.seed_sourced_reference(image="required")
        self.generate(FakeHost())
        with db.read() as connection:
            page = generation.learner_page(connection, self.lesson_id)
        served = page["media"][0]
        self.assertFalse(served.get("artifact_id"))
        self.assertTrue(served["degraded"])
        self.assertIn("src_poster", served["reason"])
        self.assertEqual(served["label"], artifacts.INCOMPLETE_REFERENCE_LABEL)
        children = [child for block in page["document"]["blocks"] for child in block["media"]]
        self.assertEqual(len(children), 1)
        self.assertFalse(children[0].get("artifact_id"))
        self.assertTrue(children[0]["degraded"])
        self.assertEqual(children[0]["reason"], served["reason"])
        self.assertEqual(children[0]["label"], artifacts.INCOMPLETE_REFERENCE_LABEL)

    def test_an_optional_sourced_reference_degrades_and_still_names_the_source(self) -> None:
        self.seed_sourced_reference(image="optional")
        summary = self.generate(FakeHost())
        self.assertEqual(summary.incomplete, 0)
        self.assertEqual(summary.degraded, 1)
        item = self.stored_media()[0]
        self.assertEqual(item["media_status"], artifacts.MEDIA_STATE_DEGRADED)
        self.assertIn("optional cited source src_poster", item["reason"])

    def test_a_lesson_with_no_recorded_capability_decision_treats_the_reference_as_required(self) -> None:
        # A page that cannot prove the reference was optional must not be allowed to look complete.
        self.seed_sourced_reference(recorded=False)
        summary = self.generate(FakeHost())
        self.assertEqual(summary.incomplete, 1)
        item = self.stored_media()[0]
        self.assertEqual(item["media_status"], artifacts.MEDIA_STATE_INCOMPLETE)
        self.assertIn("no capability decision", item["reason"])

    def test_a_cited_reference_without_a_permission_record_is_refused_by_name(self) -> None:
        self.seed_sourced_reference(image="required")
        self.execute(
            "UPDATE gen_lessons SET media_json = ? WHERE id = ?",
            (json.dumps([{**self.SOURCED_ITEM, "permission": "unknown"}]), self.lesson_id),
        )
        summary = self.generate(FakeHost())
        # The lesson still requires the reference, so the refusal is an incomplete lesson, not a
        # quiet degradation; the validation text naming the bad permission is kept.
        self.assertEqual(summary.incomplete, 1)
        self.assertEqual(summary.degraded, 0)
        item = self.stored_media()[0]
        self.assertEqual(item["media_status"], artifacts.MEDIA_STATE_INCOMPLETE)
        self.assertIn("unknown permission", item["reason"])
        self.assertFalse(item.get("artifact_id"))

    def test_the_projected_segment_names_the_missing_reference(self) -> None:
        # The lesson_segments path has no document-level reason slot: if the reason is not in the
        # text, the learner reads an ordinary paragraph and the gap disappears.
        self.seed_sourced_reference(image="required")
        self.generate(FakeHost())
        self.execute(
            "INSERT INTO lesson_runs (id, enrollment_id, objective_id, state, revision, created_at,"
            " updated_at, last_opened_at) VALUES (?, ?, ?, 'active', 0, ?, ?, ?)",
            ("run_sourced_1", self.enrollment_id, self.objective_id, NOW, NOW, NOW),
        )
        with db.transaction() as connection:
            count = media.seed_authored_media(
                connection,
                lesson_run_id="run_sourced_1",
                objective_id=self.objective_id,
                now=NOW,
            )
        self.assertEqual(count, 1)
        segment = self.rows(
            "SELECT text, artifact_id FROM lesson_segments WHERE lesson_run_id = ?",
            ("run_sourced_1",),
        )[0]
        self.assertIsNone(segment["artifact_id"])
        self.assertIn("Your country needs you", segment["text"])
        self.assertIn("src_poster", segment["text"])
        self.assertIn("not the reference", segment["text"])

    def test_a_delivered_medium_records_its_state_and_no_missing_block(self) -> None:
        self.generate(FakeHost())
        for item in self.stored_media():
            self.assertEqual(item["media_status"], artifacts.MEDIA_STATE_DELIVERED)
            self.assertIsNone(item["missing"])


class MediaSpecTest(unittest.TestCase):
    def test_audio_spec_defaults_voice_and_language_from_locale(self) -> None:
        spec = media._media_spec(
            {
                "kind": "audio",
                "role": "narration",
                "text_equivalent": "こんにちは",
                "transcript": "こんにちは",
            },
            locale="ja-JP",
        )
        self.assertEqual(spec.voice, "default")
        self.assertEqual(spec.language, "ja-JP")
        self.assertEqual(spec.transcript, "こんにちは")
        self.assertEqual(media.artifacts.media_problems(spec), [])

    def test_illustration_technical_claim_is_refused(self) -> None:
        spec = media._media_spec(
            {
                "kind": "visual",
                "role": "illustration",
                "spec": "A torque sequence",
                "text_equivalent": "A torque sequence",
                "technical": True,
            }
        )
        self.assertTrue(media.artifacts.media_problems(spec))

    def test_a_sourced_reference_gap_names_its_source_and_permission(self) -> None:
        spec = media._media_spec(
            {
                "kind": "visual",
                "role": "sourced_technical",
                "spec": "A wartime recruitment poster photograph",
                "text_equivalent": "A recruitment poster.",
                "source_ids": ["src_poster"],
                "permission": "public_domain",
            }
        )
        gap = artifacts.sourced_reference_gap(spec, required=True)
        assert gap is not None
        self.assertTrue(gap["required"])
        self.assertIn("src_poster", gap["reason"])
        self.assertIn("public_domain", gap["reason"])
        self.assertEqual(gap["missing"]["source_ids"], ["src_poster"])
        self.assertIsNone(gap["missing"]["asset"])
        # A delivered medium has no gap: the function is about the cited-reference role only.
        narration = media._media_spec(
            {"kind": "audio", "role": "narration", "text_equivalent": "hi", "transcript": "hi"}
        )
        self.assertIsNone(artifacts.sourced_reference_gap(narration, required=True))
