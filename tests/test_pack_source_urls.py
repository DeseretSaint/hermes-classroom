"""H-115 D1: a pack source URL is ``http(s)`` or absent — at every seam that can return or store it.

A pack is untrusted declarative data. ``sources[].url`` used to accept any string, so a manifest
could carry ``javascript:``, ``data:``, ``file:`` or a relative reference, and both ``pack.preview``
and the Desktop Sources tab rendered it as a link. The pack schema is structural (``cb.pack`` v1 is
frozen and its bytes are unchanged), so the rule lives in ``packs.validate_minima`` — the one gate
``pack.preview``, ``pack.import``, ``pack.export``, ``pack.convert``, the archive writer and the
fixture validator all pass through before a byte is written or returned.

These tests pin three things: the URL predicate, the pre-write refusal on a manifest (including one
whose hostile URL is hidden behind a publisher), and a real archive through the real dispatcher —
refused at preview **and** import with no pack, course, source or segment row left behind.
"""

from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from coursebook import archive, contracts, packs
from tests.test_pack_flow import PackFlowCase

PATH = "content/lesson.md"
TEXT = "# Register\n\nThe addressee decides the register.\n"

#: The five values the H-115 probe imported at 48be4af, plus the shapes a naive
#: ``startswith("http")`` check would still admit.
HOSTILE_URLS = {
    "javascript": "javascript:alert(document.domain)",
    "data-html": "data:text/html,<script>alert(1)</script>",
    "file": "file:///etc/passwd",
    "scheme-relative": "//169.254.169.254/latest/meta-data/",
    "relative": "chapter-1.md",
}


def manifest_with_source(
    url: object | None,
    *,
    publisher: str | None = None,
    source_id: str = "src-cited-01",
    pack_id: str = "source-url-fixture",
) -> dict:
    """A valid minimal pack whose one source carries *url*, re-hashed for that content.

    ``packs.build_manifest`` refuses a hostile URL, so the manifest is built with a citable URL and
    then mutated, exactly as a hand-written ``pack.json`` would be. The hash is recomputed so the
    refusal under test is never the immutability guard.
    """
    source: dict[str, object] = {
        "source_id": source_id,
        "title": "Cited page",
        "source_type": "reference",
        "url": "https://example.org/citation",
        "support_status": "unassessed",
    }
    if publisher is not None:
        source["publisher"] = publisher
    manifest = packs.build_manifest(
        pack_id=pack_id,
        pack_version="1.0.0",
        title="Source URL fixture",
        recipe="casual",
        minimum_coursebook_version="0.1.0",
        license={"id": "unspecified", "note": "test fixture", "redistribution": "local_only"},
        attribution="Written for the H-115 D1 source-URL test.",
        objectives=[
            {
                "objective_id": "obj-url-01",
                "ordinal": 1,
                "title": "Choose a register",
                "evidence_target": "comprehension",
                "evidence_criteria": [
                    "Names the addressee and the relationship",
                    "Chooses a register and says why",
                    "Transfers the reasoning to one new setting",
                ],
                "estimated_minutes": 8,
                "sections": [{"section_id": "sec-url-01", "title": "Lesson", "path": PATH}],
                "checks": [
                    {
                        "check_id": "chk-url-01",
                        "version": 1,
                        "evidence_target": "comprehension",
                        "stimulus": "Which register do you choose, and which word carries the politeness?",
                        "reference_answer": "the formal business register",
                        "accepted_alternatives": ["formal", "business register"],
                        "rubric": [
                            "Chooses the formal business register",
                            "Names the addressee and the relationship",
                            "Does not use the casual form for a first meeting",
                        ],
                        "audit_state": "unreviewed",
                    }
                ],
            }
        ],
        files={PATH: TEXT.encode("utf-8")},
        file_metadata={PATH: {"mime": "text/markdown", "role": "section"}},
        sources=[source],
    )
    if url is None:
        manifest["sources"][0].pop("url")
    else:
        manifest["sources"][0]["url"] = url
    return packs.with_content_hash(manifest)


