"""The adversarial review gate on generated illustrations.

Covers four boundaries the owner asked for:

* a generated picture is judged against its prompt before the bytes are stored, and the verdict is
  persisted on both the artifact and the lesson's media item;
* a rejected picture is re-prompted once and then degrades to its text equivalent with the reason —
  it never ships;
* a host with no vision seam yields ``unreviewed``, never a silent ``approved``;
* a technical procedure may carry context art beside its authority visual, and a lesson that drops
  the schematic for the picture is still refused.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from coursebook import artifacts, db, generation, media, policy

from tests.kernel_support import KernelCase

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"x" * 32
PNG_RETRY = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"y" * 32
JPEG = b"\xff\xd8\xff" + b"x" * 32
MP3 = b"\xff\xfb\x90\x00" + b"x" * 32
NOW = "2026-11-06T12:00:00Z"
HASH = "sha256:" + "a" * 64


class VerdictHost:
    """A host double that answers the review seam with a queued verdict per call."""

    def __init__(self, *verdicts, images=None) -> None:
        self.verdicts = list(verdicts)
        self.images = list(images or [PNG])
        self.prompts: list[str] = []
        self.reviews: list[dict] = []

    def image(self, prompt: str, *, aspect_ratio: str = "landscape"):
        self.prompts.append(prompt)
        return self.images[min(len(self.prompts) - 1, len(self.images) - 1)], "image/png"

    def review_image(self, data: bytes, *, mime: str, prompt: str, text_equivalent: str = ""):
        self.reviews.append(
            {"data": data, "mime": mime, "prompt": prompt, "text_equivalent": text_equivalent}
        )
        if not self.verdicts:
            raise AssertionError("the gate called the reviewer more times than expected")
        verdict = self.verdicts.pop(0)
        if isinstance(verdict, Exception):
            raise verdict
        return verdict


class PlainHost:
    """A host with image generation only: no vision seam exists."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def image(self, prompt: str, *, aspect_ratio: str = "landscape") -> tuple[bytes, str]:
        self.prompts.append(prompt)
        return PNG, "image/png"


class JpegHost(PlainHost):
    """A provider that returns JPEG whatever the caller asked for."""

    def image(self, prompt: str, *, aspect_ratio: str = "landscape") -> tuple[bytes, str]:
        self.prompts.append(prompt)
        return JPEG, "image/jpeg"

    def review_image(self, data: bytes, *, mime: str, prompt: str, text_equivalent: str = ""):
        return artifacts.review_record("approved", ["a caliper on a bench"])


class BuiltIllustrationPromptTest(unittest.TestCase):
    """Item 27: the illustration prompt is built, not forwarded from the author's sentence."""

    def spec(self, **overrides) -> artifacts.MediaSpec:
        item = {
            "kind": "visual",
            "role": "illustration",
            "purpose": "See the bench",
            "spec": "An editorial illustration of a workshop bench with a torque wrench",
            "text_equivalent": "A workshop bench with a torque wrench.",
        }
        item.update(overrides)
        return media._media_spec(item)

    def test_every_block_is_in_the_built_prompt(self) -> None:
        built = media.lesson_illustration_prompt(self.spec())
        prompt = built.prompt
        # subject, composition, medium and palette, textless block, negative list.
        self.assertIn("workshop bench with a torque wrench", prompt)
        self.assertIn("The picture shows", prompt)
        self.assertIn("It is composed as", prompt)
        self.assertIn("The medium is", prompt)
        self.assertIn("palette", prompt)
        self.assertIn("contains no words at all", prompt)
        self.assertIn("Avoid everything in this list", prompt)
        for negative in (
            "no text",
            "no letters, words or labels",
            "no numbers",
            "no arrows",
            "no watermark",
            "no user interface",
        ):
            with self.subTest(negative=negative):
                self.assertIn(negative, prompt)
        self.assertNotEqual(prompt, self.spec().prompt)

    def test_a_spec_that_asks_for_labels_is_not_forwarded_verbatim(self) -> None:
        spec = self.spec(
            spec=(
                "An editorial illustration of a workshop bench, with labels on every part and a "
                "numbered callout on the wrench."
            ),
            text_equivalent="A bench whose parts are labelled.",
        )
        built = media.lesson_illustration_prompt(spec)
        self.assertIn("workshop bench", built.prompt)
        # The request itself is rewritten out, and the negative list still refuses the labels.
        self.assertNotIn("with labels", built.prompt)
        self.assertNotIn("numbered callout", built.prompt)
        self.assertIn("no letters, words or labels", built.prompt)

    def test_a_labelling_adjective_is_stripped_from_the_subject(self) -> None:
        built = media.lesson_illustration_prompt(
            self.spec(spec="An illustration of a labelled brake caliper on a bench")
        )
        self.assertIn("a brake caliper on a bench", built.subject)
        self.assertNotIn("labelled", built.subject)

    def test_the_hash_covers_the_blocks_and_is_stable(self) -> None:
        first = media.lesson_illustration_prompt(self.spec())
        second = media.lesson_illustration_prompt(self.spec())
        self.assertEqual(first.prompt_hash, second.prompt_hash)
        other = media.lesson_illustration_prompt(self.spec(spec="An illustration of a brake caliper"))
        self.assertNotEqual(first.prompt_hash, other.prompt_hash)
        self.assertEqual(first.prompt_version, media.ILLUSTRATION_PROMPT_VERSION)

    def test_the_plate_ratio_is_chosen_by_role(self) -> None:
        self.assertEqual(media.figure_aspect_ratio("visual", "illustration"), "4:3")
        self.assertEqual(media.figure_aspect_ratio("visual", "schematic"), "4:3")
        self.assertEqual(
            media.figure_aspect_ratio("visual", "illustration", "a portrait of a learner"), "3:4"
        )
        self.assertIsNone(media.figure_aspect_ratio("audio", "narration"))


