"""Take-home print documents: content fixtures, HTML layout and PDF rendering.

This module is the *content and print proof* seam for GM-014. It does not queue jobs, write
evidence, enroll anybody or send anything. It owns three things:

* a source-bound Japanese L0 fixture (``bundled/homework/japanese-l0-mealtime/fixture.json``),
* a designed HTML template per print role — parent guide, learner page, answer guide and
  one-page homework — for A4 and Letter,
* a Chromium print path that produces selectable-text PDFs plus a deterministic technical
  one-pager for a procedure lesson.

Design constraints, all enforced by ``tests/test_homework_content_print.py``:

* **Low ink.** White paper, near-black ink, hairline rules. No filled colour panels and no
  meaning carried by colour alone: every state and answer label is a word.
* **Selectable text.** PDFs come from HTML printed by Chromium, not from an image. Japanese runs
  in Noto Sans CJK JP and is embedded as text.
* **Real pages.** Each page is an explicit sheet with fixed paper dimensions, generous margins
  and a printed ``Page n of N`` folio, so nothing depends on a running header the engine may
  drop.
* **No answer key on a learner page.** The answer guide is a separate document with its own
  parent-only marking.
* **No invented Japanese.** Every phrase, reading, romaji and gloss in the fixture comes from a
  cited entry recorded in the fixture's ``sources`` ledger; the lesson hash binds the tasks to
  the exact lesson text that was checked.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

#: Repo-root-relative fixture directory for the demo Japanese pack.
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "bundled" / "homework" / "japanese-l0-mealtime"
FIXTURE_PATH = FIXTURE_DIR / "fixture.json"

#: Paper sizes in CSS units, used for both ``@page`` and the sheet box.
PAPER_SIZES: dict[str, dict[str, str]] = {
    "A4": {"size": "A4", "width": "210mm", "height": "297mm", "pad": "18mm 16mm 16mm"},
    "Letter": {"size": "Letter", "width": "8.5in", "height": "11in", "pad": "0.7in 0.65in 0.62in"},
}

#: Task kinds the fixture and print templates accept (plan §10A.4).
TASK_KINDS = ("real_world_use", "observe", "label", "practice", "make", "teach_back")

#: Completion states a printed sheet may record. Never a grade or a pass.
COMPLETION_STATES = ("self_reported", "parent_reported")

#: Learner-visible words that would turn practice into grading or surrender data.
FORBIDDEN_LEARNER_WORDS = (
    "grade",
    "graded",
    "score",
    "scored",
    "xp",
    "mastery",
    "streak",
    "photo",
    "photograph",
    "geolocation",
    "location data",
)


# ── content fixture ────────────────────────────────────────────────────────


def load_fixture(path: str | Path | None = None) -> dict[str, Any]:
    """Load the Japanese L0 fixture and attach its computed lesson binding."""
    source = Path(path) if path is not None else FIXTURE_PATH
    data = json.loads(source.read_text(encoding="utf-8"))
    data["binding"] = binding(data)
    return data


def canonical_lesson(lesson: Mapping[str, Any]) -> str:
    """Canonical JSON for the lesson block; this is what the lesson hash covers."""
    return json.dumps(lesson, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def lesson_hash(lesson: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_lesson(lesson).encode("utf-8")).hexdigest()


def binding(fixture: Mapping[str, Any]) -> dict[str, str]:
    """The four fields a pack binds to its source lesson (plan §10A.2)."""
    lesson = fixture["lesson"]
    return {
        "source_course_id": lesson["source_course_id"],
        "source_objective_id": lesson["source_objective_id"],
        "source_lesson_version": lesson["source_lesson_version"],
        "source_lesson_hash": lesson_hash(lesson),
    }


def target_index(fixture: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for target in fixture["lesson"]["targets"]:
        index[target["target_id"]] = dict(target, kind="phrase")
    for group in fixture.get("target_sets") or []:
        index[group["target_id"]] = dict(group, kind=group.get("kind", "label_set"))
    return index


def label_index(fixture: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {label["label_id"]: label for label in fixture["lesson"]["labels"]}


def source_index(fixture: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {source["source_id"]: source for source in fixture["lesson"]["sources"]}


def task_by_id(fixture: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    for task in fixture["tasks"]:
        if task["task_id"] == task_id:
            return task
    raise KeyError(f"unknown task id: {task_id}")


def validate_fixture(fixture: Mapping[str, Any]) -> list[str]:
    """Return every content-rule problem; an empty list means the fixture is printable.

    These are the content rules from plan §10A.4 and the GM-014 card, expressed once so the
    tests, the proof script and any downstream caller agree.
    """
    problems: list[str] = []
    lesson = fixture.get("lesson") or {}
    sources = source_index(fixture)
    labels = label_index(fixture)
    targets = target_index(fixture)

    for key in ("source_course_id", "source_objective_id", "source_lesson_version", "title", "level"):
        if not str(lesson.get(key) or "").strip():
            problems.append(f"lesson.{key} is empty")

    if not sources:
        problems.append("lesson.sources is empty; content is not source-bound")

    for source in sources.values():
        if not str(source.get("url") or "").startswith("https://"):
            problems.append(f"source {source.get('source_id')} has no https URL")
        if not str(source.get("accessed") or "").strip():
            problems.append(f"source {source.get('source_id')} has no access date")
        if not str(source.get("quote") or "").strip():
            problems.append(f"source {source.get('source_id')} records no supporting quote")

    for target in lesson.get("targets") or []:
        for key in ("display", "reading", "romaji", "meaning", "register", "use"):
            if not str(target.get(key) or "").strip():
                problems.append(f"target {target.get('target_id')} has no {key}")
        if target.get("reading") != target.get("display"):
            problems.append(
                f"target {target.get('target_id')} reading does not match the printed form"
            )
        for source_id in target.get("source_ids") or []:
            if source_id not in sources:
                problems.append(f"target {target.get('target_id')} cites unknown source {source_id}")
        if not target.get("source_ids"):
            problems.append(f"target {target.get('target_id')} cites no source")

    for label in lesson.get("labels") or []:
        for key in ("display", "reading", "romaji", "meaning"):
            if not str(label.get(key) or "").strip():
                problems.append(f"label {label.get('label_id')} has no {key}")
        for source_id in label.get("source_ids") or []:
            if source_id not in sources:
                problems.append(f"label {label.get('label_id')} cites unknown source {source_id}")
        if not label.get("source_ids"):
            problems.append(f"label {label.get('label_id')} cites no source")

    if not fixture.get("tasks"):
        problems.append("fixture has no tasks")

    for task in fixture.get("tasks") or []:
        task_id = task.get("task_id") or "<no id>"
        if task.get("task_kind") not in TASK_KINDS:
            problems.append(f"{task_id}: task_kind {task.get('task_kind')!r} is not allowed")
        if task.get("audience") not in ("learner", "parent"):
            problems.append(f"{task_id}: audience must be learner or parent")
        if not str(task.get("title") or "").strip():
            problems.append(f"{task_id}: title is empty")
        if task.get("target_id") not in targets:
            problems.append(f"{task_id}: target_id {task.get('target_id')!r} is unknown")
        context = task.get("context")
        if not isinstance(context, str) or not context.strip():
            problems.append(f"{task_id}: exactly one context sentence is required")
        elif "\n" in context:
            problems.append(f"{task_id}: context must be one sentence, not a paragraph")
        steps = task.get("steps") or []
        if not (1 <= len(steps) <= 3):
            problems.append(f"{task_id}: steps must be between one and three")
        for step in steps:
            if not str(step or "").strip():
                problems.append(f"{task_id}: a step is empty")
        criterion = task.get("success_criterion")
        if not isinstance(criterion, str) or not criterion.strip():
            problems.append(f"{task_id}: exactly one success criterion is required")
        minutes = task.get("estimated_minutes")
        if not isinstance(minutes, int) or not (3 <= minutes <= 10):
            problems.append(f"{task_id}: estimated_minutes must be an integer from 3 to 10")
        if task.get("completion") not in COMPLETION_STATES:
            problems.append(f"{task_id}: completion must be self_reported or parent_reported")

        learner_text = " ".join(
            [str(task.get("title") or ""), str(context or ""), *[str(s) for s in steps], str(criterion or "")]
        ).lower()
        for word in FORBIDDEN_LEARNER_WORDS:
            if re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", learner_text):
                problems.append(f"{task_id}: learner text contains forbidden word {word!r}")
        if "answer" in learner_text:
            problems.append(f"{task_id}: learner text mentions an answer")

        target = targets.get(task.get("target_id"))
        if target and target.get("kind") == "label_set":
            chosen = target.get("label_ids") or []
            if not (1 <= len(chosen) <= 3):
                problems.append(f"{task_id}: a label task must choose one to three labels")
            for label_id in chosen:
                if label_id not in labels:
                    problems.append(f"{task_id}: label set cites unknown label {label_id}")
        elif target and target.get("kind") == "phrase":
            if not target.get("source_ids"):
                problems.append(f"{task_id}: phrase target is not source-bound")

    checklist = fixture.get("checklist") or {}
    for key in ("generic_task", "surveillance", "grade", "xp", "external_send"):
        if checklist.get(key) is not False:
            problems.append(f"checklist.{key} must be false")
    for key in ("one_target", "one_context", "one_success_criterion"):
        if checklist.get(key) is not True:
            problems.append(f"checklist.{key} must be true")

    return problems


# ── HTML ───────────────────────────────────────────────────────────────────

_CSS = """
@page {{ size: {size}; margin: 0; }}
* {{ box-sizing: border-box; }}
html {{ background: #ffffff; }}
body {{
  margin: 0;
  padding: 0;
  background: #ffffff;
  color: #1a1713;
  font-family: "Noto Serif", "Iowan Old Style", Georgia, "Times New Roman", serif;
  font-size: 10.5pt;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
}}
.sheet {{
  position: relative;
  width: {width};
  height: {height};
  padding: {pad};
  background: #ffffff;
  overflow: hidden;
  break-after: page;
  page-break-after: always;
}}
.sheet:last-child {{ break-after: auto; page-break-after: auto; }}
.masthead {{ border-top: 3pt solid #1a1713; padding-top: 3mm; margin-bottom: 7mm; }}
.eyebrow {{
  font-family: "Noto Sans", "Helvetica Neue", Arial, sans-serif;
  font-size: 8pt;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #5c5347;
}}
h1 {{ font-size: 21pt; line-height: 1.15; margin: 2.5mm 0 1.5mm; font-weight: 600; }}
h2 {{ font-size: 13pt; margin: 5.5mm 0 1.8mm; font-weight: 600; border-bottom: 0.75pt solid #d7cbb4; padding-bottom: 1.2mm; }}
h3 {{ font-size: 10.5pt; margin: 4mm 0 1mm; font-weight: 600; }}
p {{ margin: 0 0 2.4mm; }}
ul, ol {{ margin: 0 0 2.4mm; padding-left: 5.5mm; }}
li {{ margin-bottom: 1.2mm; }}
.jp {{
  font-family: "Noto Sans CJK JP", "Noto Sans JP", "Hiragino Sans", "Yu Gothic", "MS Gothic", sans-serif;
  font-feature-settings: "palt" 1;
}}
.target-field {{
  border: 1.5pt solid #1a1713;
  padding: 5mm 5mm 4mm;
  margin: 4mm 0 5mm;
  background: #ffffff;
}}
.target-display {{ font-size: 30pt; line-height: 1.25; margin: 0 0 1mm; }}
.target-reading {{ font-size: 13pt; color: #1a1713; margin: 0 0 1mm; }}
.target-romaji {{ font-style: italic; font-size: 12pt; margin: 0 0 1.5mm; }}
.target-meaning {{ font-size: 10pt; color: #5c5347; margin: 0; }}
.fact-row {{ display: flex; gap: 6mm; margin: 0 0 3mm; font-size: 9.5pt; color: #5c5347; }}
.fact-row strong {{ color: #1a1713; font-weight: 600; }}
.step-list li {{ margin-bottom: 2mm; }}
.criterion {{ border-left: 3pt solid #1a1713; padding: 1.5mm 0 1.5mm 4mm; margin: 5mm 0; }}
.criterion .eyebrow {{ display: block; margin-bottom: 1mm; }}
.completion {{ border-top: 0.75pt solid #1a1713; margin-top: 7mm; padding-top: 3mm; font-size: 9.5pt; }}
.completion .line {{ display: inline-block; min-width: 42mm; border-bottom: 0.75pt solid #1a1713; }}
.answer-band {{
  border: 2pt solid #1a1713;
  padding: 3mm 4mm;
  margin: 0 0 6mm;
  background: #ffffff;
}}
.answer-band .marker {{ font-family: "Noto Sans", Arial, sans-serif; font-size: 11pt; font-weight: 700; letter-spacing: 0.12em; }}
.answer-band p {{ margin: 1.5mm 0 0; font-size: 9.5pt; color: #5c5347; }}
.quiet {{ color: #4a443a; font-size: 9pt; }}
.fact-table {{ width: 100%; border-collapse: collapse; margin: 0 0 4mm; font-size: 9.5pt; }}
.fact-table th, .fact-table td {{ text-align: left; padding: 1.2mm 2mm 1.2mm 0; border-bottom: 0.5pt solid #d7cbb4; }}
.fact-table th {{ width: 18%; font-weight: 600; color: #5c5347; }}
.fact-table td {{ width: 32%; }}
.checkbox {{ font-family: "Noto Sans", Arial, sans-serif; font-size: 13pt; line-height: 1; }}
table.facts {{ width: 100%; table-layout: fixed; border-collapse: collapse; border-top: 0.75pt solid #1a1713; border-bottom: 0.75pt solid #1a1713; margin: 2mm 0 4mm; font-size: 9.5pt; }}
table.facts th, table.facts td {{ text-align: left; vertical-align: top; padding: 1.6mm 2mm; border-bottom: 0.5pt solid #d7cbb4; }}
table.facts th {{ width: 34mm; white-space: normal; padding-right: 4mm; font-weight: 600; }}
figure {{ margin: 4mm 0; }}
figure svg {{ display: block; width: 100%; max-height: 34mm; }}
figcaption {{ font-size: 8.5pt; color: #5c5347; margin-top: 1.5mm; }}
.source-list {{ font-size: 8.5pt; color: #5c5347; }}
.source-list li {{ margin-bottom: 1.4mm; }}
.hash {{ font-family: "Noto Sans Mono", "DejaVu Sans Mono", monospace; font-size: 8pt; word-break: break-all; }}
.folio {{
  position: absolute;
  left: {pad_left};
  right: {pad_right};
  bottom: 9mm;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-top: 0.5pt solid #d7cbb4;
  padding-top: 2mm;
  font-family: "Noto Sans", Arial, sans-serif;
  font-size: 8.5pt;
  color: #4a443a;
}}
.tech-step {{ border-top: 0.75pt solid #d7cbb4; padding-top: 2mm; margin-top: 2mm; }}
.tech-step .check {{ font-size: 9pt; color: #1a1713; }}
@media screen {{
  body {{ background: #ece7dc; }}
  .sheet {{ margin: 6mm auto; box-shadow: 0 1px 6px rgba(26, 23, 19, 0.18); }}
}}
"""


def _css(paper: str) -> str:
    spec = PAPER_SIZES[paper]
    horizontal_pad = spec["pad"].split()[1]
    return _CSS.format(
        size=spec["size"],
        width=spec["width"],
        height=spec["height"],
        pad=spec["pad"],
        pad_left=horizontal_pad,
        pad_right=horizontal_pad,
    )


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _page(body: str, *, role: str, paper: str, index: int, total: int, running: str) -> str:
    return (
        f'<section class="sheet" data-role="{_esc(role)}" data-page="{index}" data-paper="{_esc(paper)}">'
        f"{body}"
        f'<footer class="folio"><span>{_esc(running)}</span>'
        f"<span>Page {index} of {total}</span></footer>"
        f"</section>"
    )


def document_html(pages: Sequence[str], *, title: str, paper: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        f"<title>{_esc(title)}</title>"
        '<meta name="generator" content="coursebook-homework-print">'
        f"<style>{_css(paper)}</style></head><body>"
        + "".join(pages)
        + "</body></html>\n"
    )


def _masthead(eyebrow: str, title: str, deck: str = "") -> str:
    deck_html = f"<p>{_esc(deck)}</p>" if deck else ""
    return (
        '<header class="masthead">'
        f'<div class="eyebrow">{_esc(eyebrow)}</div>'
        f"<h1>{_esc(title)}</h1>"
        f"{deck_html}"
        "</header>"
    )


def _target_field(target: Mapping[str, Any]) -> str:
    return (
        '<div class="target-field">'
        f'<p class="target-display jp">{_esc(target["display"])}</p>'
        f'<p class="target-reading jp">{_esc(target["reading"])}</p>'
        f'<p class="target-romaji">{_esc(target["romaji"])}</p>'
        f'<p class="target-meaning">{_esc(target["meaning"])}</p>'
        "</div>"
    )


def _fact_table(target: Mapping[str, Any]) -> str:
    return (
        '<table class="fact-table"><tr>'
        f"<th>Register</th><td>{_esc(target['register'])}</td>"
        f"<th>When</th><td>{_esc(target['use'])}</td>"
        "</tr></table>"
    )


def _label_table(fixture: Mapping[str, Any], label_ids: Sequence[str]) -> str:
    labels = label_index(fixture)
    rows = "".join(
        "<tr>"
        f'<td class="jp">{_esc(labels[label_id]["display"])}</td>'
        f'<td>{_esc(labels[label_id]["romaji"])}</td>'
        f'<td>{_esc(labels[label_id]["meaning"])}</td>'
        "</tr>"
        for label_id in label_ids
        if label_id in labels
    )
    return (
        '<table class="facts"><thead><tr><th>Word (Japanese)</th><th>Romaji</th><th>Meaning</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def _label_figure() -> str:
    """A deterministic line drawing with alt text and a visible caption.

    The drawing orients three of the lesson's household objects; it states no word, reading or
    procedure, so the lesson text stays the only authority.
    """
    svg = (
        '<svg role="img" aria-labelledby="fig1-title fig1-desc" viewBox="0 0 320 150" '
        'xmlns="http://www.w3.org/2000/svg" fill="none" stroke="#1a1713" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<title id="fig1-title">Line drawing of a door, a window and a chair</title>'
        '<desc id="fig1-desc">A door with a handle on the left, a window with a cross frame in the '
        'middle, and a chair on the right. The drawing is orientation only; it labels nothing.</desc>'
        '<rect x="24" y="26" width="62" height="102" rx="2"/>'
        '<circle cx="74" cy="80" r="2.6"/>'
        '<rect x="126" y="30" width="66" height="60" rx="2"/>'
        '<path d="M159 30v60M126 60h66"/>'
        '<path d="M234 34h44v40h-44zM234 74h44v6h-44zM240 80v28M272 80v28M240 60h38"/>'
        "</svg>"
    )
    return (
        "<figure>"
        f"{svg}"
        '<figcaption id="fig1-caption">Line drawing: a door, a window and a chair. Orientation only — '
        "the drawing states no word and no reading; the lesson words are the content.</figcaption>"
        "</figure>"
    )


def _task_target(fixture: Mapping[str, Any], task: Mapping[str, Any]) -> dict[str, Any]:
    return target_index(fixture)[task["target_id"]]


def _target_display(fixture: Mapping[str, Any], task: Mapping[str, Any]) -> str:
    target = _task_target(fixture, task)
    if target.get("kind") == "label_set":
        labels = label_index(fixture)
        return "・".join(labels[label_id]["display"] for label_id in target.get("label_ids") or [])
    return target.get("display") or target.get("title") or ""


def _task_body(fixture: Mapping[str, Any], task: Mapping[str, Any], *, with_completion: bool) -> str:
    target = _task_target(fixture, task)
    parts: list[str] = [
        _masthead(
            "Japanese · L0 · take-home practice",
            task["title"],
            "One task, one place, one way to know you are done.",
        )
    ]
    if target.get("kind") == "label_set":
        chosen = target.get("label_ids") or []
        parts.append(f'<div class="target-field"><p class="target-display jp">{_esc("・".join(label_index(fixture)[i]["display"] for i in chosen))}</p><p class="target-meaning">Three of the six lesson labels; any three are acceptable.</p></div>')
        parts.append(_label_table(fixture, chosen))
        parts.append(_label_figure())
    else:
        parts.append(_target_field(target))
        parts.append(_fact_table(target))

    parts.append("<h2>Where and when</h2>")
    parts.append(f"<p>{_esc(task['context'])}</p>")
    parts.append("<h2>Do this</h2>")
    steps = "".join(f"<li>{_esc(step)}</li>" for step in task["steps"])
    parts.append(f'<ol class="step-list">{steps}</ol>')
    parts.append(
        '<div class="criterion"><span class="eyebrow">You are done when</span>'
        f"<p>{_esc(task['success_criterion'])}</p></div>"
    )
    parts.append(
        f'<p class="quiet">About {int(task["estimated_minutes"])} minutes. '
        "No photo, no recording, no location, no score. Ask for the phrase, not a grade.</p>"
    )
    if with_completion:
        parts.append(
            '<div class="completion">'
            "<p><strong>Done when:</strong> <span class=\"checkbox\">☐</span> breakfast &nbsp; "
            "<span class=\"checkbox\">☐</span> lunch &nbsp; <span class=\"checkbox\">☐</span> dinner "
            "&nbsp;&nbsp; <strong>Date</strong> <span class=\"line\">&nbsp;</span></p>"
            f'<p class="quiet">Completion is {_esc(task["completion"].replace("_", " "))} and stays in your notebook. '
            "It is not a pass, a score or evidence of mastery.</p>"
            "</div>"
        )
    return "".join(parts)


def _learner_page(fixture: Mapping[str, Any], task: Mapping[str, Any], paper: str) -> str:
    body = _task_body(fixture, task, with_completion=True)
    total = 1
    return _page(body, role="learner-page", paper=paper, index=1, total=total, running="Coursebook · learner page")


def _homework_sheet(fixture: Mapping[str, Any], task: Mapping[str, Any], paper: str) -> str:
    target = _task_target(fixture, task)
    parts = [
        _masthead("Coursebook · one-page homework", task["title"], "Take this page with you."),
    ]
    if target.get("kind") == "label_set":
        chosen = target.get("label_ids") or []
        parts.append("<h2>Words for this task</h2>")
        parts.append(
            f'<p class="target-display jp">{_esc(_target_display(fixture, task))}</p>'
        )
        parts.append('<p class="target-meaning">Three of the six lesson labels; any three are acceptable.</p>')
        parts.append(_label_table(fixture, chosen))
    else:
        parts.append(_target_field(target))
    parts.append("<h2>Where and when</h2>")
    parts.append(f"<p>{_esc(task['context'])}</p>")
    parts.append("<h2>Do this</h2>")
    parts.append(
        '<ol class="step-list">'
        + "".join(f"<li>{_esc(step)}</li>" for step in task["steps"])
        + "</ol>"
    )
    parts.append(
        '<div class="criterion"><span class="eyebrow">You are done when</span>'
        f"<p>{_esc(task['success_criterion'])}</p></div>"
    )
    parts.append(
        '<div class="completion">'
        f'<p><strong>About {int(task["estimated_minutes"])} minutes.</strong> '
        '<span class="checkbox">☐</span> breakfast &nbsp; <span class="checkbox">☐</span> lunch &nbsp; '
        '<span class="checkbox">☐</span> dinner &nbsp;&nbsp; <strong>Date</strong> '
        '<span class="line">&nbsp;</span></p>'
        '<p class="quiet">Mark done or skipped when you finish. This records what you did. It is not a grade. '
        "No photo, recording or location is asked for.</p>"
        "</div>"
    )
    return _page(
        "".join(parts), role="homework-sheet", paper=paper, index=1, total=1, running="Coursebook · homework sheet"
    )


def _parent_guide(fixture: Mapping[str, Any], task: Mapping[str, Any], paper: str) -> str:
    lesson = fixture["lesson"]
    target = _task_target(fixture, task)
    hash_value = binding(fixture)["source_lesson_hash"]
    total = 2

    page_one = [
        _masthead("Coursebook · take-home pack · parent guide", "How to use this pack"),
        "<p>This is a printed practice card, not a lesson and not a test. You read it with the learner, "
        "the learner does one small task away from the screen, and you write down only what happened.</p>",
        "<h2>The pack</h2>",
        '<table class="facts">'
        f"<tr><th>Task</th><td>{_esc(task['title'])}</td></tr>"
        f"<tr><th>Target</th><td class=\"jp\">{_esc(_target_display(fixture, task))}</td></tr>"
        f"<tr><th>Context</th><td>{_esc(task['context'])}</td></tr>"
        f"<tr><th>Minutes</th><td>{int(task['estimated_minutes'])}</td></tr>"
        f"<tr><th>Completion</th><td>{_esc(task['completion'].replace('_', ' '))} only</td></tr>"
        "</table>",
        "<h2>The four steps</h2>",
        "<ol>"
        "<li><strong>Read the learner page together once.</strong> Point at the phrase and say it slowly. "
        "The learner repeats it once; that is the whole preparation.</li>"
        "<li><strong>Send the learner to the task.</strong> The context on the card says where and when. "
        "Do not stand over the learner.</li>"
        "<li><strong>Ask for the phrase, not a grade.</strong> When the learner comes back, ask them to say "
        "the phrase again. Then write the date on the card.</li>"
        "<li><strong>Record done or skipped honestly.</strong> A skipped task is a normal week, not a failure. "
        "Nothing is sent anywhere and no score is produced.</li>"
        "</ol>",
        "<h2>Materials and preparation</h2>",
        f"<p>{_esc(_materials(task, target))}</p>",
        "<h2>Printing</h2>",
        "<p class=\"quiet\">Print in black and white at 100%. Both A4 and Letter layouts are produced by the same "
        "template; the folio at the foot of each page prints the page number.</p>",
    ]

    sources = "".join(
        f"<li>{_esc(source['title'])} — <span class=\"hash\">{_esc(source['url'])}</span> "
        f"(accessed {_esc(source['accessed'])}): {_esc(source['quote'])}</li>"
        for source in lesson["sources"]
        if source["source_id"] in _task_source_ids(fixture, task)
    )
    page_two = [
        _masthead("Coursebook · parent guide · page two", "What to notice, and where the words come from"),
        "<h2>What to notice</h2>",
        "<ul>"
        "<li>Did the learner say the phrase out loud, at the table, without reading it off the card?</li>"
        "<li>Did they choose the right moment — before eating for the before-meal phrase, after finishing "
        "for the after-meal phrase?</li>"
        "<li>Romaji is a scaffold. If the learner still needs it, that is expected at L0.</li>"
        "<li>If the learner is uncomfortable saying it aloud in front of others, let them say it quietly. "
        "Do not turn the task into a performance.</li>"
        "</ul>",
        "<h2>Expected responses and next step</h2>",
        f"<p><strong>Expected:</strong> {_esc(_expected_response(fixture, task))}</p>",
        "<p><strong>Common errors:</strong> saying the before-meal phrase after eating, or dropping the polite "
        "ending. Correct once, calmly, and move on.</p>",
        "<p><strong>Next step:</strong> repeat the same task at a different meal this week, or take the other "
        "mealtime greeting from the same lesson. Do not add a second task to this sheet.</p>",
        "<h2>Sources for this task</h2>",
        f'<ul class="source-list">{sources}</ul>',
        "<p class=\"quiet\">The fixture records each phrase, reading, romaji and gloss against the entries "
        "above. No culture claim is made beyond the cited use note.</p>",
        "<h2>Source lesson binding</h2>",
        '<table class="facts">'
        f"<tr><th>Course</th><td class=\"hash\">{_esc(binding(fixture)['source_course_id'])}</td></tr>"
        f"<tr><th>Objective</th><td class=\"hash\">{_esc(binding(fixture)['source_objective_id'])}</td></tr>"
        f"<tr><th>Lesson version</th><td class=\"hash\">{_esc(binding(fixture)['source_lesson_version'])}</td></tr>"
        f"<tr><th>Lesson hash</th><td class=\"hash\">{_esc(hash_value)}</td></tr>"
        "</table>",
        "<p class=\"quiet\">This pack prints the lesson's exact words. It does not regenerate the lesson, "
        "clone the course or touch its evidence.</p>",
    ]
    pages = [
        _page("".join(page_one), role="parent-guide", paper=paper, index=1, total=total, running="Coursebook · parent guide"),
        _page("".join(page_two), role="parent-guide", paper=paper, index=2, total=total, running="Coursebook · parent guide"),
    ]
    return "".join(pages)


def _materials(task: Mapping[str, Any], target: Mapping[str, Any]) -> str:
    if target.get("kind") == "label_set":
        return "Paper or sticky labels, a pen, and the three household objects named on the learner page."
    return "Nothing. The card, a table and a meal you were going to eat anyway."


def _task_source_ids(fixture: Mapping[str, Any], task: Mapping[str, Any]) -> set[str]:
    target = _task_target(fixture, task)
    if target.get("kind") == "label_set":
        labels = label_index(fixture)
        ids: set[str] = set()
        for label_id in target.get("label_ids") or []:
            ids.update(labels[label_id].get("source_ids") or [])
        return ids
    return set(target.get("source_ids") or [])


def _expected_response(fixture: Mapping[str, Any], task: Mapping[str, Any]) -> str:
    target = _task_target(fixture, task)
    if target.get("kind") == "label_set":
        labels = label_index(fixture)
        return "; ".join(
            f"{labels[label_id]['display']} ({labels[label_id]['romaji']}) — {labels[label_id]['meaning']}"
            for label_id in target.get("label_ids") or []
        )
    return (
        f"{target['display']} ({target['reading']} · {target['romaji']}) — {target['meaning']}. "
        f"Register: {target['register']}; used {target['use']}."
    )


def _answer_guide(fixture: Mapping[str, Any], task: Mapping[str, Any], paper: str) -> str:
    target = _task_target(fixture, task)
    parts = [
        '<div class="answer-band"><div class="marker">PARENT ONLY · ANSWER GUIDE</div>'
        "<p>Do not give this page to the learner. It is a separate document from the learner page.</p></div>",
        _masthead("Coursebook · take-home pack · answer guide", task["title"]),
        "<h2>The target</h2>",
    ]
    if target.get("kind") == "label_set":
        parts.append(_label_table(fixture, target.get("label_ids") or []))
    else:
        parts.append(_target_field(target))
        parts.append(_fact_table(target))
    parts.append("<h2>Expected responses</h2>")
    if target.get("kind") == "label_set":
        parts.append("<p>The learner says each label aloud when passing the object, for two days. Any three of the six lesson labels are equally correct.</p>")
    else:
        parts.append(
            f"<p>The learner says <span class=\"jp\">{_esc(target['display'])}</span> "
            f"({_esc(target['romaji'])}) out loud at the moment named on the sheet. A quiet, correct use counts. "
            "Reading it off the card does not meet the success criterion.</p>"
        )
    parts.append("<h2>Common errors</h2>")
    parts.append(
        "<ul><li>Using the before-meal phrase after the meal, or the reverse.</li>"
        "<li>Dropping the polite ending: keeping the plain family form is a different lesson.</li>"
        "<li>Saying it to the learner's own plate rather than at the table is fine; saying it only in their head is not.</li></ul>"
    )
    parts.append("<h2>Next step</h2>")
    parts.append(
        "<p>Repeat at one other meal this week. If the learner is ready, ask them to say it first and you answer. "
        "No grade, score or XP is recorded here.</p>"
    )
    parts.append(
        '<p class="quiet">Completion is written as self-reported or parent-reported only. '
        "It is never a pass, a mastery claim or evidence of learning.</p>"
    )
    return _page("".join(parts), role="answer-guide", paper=paper, index=1, total=1, running="Coursebook · parent-only answer guide")


def render_documents(
    fixture: Mapping[str, Any], task_id: str, *, paper: str = "A4"
) -> dict[str, str]:
    """Render the four print roles for one homework task.

    Keys: ``parent_guide``, ``learner_page``, ``answer_guide``, ``homework_sheet``. Each value is
    a complete HTML document with explicit pages; ``answer_guide`` is parent-only.
    """
    if paper not in PAPER_SIZES:
        raise ValueError(f"paper must be one of {sorted(PAPER_SIZES)}")
    task = task_by_id(fixture, task_id)
    lesson = fixture["lesson"]
    pack_title = f"{lesson['title']} — {task['title']}"
    return {
        "parent_guide": document_html(
            [_parent_guide(fixture, task, paper)], title=f"{pack_title} — parent guide", paper=paper
        ),
        "learner_page": document_html(
            [_learner_page(fixture, task, paper)], title=f"{pack_title} — learner page", paper=paper
        ),
        "answer_guide": document_html(
            [_answer_guide(fixture, task, paper)], title=f"{pack_title} — parent-only answer guide", paper=paper
        ),
        "homework_sheet": document_html(
            [_homework_sheet(fixture, task, paper)], title=f"{pack_title} — one-page homework", paper=paper
        ),
    }


# ── technical one-pager ────────────────────────────────────────────────────


def render_technical_document(document: Mapping[str, Any], *, paper: str = "A4") -> str:
    """Render a procedure lesson as one low-ink page with a deterministic schematic.

    The page reproduces the validated lesson document: typed facts, ordered steps, the
    structured schematic rows and the cited source. It never embeds a generated image, so no
    AI illustration can act as a torque or safety authority.
    """
    if paper not in PAPER_SIZES:
        raise ValueError(f"paper must be one of {sorted(PAPER_SIZES)}")
    procedure = document.get("procedure") or {}
    blocks = {block["id"]: block for block in document.get("blocks") or []}
    schematic = procedure.get("schematic") or {}

    parts = [
        _masthead(
            "Technical · procedure · take-home sheet",
            document.get("section_title") or "Procedure",
            "A printed reference, not a substitute for the manufacturer's manual.",
        ),
        "<h2>Before you start</h2>",
        '<table class="facts">'
        f"<tr><th>Tools</th><td>{_esc('; '.join(procedure.get('tools') or []))}</td></tr>"
        f"<tr><th>Parts</th><td>{_esc('; '.join(procedure.get('parts') or []))}</td></tr>"
        "</table>",
        "<h2>Hazards</h2>",
        "<ul>" + "".join(f"<li>{_esc(item)}</li>" for item in procedure.get("hazards") or []) + "</ul>",
        '<div class="criterion"><span class="eyebrow">Stop condition</span>'
        f"<p>{_esc(procedure.get('stop_condition') or '')}</p></div>",
        "<h2>Procedure</h2>",
    ]
    for number, step in enumerate(procedure.get("steps") or [], start=1):
        block = blocks.get(step.get("block_id")) or {}
        check = step.get("check")
        check_html = f'<p class="check"><strong>Check:</strong> {_esc(check)}</p>' if check else ""
        detail = block.get("short") or block.get("deep") or ""
        parts.append(
            '<div class="tech-step">'
            f'<p><strong>{number}. {_esc(block.get("headline") or step.get("block_id"))}</strong></p>'
            f'<p>{_esc(detail)}</p>'
            f"{check_html}</div>"
        )
    page_one = "".join(parts)

    second = [
        _masthead(
            "Technical · procedure · schematic and source",
            "Torque rows and source",
            "Keep this page with page one. The manual remains the authority for the final value.",
        ),
        "<h2>Deterministic schematic</h2>",
        f"<p>{_esc(schematic.get('title') or 'Schematic')}</p>",
    ]
    rows = schematic.get("rows") or []
    rows_html = "".join(
        f"<tr><td>{_esc(row.get('label'))}</td><td>{_esc(row.get('value'))}</td><td>{int(row.get('row', 0))}</td></tr>"
        for row in rows
    )
    second.append(
        '<table class="facts"><thead><tr><th>Fastener</th><th>Value</th><th>Order</th></tr></thead>'
        f"<tbody>{rows_html}</tbody></table>"
    )
    second.append(
        '<p class="quiet">This table is rendered from the lesson\'s structured rows. It is not an '
        "illustration and no generated image appears on this page. The manual page remains the "
        "authority for the final value.</p>"
    )
    source = procedure.get("source") or {}
    second.append(
        f"<p class=\"quiet\">Schematic text equivalent: {_esc(schematic.get('text_equivalent') or '')}</p>"
        f"<p class=\"quiet\">Source: <span class=\"hash\">{_esc(source.get('source_id') or 'unrecorded')}</span> · "
        f"permission: {_esc(source.get('permission') or 'unknown')}</p>"
    )
    second.append("<h2>Before the first start</h2>")
    second.append(
        "<p>Re-check the sequence, confirm every connector is seated, refill coolant, and run the engine "
        "to temperature while watching for leaks. If any step was skipped, stop and do not start the engine.</p>"
    )
    pages = [
        _page(page_one, role="technical-sheet", paper=paper, index=1, total=2, running="Coursebook · technical sheet"),
        _page("".join(second), role="technical-sheet", paper=paper, index=2, total=2, running="Coursebook · technical sheet"),
    ]
    return document_html(pages, title=f"{document.get('section_title') or 'Procedure'} — technical sheet", paper=paper)


# ── page inspection helpers ────────────────────────────────────────────────


def page_count(html_text: str) -> int:
    return len(re.findall(r'<section class="sheet"', html_text))


def learner_visible_text(html_text: str) -> str:
    """Text a learner would read: drop markup, comments and style blocks."""
    text = re.sub(r"<style.*?</style>", " ", html_text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# ── Chromium print path ────────────────────────────────────────────────────


class PrintUnavailable(RuntimeError):
    """No Chromium binary is available, so a real PDF proof cannot be produced."""


def chromium_binary() -> str:
    for name in ("chromium", "chromium-browser", "google-chrome-stable", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise PrintUnavailable("no Chromium binary found on PATH")


def write_pdf(html_text: str, out_path: str | Path, *, timeout: int = 120) -> Path:
    """Print HTML to a real PDF with headless Chromium. Text stays selectable."""
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    binary = chromium_binary()
    with tempfile.TemporaryDirectory(prefix="cb-print-") as tmp:
        tmp_path = Path(tmp)
        html_path = tmp_path / "document.html"
        html_path.write_text(html_text, encoding="utf-8")
        profile = tmp_path / ".chromium"
        profile.mkdir()
        command = [
            binary,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=2000",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={out}",
            html_path.as_uri(),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0 or not out.exists():
            raise RuntimeError(
                "Chromium print failed: "
                f"exit {result.returncode}; stderr: {result.stderr.strip()[:600]}"
            )
    return out


def pdf_info(pdf_path: str | Path) -> dict[str, Any]:
    """``pdfinfo`` facts used by the proof manifest."""
    binary = shutil.which("pdfinfo")
    if not binary:
        raise PrintUnavailable("pdfinfo is not installed")
    result = subprocess.run([binary, str(pdf_path)], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"pdfinfo failed: {result.stderr.strip()}")
    info: dict[str, Any] = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            info[key.strip()] = value.strip()
    return info


def pdf_text(pdf_path: str | Path) -> str:
    """Extracted PDF text; used to prove the Japanese and body text are selectable."""
    binary = shutil.which("pdftotext")
    if not binary:
        raise PrintUnavailable("pdftotext is not installed")
    result = subprocess.run(
        [binary, "-enc", "UTF-8", str(pdf_path), "-"], capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr.strip()}")
    return result.stdout


def pdf_to_png(pdf_path: str | Path, out_prefix: str | Path, *, dpi: int = 144, gray: bool = False) -> list[Path]:
    """Rasterise a PDF for visual review (and for a black-and-white legibility proof)."""
    binary = shutil.which("pdftoppm")
    if not binary:
        raise PrintUnavailable("pdftoppm is not installed")
    prefix = Path(out_prefix).resolve()
    prefix.parent.mkdir(parents=True, exist_ok=True)
    command = [binary, "-r", str(dpi), "-png"]
    if gray:
        command.append("-gray")
    command.extend([str(pdf_path), str(prefix)])
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"pdftoppm failed: {result.stderr.strip()}")
    return sorted(prefix.parent.glob(prefix.name + "-*.png"))


def paper_dimensions(paper: str) -> tuple[float, float]:
    """Points (72/inch) for the named paper, for pdfinfo assertions."""
    return {"A4": (595.28, 841.89), "Letter": (612.0, 792.0)}[paper]
