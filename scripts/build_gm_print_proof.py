#!/usr/bin/env python3
"""Build the GM-013 print-pack specimen and its proof.

Produces the A4 and US-Letter PDFs from one HTML source with explicit ``@page`` rules, renders
110 dpi page images, extracts per-page text, and writes ``proof.json`` with the page boxes, the
answer-key sentinel locations and the file hashes.

The specimen is **labelled as a specimen**. ``⟨…⟩`` marks a slot a real lesson fills. It proves page
anatomy, margins, low ink and answer-key separation; it is not a lesson.

Run: ``python3 scripts/build_gm_print_proof.py``
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "gm-visual" / "print"
PLATE = ROOT / "docs" / "gm-visual" / "boards" / "japanese-lantern-district.svg"
PLATE_HREF = "../boards/japanese-lantern-district.svg"

SENTINEL = "\u27e8answer-key\u27e9"  # ⟨answer-key⟩ — must appear on page 3 only

CSS = """
@page {
  size: %(size)s;
  margin: %(margin)s;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #ffffff; color: #000000; }
body {
  font-family: "Liberation Serif", "Nimbus Roman", Georgia, serif;
  font-size: 10.5pt; line-height: 15.5pt;
}
.sheet { break-before: page; page-break-before: always; }
.sheet:first-of-type { break-before: auto; page-break-before: auto; }
.masthead {
  display: flex; justify-content: space-between; align-items: baseline;
  border-bottom: 1pt solid #000; padding-bottom: 3mm; margin-bottom: 5mm;
}
.masthead .title { font-size: 20pt; line-height: 22pt; font-weight: 600; }
.masthead .tag {
  font-family: "Liberation Sans", "Nimbus Sans", sans-serif;
  font-size: 8pt; text-transform: uppercase; letter-spacing: 0.12em;
}
h2 { font-size: 15pt; line-height: 18pt; font-weight: 600; margin: 0 0 4mm; }
h3 {
  font-family: "Liberation Sans", "Nimbus Sans", sans-serif;
  font-size: 8pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.12em;
  margin: 6mm 0 2mm;
}
p { margin: 0 0 3mm; max-width: 96mm; }
.lead { font-size: 12pt; line-height: 16pt; }
.meta {
  font-family: "Liberation Sans", "Nimbus Sans", sans-serif;
  font-size: 9pt; line-height: 12pt;
}
.caption {
  font-family: "Liberation Sans", "Nimbus Sans", sans-serif;
  font-size: 8pt; line-height: 10.5pt;
}
.rule { border-top: 0.5pt solid #000; margin: 4mm 0; }
.hair { border-top: 0.25pt solid #000; margin: 3mm 0; }
.accent { border-top: 2pt solid #000; margin: 4mm 0; }
.row { display: grid; grid-template-columns: 42mm 1fr; gap: 4mm; margin-bottom: 3mm; }
.row dt {
  font-family: "Liberation Sans", "Nimbus Sans", sans-serif;
  font-size: 9pt; font-weight: 600;
}
.row dd { margin: 0; font-size: 10.5pt; line-height: 15.5pt; }
ol { margin: 0 0 3mm 6mm; padding: 0; }
li { margin-bottom: 2mm; }
table.sources { width: 100%%; border-collapse: collapse; font-size: 9pt; }
table.sources th, table.sources td {
  text-align: left; vertical-align: top; padding: 1.6mm 2mm;
  border-bottom: 0.25pt solid #000;
}
table.sources th {
  font-family: "Liberation Sans", "Nimbus Sans", sans-serif;
  font-size: 8pt; text-transform: uppercase; letter-spacing: 0.08em;
}
.plate { width: 90mm; height: 50.625mm; border: 0.5pt solid #000; }
.tear { border-top: 1pt dashed #000; margin: 6mm 0 4mm; }
.parent-only {
  font-family: "Liberation Sans", "Nimbus Sans", sans-serif;
  font-size: 24pt; font-weight: 600; letter-spacing: 0.04em; text-align: right;
  margin: 0 0 2mm;
}
.specimen {
  font-family: "Liberation Sans", "Nimbus Sans", sans-serif;
  font-size: 8pt; border: 0.5pt solid #000; padding: 2mm 3mm; margin-bottom: 5mm;
}
.footer {
  font-family: "Liberation Sans", "Nimbus Sans", sans-serif;
  font-size: 8pt; display: flex; justify-content: space-between;
  margin-top: 8mm; padding-top: 2mm; border-top: 0.25pt solid #000;
}
.page { position: relative; }
"""

PAGES = {
    # no fixed page box: the break is explicit per sheet, and content that fits stays on its page.
    "a4": {"size": "A4", "margin": "18mm", "label": "A4"},
    "letter": {"size": "Letter", "margin": "0.70in", "label": "US Letter"},
}


def body(plate_href: str) -> str:
    return f"""
<section class="sheet"><div class="page">
  <div class="specimen">PRINT PROOF SPECIMEN — GM-013. Page anatomy, margins, low-ink layout and
  answer-key separation. This is not a lesson; every <code>&#10216;&#8230;&#10217;</code> slot is
  filled from a validated source lesson at export time.</div>
  <div class="masthead">
    <div class="title">&#10216;pack title&#10217;</div>
    <div class="tag">Take-home pack &middot; parent guide</div>
  </div>
  <div class="meta">SOURCE &#10216;course title&#10217; &middot; &#10216;section&#10217; &middot;
    lesson v&#10216;n&#10217; &middot; content hash &#10216;sha256&#10217;</div>
  <div class="rule"></div>
  <div class="row"><div class="meta">OBJECTIVE</div>
    <div class="lead">&#10216;the source lesson's objective, verbatim&#10217;</div></div>
  <div class="row"><div class="meta">LEVEL AND AUDIENCE</div>
    <div>&#10216;level, e.g. L0&#10217; &middot; adult operator; the parent prepares and teaches</div></div>
  <div class="row"><div class="meta">MATERIALS</div><div>&#10216;list, or &ldquo;none&rdquo;&#10217;</div></div>
  <div class="row"><div class="meta">PREPARATION</div><div>&#10216;what to set up, 1&ndash;3 lines&#10217;</div></div>
  <h3>Script</h3>
  <ol><li>&#10216;step 1&#10217;</li><li>&#10216;step 2&#10217;</li><li>&#10216;step 3&#10217;</li></ol>
  <h3>Ask</h3>
  <p>&#10216;question&#10217; &middot; &#10216;question&#10217;</p>
  <h3>What to notice</h3>
  <p>&#10216;observable behaviour&#10217;</p>
  <div class="accent"></div>
  <p class="lead">You have done it when: &#10216;one observable sentence&#10217;</p>
  <div class="footer"><span>Answers: see the separate answer guide.</span><span>1</span></div>
</div></section>

<section class="sheet"><div class="page">
  <h2>&#10216;activity title&#10217;</h2>
  <h3>One thing to do today</h3>
  <p class="lead">&#10216;target: the exact word, phrase, concept or action&#10217;</p>
  <ol><li>&#10216;step 1&#10217;</li><li>&#10216;step 2&#10217;</li><li>&#10216;step 3&#10217;</li></ol>
  <div class="accent"></div>
  <p class="lead">You have done it when: &#10216;one observable sentence&#10217;</p>
  <p class="caption">Done (self-reported) &#9744; &nbsp;&nbsp; Done (parent-reported) &#9744;</p>
  <div class="hair"></div>
  <img class="plate" src="{plate_href}" alt="Plate: a lantern street with a cafe counter, a noren panel and a cup. Orientation only.">
  <p class="caption">World visual &mdash; generated plate; orientation only, not a diagram of the course.
  Text equivalent: a lantern district with a cafe counter and a doorway curtain; nothing in the
  plate carries a word, number, instruction or measurement.</p>
  <div class="footer"><span>Learner page &middot; no answer key on this page</span><span>2</span></div>
</div></section>

<section class="sheet"><div class="page">
  <p class="parent-only">PARENT ONLY</p>
  <h2>&#10216;activity title&#10217; &mdash; answer guide</h2>
  <div class="tear"></div>
  <div class="row"><div class="meta">EXPECTED RESPONSE</div>
    <div>{SENTINEL} &#10216;verbatim expected response from the check's reference answer&#10217;</div></div>
  <div class="row"><div class="meta">ACCEPTED ALTERNATIVES</div>
    <div>&#10216;list from the check's accepted_alternatives&#10217;</div></div>
  <div class="row"><div class="meta">COMMON ERRORS</div>
    <div>&#10216;error&#10217; &rarr; &#10216;what to say instead&#10217;</div></div>
  <div class="row"><div class="meta">NEXT STEP</div>
    <div>&#10216;the next objective, or a retrieval check in the course&#10217;</div></div>
  <p class="caption">This page is a separate file in export (<code>answer-guide.pdf</code>) and is
  never bound into the learner pack.</p>
  <div class="footer"><span>Answer guide &middot; parent only</span><span>3</span></div>
</div></section>

<section class="sheet"><div class="page">
  <h2>Sources and provenance</h2>
  <table class="sources">
    <tr><th>Title</th><th>Publisher</th><th>URL</th><th>Published</th><th>Accessed</th><th>Support</th></tr>
    <tr><td>&#10216;source title&#10217;</td><td>&#10216;publisher&#10217;</td>
        <td>&#10216;url&#10217;</td><td>&#10216;date or &ldquo;not recorded&rdquo;&#10217;</td>
        <td>&#10216;fetch date&#10217;</td><td>supports</td></tr>
    <tr><td>&#10216;source title&#10217;</td><td>&#10216;publisher&#10217;</td>
        <td>&#10216;url&#10217;</td><td>&#10216;date&#10217;</td>
        <td>&#10216;fetch date&#10217;</td><td>partial</td></tr>
  </table>
  <h3>Visual record</h3>
  <p class="meta">Plate: host-composed reference board &middot; generator
  <code>scripts/build_gm_visual_assets.py</code> &middot; prompt: none (no model call) &middot;
  palette <code>contracts/cb.tokens.v2.json</code> &middot; licence CC0-1.0 &middot;
  role: orientation &middot; not a diagram of the course.</p>
  <h3>What this pack is not</h3>
  <p>A support label is recorded, never inferred. A source with no access date prints
  &ldquo;access date not recorded&rdquo;. No value in a plate is a course fact.</p>
  <div class="footer"><span>Sources and provenance</span><span>4</span></div>
</div></section>

<section class="sheet"><div class="page">
  <h2>Visual caption sheet</h2>
  <img class="plate" src="{plate_href}" alt="Plate: a lantern street with a cafe counter, a noren panel and a cup. Orientation only.">
  <p class="caption"><strong>Caption.</strong> World visual &mdash; generated plate; orientation only,
  not a diagram of the course.</p>
  <p class="caption"><strong>Text equivalent.</strong> A lantern district at dusk: three paper lanterns,
  a cafe counter with two stools, a noren doorway panel, a cup with steam. Nothing in the plate carries
  a word, number, instruction, measurement or rating.</p>
  <p class="caption"><strong>Provenance.</strong> host-composed &middot;
  <code>scripts/build_gm_visual_assets.py</code> &middot; no model call &middot; CC0-1.0 &middot;
  role: orientation.</p>
  <p class="caption">This sheet is optional. In <code>low_ink = true</code> the plate is omitted and
  both the caption and the text equivalent are kept.</p>
  <div class="footer"><span>Visual caption sheet &middot; optional</span><span>5</span></div>
</div></section>
"""


def build_html(variant: str, only: int | None = None) -> str:
    """One HTML file. ``only`` selects a single sheet (0-based) for the per-page build.

    Chromium's print flow carried a following sheet's 24 pt label into the previous sheet's bottom
    margin (measured at y=785 of 842 pt, outside the 18 mm margin) no matter which break property
    was used. Each sheet is therefore printed from its own file and the five pages are merged with
    qpdf, so no page can inherit a neighbour's first line.
    """
    spec = PAGES[variant]
    css = CSS % spec
    href = PLATE_HREF if only is None else "../" + PLATE_HREF
    content = body(href)
    if only is not None:
        sheets = re.findall(r"<section class=\"sheet\">.*?</section>", content, re.S)
        content = sheets[only]
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>GM-013 print pack specimen</title><style>" + css + "</style></head><body>"
        + content + "</body></html>"
    )


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    chromium = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if not chromium:
        print("chromium not found", file=sys.stderr)
        return 2

    proof: dict[str, Any] = {"card": "GM-013", "variant": "specimen", "sentinel": SENTINEL, "pdfs": {}}
    qpdf = shutil.which("qpdf")
    if not qpdf:
        print("qpdf not found; cannot merge per-page prints", file=sys.stderr)
        return 2
    for variant in ("a4", "letter"):
        html_path = OUT / f"pack-specimen-{variant}.html"
        html_path.write_text(build_html(variant), encoding="utf-8")
        pdf_path = OUT / f"pack-specimen-{variant}.pdf"
        parts_dir = OUT / f".parts-{variant}"
        if parts_dir.exists():
            shutil.rmtree(parts_dir)
        parts_dir.mkdir(parents=True)
        parts = []
        for index in range(5):
            one = parts_dir / f"p{index + 1}.html"
            one.write_text(build_html(variant, only=index), encoding="utf-8")
            part_pdf = parts_dir / f"p{index + 1}.pdf"
            result = run([
                chromium, "--headless", "--disable-gpu", "--no-sandbox",
                "--no-pdf-header-footer", "--hide-scrollbars",
                f"--print-to-pdf={part_pdf}", one.as_uri(),
            ])
            if not part_pdf.exists():
                print(result.stdout, result.stderr, file=sys.stderr)
                return 3
            parts.append(str(part_pdf))
        merged = run([qpdf, "--empty", "--pages", *parts, "--", str(pdf_path)])
        if merged.returncode != 0 or not pdf_path.exists():
            print(merged.stdout, merged.stderr, file=sys.stderr)
            return 3
        shutil.rmtree(parts_dir)
        info = run(["pdfinfo", str(pdf_path)]).stdout
        pages = 0
        size = ""
        for line in info.splitlines():
            if line.startswith("Pages:"):
                pages = int(line.split(":", 1)[1].strip())
            if line.startswith("Page size:"):
                size = line.split(":", 1)[1].strip()
        # per-page text and sentinel locations
        per_page = []
        sentinel_pages = []
        for n in range(1, pages + 1):
            text = run(["pdftotext", "-f", str(n), "-l", str(n), str(pdf_path), "-"]).stdout
            per_page.append({"page": n, "chars": len(text), "has_sentinel": SENTINEL in text})
            if SENTINEL in text:
                sentinel_pages.append(n)
        proof["pdfs"][variant] = {
            "path": str(pdf_path.relative_to(ROOT)),
            "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "bytes": pdf_path.stat().st_size,
            "pages": pages,
            "page_size": size,
            "sentinel_pages": sentinel_pages,
            "per_page": per_page,
        }
        print(f"{variant}: {pages} pages, {size}, sentinel on {sentinel_pages}")

    # page images from the A4 build
    a4 = OUT / "pack-specimen-a4.pdf"
    for old in OUT.glob("page-*.png"):
        old.unlink()
    run(["pdftoppm", "-r", "110", "-png", str(a4), str(OUT / "page")])
    pngs = sorted(OUT.glob("page-*.png"))
    proof["page_images"] = [str(p.relative_to(ROOT)) for p in pngs]
    proof["page_image_count"] = len(pngs)

    # learner-page purity: no sentinel, no expected-response slot marker
    learner = [p for p in proof["pdfs"].values()][0]
    proof["answer_key_separated"] = learner["sentinel_pages"] == [3]

    html_a4 = OUT / "pack-specimen-a4.html"
    proof["html_sha256"] = hashlib.sha256(html_a4.read_bytes()).hexdigest()
    (OUT / "proof.json").write_text(json.dumps(proof, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"page images: {len(pngs)}")
    print(f"answer key separated: {proof['answer_key_separated']}")
    return 0 if proof["answer_key_separated"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