class ReviewGateCase(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.course_id, self.plan_id = self.new_course()
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        self.objective_id = self.seed_objective(self.plan_id)
        self.store = artifacts.ArtifactStore()
        self.execute(
            "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint, plan_hash,"
            " document_json, research_json, generation_state, validation_id, result_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, '{}', 'validated', NULL, '{}', ?)",
            ("gen_doc_1", self.plan_id, self.course_id, "fp-1", HASH, json.dumps({"locale": "en-US"}), NOW),
        )
        self.execute(
            "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
            " objective_refs_json, context_needs_json, source_ids_json)"
            " VALUES (?, ?, 1, ?, ?, ?, ?, '[]', '[]')",
            (
                "sec_1",
                self.plan_id,
                HASH,
                "Replace the front brake pads",
                "Follow the pad replacement sequence",
                json.dumps([1]),
            ),
        )
        self.lesson_id = "gen_lesson_review"
        self.media_items = [
            {
                "kind": "visual",
                "role": "illustration",
                "purpose": "See the brake caliper on the bench",
                "spec": "An editorial illustration of a brake caliper on a workshop bench",
                "text_equivalent": "A brake caliper rests on a workshop bench.",
            }
        ]
        self.insert_lesson(self.media_items)

    def insert_lesson(self, items: list[dict]) -> None:
        if self.rows("SELECT id FROM gen_lessons WHERE id = ?", (self.lesson_id,)):
            self.execute(
                "UPDATE gen_lessons SET media_json = ? WHERE id = ?",
                (json.dumps(items), self.lesson_id),
            )
            return
        self.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json,"
            " media_json, parent_notes_json, rejection_reasons_json, validation_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 1, 'validated', '{}', ?, '{}', '[]', NULL, ?, ?)",
            (self.lesson_id, self.plan_id, "sec_1", HASH, json.dumps(items), NOW, NOW),
        )

    def generate(self, host):
        with db.read() as connection:
            return media.generate_for_lessons(
                connection,
                lesson_ids=[self.lesson_id],
                job_id="job_review_1",
                host=host,
                store=self.store,
                now=datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc),
            )

    def stored_media(self) -> list[dict]:
        row = self.rows("SELECT media_json FROM gen_lessons WHERE id = ?", (self.lesson_id,))[0]
        return json.loads(row["media_json"])

    def provenance_of(self, artifact_id: str) -> dict:
        return json.loads(
            str(self.scalar("SELECT provenance_json FROM artifacts WHERE id = ?", (artifact_id,)))
        )


