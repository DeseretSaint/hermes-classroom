"""Preview shape and trust-dimension tests. Preview never collapses trust into a safe badge."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from coursebook import archive, packs
from coursebook.contracts import validate_response_payload

ROOT = Path(__file__).resolve().parent.parent
JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"
PARENT = ROOT / "bundled" / "packs" / "parent-measurement-practice"


class PreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.manifest, self.files = archive.read_directory(JAPANESE)

    def test_preview_matches_the_rpc_response_shape(self) -> None:
        result = packs.preview(self.manifest)
        self.assertEqual(set(result), {"manifest", "integrity", "trust"})
        self.assertEqual(set(result["integrity"]), {"hashes_match", "file_count", "expanded_bytes"})
        self.assertTrue(set(result["trust"]["labels"]) <= {
            "integrity_verified",
            "automated_checks_passed",
            "human_review_recorded",
            "model_assessed_support",
        })

    def test_preview_carries_author_outcomes_sources_licenses_notes_media_and_versions(self) -> None:
        result = packs.preview(self.manifest)
        shown = result["manifest"]
        self.assertTrue(shown["attribution"])
        self.assertEqual(shown["contributors"][0]["role"], "author")
        self.assertEqual(len(shown["objectives"]), 4)
        self.assertTrue(all(objective["checks"] for objective in shown["objectives"]))
        self.assertTrue(shown["sources"])
        self.assertIn("license", shown)
        self.assertIn("redistribution", shown["license"])
        self.assertTrue(shown["content_notes"])
        self.assertTrue(shown["accessibility_notes"])
        # H-186 shipped the demo pack as cb.pack v2; the preview carries whatever the pack
        # manifest declares rather than a literal pinned to one revision of the fixture.
        self.assertEqual(shown["pack_version"], self.manifest["pack_version"])
        # CP-014 integrated the painted cover and released the pack as 2.2.0; CP-042's wording
        # revision is 2.3.0.
        self.assertEqual(shown["pack_version"], "2.4.0")
        self.assertEqual(shown["minimum_coursebook_version"], "0.1.0")
        self.assertGreater(result["integrity"]["expanded_bytes"], 0)
        self.assertEqual(result["integrity"]["file_count"], len(shown["files"]))
        self.assertTrue(any(entry["path"].endswith(".png") for entry in shown["files"]))

    def test_trust_labels_stay_separate(self) -> None:
        result = packs.preview(self.manifest, integrity={"hashes_match": True, "file_count": 5, "expanded_bytes": 10})
        labels = result["trust"]["labels"]
        self.assertIn("integrity_verified", labels)
        self.assertIn("automated_checks_passed", labels)
        self.assertIn("model_assessed_support", labels)
        self.assertNotIn("human_review_recorded", labels)
        lowered = {label.lower() for label in labels}
        self.assertNotIn("safe", lowered)
        self.assertNotIn("verified", lowered)

    def test_integrity_failure_removes_the_integrity_label(self) -> None:
        result = packs.preview(self.manifest, integrity={"hashes_match": False, "file_count": 5, "expanded_bytes": 10})
        self.assertNotIn("integrity_verified", result["trust"]["labels"])
        self.assertIn("automated_checks_passed", result["trust"]["labels"])

    def test_human_review_is_only_reported_when_recorded(self) -> None:
        """t_d33984eb: a manifest's own trust block is provenance, never a label.

        ``packs.preview`` has no store verdict to offer, so even a manifest that names a reviewer
        yields no ``human_review_recorded`` label. The author's strings stay in ``manifest.trust``
        where a reader can see them as a declaration; the label appears only when a caller passes
        store evidence for these exact bytes.
        """
        forged = copy.deepcopy(self.manifest)
        forged["trust"] = {"labels": ["human_review_recorded"], "reviewed_by": "A named reviewer", "reviewed_at": "2026-11-06"}
        packs.validate_manifest(forged)
        result = packs.preview(forged)
        self.assertNotIn("human_review_recorded", result["trust"]["labels"])
        self.assertEqual(set(result["trust"]), {"labels"})
        # The claim is still readable as provenance inside the manifest itself.
        self.assertEqual(result["manifest"]["trust"]["reviewed_by"], "A named reviewer")
        self.assertEqual(result["manifest"]["trust"]["reviewed_at"], "2026-11-06")
        unrecorded = packs.preview(self.manifest)
        self.assertNotIn("reviewed_by", unrecorded["trust"])
        # A store-held verdict for the same manifest is the only thing that adds the label.
        recorded = packs.preview(forged, store_review_recorded=True)
        self.assertIn("human_review_recorded", recorded["trust"]["labels"])
        self.assertNotIn("human_review_recorded", packs.preview(forged, store_review_recorded=False)["trust"]["labels"])

    def test_trust_labels_never_infer_the_label_from_a_manifest(self) -> None:
        """``packs.trust_labels`` has no declared-provenance branch left to reach."""
        forged = copy.deepcopy(self.manifest)
        forged["trust"] = {"reviewed_by": "A named reviewer", "reviewed_at": "2026-11-06"}
        self.assertNotIn(
            "human_review_recorded",
            packs.trust_labels(forged, integrity_verified=True, automated_checks_passed=True),
        )
        self.assertIn(
            "human_review_recorded",
            packs.trust_labels(
                forged,
                integrity_verified=True,
                automated_checks_passed=True,
                store_review_recorded=True,
            ),
        )

    def test_preview_validates_against_the_current_rpc_contract(self) -> None:
        result = packs.preview(self.manifest, integrity={"hashes_match": True, "file_count": 5, "expanded_bytes": 10})
        validate_response_payload("pack.preview", result)

    def test_preview_of_a_staged_pack_uses_measured_integrity(self) -> None:
        path = self.base / "japanese.zip"
        archive.write_archive(path, self.manifest, self.files)
        staging = archive.StagingArea(self.base / "staging")
        staged = staging.stage(staging.grant_local_file(path))
        result = packs.preview(staged.manifest, integrity=staged.integrity)
        self.assertTrue(result["integrity"]["hashes_match"])
        self.assertEqual(result["integrity"]["expanded_bytes"], sum(entry["bytes"] for entry in self.manifest["files"]))

    def test_preview_does_not_badge_answer_keys_as_safe(self) -> None:
        result = packs.preview(self.manifest)
        self.assertEqual(result["trust"]["labels"].count("human_review_recorded"), 0)
        self.assertNotIn("review", packs.canonical_json_bytes(result["trust"]).decode("utf-8").lower())
        answers = [
            check["reference_answer"]
            for objective in self.manifest["objectives"]
            for check in objective["checks"]
        ]
        self.assertTrue(answers)
        self.assertEqual(len(answers), 4)

    def test_preview_holds_no_private_fields(self) -> None:
        result = packs.preview(self.manifest)
        self.assertEqual(packs.contains_private_fields(result), [])


class PreviewParentTests(unittest.TestCase):
    def test_parent_preview_declares_the_answer_guide_role(self) -> None:
        manifest = packs.load_manifest(PARENT / "pack.json")
        result = packs.preview(manifest, integrity={"hashes_match": True, "file_count": 3, "expanded_bytes": 1})
        roles = {entry["role"] for entry in result["manifest"]["files"]}
        self.assertIn("answer_guide", roles)
        self.assertIn("learner_page", roles)
        self.assertIn("parent_guide", roles)
        self.assertEqual(result["manifest"]["recipe"], "parent")


if __name__ == "__main__":
    unittest.main()
