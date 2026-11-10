#!/usr/bin/env python3
"""CP-016 live proof: two non-demo topics through the runtime world prompt builder.

Topics: one technical (bicycle hydraulic brake bleed -> workshop_manual) and one creative
(fingerpicking guitar -> studio_bench). Neither is in the demo set.

For each topic this script:

1. builds the three style boards and the approved kit with the shipping
   ``coursebook.world`` builders (the same functions the backend job calls);
2. generates each plate with the host's own ``image_generate`` tool (the managed Nous/FAL
   gateway the profile is configured for) — no test double, no re-hosted art;
3. downloads the provider's returned URL to ``docs/concept-parity/art/cp016/<topic>/`` and
   records the URL, sha256, prompt hash and prompt text in ``provenance.json``;
4. OCR-checks every plate for lettering and writes a Pillow-labelled contact sheet.

The product clamps provider aspect ratios to the host's three values (landscape / square /
portrait), exactly as ``HostMedia`` does; the contact sheet applies the mechanical crop the
layout uses (3:2 card, 16:9 hero, 4:5 cover, 1:1 section).

Usage:
  python3 scripts/cp016-world-proof.py --dry-run
  python3 scripts/cp016-world-proof.py
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HERMES = Path(os.environ.get("HERMES_AGENT_PATH", "/home/deseretsaint/.hermes/hermes-agent"))
sys.path.insert(0, str(HERMES))

from coursebook import world  # noqa: E402

OUT = ROOT / "docs/concept-parity/art/cp016"
PROVIDER = "image_generate (managed Nous tool gateway -> fal-queue)"
#: The proof uses the managed catalog's pro model: the fast default rendered flat vector and
#: pseudo-text on the first pass, which the art bible forbids. The model is recorded per plate.
PROOF_MODEL = "fal-ai/flux-2-pro"

#: Provider values the host accepts; the plate's own ratio stays in the prompt/provenance.
HOST_ASPECT = {"3:2": "landscape", "16:9": "landscape", "4:5": "portrait", "1:1": "square"}

#: Contact-sheet crop per role (mechanical, never stretched; SPEC-V3 §2).
CROP = {"style_board": (3, 2), "hero": (16, 9), "cover": (4, 5), "section": (1, 1), "card": (3, 2)}

TOPICS = {
    "technical-brake-bleed": {
        "course_id": "course_cp016_brake",
        "title": "Bleed a bicycle hydraulic brake",
        "subject_domain": "trades",
        "end_capability": "Bleed a hydraulic disc brake and restore a firm lever",
        "audience": "home mechanic",
        "level": "novice",
        "tone": "practical, calm, competent",
        "safety_class": "workshop",
        "motifs": ["service stand", "brake caliper", "bleed kit", "handlebar lever"],
        "forbidden": ["brand logos", "text"],
        "sections": [
            {"id": "s1", "title": "Setting up the bleed kit"},
            {"id": "s2", "title": "Pulling air through the line"},
        ],
    },
    "creative-fingerpicking": {
        "course_id": "course_cp016_guitar",
        "title": "Fingerpicking patterns for acoustic guitar",
        "subject_domain": "music",
        "end_capability": "Play three fingerpicking patterns in steady time",
        "audience": "adult beginner",
        "level": "novice",
        "tone": "warm, unhurried, curious",
        "safety_class": "none",
        "motifs": ["studio bench", "acoustic guitar", "felt pick", "open notebook"],
        "forbidden": ["brand logos", "text"],
        "sections": [
            {"id": "s1", "title": "Thumb and finger independence"},
            {"id": "s2", "title": "A first travis pattern"},
        ],
    },
}


def provider_generate(prompt: str, aspect_ratio: str, model: str | None = None) -> str:
    from tools.image_generation_tool import image_generate_tool

    if model:
        raw = image_generate_tool(prompt, aspect_ratio=HOST_ASPECT[aspect_ratio], fal_model=model)
    else:
        raw = image_generate_tool(prompt, aspect_ratio=HOST_ASPECT[aspect_ratio])
    payload = json.loads(raw)
    if not payload.get("success") or not payload.get("image"):
        raise RuntimeError(payload.get("error") or "image generation failed")
    return str(payload["image"])


def provider_edit(prompt: str, aspect_ratio: str, source: Path, model: str | None = None) -> str:
    """Edit an existing plate (the model's own edit endpoint) instead of re-rolling it.

    Used when a plate is compositionally right but carries one printed mark: an edit keeps the
    approved scene and removes the mark, where a fresh generation re-rolls every other detail.
    """
    from tools.image_generation_tool import image_generate_tool

    raw = image_generate_tool(
        prompt,
        aspect_ratio=HOST_ASPECT[aspect_ratio],
        fal_model=model or PROOF_MODEL,
        image_url=str(source.resolve()),
    )
    payload = json.loads(raw)
    if not payload.get("success") or not payload.get("image"):
        raise RuntimeError(payload.get("error") or "image edit failed")
    return str(payload["image"])


def download(url: str, path: Path) -> bytes:
    if url.startswith("data:"):
        header, _, payload = url.partition(",")
        if ";base64" not in header:
            raise RuntimeError("unsupported data URL encoding")
        data = base64.b64decode(payload)
    else:
        with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - provider URL
            data = response.read()
    if not data:
        raise RuntimeError(f"empty image at {url[:60]}")
    path.write_bytes(data)
    return data


def ocr(path: Path) -> dict:
    """CP-010 lettering standard: a word of two or more characters at >=70 confidence."""
    if not shutil.which("tesseract"):
        return {"text": "tesseract missing", "letters": None, "words": None}
    proc = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", "11", "tsv"],
        capture_output=True, text=True, check=False,
    )
    words = []
    for line in (proc.stdout or "").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        try:
            confidence = float(parts[10])
        except ValueError:
            continue
        token = parts[11].strip()
        if confidence >= 70 and len(token) >= 2:
            words.append(token)
    text = " ".join(words)
    return {"text": text, "letters": len(text), "words": words}


def _last_json_object(text: str) -> dict | None:
    """The last JSON object in a model answer that carries a ``notation`` key."""
    import re

    decoder = json.JSONDecoder()
    for match in reversed(list(re.finditer(r"\{", text))):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "notation" in value:
            return value
    return None


#: The notation/diagram gate question. One vision read per plate: the OCR gate in :func:`ocr`
#: only sees a >=2-character word at >=70 confidence, so staves, chord boxes, tick boxes and
#: single glyphs pass it by construction. A "clean" here is a measured result, not a claim.
NOTATION_QUESTION = (
    "Audit this illustration for printed marks. Answer with JSON only: "
    '{"notation": true|false, "kind": "what you saw", "evidence": "where"}. '
    "notation=true if the image contains any musical notation, staves, noteheads, clefs, chord "
    "boxes, tablature, fret numbers, code, equations, tick boxes, tables, diagrams, charts, "
    "letters, numerals, brand names or any symbol that resembles writing, or if it shows hands "
    "performing a technique or an instruction step. Ignore brush marks, paper grain, paint "
    "texture and the silhouette of ordinary objects."
)


def notation_check(path: Path) -> dict:
    """Vision read for the printed-mark class, recorded beside the OCR result. Fail-closed."""
    import asyncio

    sys.path.insert(0, str(HERMES))
    try:
        from tools.vision_tools import _handle_vision_analyze
    except Exception as error:  # noqa: BLE001 - recorded, never hidden
        return {"verdict": "unchecked", "notation": None, "error": str(error)[:400], "read": ""}
    try:
        raw = asyncio.run(
            _handle_vision_analyze(
                {"image_url": str(path.resolve()), "question": NOTATION_QUESTION}
            )
        )
    except Exception as error:  # noqa: BLE001
        return {"verdict": "unchecked", "notation": None, "error": str(error)[:400], "read": ""}
    payload = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(payload, dict) or not payload.get("success"):
        return {"verdict": "unchecked", "notation": None, "error": str(payload)[:400], "read": ""}
    analysis = str(payload.get("analysis") or "")
    parsed = _last_json_object(analysis)
    if parsed is None:
        return {"verdict": "unparsed", "notation": None, "read": analysis[-1500:]}
    flag = bool(parsed.get("notation"))
    return {
        "verdict": "suspect" if flag else "clean",
        "notation": flag,
        "kind": str(parsed.get("kind") or "")[:200],
        "evidence": str(parsed.get("evidence") or "")[:400],
        "read": analysis[-1500:],
    }


def summary_entry(slug: str, grammar: str, plates: list[dict], sheet: Path) -> dict:
    """The per-topic summary: counts a reader can re-derive from ``provenance.json``."""
    return {
        "topic": slug,
        "grammar": grammar,
        "plates": len(plates),
        "sheet": str(sheet),
        "prompt_versions": sorted({str(row.get("prompt_version") or "") for row in plates}),
        "lettering_gate_clean": sum(1 for row in plates if not row["ocr"].get("words")),
        "notation_gate_clean": sum(
            1 for row in plates if (row.get("notation") or {}).get("verdict") == "clean"
        ),
        "notation_gate_suspect": sum(
            1 for row in plates if (row.get("notation") or {}).get("verdict") == "suspect"
        ),
    }


def plan_for(slug: str) -> tuple[world.WorldBrief, str, list[world.WorldPrompt]]:
    brief = world.WorldBrief.from_mapping(TOPICS[slug])
    grammar = world.WorldPolicy.select(brief)
    boards = world.build_style_boards(brief)
    chosen = boards[0]  # the authored direction; approval record is named in provenance
    kit = world.build_kit_prompts(
        brief, grammar, style_id=chosen.style_id, style=chosen
    )
    return brief, grammar, list(boards) + kit


def contact_sheet(slug: str, rows: list[dict]) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    paper = (247, 241, 228)
    ink = (26, 23, 19)
    soft = (92, 83, 71)
    rule = (215, 203, 180)
    font_dir = "/usr/share/fonts/liberation"
    regular = ImageFont.truetype(f"{font_dir}/LiberationSans-Regular.ttf", 15)
    bold = ImageFont.truetype(f"{font_dir}/LiberationSans-Bold.ttf", 19)
    title_font = ImageFont.truetype(f"{font_dir}/LiberationSans-Bold.ttf", 28)

    cell_w, cell_h, cols = 420, 340, 4
    head, foot = 118, 96
    height = head + ((len(rows) + cols - 1) // cols) * cell_h + foot
    sheet = Image.new("RGB", (cols * cell_w + 48, height), paper)
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 22), f"CP-016 live proof — {slug}", font=title_font, fill=ink)
    draw.text(
        (24, 62),
        f"{world.PROMPT_VERSION}; {len(rows)} plates; provider {PROVIDER}",
        font=regular, fill=soft,
    )
    draw.line([(24, 96), (sheet.width - 24, 96)], fill=rule, width=1)

    for index, row in enumerate(rows):
        col, line = index % cols, index // cols
        x = 24 + col * cell_w
        y = head + line * cell_h
        image = Image.open(row["file"]).convert("RGB")
        ratio_w, ratio_h = CROP[row["role"]]
        # Mechanical centre crop to the layout ratio: cover the target, never stretch.
        target = ratio_w / ratio_h
        if image.width / image.height > target:
            new_w = int(round(image.height * target))
            box = ((image.width - new_w) // 2, 0, (image.width + new_w) // 2, image.height)
        else:
            new_h = int(round(image.width / target))
            box = (0, (image.height - new_h) // 2, image.width, (image.height + new_h) // 2)
        image = image.crop(box)
        image.thumbnail((cell_w - 40, 248), Image.Resampling.LANCZOS)
        sheet.paste(image, (x + (cell_w - image.width) // 2, y + 8))
        draw.text((x + 20, y + 268), f"{row['role']}  {row['aspect_ratio']}", font=bold, fill=ink)
        draw.text((x + 20, y + 292), row["style_id"], font=regular, fill=soft)
        draw.text(
            (x + 20, y + 312),
            f"sha {row['sha256'][:16]}  hash {row['prompt_hash'][7:19]}",
            font=regular, fill=soft,
        )

    draw.text(
        (24, height - 62),
        "Review artifact. Labels are drawn by Pillow from the file list, never by the model and "
        "never shipped as product UI.",
        font=regular, fill=soft,
    )
    path = OUT / slug / "contact-sheet.png"
    sheet.save(path)
    return path


def main() -> int:
    dry = "--dry-run" in sys.argv
    probe = "--probe" in sys.argv
    notation_only = "--notation-only" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    slug_filter = None
    if "--slug" in sys.argv:
        slug_filter = sys.argv[sys.argv.index("--slug") + 1]
    if notation_only:
        # Re-read the final plates only. No generation, no re-crop: this is the gate's second
        # lens over art that already exists, recorded beside the OCR result in provenance.
        for slug in TOPICS:
            if slug_filter and slug != slug_filter:
                continue
            folder = OUT / slug
            provenance = json.loads((folder / "provenance.json").read_text(encoding="utf-8"))
            for row in provenance["plates"]:
                check = notation_check(Path(row["file"]))
                row["notation"] = check
                print(
                    f"{slug}/{Path(row['file']).name}: notation={check['verdict']}"
                    f" ocr_words={len(row['ocr'].get('words') or [])}"
                )
            (folder / "provenance.json").write_text(
                json.dumps(provenance, indent=2), encoding="utf-8"
            )
        print("notation check complete")
        return 0
    if "--summary-only" in sys.argv:
        # Rebuild SUMMARY.json from the provenances already on disk. No provider call.
        manifest = []
        for slug in TOPICS:
            provenance = json.loads(
                (OUT / slug / "provenance.json").read_text(encoding="utf-8")
            )
            manifest.append(
                summary_entry(
                    slug,
                    provenance["grammar"],
                    provenance["plates"],
                    Path(provenance["contact_sheet"]),
                )
            )
        (OUT / "SUMMARY.json").write_text(
            json.dumps({"card": "CP-016", "topics": manifest}, indent=2), encoding="utf-8"
        )
        print(json.dumps(manifest, indent=2))
        return 0
    if probe:
        slug = slug_filter or "technical-brake-bleed"
        brief, grammar, prompts = plan_for(slug)
        hero = next(item for item in prompts if item.role == "hero")
        folder = OUT / "probe"
        folder.mkdir(parents=True, exist_ok=True)
        model = None
        if "--model" in sys.argv:
            model = sys.argv[sys.argv.index("--model") + 1]
        url = provider_generate(hero.prompt, hero.aspect_ratio, model)
        path = folder / "probe-hero.png"
        data = download(url, path)
        check = ocr(path)
        print("PROBE", url, len(data), "bytes", "ocr_letters", check["letters"])
        print(json.dumps(hero.as_dict(), indent=2))
        return 0
    summary = []
    if "--repair" in sys.argv:
        hard = (
            " This is a repair attempt: leave every surface completely blank; do not invent any "
            "mark that resembles writing, letters or symbols anywhere in the image. Light is "
            "strictly from the upper left; every shadow falls to the lower right. Paint every "
            "swatch, card and sign blank, with no codes, labels or lettering on any object."
        )
        if "--harden-file" in sys.argv:
            harden = Path(sys.argv[sys.argv.index("--harden-file") + 1]).read_text(
                encoding="utf-8"
            ).strip()
            if harden:
                hard = f"{hard} {harden}"
        # ``--only`` may repeat: one pass regenerates every plate whose prompt or pictured
        # content failed a gate, and nothing else.
        only: list[str] = [
            sys.argv[index + 1]
            for index, token in enumerate(sys.argv)
            if token == "--only" and index + 1 < len(sys.argv)
        ]
        repair_round = 2
        if "--round" in sys.argv:
            repair_round = int(sys.argv[sys.argv.index("--round") + 1])
        manifest = []
        for slug in TOPICS:
            brief, grammar, prompts = plan_for(slug)
            folder = OUT / slug
            provenance = json.loads((folder / "provenance.json").read_text(encoding="utf-8"))
            lookup = {(item.role, item.section_id): item for item in prompts}
            for row in provenance["plates"]:
                forced = bool(only) and any(token in row["file"] for token in only)
                # With an explicit --only list, nothing else is re-rendered — the spend guard:
                # only the frames whose prompt or pictured content failed a gate.
                if only and not forced:
                    continue
                if not only and not row["ocr"]["words"]:
                    continue
                prompt = lookup[(row["role"], row["section_id"])]
                path = Path(row["file"])
                edit = "--edit" in sys.argv
                if edit:
                    url = provider_edit(
                        prompt.prompt + hard, prompt.aspect_ratio, path, PROOF_MODEL
                    )
                else:
                    url = provider_generate(
                        prompt.prompt + hard, prompt.aspect_ratio, PROOF_MODEL
                    )
                data = download(url, path)
                if url.startswith("data:"):
                    source = {
                        "kind": "inline_data_url",
                        "sha256": "sha256:" + hashlib.sha256(url.encode()).hexdigest(),
                    }
                else:
                    source = {"kind": "url", "url": url}
                row.update(
                    {
                        "prompt_hash": prompt.prompt_hash,
                        "prompt_version": prompt.prompt_version,
                        "prompt": prompt.prompt,
                        "negative_prompt": prompt.negative_prompt,
                        "medium": prompt.medium,
                        "light": prompt.light,
                        "palette": list(prompt.palette),
                        "provider_media": source,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "bytes": len(data),
                        "ocr": ocr(path),
                        "notation": notation_check(path),
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "repair_round": repair_round,
                        "repair_method": "edit" if edit else "regenerate",
                    }
                )
                print(
                    f"repaired {slug}/{path.name} words={row['ocr']['words']}"
                    f" notation={row['notation']['verdict']}"
                )
            sheet = contact_sheet(slug, provenance["plates"])
            provenance["contact_sheet"] = str(sheet)
            (folder / "provenance.json").write_text(
                json.dumps(provenance, indent=2), encoding="utf-8"
            )
            manifest.append(summary_entry(slug, grammar, provenance["plates"], sheet))
        (OUT / "SUMMARY.json").write_text(
            json.dumps({"card": "CP-016", "topics": manifest}, indent=2), encoding="utf-8"
        )
        print("repair complete")
        return 0
    for slug in TOPICS:
        brief, grammar, prompts = plan_for(slug)
        folder = OUT / slug
        folder.mkdir(parents=True, exist_ok=True)
        print(f"\n== {slug}: grammar={grammar} plates={len(prompts)}")
        rows = []
        for index, prompt in enumerate(prompts, start=1):
            name = (
                f"{index:02d}-{prompt.role}"
                + (f"-{prompt.section_id}" if prompt.section_id else "")
                + f"-{prompt.style_id.split('--')[-1]}.png"
            )
            print(
                f"  {name}  aspect={prompt.aspect_ratio} host={HOST_ASPECT[prompt.aspect_ratio]}"
                f"  hash={prompt.prompt_hash[7:19]}"
            )
            if dry:
                continue
            url = provider_generate(prompt.prompt, prompt.aspect_ratio, PROOF_MODEL)
            data = download(url, folder / name)
            if url.startswith("data:"):
                source = {
                    "kind": "inline_data_url",
                    "sha256": "sha256:" + hashlib.sha256(url.encode()).hexdigest(),
                }
            else:
                source = {"kind": "url", "url": url}
            row = {
                "file": str(folder / name),
                "role": prompt.role,
                "section_id": prompt.section_id,
                "style_id": prompt.style_id,
                "aspect_ratio": prompt.aspect_ratio,
                "host_aspect_ratio": HOST_ASPECT[prompt.aspect_ratio],
                "prompt_hash": prompt.prompt_hash,
                "prompt_version": prompt.prompt_version,
                "prompt": prompt.prompt,
                "negative_prompt": prompt.negative_prompt,
                "medium": prompt.medium,
                "light": prompt.light,
                "palette": list(prompt.palette),
                "provider": PROVIDER,
                "model": PROOF_MODEL,
                "provider_media": source,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "ocr": ocr(folder / name),
                "notation": notation_check(folder / name),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            rows.append(row)
            print(f"    {len(data)} bytes  {row['sha256'][:16]}  ocr_letters={row['ocr']['letters']}")

        if dry:
            continue
        sheet = contact_sheet(slug, rows)
        provenance = {
            "card": "CP-016",
            "topic": brief.title,
            "brief": brief.as_dict(),
            "grammar": grammar,
            "prompt_version": world.PROMPT_VERSION,
            "style_selection": {
                "style_id": prompts[0].style_id,
                "rule": "deterministic authored direction; the World Studio owner-approval gate "
                        "is review, not asserted by this proof",
            },
            "provider": PROVIDER,
            "plates": rows,
            "contact_sheet": str(sheet),
        }
        (folder / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
        summary.append(
            summary_entry(slug, grammar, rows, sheet)
        )

    if not dry:
        (OUT / "SUMMARY.json").write_text(
            json.dumps({"card": "CP-016", "topics": summary}, indent=2), encoding="utf-8"
        )
        print("\nWrote", OUT / "SUMMARY.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
