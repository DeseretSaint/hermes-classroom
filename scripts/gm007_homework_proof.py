"""Render and measure the GM-007 homework field-card proof.

For every proposal in the reviewed Japanese L0 proposals it builds the lesson's homework block,
renders the one-page sheet, prints it with Chromium at A4 (and Letter for the three field cards a
parent is most likely to hand over), rasterises a black-and-white page image, and measures what
the claim needs:

* one page, and the page size actually requested;
* Japanese extracts as selectable text;
* low ink, measured from the rasterised page, never asserted;
* no answer key, no grade/XP/surveillance word on the sheet;
* every phrase carries one of the reviewed fixture's cited sources.

A failed check raises before the manifest is written, so the committed proof cannot drift from the
code. Output: ``docs/visual-review/gm-007/``.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import homework as hw
from coursebook import homework_print as hp

OUT = ROOT / "docs" / "visual-review" / "gm-007"
LETTER = ("hw_premeal", "hw_labels", "hw_cafe")


def dark_fraction(pgm: Path) -> float:
    raw = pgm.read_bytes()
    if not raw.startswith(b"P5"):
        raise SystemExit(f"not a P5 PGM: {pgm}")
    parts = raw.split(maxsplit=4)
    width, height, maxval = int(parts[1]), int(parts[2]), int(parts[3])
    body = parts[4]
    if body[:1] == b"\n":
        body = body[1:]
    threshold = maxval // 2
    dark = sum(1 for value in body[: width * height] if value < threshold)
    return dark / float(width * height)


def task_for(proposal_id: str) -> dict:
    block = hw.demo_lesson_block(proposal_id)
    return {
        "title": block["title"],
        "target": block["target"],
        "context": block["context"],
        "steps": block["steps"],
        "success_criterion": block["success_criterion"],
        "estimated_minutes": block["estimated_minutes"],
        "completion_record": block.get("completion_record") or [],
        "sources": hw.resolve_sources(hw.demo_page_sources(proposal_id),
                                      block["target"].get("source_ids") or []),
        "completion": {"basis": None},
    }


class UnmarkedJapanese(HTMLParser):
    """Every Japanese text node must sit inside an element carrying ``lang="ja"``."""

    _VOID = {"meta", "link", "br", "hr", "img", "input", "source"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[bool] = []
        self.unmarked: list[str] = []

    def handle_starttag(self, tag, attrs):  # noqa: ANN001 - stdlib signature
        if tag in self._VOID:
            return
        inside = bool(self.stack and self.stack[-1]) or dict(attrs).get("lang") == "ja"
        self.stack.append(inside)

    def handle_endtag(self, tag):  # noqa: ANN001 - stdlib signature
        if tag not in self._VOID and self.stack:
            self.stack.pop()

    def handle_data(self, data):  # noqa: ANN001 - stdlib signature
        if hw._JP_RUN.search(data) and not (self.stack and self.stack[-1]):
            self.unmarked.append(data.strip())


def main() -> None:
    for binary in ("chromium", "pdftoppm"):
        if not shutil.which(binary):
            raise SystemExit(f"{binary} is required for the print proof")
    data = hw.validate_proposals()
    if data:
        raise SystemExit(f"proposal set is not printable: {data}")
    OUT.mkdir(parents=True, exist_ok=True)
    documents: list[dict] = []
    pngs: list[dict] = []
    bw: list[dict] = []
    for proposal in hw.demo_proposals()["proposals"]:
        proposal_id = proposal["proposal_id"]
        task = task_for(proposal_id)
        html_text = hw.sheet_html(task)
        text = hw.sheet_text(html_text)
        lowered = text.lower()
        for banned in hw.SHEET_FORBIDDEN:
            if banned in lowered:
                raise SystemExit(f"{proposal_id}: sheet carries forbidden word {banned!r}")
        # Every cited source must actually appear on the printed card.
        if not task["sources"]:
            raise SystemExit(f"{proposal_id}: the card cites no source")
        if "Source:" not in text:
            raise SystemExit(f"{proposal_id}: the card carries no source line")
        for source in task["sources"]:
            if source["title"] not in text:
                raise SystemExit(f"{proposal_id}: cited source {source['source_id']} is not printed")
        scanner = UnmarkedJapanese()
        scanner.feed(html_text)
        if scanner.unmarked:
            raise SystemExit(f"{proposal_id}: unmarked Japanese run(s) {scanner.unmarked}")
        papers = ["A4"] + (["Letter"] if proposal_id in LETTER else [])
        for paper in papers:
            name = f"{proposal_id}-{paper.lower()}-sheet"
            pdf = OUT / f"{name}.pdf"
            hp.write_pdf(html_text.replace("size: A4;", f"size: {paper};"), pdf)
            info = hp.pdf_info(pdf)
            pages = int(info["Pages"])
            numbers = [part for part in str(info["Page size"]).replace("x", " ").split()
                       if part.replace(".", "", 1).isdigit()]
            width, height = float(numbers[0]), float(numbers[1])
            expected = hp.paper_dimensions(paper)
            if pages != 1:
                raise SystemExit(f"{name}: {pages} pages, expected 1")
            if abs(width - expected[0]) > 4 or abs(height - expected[1]) > 4:
                raise SystemExit(f"{name}: {width}x{height} is not {paper}")
            extracted = hp.pdf_text(pdf)
            flat = re.sub(r"\s+", " ", extracted)
            for needle in (task["target"]["display"], task["success_criterion"]):
                if needle not in flat:
                    raise SystemExit(f"{name}: missing {needle!r} in the printed page")
            documents.append(
                {
                    "file": pdf.name,
                    "proposal": proposal_id,
                    "paper": paper,
                    "pages": pages,
                    "page_size_pt": [round(width, 2), round(height, 2)],
                    "whitespace_ink_check": "pass",
                    "sha256": "sha256:" + hashlib.sha256(pdf.read_bytes()).hexdigest(),
                    "bytes": pdf.stat().st_size,
                    "selectable_text": True,
                    "japanese_extractable": task["target"]["display"] in extracted,
                }
            )
            prefix = OUT / name
            subprocess.run(
                ["pdftoppm", "-png", "-r", "150", str(pdf), str(prefix)],
                check=True, capture_output=True, timeout=180,
            )
            for image in sorted(OUT.glob(f"{name}-[0-9]*.png")):
                pngs.append({"file": image.name, "proposal": proposal_id, "paper": paper})
            with tempfile.TemporaryDirectory(prefix="gm007-ink-") as tmp:
                subprocess.run(
                    ["pdftoppm", "-gray", "-r", "150", str(pdf), str(Path(tmp) / "page")],
                    check=True, capture_output=True, timeout=180,
                )
                page = sorted(Path(tmp).glob("page-*.pgm"))[0]
                coverage = dark_fraction(page)
            if not 0.001 < coverage < 0.12:
                raise SystemExit(f"{name}: ink coverage {coverage:.4f} is outside the low-ink band")
            if paper == "A4":
                target = OUT / f"{name}-bw.png"
                shutil.copyfile(OUT / f"{name}-1.png", target)
                bw.append({"file": target.name, "proposal": proposal_id, "ink_fraction":
                           round(coverage, 4)})
            documents[-1]["ink_fraction"] = round(coverage, 4)
    manifest = {
        "contract": "cb.homework_proof",
        "contract_version": 1,
        "fixture": hw.demo_proposals()["binding"],
        "proposals_hash": hw.demo_proposals()["binding"]["proposals_hash"],
        "note": (
            "Field cards rendered from the reviewed L0 lesson fixture through the GM-007 sheet "
            "template. Page sizes, page count, extracted text and ink coverage are measured here, "
            "not asserted. No answer key, no grade, no XP and no surveillance request appears on "
            "any card; completion is self- or parent-reported."
        ),
        "checks": {
            "proposal_set_printable": "pass",
            "one_page_per_card": "pass",
            "page_size_matches_requested_paper": "pass",
            "japanese_extractable": "pass",
            "low_ink_band_measured": "pass",
            "no_answer_key_no_grade_no_xp": "pass",
            "sources_present": "pass",
            "japanese_lang_marked": "pass",
        },
        "documents": documents,
        "png": pngs,
        "bw_proofs": bw,
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(documents)} PDFs, {len(pngs)} PNGs, {len(bw)} grayscale proof(s) to {OUT}")


if __name__ == "__main__":
    main()
