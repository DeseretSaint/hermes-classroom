"""PRINT-2 (kanban t_6418b9dd): the colouring page is a pack role, not a promised orphan.

The colouring page used to render and then go nowhere: ``homework_print.render_documents`` had four
keys, the parent guide said "print the colouring page", and no pack could carry it. These tests pin
the amendment that closed that gap:

* ``cb.pack`` v4 names ``coloring_page`` and admits ``text/html``, the byte form of a print page;
* a colouring page is learner-facing, so the answer-leak audit reads it exactly as it reads
  ``learner_page``;
* a real ``hw_labels`` pack builds, audits clean, and lists the colouring artifact by role and path;
* a v3 pack with the four original roles still validates, and a v3 document may not smuggle the new
  role in — old packs do not move;
* the shipped artifact is the page: ``pdftotext`` finds the word bank and the "While they colour"
  tie-in is in the parent guide, and no answer-guide text is in the artifact.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from coursebook import contracts, homework_print as hp, packs

ROOT = Path(__file__).resolve().parent.parent
TASK = "hw_labels"


def fixture() -> dict:
    return hp.load_fixture()


def write_pack(directory: Path, manifest: dict, files: dict[str, bytes]) -> Path:
    """Persist a manifest and its declared bytes the way an archive extract would."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / packs.root_file()).write_bytes(packs.canonical_json_bytes(manifest) + b"\n")
    for path, data in files.items():
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return directory


def v3_four_role_pack() -> tuple[dict, dict[str, bytes]]:
    """A pack authoring exactly the four roles a pre-PRINT-2 builder emits, at contract v3."""
    files = {
        "content/lesson.md": b"# Lesson\n\nSay the word as you point at the object.\n",
        "content/parent-guide.md": b"# Parent guide\n\nAsk for the word, never a translation.\n",
        "content/learner-page.md": b"# Learner page\n\nDay 1  Day 2\n",
        "content/answer-guide.md": b"# Answer guide - parent only\n\nThe learner says each label aloud.\n",
    }
    metadata = {
        "content/lesson.md": {"mime": "text/markdown", "role": "section"},
        "content/parent-guide.md": {"mime": "text/markdown", "role": "parent_guide"},
        "content/learner-page.md": {"mime": "text/markdown", "role": "learner_page"},
        "content/answer-guide.md": {"mime": "text/markdown", "role": "answer_guide"},
    }
    objective = {
        "objective_id": "obj-four-role",
        "ordinal": 1,
        "title": "The four-role take-home pack",
        "evidence_target": "comprehension",
        "evidence_criteria": ["Says the word", "Hears the word", "Two days"],
        "estimated_minutes": 10,
        "sections": [{"section_id": "sec-one", "title": "Lesson", "path": "content/lesson.md"}],
        "checks": [
            {
                "check_id": "chk-four-role-1",
                "version": 1,
                "evidence_target": "comprehension",
                "stimulus": "Point at the object and ask for the word.",
                "rubric": ["Says a lesson word", "Is audible", "Does not read it off the page"],
                "reference_answer": "the hidden answer 42",
                "accepted_alternatives": [],
                "audit_state": "unreviewed",
            }
        ],
    }
    manifest = packs.build_manifest(
        pack_id="four-role-pack",
        pack_version="1.0.0",
        title="Four role pack",
        recipe="parent",
        minimum_coursebook_version="0.1.0",
        license={"id": "all-rights-reserved", "redistribution": "local_only"},
        attribution="test fixture",
        objectives=[objective],
        files=files,
        file_metadata=metadata,
        contract_version=3,
    )
    return manifest, files


class ContractTests(unittest.TestCase):
    def test_v4_names_the_role_and_the_html_mime(self) -> None:
        v4 = contracts.contract_as("cb.pack", 4)
        files = v4["properties"]["files"]["items"]["properties"]
        self.assertIn("coloring_page", files["role"]["enum"])
        self.assertIn("text/html", files["mime"]["enum"])
        self.assertEqual(int(v4["x-contract-version"]), 4)

    def test_v3_is_unchanged_and_still_offered(self) -> None:
        v3 = contracts.contract_as("cb.pack", 3)
        files = v3["properties"]["files"]["items"]["properties"]
        self.assertNotIn("coloring_page", files["role"]["enum"])
        self.assertNotIn("text/html", files["mime"]["enum"])
        self.assertIn(3, contracts.version_files("cb.pack"))
        # The inventory current does not move: no existing builder's output changes.
        self.assertEqual(contracts.CONTRACT_FILES["cb.pack"], "pack-manifest.v3.json")

    def test_pack_module_reads_the_role_from_the_newest_accepted_contract(self) -> None:
        self.assertIn("coloring_page", packs.FILE_ROLES)
        self.assertIn("coloring_page", packs.EXPORTABLE_ROLES)
        self.assertIn("coloring_page", packs.LEARNER_FACING_ROLES)


class PackReachabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.fixture = fixture()

    def test_a_built_hw_labels_pack_carries_the_coloring_artifact(self) -> None:
        manifest = hp.pack_manifest(self.fixture, TASK, paper="A4")
        files = hp.pack_documents(self.fixture, TASK, paper="A4")
        directory = write_pack(self.base / "pack", manifest, files)

        self.assertEqual(manifest["contract_version"], 4)
        entries = {str(entry["role"]): entry for entry in manifest["files"]}
        self.assertIn("coloring_page", entries)
        coloring = entries["coloring_page"]
        self.assertEqual(coloring["path"], "content/coloring-page.html")
        self.assertEqual(coloring["mime"], "text/html")
        # The artifact is reachable and audits clean: declared bytes, hash, role/MIME, no answer.
        self.assertTrue((directory / coloring["path"]).is_file())
        self.assertEqual(packs.audit_bundle(directory), [])

    def test_the_coloring_page_is_learner_facing_and_holds_no_answer_guide(self) -> None:
        docs = hp.render_documents(self.fixture, TASK)
        coloring = docs["coloring_page"]
        self.assertIn("Words in this picture", coloring)
        self.assertIn('class="word-jp jp" lang="ja"', coloring)
        self.assertNotIn("PARENT ONLY", coloring)
        self.assertNotIn("Expected responses", coloring)

    def test_a_reference_answer_in_the_coloring_page_is_refused(self) -> None:
        """The answer-leak audit reads the colouring page exactly as it reads ``learner_page``."""
        manifest = hp.pack_manifest(self.fixture, TASK, paper="A4")
        files = hp.pack_documents(self.fixture, TASK, paper="A4")
        # Give the pack a check whose reference answer is long enough for the audit to compare.
        manifest["objectives"][0]["checks"][0]["reference_answer"] = "the hidden answer 42"
        manifest = packs.with_content_hash(manifest)
        directory = write_pack(self.base / "clean", manifest, files)
        self.assertEqual(packs.audit_bundle(directory), [])
        # Now the exact same string appears in the learner-facing colouring artifact.
        path = "content/coloring-page.html"
        files[path] = files[path].replace(
            b"Colour the picture.", b"the hidden answer 42. Colour the picture.", 1
        )
        record = next(item for item in manifest["files"] if item["path"] == path)
        record["sha256"] = packs.file_sha256(files[path])
        record["bytes"] = len(files[path])
        manifest = packs.with_content_hash(manifest)
        directory = write_pack(self.base / "leak", manifest, files)
        problems = packs.audit_bundle(directory)
        self.assertTrue(
            any("coloring-page.html" in problem and "reference answer" in problem for problem in problems),
            f"the colouring page was not scanned for the answer key: {problems}",
        )

    def test_old_four_role_v3_pack_still_validates(self) -> None:
        """The test that proves old packs cannot break: four roles, contract v3, audited clean."""
        manifest, files = v3_four_role_pack()
        self.assertEqual(manifest["contract_version"], 3)
        packs.validate_manifest(manifest)
        packs.validate_minima(manifest)
        directory = write_pack(self.base / "v3", manifest, files)
        self.assertEqual(packs.audit_bundle(directory), [])

    def test_a_v3_document_may_not_declare_the_new_role(self) -> None:
        manifest, files = v3_four_role_pack()
        manifest["files"][1]["role"] = "coloring_page"
        manifest["files"][1]["mime"] = "text/html"
        manifest = packs.with_content_hash(manifest)
        with self.assertRaises(packs.PackRejected):
            packs.validate_manifest(manifest)

    def test_an_html_print_document_may_not_carry_active_content(self) -> None:
        manifest = hp.pack_manifest(self.fixture, TASK, paper="A4")
        files = hp.pack_documents(self.fixture, TASK, paper="A4")
        files["content/coloring-page.html"] = files["content/coloring-page.html"].replace(
            b"</body>", b"<script>print(1)</script></body>", 1
        )
        manifest = hp.pack_manifest(self.fixture, TASK, paper="A4")
        directory = write_pack(self.base / "active", manifest, files)
        problems = packs.audit_bundle(directory)
        self.assertTrue(any("active content" in problem for problem in problems), problems)


@unittest.skipUnless(shutil.which("chromium") and shutil.which("pdftotext"), "print path needs chromium and pdftotext")
class ArtifactPrintTests(unittest.TestCase):
    def test_the_pack_artifact_prints_and_carries_no_answer_text(self) -> None:
        """End to end: the artifact's own bytes are printed, and ``pdftotext`` reads the result."""
        data = fixture()
        manifest = hp.pack_manifest(data, TASK, paper="A4")
        files = hp.pack_documents(data, TASK, paper="A4")
        entry = next(item for item in manifest["files"] if item["role"] == "coloring_page")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            directory = write_pack(base / "pack", manifest, files)
            artifact = directory / entry["path"]
            html_text = artifact.read_text(encoding="utf-8")
            pdf = hp.write_pdf(html_text, base / "coloring-page.pdf")
            text = subprocess.run(
                ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, timeout=120
            ).stdout
        labels = hp.label_index(data)
        for label in labels.values():
            self.assertIn(label["display"], text)
            self.assertIn(label["romaji"], text)
        self.assertIn("Words in this picture", text)
        self.assertNotIn("Expected responses", text)
        self.assertNotIn("PARENT ONLY", text)
        self.assertNotIn("answer guide", text.lower())
        # And the parent guide is the thing that tells the parent to print it.
        guide = hp.render_documents(data, TASK)["parent_guide"]
        self.assertIn("While they colour", guide)
        self.assertIn("Print the colouring page with this pack", guide)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
