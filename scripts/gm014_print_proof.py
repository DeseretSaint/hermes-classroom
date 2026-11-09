#!/usr/bin/env python3
"""Build the GM-014 print proof under ``docs/visual-review/gm-014/``.

Run from the repository root:

    python3 scripts/gm014_print_proof.py

The script prints the real PDFs with headless Chromium, rasterises page images, extracts the PDF
text back with ``pdftotext`` and refuses to write a manifest when a page has lost body text
(which is what a clipped fixed-height sheet looks like). It also measures every manifest check
from the written files instead of asserting it. Nothing is sent anywhere.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import homework_print as hp  # noqa: E402
from tests.test_procedure_document import head_gasket_document  # noqa: E402

PROOF = ROOT / "docs" / "visual-review" / "gm-014"


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text: str) -> str:
    return re.sub(r"\s+", "", text)


def chromium_version() -> str:
    try:
        binary = hp.chromium_binary()
    except hp.PrintUnavailable:
        return "unavailable"
    result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=30)
    return result.stdout.strip() or "unknown"


def require_text(pdf: Path, needles: list[str]) -> tuple[bool, list[str]]:
    extracted = normalized(hp.pdf_text(pdf))
    missing = [needle for needle in needles if normalized(needle) not in extracted]
    return not missing, missing


def add_document(
    documents: list[dict],
    pngs: list[dict],
    *,
    html_text: str,
    relative: str,
    paper: str,
    role: str,
    task_id: str | None,
    required: list[str],
) -> Path:
    pdf_path = PROOF / relative
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    hp.write_pdf(html_text, pdf_path)
    info = hp.pdf_info(pdf_path)
    pages = int(info["Pages"])
    if pages != hp.page_count(html_text):
        raise SystemExit(f"{relative}: HTML has {hp.page_count(html_text)} sheets but PDF has {pages}")
    ok, missing = require_text(pdf_path, required)
    if not ok:
        raise SystemExit(f"{relative}: page text missing (possible clipping): {missing}")
    stem = pdf_path.stem
    for png in hp.pdf_to_png(pdf_path, pdf_path.parent / stem, dpi=144):
        pngs.append({"file": str(png.relative_to(PROOF)), "source": relative, "dpi": 144})
    documents.append(
        {
            "file": relative,
            "paper": paper,
            "role": role,
            "task_id": task_id,
            "pages": pages,
            "page_size": info["Page size"],
            "sha256": sha256(pdf_path),
            "bytes": pdf_path.stat().st_size,
            "required_text": required,
            "required_text_present": ok,
            "missing_text": missing,
        }
    )
    return pdf_path


def compute_checks(
    fixture: Mapping[str, Any], documents: list[dict], technical_html: str
) -> dict[str, str]:
    """Evaluate each manifest check from the printed files and rendered HTML.

    Nothing here is asserted from memory: page size comes from ``pdfinfo`` on the written PDF,
    separation and low ink come from the rendered documents, and the technical check inspects the
    technical HTML for any image element.
    """
    size_ok = True
    for entry in documents:
        info = hp.pdf_info(PROOF / entry["file"])
        width, height = hp.paper_dimensions(entry["paper"])
        try:
            parts = info["Page size"].split()
            got_width, got_height = float(parts[0]), float(parts[2])
        except (KeyError, ValueError, IndexError):
            size_ok = False
            break
        if abs(got_width - width) > 3.0 or abs(got_height - height) > 3.0:
            size_ok = False
            break

    separation_ok = True
    low_ink_ok = True
    for task in fixture["tasks"]:
        rendered = hp.render_documents(fixture, task["task_id"], paper="A4")
        learner = hp.learner_visible_text(rendered["learner_page"]).upper()
        guide = hp.learner_visible_text(rendered["answer_guide"])
        if "PARENT ONLY" in learner or "ANSWER GUIDE" in learner or "DO NOT GIVE THIS PAGE" in learner:
            separation_ok = False
        if "PARENT ONLY · ANSWER GUIDE" not in guide or "Do not give this page to the learner" not in guide:
            separation_ok = False
        for html_text in rendered.values():
            print_css = re.sub(r"@media screen \{.*", "", html_text, flags=re.S)
            backgrounds = set(re.findall(r"background(?:-color)?:\s*(#[0-9a-fA-F]{6})", print_css))
            if backgrounds != {"#ffffff"} or "linear-gradient" in print_css:
                low_ink_ok = False

    no_image_ok = (
        "<img" not in technical_html
        and "<svg" not in technical_html
        and "data:image" not in technical_html
    )
    problems = hp.validate_fixture(fixture)
    checks = {
        "content_rules": "pass" if not problems else "fail",
        "page_size_matches_requested_paper": "pass" if size_ok else "fail",
        "page_count_matches_html_sheet_count": "pass",
        "required_text_and_tail_present_in_pdf": "pass",
        "answer_guide_separate_from_learner_page": "pass" if separation_ok else "fail",
        "no_generated_image_in_technical_sheet": "pass" if no_image_ok else "fail",
        "low_ink_backgrounds": "pass" if low_ink_ok else "fail",
    }
    failed = [name for name, value in checks.items() if value != "pass"]
    if failed:
        raise SystemExit("proof checks failed: " + "; ".join(failed))
    return checks


def main() -> int:
    fixture = hp.load_fixture()
    problems = hp.validate_fixture(fixture)
    if problems:
        raise SystemExit("fixture failed content rules: " + "; ".join(problems))

    PROOF.mkdir(parents=True, exist_ok=True)
    documents: list[dict] = []
    pngs: list[dict] = []
    bw: list[dict] = []

    tail = {
        "learner_page": "It is not a pass, a score or evidence of mastery.",
        "homework_sheet": "No photo, recording or location is asked for.",
        "answer_guide": "It is never a pass, a mastery claim or evidence of learning.",
        "parent_guide": "It does not regenerate a lesson, clone a course or touch any evidence.",
    }
    targets = hp.target_index(fixture)
    labels = hp.label_index(fixture)
    for task in fixture["tasks"]:
        task_id = task["task_id"]
        target = targets[task["target_id"]]
        if target.get("kind") == "label_set":
            display = "・".join(labels[label_id]["display"] for label_id in target.get("label_ids") or [])
        else:
            display = target.get("display") or target.get("title")
        docs = hp.render_documents(fixture, task_id, paper="A4")
        for role, html_text in docs.items():
            required = [task["title"], display, tail[role], "Page 1 of"]
            if role == "parent_guide":
                required = [task["title"], display, "The four steps", tail[role], "Page 2 of 2"]
            if role == "answer_guide":
                required = ["PARENT ONLY", "ANSWER GUIDE", "Common errors", tail[role], "Page 1 of 1"]
            relative = f"a4/{task_id}-{role.replace('_', '-')}.pdf"
            pdf = add_document(
                documents, pngs,
                html_text=html_text, relative=relative, paper="A4", role=role,
                task_id=task_id, required=required,
            )
            if task_id == "hw_premeal" and role in ("learner_page", "answer_guide", "homework_sheet", "parent_guide"):
                for png in hp.pdf_to_png(pdf, PROOF / "bw" / f"{task_id}-{role.replace('_', '-')}", dpi=150, gray=True):
                    bw.append({"file": str(png.relative_to(PROOF)), "source": relative, "dpi": 150, "grayscale": True})

    # Letter proof for the whole premeal set.
    letter_docs = hp.render_documents(fixture, "hw_premeal", paper="Letter")
    for role in ("parent_guide", "learner_page", "answer_guide", "homework_sheet"):
        relative = f"letter/hw_premeal-{role.replace('_', '-')}.pdf"
        required = [fixture["tasks"][0]["title"], "いただきます", tail[role], "Page 1 of 1"]
        if role == "parent_guide":
            required = [fixture["tasks"][0]["title"], "いただきます", "The four steps", tail[role], "Page 2 of 2"]
        if role == "answer_guide":
            required = ["PARENT ONLY", "ANSWER GUIDE", "Common errors", tail[role], "Page 1 of 1"]
        add_document(
            documents, pngs,
            html_text=letter_docs[role], relative=relative, paper="Letter", role=role,
            task_id="hw_premeal", required=required,
        )

    # Technical one-pager: two pages, deterministic rows, no image at all.
    technical = head_gasket_document()
    technical_html = hp.render_technical_document(technical, paper="A4")
    technical_pdf = add_document(
        documents, pngs,
        html_text=technical_html, relative="a4/technical-head-gasket.pdf", paper="A4",
        role="technical_sheet", task_id=None,
        required=[
            "Replace the head gasket",
            "STOP CONDITION",
            "20 Nm",
            "40 Nm",
            "Deterministic schematic",
            "permission: licensed",
            "If any step was skipped, stop and do not start the engine.",
            "Page 2 of 2",
        ],
    )
    for png in hp.pdf_to_png(technical_pdf, PROOF / "bw" / "technical-head-gasket", dpi=150, gray=True):
        bw.append({"file": str(png.relative_to(PROOF)), "source": "a4/technical-head-gasket.pdf", "dpi": 150, "grayscale": True})

    checks = compute_checks(fixture, documents, technical_html)
    manifest = {
        "contract": "cb.print_proof",
        "contract_version": 1,
        "generated": date.today().isoformat(),
        "generated_by": "scripts/gm014_print_proof.py",
        "fixture": {
            "path": str(hp.FIXTURE_PATH.relative_to(ROOT)),
            "fixture_id": fixture["fixture_id"],
            "binding": fixture["binding"],
            "source_lesson_hash": fixture["binding"]["source_lesson_hash"],
            "fixture_lesson_block_hash": fixture["binding"]["source_lesson_hash"],
            "lesson_hash_covers": "the fixture's own lesson block, not a live course lesson",
            "content_problems": problems,
        },
        "environment": {
            "chromium": chromium_version(),
            "pdfinfo": Path(shutil.which("pdfinfo") or "unavailable").name,
            "pdftotext": Path(shutil.which("pdftotext") or "unavailable").name,
            "pdftoppm": Path(shutil.which("pdftoppm") or "unavailable").name,
            "japanese_font_expected": "Noto Sans CJK JP",
        },
        "documents": documents,
        "png_proofs": pngs,
        "bw_proofs": bw,
        "checks": checks,
    }
    (PROOF / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_report(manifest, PROOF / "PRINT-PROOF.md")
    print(f"wrote {len(documents)} PDFs, {len(pngs)} colour PNGs and {len(bw)} grayscale PNGs under {PROOF}")
    return 0


def write_report(manifest: dict, path: Path) -> None:
    rows = "\n".join(
        f"| `{entry['file']}` | {entry['paper']} | {entry['role']} | {entry['pages']} | "
        f"{entry['page_size']} | {'yes' if entry['required_text_present'] else 'NO'} |"
        for entry in manifest["documents"]
    )
    text = f"""# GM-014 print proof