def write_archive_unchecked(destination: Path, manifest: dict) -> Path:
    """Write the archive layout ``archive.write_archive`` writes, without validating the manifest.

    The writer refuses a manifest it would never have produced, which is the point of the fix; the
    hostile archive under test therefore has to be assembled here so preview and import can be the
    seams that refuse it.
    """
    root = f"{manifest['pack_id']}-{manifest['pack_version']}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path, data in {PATH: TEXT.encode("utf-8")}.items():
            bundle.writestr(zipfile.ZipInfo(f"{root}/{path}", date_time=(1980, 1, 1, 0, 0, 0)), data)
        bundle.writestr(
            zipfile.ZipInfo(f"{root}/pack.json", date_time=(1980, 1, 1, 0, 0, 0)),
            packs.canonical_json_bytes(manifest) + b"\n",
        )
    return destination


class HttpUrlPredicateTest(unittest.TestCase):
    """The predicate itself: scheme case, host presence and the bytes around it."""

    def test_absolute_http_and_https_urls_are_accepted(self) -> None:
        for url in (
            "https://example.org/citation",
            "http://example.org/citation?page=2#note",
            "HTTPS://Example.ORG/Citation",
            "https://例え.jp/ページ",
        ):
            with self.subTest(url=url):
                self.assertTrue(packs.is_http_url(url))

    def test_every_other_scheme_and_relative_form_is_rejected(self) -> None:
        for url in (
            *HOSTILE_URLS.values(),
            "JavaScript:alert(1)",
            " javascript:alert(1)",
            "javascript:alert(1) ",
            "mailto:author@example.org",
            "tel:+18015550100",
            "ftp://example.org/file.pdf",
            "blob:https://example.org/1234",
            "about:blank",
            "http://",
            "https:///no-host",
            "http:no-host.example",
            "http://exa mple.org/page",
            "https://example.org/\talert",
            "",
            None,
            42,
        ):
            with self.subTest(url=url):
                self.assertFalse(packs.is_http_url(url))


class ManifestRefusalTest(unittest.TestCase):
    """The manifest gate: a hostile URL is refused before preview or import can return it."""

    def test_each_hostile_scheme_is_refused_naming_the_source_and_the_rule(self) -> None:
        for label, url in HOSTILE_URLS.items():
            with self.subTest(case=label):
                manifest = manifest_with_source(url)
                with self.assertRaises(packs.PackRejected) as caught:
                    packs.validate_minima(manifest)
                message = str(caught.exception)
                self.assertIn("src-cited-01", message)
                self.assertIn("not an absolute http(s) URL", message)
                self.assertIn(url, message)

    def test_a_publisher_does_not_excuse_a_hostile_url(self) -> None:
        manifest = manifest_with_source("javascript:alert(1)", publisher="Example Press")
        with self.assertRaises(packs.PackRejected) as caught:
            packs.validate_minima(manifest)
        self.assertIn("javascript:alert(1)", str(caught.exception))

    def test_a_source_may_omit_its_url_when_it_names_a_publisher(self) -> None:
        packs.validate_minima(manifest_with_source(None, publisher="Example Press"))
        packs.validate_minima(manifest_with_source("", publisher="Example Press"))

    def test_a_source_with_neither_url_nor_publisher_is_still_refused(self) -> None:
        for url in (None, ""):
            with self.subTest(url=url):
                with self.assertRaises(packs.PackRejected) as caught:
                    packs.validate_minima(manifest_with_source(url))
                self.assertIn("neither a URL nor a publisher", str(caught.exception))

    def test_export_refuses_a_hostile_source_url_rather_than_propagating_it(self) -> None:
        manifest = manifest_with_source("javascript:alert(1)")
        with self.assertRaises(packs.PackRejected) as caught:
            packs.build_export(manifest, {PATH: TEXT.encode("utf-8")})
        self.assertIn("not an absolute http(s) URL", str(caught.exception))

    def test_reading_a_pack_directory_applies_the_same_rule(self) -> None:
        # ``pack.inspect``/``pack.list`` re-read an adopted pack through read_directory, so a pack
        # adopted before this rule cannot keep echoing the link.
        manifest = manifest_with_source("data:text/html,<script>alert(1)</script>")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / PATH).parent.mkdir(parents=True, exist_ok=True)
            (root / PATH).write_bytes(TEXT.encode("utf-8"))
            (root / "pack.json").write_text(
                packs.canonical_json_bytes(manifest).decode("utf-8") + "\n", encoding="utf-8"
            )
            with self.assertRaises(packs.PackRejected) as caught:
                archive.read_directory(root)
            self.assertIn("not an absolute http(s) URL", str(caught.exception))

    def test_the_contract_stays_structural_and_the_policy_refuses(self) -> None:
        # cb.pack v1 declares `url` as a bounded string and nothing more; that is why the rule is a
        # policy minimum rather than a schema change.
        manifest = manifest_with_source("javascript:alert(1)")
        packs.validate_manifest(manifest)
        with self.assertRaises(packs.PackRejected):
            packs.validate_minima(manifest)

    def test_the_frozen_manifest_contract_is_unchanged(self) -> None:
        # The rule is a policy minimum, not a cb.pack schema field: installed v1 packs keep
        # parsing and the frozen v1 contract file keeps its bytes and version. cb.pack has since
        # advanced for unrelated reasons (v2 media, v3 presentation), so this pins v1 only.
        self.assertEqual(int(contracts.contract_as("cb.pack", 1)["x-contract-version"]), 1)
        self.assertEqual(contracts.version_files("cb.pack")[1], "pack-manifest.v1.json")
        v1_bytes = (contracts.CONTRACT_DIR / "pack-manifest.v1.json").read_bytes()
        self.assertEqual(
            "sha256:" + hashlib.sha256(v1_bytes).hexdigest(),
            "sha256:ca0c5e44ab099227d138a360b705654978718477eeb3d170f5885cbb181ccb32",
        )
        # v1 declares `url` as a bounded string and nothing more, which is exactly why the scheme
        # rule is a policy minimum in packs.py rather than a schema change.
        url_schema = contracts.contract_as("cb.pack", 1)["properties"]["sources"]["items"]["properties"]["url"]
        self.assertEqual(url_schema, {"type": "string", "maxLength": 1000})