class ApprovedIllustrationTest(ReviewGateCase):
    def test_an_approved_illustration_is_stored_with_its_verdict(self) -> None:
        verdict = artifacts.review_record(
            "approved", ["a brake caliper on a bench; no text, steps or measurements"]
        )
        host = VerdictHost(verdict)
        summary = self.generate(host)

        self.assertEqual(summary.generated, 1)
        self.assertEqual(summary.degraded, 0)
        self.assertEqual(summary.reviewed, 1)
        self.assertEqual(summary.rejected, 0)
        self.assertEqual(summary.as_checkpoint()["reviewed"], 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 1)
        item = self.stored_media()[0]
        self.assertEqual(item["review"], verdict)
        self.assertTrue(item["artifact_id"])
        self.assertFalse(item["degraded"])
        self.assertIn("context only", item["label"])

        # The verdict is part of the artifact, not just the lesson row: a later reader of the bytes
        # can see what the reviewer said without trusting the lesson projection.
        provenance = self.provenance_of(item["artifact_id"])
        self.assertEqual(provenance["review"], verdict)
        preview = media.preview_artifact(item["artifact_id"])
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["review"], verdict)

        # The reviewer saw the generated bytes and the prompt the author wrote.
        self.assertEqual(len(host.reviews), 1)
        self.assertEqual(host.reviews[0]["data"], PNG)
        self.assertEqual(host.reviews[0]["mime"], "image/png")
        self.assertEqual(
            host.reviews[0]["prompt"],
            "An editorial illustration of a brake caliper on a workshop bench",
        )

    def test_a_rejected_first_attempt_is_replaced_by_an_approved_retry(self) -> None:
        rejected = artifacts.review_record(
            "rejected",
            ["the picture contains legible text or numbers a learner could read as a fact"],
            ["contains_legible_text"],
        )
        approved = artifacts.review_record("approved", ["a caliper on a bench, no text"])
        host = VerdictHost(rejected, approved, images=[PNG, PNG_RETRY])
        summary = self.generate(host)

        self.assertEqual(summary.generated, 1)
        self.assertEqual(len(host.prompts), 2)
        # Item 32: the second request is rebuilt for the failed criterion, not the first request
        # with a paragraph appended.
        self.assertNotEqual(host.prompts[1], host.prompts[0])
        self.assertIn(media.REVISION_CRITERIA["contains_legible_text"], host.prompts[1])
        self.assertIn(media.ILLUSTRATION_TEXTLESS_STRICT, host.prompts[1])
        self.assertNotIn("previous attempt was rejected", host.prompts[1])
        self.assertEqual(host.reviews[-1]["data"], PNG_RETRY)

        item = self.stored_media()[0]
        self.assertEqual(item["review"], approved)
        stored = Path(
            str(self.scalar("SELECT path FROM artifacts WHERE id = ?", (item["artifact_id"],)))
        ).read_bytes()
        self.assertEqual(stored, PNG_RETRY)

    def test_the_second_request_differs_structurally_not_by_appended_prose(self) -> None:
        """Item 32 acceptance: a first-attempt rejection produces a structurally different request.

        The four things proved here are the four ways the old prose retry failed:
        the request is not a superset of the first one; the failing criterion is named; the
        textless discipline becomes a hard constraint block; and the reviewer's own sentence is
        never forwarded to the provider.
        """
        verdict = artifacts.review_record(
            "rejected",
            ["the picture contains legible text or numbers a learner could read as a fact"],
            ["contains_legible_text"],
        )
        spec = media._media_spec(self.media_items[0], locale="en-US")
        first = media.lesson_illustration_prompt(spec)
        revised = media.revision_request(spec, verdict)

        self.assertEqual(revised.criteria, ("contains_legible_text",))
        self.assertNotEqual(revised.prompt_hash, first.prompt_hash)
        self.assertFalse(revised.prompt.startswith(first.prompt))
        self.assertIn(media.REVISION_CRITERIA["contains_legible_text"], revised.prompt)
        self.assertIn(media.ILLUSTRATION_TEXTLESS_STRICT, revised.prompt)
        self.assertNotIn(media.ILLUSTRATION_TEXTLESS, revised.prompt)
        self.assertNotIn(verdict["reasons"][0], revised.prompt)
        # The house rule survives the repair: subject, composition, medium, palette and negatives.
        for block in (
            first.subject,
            media.ILLUSTRATION_MEDIUM,
            media.ILLUSTRATION_PALETTE,
            media.ILLUSTRATION_NEGATIVES[0],
        ):
            self.assertIn(block, revised.prompt)
        self.assertEqual(revised.subject, first.subject)

    def test_a_legacy_verdict_without_criteria_still_gets_a_different_request(self) -> None:
        # A hand-built verdict (or one written before the gate recorded ``criteria``) must not
        # re-ask the identical request: re-rolling is the one repair that cannot work.
        spec = media._media_spec(self.media_items[0], locale="en-US")
        first = media.lesson_illustration_prompt(spec)
        legacy = artifacts.review_record("rejected", ["it felt wrong"])
        revised = media.revision_request(spec, legacy)
        self.assertNotEqual(revised.prompt, first.prompt)
        self.assertEqual(revised.criteria, artifacts.REVIEW_CHECKS)


