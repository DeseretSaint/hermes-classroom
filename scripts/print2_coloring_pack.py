#!/usr/bin/env python3
"""PRINT-2 (kanban t_6418b9dd) proof: the colouring page ships inside a real pack.

Before this card the page rendered and went nowhere: ``homework_print.render_documents`` had four
keys, the parent guide said "print the colouring page", and no pack could carry it. This script
builds the ``hw_labels`` take-home pack at A4 through the production builder
(:func:`coursebook.homework_print.pack_manifest`), writes a real ``cb.pack`` archive, audits it,
extracts it back, and prints the measurements the card asks for:

* the colouring artifact is present, with its role and its pack-relative path;
* the parent guide carries the "While they colour" section;
* ``pdftotext`` of the shipped artifact prints the word bank and no answer-guide text;
* the archive round-trips through :func:`coursebook.archive.extract_archive`.

Writes ``docs/visual-review/print-2-coloring/``. Run: ``python3 scripts/print2_coloring_pack.py``
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import archive, homework_print as hp, packs  # noqa: E402

OUT = ROOT / "docs" / "visual-review" / "print-2-coloring"
TASK = "hw_labels"
PAPER = "A4"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    fixture = hp.load_fixture()
    manifest = hp.pack_manifest(fixture, TASK, paper=PAPER)
    files = hp.pack_documents(fixture, TASK, paper=PAPER)
    OUT.mkdir(parents=True, exist_ok=True)

    archive_path = archive.write_archive(OUT / f"{manifest['pack_id']}-{manifest['pack_version']}.zip", manifest, files)

    with tempfile.TemporaryDirectory(prefix="print2-pack-") as tmp:
        extraction = Path(tmp) / "pack"
        round_trip = archive.extract_archive(archive_path, extraction)
        root = next(path for path in extraction.iterdir() if path.is_dir())
        round_trip_manifest, round_trip_files = archive.read_directory(root)
        if round_trip_manifest["content_hash"] != manifest["content_hash"]:
            raise SystemExit("the extracted pack does not hash to the manifest's content_hash")
        if set(round_trip_files) != set(files):
            raise SystemExit("the extracted pack does not declare the same files")
        problems = packs.audit_bundle(root)
        if problems:
            raise SystemExit("the pack does not audit clean: " + "; ".join(problems))
        artifact = (root / "content/coloring-page.html").read_bytes()
    if artifact != files["content/coloring-page.html"]:
        raise SystemExit("the extracted colouring artifact is not the built artifact")

    # pdftotext the shipped artifact. The pack carries the HTML the print path renders to PDF, so
    # the PDF is made from the artifact's own bytes, not from a re-render.
    pdf = hp.write_pdf(artifact.decode("utf-8"), OUT / "coloring-page.pdf")
    text = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, timeout=120, check=True
    ).stdout
    (OUT / "coloring-page.txt").write_text(text, encoding="utf-8")

    labels = hp.label_index(fixture)
    missing_words = [row["display"] for row in labels.values() if row["display"] not in text]
    leaked = [phrase for phrase in ("Expected responses", "PARENT ONLY", "answer guide") if phrase in text]
    guide = hp.render_documents(fixture, TASK, paper=PAPER)["parent_guide"]
    if "While they colour" not in guide:
        raise SystemExit("the parent guide has lost the 'While they colour' tie-in")
    if missing_words:
        raise SystemExit(f"the printed artifact is missing the word bank: {missing_words}")
    if leaked:
        raise SystemExit(f"the printed artifact carries answer-guide text: {leaked}")

    roles = [
        {"role": entry["role"], "path": entry["path"], "mime": entry["mime"], "bytes": entry["bytes"]}
        for entry in manifest["files"]
    ]
    record = {
        "card": "PRINT-2 (kanban t_6418b9dd)",
        "generated_by": "scripts/print2_coloring_pack.py",
        "task": TASK,
        "paper": PAPER,
        "pack": {
            "pack_id": manifest["pack_id"],
            "pack_version": manifest["pack_version"],
            "contract": manifest["contract"],
            "contract_version": manifest["contract_version"],
            "content_hash": manifest["content_hash"],
            "archive": archive_path.name,
            "archive_sha256": sha256(archive_path),
            "audit_problems": problems,
            "round_trip_content_hash": round_trip["content_hash"],
        },
        "roles": roles,
        "coloring_artifact": next(entry for entry in roles if entry["role"] == "coloring_page"),
        "parent_guide_carries_while_they_colour": "While they colour" in guide,
        "pdftotext": {
            "pdf": pdf.name,
            "pdf_sha256": sha256(pdf),
            "text": "coloring-page.txt",
            "text_sha256": sha256(OUT / "coloring-page.txt"),
            "word_bank_words_found": [row["display"] for row in labels.values()],
            "answer_guide_phrases_found": leaked,
            "lines": [line.strip() for line in text.splitlines() if line.strip()][:8],
        },
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"pack      {manifest['pack_id']} {manifest['pack_version']} contract v{manifest['contract_version']}")
    print(f"archive   {archive_path.name} {record['pack']['archive_sha256']}")
    print(f"audit     {len(problems)} problems (round trip hash {round_trip['content_hash']})")
    print("roles")
    for entry in roles:
        print(f"  {entry['role']:<13} {entry['path']:<32} {entry['mime']:<12} {entry['bytes']} bytes")
    print(f"guide says 'While they colour': {record['parent_guide_carries_while_they_colour']}")
    print("pdftotext (first lines)")
    for line in record["pdftotext"]["lines"]:
        print(f"  {line}")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