class ImportRefusalTest(PackFlowCase):
    """A real hostile archive through the real dispatcher: refused at preview and at import."""

    def _assert_no_residue(self) -> None:
        for table, count in self.counts().items():
            self.assertEqual(count, 0, f"{table} must stay empty after a refused import")

    def test_hostile_source_url_is_refused_at_preview_and_import_with_no_residue(self) -> None:
        for label, url in HOSTILE_URLS.items():
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory(dir=self.work) as directory:
                    manifest = manifest_with_source(url, pack_id=f"source-url-{label}")
                    destination = Path(directory) / f"{label}.zip"
                    write_archive_unchecked(destination, manifest)
                    staged_id = self.grant_zip(destination)

                    preview = self.dispatch("pack.preview", {"staged_id": staged_id})
                    self.assertFalse(preview["ok"], f"preview accepted {label}")
                    self.assertEqual(preview["error"]["code"], "PACK_REJECTED")
                    self.assertEqual(preview["error"]["details"]["reason"], "pack_not_importable")
                    self.assertIn("not an absolute http(s) URL", preview["error"]["message"])

                    imported = self.dispatch("pack.import", {"staged_id": staged_id, "mode": "fresh"})
                    self.assertFalse(imported["ok"], f"import accepted {label}")
                    self.assertEqual(imported["error"]["code"], "PACK_REJECTED")
                    self.assertIn("not an absolute http(s) URL", imported["error"]["message"])
                self._assert_no_residue()

    def test_a_citable_https_source_still_imports_and_is_stored_verbatim(self) -> None:
        url = "https://example.org/citation?page=2"
        manifest = manifest_with_source(url, pack_id="source-url-accepted")
        destination = self.work / "accepted.zip"
        write_archive_unchecked(destination, manifest)
        staged_id = self.grant_zip(destination)

        preview = self.ok("pack.preview", {"staged_id": staged_id})["result"]
        self.assertEqual(preview["manifest"]["sources"][0]["url"], url)

        imported = self.import_pack(staged_id)["result"]
        rows = self.rows("SELECT url, title FROM sources WHERE course_id = ?", (imported["course_id"],))
        self.assertEqual([str(row["url"]) for row in rows], [url])


if __name__ == "__main__":
    unittest.main()