class BuiltPromptProvenanceTest(ReviewGateCase):
    """Item 27/30: what the provider was asked for is recorded with the bytes."""

    def built(self):
        return media.lesson_illustration_prompt(
            media._media_spec(self.media_items[0], locale="en-US")
        )

    def test_the_provenance_records_the_built_prompt_hash(self) -> None:
        host = VerdictHost(artifacts.review_record("approved", ["a caliper on a bench"]))
        self.generate(host)
        item = self.stored_media()[0]
        built = self.built()
        self.assertEqual(host.prompts, [built.prompt])
        self.assertNotEqual(host.prompts[0], self.media_items[0]["spec"])
        provenance = self.provenance_of(item["artifact_id"])
        self.assertEqual(provenance["prompt_hash"], built.prompt_hash)
        self.assertEqual(provenance["prompt_version"], media.ILLUSTRATION_PROMPT_VERSION)
        self.assertEqual(provenance["aspect_ratio"], "4:3")
        self.assertEqual(provenance["min_width_px"], media.MIN_FIGURE_WIDTH_PX)

    def test_a_rejected_illustration_is_re_prompted_from_the_built_request(self) -> None:
        host = VerdictHost(
            artifacts.review_record(
                "rejected", ["legible text on the bench"], ["contains_legible_text"]
            ),
            artifacts.review_record("approved", ["a caliper on a bench, no text"]),
            images=[PNG, PNG_RETRY],
        )
        self.generate(host)
        built = self.built()
        # The revision keeps the textless discipline and the negative list; dropping them would
        # repaint the same defect the reviewer rejected, and it names the failed criterion instead
        # of forwarding the reviewer's sentence.
        self.assertIn("no letters, words or labels", host.prompts[1])
        self.assertIn(media.REVISION_CRITERIA["contains_legible_text"], host.prompts[1])
        self.assertNotIn("legible text on the bench", host.prompts[1])
        self.assertIn(built.subject, host.prompts[1])

    def test_a_rejected_illustration_with_schematic_rows_falls_back_to_the_drawn_table(self) -> None:
        """Item 32 acceptance: rows exist, so the repair is the deterministic schematic.

        No second provider call is made. The table is drawn from the typed rows the item already
        carries, so it cannot paint a number or a step, and the rejection that caused the fallback
        stays on the item with the criteria that failed.
        """
        self.media_items[0]["facts"] = {
            "procedure": {
                "schematic": {
                    "title": "Front brake pad replacement",
                    "rows": [
                        {"label": "Caliper bolt", "value": "25 Nm"},
                        {"label": "Pad thickness", "value": "3 mm minimum"},
                    ],
                }
            }
        }
        self.insert_lesson(self.media_items)
        rejected = artifacts.review_record(
            "rejected",
            ["the picture contains legible text or numbers a learner could read as a fact"],
            ["contains_legible_text"],
        )
        host = VerdictHost(rejected)
        summary = self.generate(host)

        self.assertEqual(len(host.prompts), 1, "the schematic fallback spends no second provider call")
        self.assertEqual(len(host.reviews), 1)
        self.assertEqual(summary.generated, 1)
        self.assertEqual(summary.degraded, 1)
        self.assertEqual(summary.rejected, 1)
        item = self.stored_media()[0]
        self.assertEqual(item["mime"], "image/svg+xml")
        self.assertTrue(item["artifact_id"])
        self.assertTrue(item["degraded"])
        self.assertEqual(item["media_status"], artifacts.MEDIA_STATE_DEGRADED)
        self.assertIn("deterministic schematic", item["reason"])
        self.assertIn("contains_legible_text", item["reason"])
        self.assertEqual(item["review"]["state"], "rejected")
        self.assertEqual(item["review"]["criteria"], ["contains_legible_text"])

        provenance = self.provenance_of(item["artifact_id"])
        self.assertEqual(provenance["fallback"], "schematic")
        self.assertEqual(provenance["review"], item["review"])
        # The bytes are the product's own table render, not a provider picture.
        self.assertTrue(
            Path(str(self.scalar("SELECT path FROM artifacts WHERE id = ?", (item["artifact_id"],))))
            .read_bytes()
            .lstrip()
            .startswith(b"<svg")
        )
        preview = media.preview_artifact(item["artifact_id"])
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["mime"], "image/svg+xml")
        self.assertEqual(preview["review"]["state"], "rejected")

    def test_a_rejection_without_schematic_rows_keeps_the_text_equivalent(self) -> None:
        rejected = artifacts.review_record(
            "rejected", ["legible text"], ["contains_legible_text"]
        )
        host = VerdictHost(rejected, rejected, images=[PNG, PNG_RETRY])
        summary = self.generate(host)
        self.assertEqual(len(host.prompts), 2, "no rows means the one rebuilt request")
        self.assertEqual(summary.generated, 0)
        item = self.stored_media()[0]
        self.assertFalse(item.get("artifact_id"))
        self.assertTrue(item["degraded"])