Generated by `scripts/gm014_print_proof.py` on {manifest['generated']}. This file and the PDFs
beside it are the real proof, not a description of one.

## What was printed

| file | paper | role | pages | PDF page size | all page text present |
|---|---|---|---|---|---|
{rows}

- Fixture: `{manifest['fixture']['path']}` (`{manifest['fixture']['fixture_id']}`).
- Fixture lesson block hash: `{manifest['fixture']['source_lesson_hash']}` — sha256 over the demo fixture's own `lesson` block, not over a live course lesson.
- Renderer: headless Chromium `{manifest['environment']['chromium'].splitlines()[0] if manifest['environment']['chromium'] else 'unknown'}` printing HTML; text stays selectable and is extracted back with `pdftotext` to prove it.
- Japanese face: {manifest['environment']['japanese_font_expected']} (system font), so kana and kanji print as text, not an image.
- Colour PNGs: {len(manifest['png_proofs'])} pages at 144 dpi.
- Black-and-white PNGs: {len(manifest['bw_proofs'])} pages at 150 dpi from the same PDFs.

## How the no-clipping claim is checked

Every sheet is a fixed paper box with real margins; the page count, the ``Page n of N`` folio
and the *last body sentence* of each role are read back out of the PDF. A clipped page loses the
tail sentence and the script exits non-zero instead of writing this manifest. The table above
records `all page text present = yes` from that live extraction.

## What the manifest checks measure

`checks` in `MANIFEST.json` is computed by `scripts/gm014_print_proof.py`, not typed by hand:
page size is read from `pdfinfo` on each written PDF, answer-guide separation and low-ink
backgrounds come from the rendered HTML, and the technical-sheet check inspects that HTML for any
image element. If any check fails the script exits without writing a manifest.

## What is not claimed

- These are demo fixtures, not a published course. No native-speaker review is recorded and none is claimed.
- **PDF tagging is not claimed.** Japanese runs in the HTML carry `lang="ja"`, but the Chromium PDF export is untagged, so the SVG's accessible title and description do not survive into the PDF. Selectable text is claimed and proven; PDF accessibility tagging is not.
- The parent guide's hash binds the pack to the demo fixture's own lesson block. `demo-japanese-l0-mealtime` and `obj_mealtime_greetings` name that fixture; no course with those ids exists in this repository.
- No learner attempt, tutor turn, observation or child data is in any page.
- No page was sent anywhere; generating and printing are local actions.
"""
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
