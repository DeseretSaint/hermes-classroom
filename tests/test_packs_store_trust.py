"""The store owns ``human_review_recorded``; a pack cannot assert it about itself.

t_f3b7be3e. ``store/packs/<pack_id>.zip`` is untrusted data: ``trust.reviewed_by`` and
``trust.reviewed_at`` are strings the pack's author typed into their own ``pack.json``. A store
card that reported ``human_review_recorded`` from them would be repeating the pack's claim about
itself as if the store had verified it.

These tests build a real community archive whose manifest forges the label, then read the real
``workshop.catalog_view()`` card. The label may appear only when the store's own review ledger
(``store/reviews.json``) holds a record for *exactly that content hash*.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from coursebook import archive, packs, workshop
from tests.kernel_support import KernelCase

ROOT = Path(__file__).resolve().parent.parent
JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"
PACK_ID = "forged-review-l0"
FORGED_REVIEWER = "A. Reviewer Who Never Existed"
FORGED_DATE = "2026-11-01"


class StoreOwnedReviewTests(KernelCase):
    """A forged manifest claim is not store evidence; a store record is."""

    def setUp(self) -> None:
        super().setUp()
        self.temp = tempfile.TemporaryDirectory(prefix="cb-store-trust-")
        self.addCleanup(self.temp.cleanup)
        self.store = Path(self.temp.name) / "store"
        (self.store / "packs").mkdir(parents=True)
        self._bind("COMMUNITY_ROOT", self.store / "packs")
        self._bind("COMMUNITY_INDEX_PATH", self.store / "index.json")
        self._bind("STORE_REVIEWS_PATH", self.store / "reviews.json")
        self.manifest = self._forged_community_pack()

    def _bind(self, name: str, value: Path) -> None:
        original = getattr(workshop, name)
        self.addCleanup(setattr, workshop, name, original)
        setattr(workshop, name, value)

    def _forged_community_pack(self) -> dict:
        """A valid pack whose own manifest asserts a human review that never happened."""
        manifest, files = archive.read_directory(JAPANESE)
        manifest = dict(manifest)
        manifest["pack_id"] = PACK_ID
        manifest["trust"] = {
            "labels": ["human_review_recorded"],
            "reviewed_by": FORGED_REVIEWER,
            "reviewed_at": FORGED_DATE,
        }
        manifest = packs.with_content_hash(manifest)
        packs.validate_manifest(manifest)
        archive.write_archive(self.store / "packs" / f"{PACK_ID}.zip", manifest, files)
        index = {
            "schema": "cb.store-index.v1",
            "pack_count": 1,
            "packs": [
                {
                    "pack_id": PACK_ID,
                    "pack_version": manifest["pack_version"],
                    "content_hash": manifest["content_hash"],
                    "origin": "community",
                    "title": manifest["title"],
                    "subtitle": manifest.get("subtitle"),
                }
            ],
        }
        (self.store / "index.json").write_text(json.dumps(index), encoding="utf-8")
        return manifest

    def _card(self) -> dict:
        view = workshop.catalog_view()
        self.assertEqual(view["refused"], [], "the forged pack must still be a readable card")
        return next(item for item in view["items"] if item["pack_id"] == PACK_ID)

    def _write_reviews(self, records: list[dict]) -> None:
        (self.store / "reviews.json").write_text(json.dumps({"reviews": records}), encoding="utf-8")

    def test_forged_manifest_review_does_not_reach_the_store_card(self) -> None:
        """No ledger at all: the author's claim is provenance, never evidence."""
        card = self._card()
        self.assertNotIn("human_review_recorded", card["trust_labels"])
        # The store still reports the machine facts it measured for itself.
        self.assertIn("integrity_verified", card["trust_labels"])
        self.assertIn("automated_checks_passed", card["trust_labels"])

    def test_store_verified_review_is_still_reported(self) -> None:
        """A record the store owns, for these exact bytes, does surface the label."""
        self._write_reviews(
            [
                {
                    "pack_id": PACK_ID,
                    "content_hash": self.manifest["content_hash"],
                    "reviewed_by": "Keaton Brumley",
                    "reviewed_at": "2026-11-12",
                }
            ]
        )
        card = self._card()
        self.assertIn("human_review_recorded", card["trust_labels"])

    def test_review_of_other_bytes_does_not_bless_this_release(self) -> None:
        """A review is bound to the content hash; a changed pack needs a new review."""
        self._write_reviews(
            [
                {
                    "pack_id": PACK_ID,
                    "content_hash": "sha256:" + "0" * 64,
                    "reviewed_by": "Keaton Brumley",
                    "reviewed_at": "2026-11-12",
                }
            ]
        )
        card = self._card()
        self.assertNotIn("human_review_recorded", card["trust_labels"])

    def test_a_malformed_ledger_fails_closed(self) -> None:
        """A ledger that cannot be read is no evidence, and never an exception on the card path."""
        (self.store / "reviews.json").write_text("{ not json", encoding="utf-8")
        card = self._card()
        self.assertNotIn("human_review_recorded", card["trust_labels"])

    def test_an_oversized_ledger_is_not_read(self) -> None:
        """The ledger is bounded data; one that exceeds the bound proves nothing."""
        matching = json.dumps(
            {
                "reviews": [
                    {
                        "pack_id": PACK_ID,
                        "content_hash": self.manifest["content_hash"],
                        "reviewed_by": "Keaton Brumley",
                        "reviewed_at": "2026-11-12",
                    }
                ]
            }
        )
        padding = " " * (workshop.MAX_STORE_REVIEWS_BYTES + 1)
        (self.store / "reviews.json").write_text(matching + padding, encoding="utf-8")
        card = self._card()
        self.assertNotIn("human_review_recorded", card["trust_labels"])


if __name__ == "__main__":
    unittest.main()