class RejectedIllustrationTest(ReviewGateCase):
    def test_a_rejected_illustration_degrades_with_the_reason_and_never_ships(self) -> None:
        rejected = artifacts.review_record(
            "rejected",
            [
                "the picture depicts a procedure or measurement and could be read as authority",
                "it shows a torque wrench with a visible setting",
            ],
        )
        host = VerdictHost(rejected, rejected)
        summary = self.generate(host)

        self.assertEqual(summary.generated, 0)
        self.assertEqual(summary.degraded, 1)
        self.assertEqual(summary.rejected, 1)
        self.assertEqual(summary.as_checkpoint()["rejected"], 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM artifacts"), 0)
        self.assertEqual(len(host.prompts), 2, "a rejection earns exactly one re-prompt")

        item = self.stored_media()[0]
        self.assertTrue(item["degraded"])
        self.assertFalse(item.get("artifact_id"))
        self.assertEqual(item["review"]["state"], "rejected")
        self.assertIn("rejected by review", item["reason"])
        self.assertIn("depicts a procedure or measurement", item["reason"])
        self.assertIn("torque wrench", item["reason"])
        self.assertEqual(item["text_equivalent"], "A brake caliper rests on a workshop bench.")

    def test_a_second_rejection_keeps_both_reasons(self) -> None:
        first = artifacts.review_record(
            "rejected", ["does not show the subject the prompt asked for"], ["subject_matches"]
        )
        second = artifacts.review_record(
            "rejected", ["contains legible numbers"], ["contains_legible_text"]
        )
        host = VerdictHost(first, second)
        self.generate(host)
        review = self.stored_media()[0]["review"]
        self.assertEqual(review["state"], "rejected")
        self.assertTrue(any("does not show the subject" in reason for reason in review["reasons"]))
        self.assertTrue(any("legible numbers" in reason for reason in review["reasons"]))
        self.assertTrue(any("revised" in reason for reason in review["reasons"]))
        # Both attempts' failed checks travel with the final verdict.
        self.assertEqual(review["criteria"], ["subject_matches", "contains_legible_text"])


class UnreviewedIllustrationTest(ReviewGateCase):
    def test_a_jpeg_provider_result_is_stored_with_its_real_type(self) -> None:
        verdict = artifacts.review_record("approved", ["a caliper on a bench"])
        summary = self.generate(JpegHost())
        self.assertEqual(summary.generated, 1)
        item = self.stored_media()[0]
        self.assertEqual(item["mime"], "image/jpeg")
        self.assertEqual(
            self.scalar("SELECT mime FROM artifacts WHERE id = ?", (item["artifact_id"],)),
            "image/jpeg",
        )
        self.assertEqual(item["review"], verdict)

    def test_no_vision_seam_yields_unreviewed_never_approved(self) -> None:
        summary = self.generate(PlainHost())
        self.assertEqual(summary.generated, 1)
        item = self.stored_media()[0]
        self.assertEqual(item["review"]["state"], "unreviewed")
        self.assertTrue(item["review"]["reasons"])
        self.assertIn("no vision review seam", item["review"]["reasons"][0])
        self.assertIn("context only", item["label"])
        self.assertEqual(self.provenance_of(item["artifact_id"])["review"], item["review"])

    def test_a_reviewer_that_crashes_yields_unreviewed_not_a_failed_lesson(self) -> None:
        host = VerdictHost(RuntimeError("vision provider offline"))
        summary = self.generate(host)
        self.assertEqual(summary.generated, 1)
        item = self.stored_media()[0]
        self.assertEqual(item["review"]["state"], "unreviewed")
        self.assertIn("vision provider offline", " ".join(item["review"]["reasons"]))

    def test_a_cached_artifact_without_a_verdict_reads_unreviewed(self) -> None:
        spec = media._media_spec(self.media_items[0], locale="en-US")
        self.store.save(
            course_id=self.course_id,
            kind="visual",
            data=PNG,
            mime="image/png",
            provenance={
                "spec_hash": artifacts.spec_hash(spec.as_cache_spec()),
                "source_hash": artifacts.source_hash(
                    [spec.text_equivalent, spec.prompt or "", ""]
                ),
                "label": "an artifact written before the gate existed",
            },
        )
        summary = self.generate(PlainHost())
        self.assertEqual(summary.reused, 1)
        review = self.stored_media()[0]["review"]
        self.assertEqual(review["state"], "unreviewed")
        self.assertIn("predates the review gate", review["reasons"][0])

    def test_a_cache_hit_keeps_the_recorded_verdict(self) -> None:
        verdict = artifacts.review_record("approved", ["a caliper on a bench"])
        self.generate(VerdictHost(verdict))
        second = VerdictHost(artifacts.review_record("rejected", ["should not be reached"]))
        summary = self.generate(second)
        self.assertEqual(summary.reused, 1)
        self.assertEqual(second.reviews, [], "a cached approved picture is not re-reviewed")
        self.assertEqual(self.stored_media()[0]["review"], verdict)


class HostVisionSeamTest(ReviewGateCase):
    """The dispatch shape and the graceful fallbacks, exercised through the real HostMedia."""

    def host(self, answers: dict, *, calls: list) -> media.HostMedia:
        image_path = Path(self.home) / "generated.png"
        image_path.write_bytes(PNG)

        def dispatch(name: str, args: dict):
            calls.append((name, args))
            if name in answers:
                value = answers[name]
                if isinstance(value, Exception):
                    raise value
                return value
            if name == "image_generate":
                return {"success": True, "image": str(image_path)}
            raise AssertionError(f"unexpected host tool {name!r}")

        return media.HostMedia(dispatch, timeout_s=5)

    def test_the_vision_call_is_a_data_url_with_the_typed_question(self) -> None:
        calls: list = []
        answer = {
            "success": True,
            "result": json.dumps(
                {
                    "subject_matches": True,
                    "contains_legible_text": False,
                    "depicts_procedure_or_measurement": False,
                    "reason": "a caliper on a bench, no text",
                }
            ),
        }
        host = self.host({"vision_analyze": answer}, calls=calls)
        summary = self.generate(host)
        self.assertEqual(summary.generated, 1)
        self.assertEqual(self.stored_media()[0]["review"]["state"], "approved")

        review_calls = [call for call in calls if call[0] == "vision_analyze"]
        self.assertEqual(len(review_calls), 1)
        args = review_calls[0][1]
        self.assertTrue(args["image_url"].startswith("data:image/png;base64,"))
        self.assertIn("subject_matches", args["question"])
        self.assertIn("depicts_procedure_or_measurement", args["question"])
        self.assertIn("brake caliper", args["question"])

    def test_an_unavailable_vision_tool_yields_unreviewed(self) -> None:
        calls: list = []
        # The registry's own body for an unregistered tool, exactly as dispatch returns it.
        unavailable = json.dumps({"error": "Unknown tool: vision_analyze", "success": False})
        host = self.host({"vision_analyze": unavailable}, calls=calls)
        summary = self.generate(host)
        self.assertEqual(summary.generated, 1)
        review = self.stored_media()[0]["review"]
        self.assertEqual(review["state"], "unreviewed")
        self.assertIn("Unknown tool", " ".join(review["reasons"]))

    def test_a_dispatch_exception_yields_unreviewed(self) -> None:
        calls: list = []
        host = self.host({"vision_analyze": RuntimeError("tool exploded")}, calls=calls)
        self.generate(host)
        review = self.stored_media()[0]["review"]
        self.assertEqual(review["state"], "unreviewed")
        self.assertIn("tool exploded", " ".join(review["reasons"]))


class VerdictParserTest(unittest.TestCase):
    """The parser is the trust boundary: it may only ever downgrade."""

    def test_fenced_json_and_string_booleans_are_accepted(self) -> None:
        raw = (
            "Here is my verdict:\n```json\n"
            '{"subject_matches": "true", "contains_legible_text": "false", '
            '"depicts_procedure_or_measurement": "no", "reason": "a bench scene"}\n```'
        )
        verdict = media.parse_review_verdict(raw)
        self.assertEqual(verdict["state"], "approved")
        self.assertEqual(verdict["reasons"], ["a bench scene"])

    def test_legible_text_rejects(self) -> None:
        verdict = media.parse_review_verdict(
            json.dumps(
                {
                    "subject_matches": True,
                    "contains_legible_text": True,
                    "depicts_procedure_or_measurement": False,
                    "reason": "a label reads 45 Nm",
                }
            )
        )
        self.assertEqual(verdict["state"], "rejected")
        self.assertIn("legible text", verdict["reasons"][0])
        self.assertTrue(any("45 Nm" in reason for reason in verdict["reasons"]))

    def test_a_depicted_procedure_rejects(self) -> None:
        verdict = media.parse_review_verdict(
            json.dumps(
                {
                    "subject_matches": True,
                    "contains_legible_text": False,
                    "depicts_procedure_or_measurement": True,
                    "reason": "hands tightening a bolt in order",
                }
            )
        )
        self.assertEqual(verdict["state"], "rejected")
        self.assertIn("procedure or measurement", " ".join(verdict["reasons"]))

    def test_an_incomplete_verdict_is_unreviewed(self) -> None:
        verdict = media.parse_review_verdict(
            json.dumps({"subject_matches": True, "reason": "looks fine"})
        )
        self.assertEqual(verdict["state"], "unreviewed")
        self.assertIn("omitted", verdict["reasons"][0])

    def test_prose_without_json_is_unreviewed(self) -> None:
        verdict = media.parse_review_verdict("It looks like a nice picture of a car.")
        self.assertEqual(verdict["state"], "unreviewed")

    def test_an_earlier_brace_in_the_prose_does_not_hide_the_verdict(self) -> None:
        raw = (
            'Here {is} my verdict: {"subject_matches": true, "contains_legible_text": false, '
            '"depicts_procedure_or_measurement": false, "reason": "a bench scene"}'
        )
        verdict = media.parse_review_verdict(raw)
        self.assertEqual(verdict["state"], "approved")
        self.assertEqual(verdict["reasons"], ["a bench scene"])

    def test_a_structured_result_envelope_is_accepted(self) -> None:
        verdict = media.parse_review_verdict(
            {
                "success": True,
                "result": {
                    "subject_matches": True,
                    "contains_legible_text": False,
                    "depicts_procedure_or_measurement": False,
                    "reason": "a bench scene",
                },
            }
        )
        self.assertEqual(verdict["state"], "approved")

    def test_a_native_vision_envelope_is_unreviewed(self) -> None:
        envelope = media.parse_review_verdict({"_multimodal": [{"type": "image"}], "text": ""})
        self.assertEqual(envelope["state"], "unreviewed")
        self.assertIn("attached the picture", envelope["reasons"][0])

    def test_a_review_never_reports_approved_without_all_three_checks(self) -> None:
        for payload in (
            {},
            {"subject_matches": True},
            {"subject_matches": True, "contains_legible_text": False},
            {"subject_matches": "maybe", "contains_legible_text": False,
             "depicts_procedure_or_measurement": False},
        ):
            verdict = media.parse_review_verdict(json.dumps(payload))
            self.assertNotEqual(verdict["state"], "approved", payload)


class PolicyContextArtTest(unittest.TestCase):
    """A procedure lesson may carry context art, and the schematic stays the authority."""

    def procedure(self, intent: str, *, check_angle: str = "procedure") -> policy.LessonCapabilityPlan:
        return policy.plan_lesson_capability(
            recipe="committed",
            evidence_target=check_angle,
            lesson_intent=intent,
            subject_domain="technical_procedure",
        )

    def test_context_art_rides_alongside_a_required_schematic(self) -> None:
        plan = self.procedure(
            "Replace the front pads: follow the labelled torque sequence in the diagram and use a "
            "picture of the caliper in place for context."
        )
        self.assertEqual((plan.image, plan.image_role), ("required", "schematic"))
        self.assertTrue(plan.context_illustration)
        self.assertEqual(plan.image_authority, "deterministic")
        self.assertEqual(
            policy.permitted_image_roles(plan), ("schematic", "illustration")
        )
        self.assertIn("context art", " ".join(plan.reasons))
        # The persisted policy object is the closed POLICY_SCHEMA contract; the typed permission is
        # a runtime property and the reason string carries it into the stored plan.
        projected = plan.to_dict()
        self.assertNotIn("context_illustration", projected)
        self.assertIn("authority none", str(projected["reasons"]))

    def test_context_art_never_satisfies_the_required_schematic(self) -> None:
        plan = self.procedure(
            "Replace the front pads: follow the labelled torque sequence in the diagram and use a "
            "picture of the caliper in place for context."
        )
        context_only = [
            {"kind": "visual", "role": "illustration", "text_equivalent": "A caliper on a bench."}
        ]
        problems = policy.missing_required_media(plan, context_only)
        self.assertEqual(len(problems), 1)
        self.assertIn("schematic", problems[0])
        self.assertEqual(policy.media_policy_problems(plan, context_only), [])

        with_schematic = context_only + [
            {
                "kind": "visual",
                "role": "schematic",
                "text_equivalent": "Tighten in a cross pattern.",
                "facts": {"rows": [{"label": "Step 1", "value": "20 Nm"}]},
            }
        ]
        self.assertEqual(policy.missing_required_media(plan, with_schematic), [])
        self.assertEqual(policy.media_policy_problems(plan, with_schematic), [])

    def test_a_cited_source_stays_the_authority_when_context_art_is_added(self) -> None:
        plan = self.procedure(
            "Identify the worn pad from the workshop manual photograph, and use a picture of the "
            "bench for context."
        )
        self.assertEqual((plan.image, plan.image_role), ("required", "sourced_reference"))
        self.assertTrue(plan.context_illustration)
        self.assertEqual(plan.image_authority, "cited_source")
        self.assertEqual(policy.permitted_image_roles(plan), ("sourced_technical", "illustration"))

    def test_an_illustration_can_never_be_the_required_visual(self) -> None:
        with self.assertRaises(policy.CapabilityPolicyError) as caught:
            policy.LessonCapabilityPlan(
                recipe="committed",
                evidence_target="procedure",
                check_angle="procedure",
                rubric_profile="procedural",
                image="required",
                image_role="illustration",
                audio="none",
                audio_role=None,
                reasons=("it looks technical",),
            )
        message = str(caught.exception)
        self.assertIn("context only", message)
        self.assertIn("authority none", message)
        self.assertIn("deterministic schematic", message)

    def test_a_context_only_procedure_keeps_illustration_optional(self) -> None:
        plan = self.procedure("Replace the cabin filter; a picture of the glovebox helps.")
        self.assertEqual((plan.image, plan.image_role), ("optional", "illustration"))
        self.assertTrue(plan.context_illustration)
        self.assertEqual(plan.image_authority, "none")
        self.assertEqual(policy.permitted_image_roles(plan), ("illustration",))

    def test_one_off_and_non_procedure_lessons_get_no_context_art(self) -> None:
        one_off = policy.plan_lesson_capability(
            recipe="one_off",
            evidence_target="procedure",
            lesson_intent="Replace the cabin filter; a picture of the glovebox helps.",
            subject_domain="technical_procedure",
        )
        self.assertFalse(one_off.context_illustration)

        language = policy.plan_lesson_capability(
            recipe="committed",
            evidence_target="comprehension",
            lesson_intent="Use a picture of a station for the vocabulary.",
            subject_domain="language",
            locale="ja-JP",
        )
        self.assertFalse(language.context_illustration)

    def test_a_parent_lesson_and_a_withheld_visual_carry_no_context_art(self) -> None:
        parent = policy.plan_lesson_capability(
            recipe="parent",
            evidence_target="procedure",
            lesson_intent="Watch your child follow the diagram and use a picture of the bench.",
            subject_domain="technical_procedure",
        )
        self.assertFalse(parent.context_illustration)

        # A brief that withheld visuals also withholds the art that would have accompanied them;
        # the plan must not carry media it just decided against.
        withheld = policy.plan_lesson_capability(
            recipe="committed",
            evidence_target="procedure",
            lesson_intent="Follow the labelled torque diagram and use a picture of the bench.",
            subject_domain="technical_procedure",
            media_preferences={"desired_visuals": "none"},
        )
        self.assertEqual((withheld.image, withheld.image_role), ("none", None))
        self.assertFalse(withheld.context_illustration)
        self.assertEqual(policy.permitted_image_roles(withheld), ())

    def test_declared_context_art_on_a_procedure_is_accepted_without_authority(self) -> None:
        plan = policy.plan_lesson_capability(
            recipe="committed",
            evidence_target="procedure",
            lesson_intent="Replace the front pads.",
            subject_domain="technical_procedure",
            media_need={
                "construct": "a picture of the caliper on the bench",
                "image": {"level": "optional", "role": "illustration"},
                "audio": {"level": "none", "role": "none"},
            },
        )
        self.assertEqual((plan.image, plan.image_role), ("optional", "illustration"))
        self.assertEqual(plan.image_authority, "none")
        self.assertIn("context art with authority none", " ".join(plan.reasons))


if __name__ == "__main__":
    unittest.main()
