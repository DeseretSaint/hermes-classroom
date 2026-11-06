"""Artifact cache, safe media policies, text fallback and renderer manifest.

These run against the real profile database and a real content-addressed directory under the
throwaway ``HERMES_HOME``; nothing about the store is mocked.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from coursebook import artifacts, db, workers
from tests.kernel_support import KernelCase

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"x" * 32
WAV = b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt " + b"\x00" * 32

SAFE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    b'<title>Box</title><rect x="1" y="1" width="10" height="10" fill="#000"/></svg>'
)


class SvgPolicyTest(unittest.TestCase):
    def test_safe_subset_is_accepted(self) -> None:
        once = artifacts.sanitize_svg(SAFE_SVG)
        self.assertIn(b"<svg", once)
        self.assertIn(b"<rect", once)
        self.assertEqual(artifacts.sanitize_svg(once), once, "sanitizing is idempotent")

    def test_script_element_is_rejected(self) -> None:
        with self.assertRaises(artifacts.UnsafeMedia):
            artifacts.sanitize_svg(b'<svg xmlns="http://www.w3.org/2000/svg"><script>x()</script></svg>')

    def test_event_handler_attribute_is_rejected(self) -> None:
        with self.assertRaises(artifacts.UnsafeMedia):
            artifacts.sanitize_svg(b'<svg xmlns="http://www.w3.org/2000/svg" onload="x()"/>')

    def test_foreign_object_is_rejected(self) -> None:
        with self.assertRaises(artifacts.UnsafeMedia):
            artifacts.sanitize_svg(
                b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>'
            )

    def test_external_href_is_rejected(self) -> None:
        with self.assertRaises(artifacts.UnsafeMedia):
            artifacts.sanitize_svg(
                b'<svg xmlns="http://www.w3.org/2000/svg"><use href="https://evil.test/x.svg"/></svg>'
            )

    def test_doctype_and_entities_are_rejected(self) -> None:
        with self.assertRaises(artifacts.UnsafeMedia):
            artifacts.sanitize_svg(b'<!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg"/>')

    def test_schematic_is_deterministic_and_labelled(self) -> None:
        facts = [{"label": "Voltage", "value": "12 V", "row": 1}, {"label": "Current", "value": "2 A", "row": 2}]
        first = artifacts.make_schematic_svg("Circuit", facts)
        second = artifacts.make_schematic_svg("Circuit", facts)
        self.assertEqual(first, second)
        self.assertIn(b"Deterministic schematic", first)
        self.assertIn(b"12 V", first)


class PdfPolicyTest(unittest.TestCase):
    def test_pdf_has_selectable_text_and_no_active_content(self) -> None:
        data = artifacts.make_pdf("Lesson: braising", ["Step one: sear the meat", "Step two: simmer"])
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertTrue(data.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"(Step one: sear the meat) Tj", data)
        self.assertNotIn(b"/JavaScript", data)
        self.assertNotIn(b"/EmbeddedFile", data)

    def test_pdf_escapes_parentheses(self) -> None:
        data = artifacts.make_pdf("Title (draft)", ["a (b) c"])
        self.assertIn(b"a \\(b\\) c", data)


class MimePolicyTest(unittest.TestCase):
    def test_text_declared_as_png_is_rejected(self) -> None:
        with self.assertRaises(artifacts.UnsafeMedia):
            artifacts.sniff_mime(b"hello", "image/png")

    def test_unknown_bytes_are_rejected(self) -> None:
        with self.assertRaises(artifacts.UnsafeMedia):
            artifacts.sniff_mime(b"hello")

    def test_svg_declared_as_png_is_rejected(self) -> None:
        with self.assertRaises(artifacts.UnsafeMedia):
            artifacts.sniff_mime(SAFE_SVG, "image/png")

    def test_audio_magic_is_detected(self) -> None:
        self.assertEqual(artifacts.sniff_mime(WAV), "audio/wav")


class SpecPolicyTest(unittest.TestCase):
    def spec(self, **kwargs) -> artifacts.MediaSpec:
        base = dict(kind="visual", role="schematic", text_equivalent="A box", facts={"rows": 1})
        base.update(kwargs)
        return artifacts.MediaSpec(**base)

    def test_missing_text_equivalent_is_refused(self) -> None:
        problems = artifacts.media_problems(self.spec(text_equivalent=""))
        self.assertIn("every artifact needs a text equivalent", problems)

    def test_illustration_may_not_claim_technical_authority(self) -> None:
        problems = artifacts.media_problems(self.spec(role="illustration", technical=True))
        self.assertIn("an illustration may not claim technical authority", problems)
        self.assertIn("not a measurement", artifacts.honesty_label(self.spec(role="illustration")))

    def test_sourced_reference_needs_source_and_permission(self) -> None:
        problems = artifacts.media_problems(self.spec(role="sourced_technical"))
        self.assertIn("sourced technical reference needs at least one cited source", problems)
        problems = artifacts.media_problems(
            self.spec(role="sourced_technical", source_ids=("src_1",), permission="unknown")
        )
        self.assertIn("unknown permission cannot be presented as a technical reference", problems)

    def test_narration_needs_transcript_and_voice_metadata(self) -> None:
        problems = artifacts.media_problems(self.spec(kind="audio", role="narration"))
        self.assertIn("narration needs its transcript (the text equivalent)", problems)
        self.assertIn("narration needs voice and language metadata", problems)

    def test_schematic_needs_structured_facts(self) -> None:
        problems = artifacts.media_problems(self.spec(facts={}))
        self.assertIn("a schematic must be rendered from structured facts, not free text", problems)


class StoreTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = artifacts.ArtifactStore(Path(self.home) / "artifacts")
        self.course_id, _ = self.new_course()

    def test_store_roundtrip_is_content_addressed(self) -> None:
        artifact = self.store.save(
            course_id=self.course_id, kind="visual", data=PNG, mime="image/png",
            provenance={"role": "illustration", "text_equivalent": "A diagram"},
        )
        self.assertTrue(artifact["content_hash"].startswith("sha256:"))
        path = Path(self.rows("SELECT path FROM artifacts WHERE id = ?", (artifact["artifact_id"],))[0]["path"])
        self.assertTrue(path.exists())
        self.assertIn(artifact["content_hash"].split(":", 1)[1], path.name)

    def test_duplicate_bytes_are_one_row_and_one_file(self) -> None:
        first = self.store.save(course_id=self.course_id, kind="visual", data=PNG, mime="image/png",
                                provenance={"text_equivalent": "A"})
        second = self.store.save(course_id=self.course_id, kind="visual", data=PNG, mime="image/png",
                                 provenance={"text_equivalent": "A"})
        self.assertEqual(first["artifact_id"], second["artifact_id"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 1)
        self.assertEqual(self.scalar("SELECT ref_count FROM artifacts"), 2)
        objects = [p for p in (Path(self.home) / "artifacts" / "objects").rglob("*") if p.is_file()]
        self.assertEqual(len(objects), 1)

    def test_cache_lookup_by_spec_and_source_hash(self) -> None:
        spec_fp = artifacts.spec_hash({"x": 1})
        source_fp = artifacts.source_hash(["page one"])
        artifact = self.store.save(
            course_id=self.course_id, kind="visual", data=PNG, mime="image/png",
            provenance={"text_equivalent": "A", "spec_hash": spec_fp, "source_hash": source_fp},
        )
        with db.read() as connection:
            by_spec = self.store.lookup(connection, kind="visual", spec_fingerprint=spec_fp)
            by_source = self.store.lookup(connection, kind="visual", source_fingerprint=source_fp)
            miss = self.store.lookup(connection, kind="visual", spec_fingerprint="nope")
        self.assertEqual(by_spec["artifact_id"], artifact["artifact_id"])
        self.assertEqual(by_source["artifact_id"], artifact["artifact_id"])
        self.assertIsNone(miss)

    def test_reconcile_removes_stale_staging_and_unreferenced_objects_only(self) -> None:
        artifact = self.store.save(course_id=self.course_id, kind="visual", data=PNG, mime="image/png",
                                   provenance={"text_equivalent": "A"})
        kept = Path(self.rows("SELECT path FROM artifacts WHERE id = ?", (artifact["artifact_id"],))[0]["path"])
        staging = self.store.staging_dir
        staging.mkdir(parents=True, exist_ok=True)
        orphan_stage = staging / "old.part"
        orphan_stage.write_bytes(b"junk")
        orphan_object = self.store.objects_dir / "ff" / "deadbeef"
        orphan_object.parent.mkdir(parents=True, exist_ok=True)
        orphan_object.write_bytes(b"orphan")
        old = (artifacts._now()).timestamp() - 7200
        os.utime(orphan_stage, (old, old))
        os.utime(orphan_object, (old, old))
        counts = self.store.reconcile()
        self.assertFalse(orphan_stage.exists())
        self.assertFalse(orphan_object.exists())
        self.assertTrue(kept.exists(), "a referenced artifact is never deleted")
        self.assertEqual(counts["staging"], 1)
        self.assertEqual(counts["objects"], 1)


class FallbackTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = artifacts.ArtifactStore(Path(self.home) / "artifacts")

    def test_provider_failure_returns_complete_text_and_triage(self) -> None:
        spec = artifacts.MediaSpec(kind="audio", role="narration", text_equivalent="Full lesson text",
                                   voice="voice-a", language="ja-JP", transcript="Full lesson text")

        def unavailable() -> bytes:
            raise artifacts.MediaUnavailable("voice not installed")

        outcome = artifacts.produce_with_fallback(
            self.store, spec, unavailable, course_id=None, mime="audio/wav"
        )
        self.assertTrue(outcome.degraded)
        self.assertIsNone(outcome.artifact)
        self.assertEqual(outcome.text_equivalent, "Full lesson text")
        self.assertIn("use_text_fallback", outcome.triage["options"])
        self.assertFalse(outcome.triage["silent_substitution"])

    def test_unavailable_voice_reuses_cached_original_without_new_spend(self) -> None:
        spec = artifacts.MediaSpec(kind="audio", role="narration", text_equivalent="Text",
                                   voice="voice-a", language="en-US", transcript="Text")
        cached = {"artifact_id": "art_cached", "mime": "audio/wav", "content_hash": "sha256:abc"}

        def unavailable() -> bytes:
            raise artifacts.MediaUnavailable("voice not installed")

        outcome = artifacts.produce_with_fallback(
            self.store, spec, unavailable, course_id=None, mime="audio/wav", cached=cached
        )
        self.assertEqual(outcome.artifact["artifact_id"], "art_cached")
        self.assertIn("kept the cached original", outcome.reason)

    def test_non_renderable_mime_cannot_reach_the_renderer(self) -> None:
        with self.assertRaises(artifacts.UnsafeMedia):
            artifacts.media_marker({"mime": "text/html", "path": "/tmp/x"}, path="/tmp/x")


class MediaJobTest(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = artifacts.ArtifactStore(Path(self.home) / "artifacts")
        self.course_id, _ = self.new_course()

    def request(self, producer, *, text: str = "A labelled box") -> workers.MediaRequest:
        spec = artifacts.MediaSpec(kind="visual", role="schematic", text_equivalent=text,
                                   facts={"rows": 1})
        return workers.MediaRequest(
            spec=spec, producer=producer, mime="image/svg+xml", course_id=self.course_id,
            source_texts=("facts-v1",), provenance={"provider": "deterministic"},
        )

    def test_second_job_with_same_spec_makes_no_provider_call(self) -> None:
        calls = {"n": 0}

        def producer() -> bytes:
            calls["n"] += 1
            return artifacts.make_schematic_svg("Box", [{"label": "a", "value": "b", "row": 1}])

        first = workers.run_media_job(self.request(producer), store=self.store)
        self.assertEqual(first["state"], "completed")
        second = workers.run_media_job(self.request(producer), store=self.store)
        self.assertEqual(second["state"], "completed")
        self.assertEqual(calls["n"], 1, "the cache must prevent a second provider call")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 1)

    def test_crash_after_adoption_does_not_duplicate_the_artifact_on_retry(self) -> None:
        calls = {"n": 0}

        def producer() -> bytes:
            calls["n"] += 1
            return artifacts.make_schematic_svg("Box", [{"label": "a", "value": "b", "row": 1}])

        from coursebook import job_service

        request = self.request(producer)
        job_id = job_service.create("media", {"kind": "visual"})["job_id"]
        from unittest import mock

        with mock.patch.object(artifacts, "renderer_manifest", side_effect=RuntimeError("renderer down")):
            view = job_service.execute(job_id, workers.media_stages(request, store=self.store))
        self.assertEqual(view["state"], "failed")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 1)

        job_service.resume(job_id)
        view = job_service.execute(job_id, workers.media_stages(request, store=self.store))
        self.assertEqual(view["state"], "completed")
        self.assertEqual(calls["n"], 1, "the retry reuses the adopted artifact instead of paying again")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 1)
        objects = [p for p in (Path(self.home) / "artifacts" / "objects").rglob("*") if p.is_file()]
        self.assertEqual(len(objects), 1)

    def test_generation_failure_completes_with_text_fallback(self) -> None:
        def producer() -> bytes:
            raise artifacts.MediaUnavailable("image provider offline")

        view = workers.run_media_job(self.request(producer), store=self.store)
        self.assertEqual(view["state"], "completed")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)
        self.assertTrue(view["checkpoint"]["degraded"])
        self.assertIn("image provider offline", view["checkpoint"]["reason"])
        self.assertEqual(view["checkpoint"]["text_equivalent"], "A labelled box")


if __name__ == "__main__":
    unittest.main()
