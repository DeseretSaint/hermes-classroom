"""Student syllabus import: bounded intake, deterministic parse, anchors and alignment.

This module is the backend half of the second import path (``docs/STUDENT-MODE.md``). A syllabus
is **untrusted read-only scope input**: Coursebook authors its own lessons from it and never treats
it as a pack, an enrollment authority, a plan hash or a grading path.

Frozen rules implemented here:

* intake takes bytes or pasted text only — there is no path field, no URL fetch, no LMS client;
* magic bytes decide the format, never a filename or a declared MIME;
* extraction is deterministic and local (stdlib for text/DOCX, optional ``pypdf`` for PDF); a
  missing extractor is ``PARSER_UNAVAILABLE``, never a guess;
* every parsed value carries an anchor (block id + verbatim quote); a field the document does not
  state stays ``unknown`` and is never filled from world knowledge or another field;
* no date arithmetic without an extracted term start; points and percentages are never converted;
* provider work never runs inside a transaction. The shipped parse and align stages are fully
  deterministic: they read blocks/items and write rows, and they call no model.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import unicodedata
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Iterable
from xml.etree import ElementTree

from . import api, db, job_service
from .api import RpcError

# ── caps (docs/STUDENT-MODE.md §2.1) ───────────────────────────────────────

MAX_TEXT_CHARS = 200_000
MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_BINARY_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 60
MAX_DOCX_PARAGRAPHS = 2_000
MAX_DOCX_EXPANDED = 32 * 1024 * 1024
MAX_BLOCK_TEXT = 20_000
MAX_ITEMS = 2_000

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"

#: The same conservative active-content scan ``coursebook.archive`` already uses for packs.
PDF_ACTIVE_MARKERS = (
    b"/Encrypt", b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile",
    b"/OpenAction", b"/AA", b"/RichMedia", b"/XFA",
)

ASSESSMENT_KINDS = (
    ("exam", ("exam", "midterm", "final")),
    ("quiz", ("quiz", "test")),
    ("lab", ("lab", "laboratory", "practical")),
    ("paper", ("paper", "essay")),
    ("project", ("project",)),
    ("report", ("report",)),
    ("homework", ("homework", "assignment", "problem set")),
)

POLICY_WORDS = (
    "attendance", "late work", "late policy", "academic integrity", "academic honesty",
    "collaboration", "plagiarism", "tool use", "ai use", "classroom conduct",
)

STOPWORDS = frozenset(
    "the a an and or of to in for with on at by from into week module unit chapter course class "
    "students student will be is are this that these those your you their its it as about after "
    "before over under reading readings topic topics".split()
)

NOW = lambda: datetime.now(timezone.utc).isoformat(timespec="microseconds")  # noqa: E731


class SyllabusRefused(Exception):
    """A typed syllabus refusal, raised before any write."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return default
    return parsed


def _refusal(exc: SyllabusRefused) -> RpcError:
    return RpcError.of(exc.code, exc.message, **exc.details)


# ── idempotency (same shape as the kernel's, kept local to avoid an import cycle) ──

def _payload_hash(method: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps({"method": method, "payload": payload}, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _idempotent_lookup(connection, key: str | None, method: str,
                       payload_hash: str) -> tuple[int, dict[str, Any]] | None:
    if not key:
        return None
    row = connection.execute(
        "SELECT payload_hash, method, response_json FROM idempotency_keys WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    if row["payload_hash"] != payload_hash or row["method"] != method:
        raise RpcError.of(
            "IDEMPOTENCY_CONFLICT",
            "this idempotency key was already used with a different payload.",
            key=key, method=row["method"],
        )
    stored = _load(row["response_json"], {})
    return int(stored.get("revision", 0)), dict(stored.get("result") or {})


def _remember(connection, key: str | None, method: str, payload_hash: str, operation_id: str,
              revision: int, result: dict[str, Any]) -> None:
    if not key:
        return
    connection.execute(
        "INSERT INTO idempotency_keys (key, payload_hash, method, operation_id, response_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (key, payload_hash, method, operation_id, _json({"revision": revision, "result": result}), NOW()),
    )


# ── intake validation ──────────────────────────────────────────────────────

def _decode_base64(text: str) -> bytes:
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SyllabusRefused("SYLLABUS_REJECTED", "content_base64 is not valid base64.", reason="bad_base64") from exc


def _pdf_module() -> Any | None:
    try:  # optional declared dependency
        import pypdf  # type: ignore

        return pypdf
    except Exception:  # noqa: BLE001 - absence is a typed refusal, not a crash
        return None


def _pdf_pages(data: bytes) -> list[str]:
    """Page text via ``pypdf``. Raises ``PARSER_UNAVAILABLE`` when it is not installed."""
    module = _pdf_module()
    if module is None:
        raise SyllabusRefused(
            "PARSER_UNAVAILABLE",
            "PDF extraction needs the optional pypdf dependency, which this build does not have.",
            parser="pypdf",
        )
    import io

    try:
        reader = module.PdfReader(io.BytesIO(data))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise SyllabusRefused(
                "SYLLABUS_REJECTED",
                f"the PDF has {len(reader.pages)} pages; the cap is {MAX_PDF_PAGES}.",
                reason="too_many_pages",
                pages=len(reader.pages),
            )
        pages = [(page.extract_text() or "") for page in reader.pages]
    except SyllabusRefused:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SyllabusRefused(
            "SYLLABUS_REJECTED", "the PDF could not be read.", reason="malformed_pdf", detail=type(exc).__name__
        ) from exc
    if not any(page.strip() for page in pages):
        raise SyllabusRefused(
            "SYLLABUS_NO_TEXT_LAYER",
            "this PDF has no extractable text layer; a scanned document is not OCR'd.",
            reason="no_text_layer",
        )
    return pages


def _docx_paragraphs(data: bytes) -> list[tuple[str, str]]:
    """``(style, text)`` per paragraph / table row, with DTD, entity and zip-bomb guards."""
    try:
        archive = zipfile.ZipFile(__import__("io").BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SyllabusRefused("SYLLABUS_REJECTED", "the DOCX is not a valid ZIP archive.", reason="bad_zip") from exc
    names = archive.namelist()
    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
        raise SyllabusRefused(
            "SYLLABUS_REJECTED", "the DOCX is missing [Content_Types].xml or word/document.xml.", reason="bad_docx"
        )
    if any(name.lower().endswith("vbaproject.bin") for name in names):
        raise SyllabusRefused("SYLLABUS_REJECTED", "the DOCX contains a macro project.", reason="macro_present")
    if len(names) > 2_000:
        raise SyllabusRefused("SYLLABUS_REJECTED", "the DOCX archive has too many members.", reason="too_many_members")
    expanded = sum(info.file_size for info in archive.infolist())
    if expanded > MAX_DOCX_EXPANDED:
        raise SyllabusRefused(
            "SYLLABUS_REJECTED", "the DOCX expands past the archive bound.", reason="expanded_too_large", bytes=expanded
        )
    for info in archive.infolist():
        if info.file_size > MAX_BINARY_BYTES:
            raise SyllabusRefused("SYLLABUS_REJECTED", "a DOCX member is over the size bound.", reason="member_too_large")
    for name in names:
        if not name.endswith(".rels"):
            continue
        try:
            rels = archive.read(name).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            continue
        if "TargetMode=\"External\"" in rels or "TargetMode='External'" in rels:
            raise SyllabusRefused(
                "SYLLABUS_REJECTED", "the DOCX has an external relationship target.", reason="external_relationship"
            )
    try:
        document = archive.read("word/document.xml")
    except KeyError as exc:  # pragma: no cover - checked above
        raise SyllabusRefused("SYLLABUS_REJECTED", "the DOCX has no document body.", reason="bad_docx") from exc
    if b"<!DOCTYPE" in document or b"<!ENTITY" in document:
        raise SyllabusRefused("SYLLABUS_REJECTED", "the DOCX declares a DTD or entity.", reason="dtd_present")
    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as exc:
        raise SyllabusRefused("SYLLABUS_REJECTED", "the DOCX body is not well-formed XML.", reason="bad_xml") from exc
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    out: list[tuple[str, str]] = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "p":
            style = ""
            style_node = node.find("./w:pPr/w:pStyle", ns)
            if style_node is not None:
                style = style_node.get(f"{{{ns['w']}}}val", "") or ""
            text = "".join(part.text or "" for part in node.iter(f"{{{ns['w']}}}t")).strip()
            if text:
                out.append((style, text))
            if len(out) > MAX_DOCX_PARAGRAPHS:
                raise SyllabusRefused(
                    "SYLLABUS_REJECTED",
                    f"the DOCX has more than {MAX_DOCX_PARAGRAPHS} paragraphs.",
                    reason="too_many_paragraphs",
                )
        elif tag == "tbl":
            for row in node.findall("./w:tr", ns):
                cells = []
                for cell in row.findall("./w:tc", ns):
                    cells.append("".join(part.text or "" for part in cell.iter(f"{{{ns['w']}}}t")).strip())
                text = "\t".join(cells).strip()
                if text:
                    out.append(("Table", text))
    return out


def _text_format(name: str) -> str:
    lowered = (name or "").lower()
    return "markdown" if lowered.endswith((".md", ".markdown")) else "text"


def _validate_intake(payload: dict[str, Any]) -> dict[str, Any]:
    """Return ``{source_kind, mime, raw_bytes, text}`` or raise a typed refusal. Writes nothing."""
    has_bytes = payload.get("content_base64") is not None
    has_text = payload.get("pasted_text") is not None
    if has_bytes == has_text:
        raise RpcError.of(
            "VALIDATION_FAILED",
            "syllabus.intake.create takes exactly one of content_base64 or pasted_text.",
            field="content_base64" if has_bytes else "pasted_text",
        )
    name = str(payload.get("file_name") or ("Pasted text" if has_text else "syllabus"))
    if has_text:
        text = str(payload["pasted_text"])
        raw = text.encode("utf-8")
        if len(text) > MAX_TEXT_CHARS or len(raw) > MAX_TEXT_BYTES:
            raise _refusal(SyllabusRefused(
                "SYLLABUS_REJECTED",
                f"the pasted text is over the {MAX_TEXT_CHARS}-character bound.",
                reason="too_large", characters=len(text),
            ))
        if "\x00" in text[:8000]:
            raise _refusal(SyllabusRefused("SYLLABUS_REJECTED", "the text contains NUL bytes.", reason="binary_text"))
        return {"source_kind": "pasted", "mime": "text/plain", "raw": raw, "text": text, "file_name": name}

    raw = _decode_base64(str(payload["content_base64"]))
    if raw.startswith(PDF_MAGIC):
        if len(raw) > MAX_BINARY_BYTES:
            raise _refusal(SyllabusRefused(
                "SYLLABUS_REJECTED", f"the PDF is {len(raw)} bytes; the cap is {MAX_BINARY_BYTES}.",
                reason="too_large", bytes=len(raw),
            ))
        lowered = raw.lower()
        for marker in PDF_ACTIVE_MARKERS:
            if marker.lower() in lowered:
                raise _refusal(SyllabusRefused(
                    "SYLLABUS_REJECTED", "the PDF carries encrypted or active content.",
                    reason="active_content", marker=marker.decode("ascii", "replace"),
                ))
        _pdf_pages(raw)  # availability + text-layer check before anything is stored
        return {"source_kind": "pdf", "mime": "application/pdf", "raw": raw, "text": None, "file_name": name}
    if raw.startswith(ZIP_MAGIC):
        if len(raw) > MAX_BINARY_BYTES:
            raise _refusal(SyllabusRefused(
                "SYLLABUS_REJECTED", f"the DOCX is {len(raw)} bytes; the cap is {MAX_BINARY_BYTES}.",
                reason="too_large", bytes=len(raw),
            ))
        _docx_paragraphs(raw)
        return {
            "source_kind": "docx",
            "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "raw": raw, "text": None, "file_name": name,
        }
    if len(raw) > MAX_TEXT_BYTES:
        raise _refusal(SyllabusRefused(
            "SYLLABUS_REJECTED", f"the text file is {len(raw)} bytes; the cap is {MAX_TEXT_BYTES}.",
            reason="too_large", bytes=len(raw),
        ))
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _refusal(SyllabusRefused("SYLLABUS_REJECTED", "the text file is not valid UTF-8.", reason="not_utf8")) from exc
    if "\x00" in text[:8000]:
        raise _refusal(SyllabusRefused("SYLLABUS_REJECTED", "the text file contains NUL bytes.", reason="binary_text"))
    if len(text) > MAX_TEXT_CHARS:
        raise _refusal(SyllabusRefused(
            "SYLLABUS_REJECTED", f"the text is over the {MAX_TEXT_CHARS}-character bound.",
            reason="too_large", characters=len(text),
        ))
    return {"source_kind": _text_format(name), "mime": "text/markdown" if _text_format(name) == "markdown" else "text/plain",
            "raw": raw, "text": text, "file_name": name}


# ── extraction (deterministic, local; no model) ────────────────────────────

def extract_blocks(source_kind: str, raw: bytes) -> list[dict[str, Any]]:
    """Extract anchor blocks. Extraction never interprets and never follows a link."""
    if source_kind == "pdf":
        return [
            {"kind": "page", "label": f"Page {index}", "page": index, "line_start": None, "line_end": None,
             "text": text}
            for index, text in enumerate(_pdf_pages(raw), start=1)
            if text.strip()
        ]
    if source_kind == "docx":
        blocks: list[dict[str, Any]] = []
        section: list[str] = []
        for style, text in _docx_paragraphs(raw):
            label = " / ".join(section) if section else None
            heading = _heading_level(style)
            if heading:
                section = section[: heading - 1] + [text]
                label = " / ".join(section)
            blocks.append({"kind": "paragraph", "label": label, "page": None,
                           "line_start": None, "line_end": None, "text": text})
        return blocks
    text = raw.decode("utf-8")
    return _text_blocks(text, markdown=(source_kind == "markdown"))


def _heading_level(style: str) -> int:
    match = re.match(r"^Heading\s*([123])$", style or "", re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _text_blocks(text: str, *, markdown: bool) -> list[dict[str, Any]]:
    lines = text.splitlines()
    if markdown:
        blocks: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for index, line in enumerate(lines, start=1):
            match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if match:
                if current:
                    blocks.append(current)
                current = {
                    "kind": "section",
                    "label": match.group(2).strip(),
                    "page": None,
                    "line_start": index,
                    "line_end": index,
                    "text": line,
                }
                continue
            if current is None:
                current = {"kind": "lines", "label": None, "page": None, "line_start": index,
                           "line_end": index, "text": line}
            else:
                current["line_end"] = index
                current["text"] = f"{current['text']}\n{line}"
        if current:
            blocks.append(current)
        return [block for block in blocks if block["text"].strip()]
    # Plain text / pasted: paragraph groups, labelled heuristically.
    blocks = []
    start = 1
    buffer: list[str] = []

    def flush(end: int) -> None:
        nonlocal buffer, start
        body = "\n".join(buffer).strip()
        if body:
            first = body.splitlines()[0]
            label = first.strip().lstrip("#").strip().rstrip(":") if _looks_like_label(first) else None
            blocks.append({"kind": "paragraph", "label": label, "page": None,
                           "line_start": start, "line_end": end, "text": body})
        buffer = []

    for index, line in enumerate(lines, start=1):
        heading = re.match(r"^#{1,6}\s+\S", line)
        if heading and buffer:
            flush(index - 1)
            start = index
        if not line.strip():
            flush(index - 1)
            start = index + 1
            continue
        if not buffer:
            start = index
        buffer.append(line)
    flush(len(lines))
    return blocks


def _looks_like_label(line: str) -> bool:
    stripped = line.strip().lstrip("#").strip()
    if len(stripped) > 80:
        return False
    return bool(
        re.match(r"^(week|module|unit|topic|readings?|assessments?|policies|learning outcomes?|"
                 r"course|instructor|term|semester|schedule)\b", stripped, re.IGNORECASE)
        or stripped.endswith(":")
    )


def _norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# ── syllabus.parse.v1 (closed document, every scalar an item) ───────────────

def _item(value: Any, block: dict[str, Any] | None, *, quote: str | None = None,
          derivation: str = "explicit") -> dict[str, Any]:
    if block is None:
        return {"value": None, "state": "unknown", "anchors": [], "derivation": "unknown"}
    return {
        "value": value,
        "state": "extracted",
        "anchors": [{"block_id": block["id"], "quote": _norm_space(quote or block["text"])[:400]}],
        "derivation": derivation,
    }


def _unknown() -> dict[str, Any]:
    return {"value": None, "state": "unknown", "anchors": [], "derivation": "unknown"}


def _find(blocks: Iterable[dict[str, Any]], pattern: str, flags: int = re.IGNORECASE) -> tuple[dict, re.Match] | None:
    regex = re.compile(pattern, flags)
    for block in blocks:
        match = regex.search(block["text"])
        if match:
            return block, match
    return None


ISO_DATE = r"\b(\d{4}-\d{2}-\d{2})\b"
COURSE_CODE = r"\b([A-Z]{2,5})[ -]?(\d{2,4}[A-Z]?)\b"


def parse_document(blocks: list[dict[str, Any]], *, source_kind: str) -> dict[str, Any]:
    """Build the closed ``syllabus.parse.v1`` document from anchor blocks.

    Deterministic only: a literal pattern is extracted, and everything the document does not state
    is ``unknown``. No model, no world knowledge, no date arithmetic without a term start, no weight
    normalization.
    """
    items: list[dict[str, Any]] = []
    unknowns: list[str] = []

    def add(kind: str, title: str | None, item: dict[str, Any], *, week: int | None = None) -> dict[str, Any]:
        items.append({"kind": kind, "title": title, "item": item, "week_ordinal": week})
        if item["state"] == "unknown":
            unknowns.append(kind if title is None else f"{kind}:{title}")
        return item

    course_code = _unknown()
    course_title = _unknown()
    found = _find(blocks, rf"{COURSE_CODE}\s*[—–\-:]\s*(.+)")
    if found is None:
        found = _find(blocks, COURSE_CODE)
    if found is not None:
        block, match = found
        code = f"{match.group(1)} {match.group(2)}"
        course_code = _item(code, block, quote=match.group(0))
        rest = match.group(3).strip() if match.lastindex and match.lastindex >= 3 and match.group(3) else ""
        if not rest and "—" in block["text"]:
            rest = block["text"].split("—", 1)[1].strip()
        if rest:
            course_title = _item(rest[:200], block, quote=rest[:200])
    if course_title["state"] == "unknown" and blocks:
        heading = next((b for b in blocks if b.get("kind") in ("section", "paragraph") and b.get("label")), None)
        if heading is not None:
            course_title = _item(str(heading["label"])[:200], heading, quote=str(heading["label"])[:200])
    add("course_code", None, course_code)
    add("course_title", None, course_title)

    institution = _unknown()
    found = _find(blocks, r"^(.{3,120}(?:University|College|Institute|School).{0,80})\s*$", re.MULTILINE)
    if found:
        block, match = found
        institution = _item(_norm_space(match.group(1)), block, quote=match.group(1))
    add("institution", None, institution)

    instructor = _unknown()
    found = _find(blocks, r"(?:Instructor|Professor|Lecturer)\s*:\s*([^\n]{2,120})")
    if found:
        block, match = found
        instructor = _item(match.group(1).strip(), block, quote=match.group(0))
    add("instructor", None, instructor)

    meeting = _unknown()
    found = _find(blocks, r"(?:Meets|Meeting(?: pattern)?|Class time)\s*:\s*([^\n]{2,120})")
    if found:
        block, match = found
        meeting = _item(match.group(1).strip(), block, quote=match.group(0))
    add("meeting_pattern", None, meeting)

    term_label = _unknown()
    found = _find(blocks, r"(?:Term|Semester|Quarter)\s*:\s*([^\n]{2,120})")
    if found:
        block, match = found
        term_label = _item(match.group(1).strip(), block, quote=match.group(0))
    start_date = _unknown()
    end_date = _unknown()
    found = _find(blocks, rf"(?:Start(?: date)?|Begins)\s*:\s*{ISO_DATE}")
    if found:
        block, match = found
        start_date = _item(match.group(1), block, quote=match.group(0))
    found = _find(blocks, rf"(?:End(?: date)?|Ends)\s*:\s*{ISO_DATE}")
    if found:
        block, match = found
        end_date = _item(match.group(1), block, quote=match.group(0))
    add("term_label", None, term_label)
    add("term_start", None, start_date)
    add("term_end", None, end_date)

    # Weeks: a heading or line that starts with Week/Module/Unit N.
    weeks: list[dict[str, Any]] = []
    current_week: dict[str, Any] | None = None
    for block in blocks:
        head = _week_heading(block["text"])
        if head is not None:
            ordinal, label, topic = head
            item = _item(ordinal, block, quote=label)
            topic_item = _item(topic, block, quote=topic) if topic else _unknown()
            current_week = {"ordinal": item, "label": _item(label, block, quote=label),
                            "topic": topic_item, "readings": [], "assessments": [],
                            "anchors": item["anchors"], "block": block}
            weeks.append(current_week)
            items.append({"kind": "week", "title": f"{label}: {topic}" if topic else label,
                          "item": item, "week_ordinal": ordinal})
        if current_week is None:
            continue
        reading = _reading_from(block)
        if reading is not None:
            current_week["readings"].append(reading)
            add("reading", reading["value"], reading, week=int(current_week["ordinal"]["value"] or 0))
        for assessment in _assessments_in(block, current_week["ordinal"]["value"]):
            current_week["assessments"].append(assessment)
            add("assessment", assessment["title"]["value"], _assessment_item(assessment),
                week=current_week["ordinal"]["value"])
            if assessment["due"]["state"] == "unknown":
                add("assessment", f"{assessment['title']['value']} (due)", assessment["due"],
                    week=current_week["ordinal"]["value"])

    # Assessments outside a week heading are still assessments.
    seen_titles = {week_assess["title"]["value"] for week in weeks for week_assess in week["assessments"]}
    for block in blocks:
        for assessment in _assessments_in(block, None):
            if assessment["title"]["value"] in seen_titles:
                continue
            seen_titles.add(assessment["title"]["value"])
            add("assessment", assessment["title"]["value"], _assessment_item(assessment))
            if assessment["due"]["state"] == "unknown":
                add("assessment", f"{assessment['title']['value']} (due)", assessment["due"])

    # Outcomes: blocks under a outcomes/objectives heading.
    outcomes: list[dict[str, Any]] = []
    for block in blocks:
        label = (block.get("label") or "").lower()
        in_outcomes = bool(re.search(r"\b(learning )?outcomes?\b|\bobjectives\b", label))
        if not in_outcomes:
            continue
        for line in block["text"].splitlines():
            if line.strip().startswith("#"):
                continue
            stripped = line.strip().lstrip("-*0123456789. ").strip()
            if len(stripped) >= 12 and not stripped.lower().startswith(("week", "module", "unit")):
                item = _item(stripped[:600], block, quote=stripped[:400])
                outcomes.append(item)
                add("learning_outcome", stripped[:80], item)

    # Policies: only study-affecting policy text, preserved verbatim.
    policies: list[dict[str, Any]] = []
    for block in blocks:
        label = (block.get("label") or "").lower()
        text_lower = block["text"].lower()
        policy_context = any(word in label for word in POLICY_WORDS) or label.startswith("polic")
        for line in block["text"].splitlines():
            stripped = line.strip()
            if len(stripped) < 8 or stripped.startswith("#"):
                continue
            if policy_context or any(word in stripped.lower() for word in POLICY_WORDS):
                if stripped.lower().startswith(("week", "module", "unit")):
                    continue
                item = _item(stripped[:1200], block, quote=stripped[:400])
                policies.append(item)
                add("policy", stripped[:80], item)

    # Coverage and parse result.
    extracted = sum(1 for entry in items if entry["item"]["state"] == "extracted")
    coverage = {
        "pages": max((block.get("page") or 0) for block in blocks) or None,
        "blocks": len(blocks),
        "extracted_chars": sum(len(block["text"]) for block in blocks),
        "items_total": len(items),
        "items_extracted": extracted,
    }
    document = {
        "schema": "syllabus.parse.v1",
        "source_kind": source_kind,
        "institution": institution,
        "course": {"code": course_code, "title": course_title},
        "term": {"label": term_label, "start_date": start_date, "end_date": end_date},
        "instructor": instructor,
        "meeting_pattern": meeting,
        "learning_outcomes": outcomes,
        "weeks": [
            {"ordinal": week["ordinal"], "label": week["label"], "topic": week["topic"],
             "readings": week["readings"], "assessments": week["assessments"],
             "anchors": week["anchors"]}
            for week in weeks
        ],
        "assessments": [assessment for week in weeks for assessment in week["assessments"]],
        "policies": policies,
        "unknowns": unknowns,
        "coverage": coverage,
        "_items": items,
    }
    return document


def _week_heading(text: str) -> tuple[int, str, str] | None:
    first = text.strip().splitlines()[0] if text.strip() else ""
    first = first.lstrip("#").strip()
    match = re.match(r"^(Week|Module|Unit)\s+(\d{1,3})\b\s*[—–:\-]?\s*(.*)$", first, re.IGNORECASE)
    if not match:
        return None
    label = f"{match.group(1).title()} {match.group(2)}"
    topic = match.group(3).strip()
    return int(match.group(2)), label, topic


def _reading_from(block: dict[str, Any]) -> dict[str, Any] | None:
    match = re.search(r"(?:Readings?|Reading assignment)\s*:\s*([^\n]{2,400})", block["text"], re.IGNORECASE)
    if match:
        value = match.group(1).strip()
    else:
        match = re.search(r"\b(Chapter\s+\d+[^\n,;]{0,120})", block["text"], re.IGNORECASE)
        if not match:
            return None
        value = match.group(1).strip()
    if re.fullmatch(r"TBD|TBA|to be determined|to be announced", value.strip(), re.IGNORECASE):
        return {"value": None, "state": "unknown", "anchors": [], "derivation": "unknown"}
    return _item(value[:400], block, quote=match.group(0))


def _assessment_item(assessment: dict[str, Any]) -> dict[str, Any]:
    """The persisted assessment item: the title as ``value`` plus the stated ``fields``.

    ``fields.due`` and ``fields.weight`` reuse the same item objects ``_assessments_in`` built and
    ``verify_anchors`` already visits, so an anchor mismatch downgrades the field itself and this
    adds no second verification pass. ``fields`` is additive response surface (the v13 H-26b
    amendment); the
    item ``kind`` stays ``assessment`` and ``cb.db`` v8's closed enum never sees a new value.
    """
    item = dict(assessment["title"])
    item["fields"] = {
        "due": assessment["due"],
        "weight": assessment["weight"],
        "weight_unit": assessment["weight_unit"],
    }
    return item


def _assessments_in(block: dict[str, Any], week_ordinal: int | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in block["text"].splitlines():
        stripped = line.strip()
        if len(stripped) < 5 or stripped.startswith("#"):
            continue
        # A week heading may itself carry the assessment ("Week 8: Midterm exam (20%)"). Analyse
        # the part after the week label rather than dropping the line.
        week_prefix = re.match(r"^(Week|Module|Unit)\s+\d{1,3}\s*[:—–-]\s*(.*)$", stripped, re.IGNORECASE)
        if week_prefix:
            stripped = week_prefix.group(2).strip()
            if len(stripped) < 5:
                continue
        kind = _assessment_kind(stripped)
        if kind is None:
            continue
        weight_match = re.search(r"\b(\d{1,3}(?:\.\d+)?)\s*%", stripped)
        points_match = re.search(r"\b(\d{1,4})\s*points?\b", stripped, re.IGNORECASE)
        date_match = re.search(ISO_DATE, stripped)
        # A line only counts as an assessment when it names an assessment *and* carries a
        # deadline or a weight, or opens with the assessment word. A policy sentence that
        # mentions a lab ("labs are mandatory") is not an assessment.
        if not (date_match or weight_match or points_match
                or re.match(r"^(quiz|exam|midterm|final|lab|paper|project|report|homework|assignment)\b",
                            stripped, re.IGNORECASE)):
            continue
        title_text = re.split(r"\s+(?:due|date|on|by|—|–|-)\s+", stripped, maxsplit=1, flags=re.IGNORECASE)[0]
        title_text = re.split(r"\s*\(?\b\d{1,3}(?:\.\d+)?\s*%", title_text, maxsplit=1)[0].strip(" .;:-")
        title = _item(title_text[:160], block, quote=title_text[:160])
        due = _item(date_match.group(1), block, quote=date_match.group(0)) if date_match else _unknown()
        if weight_match:
            weight = _item(float(weight_match.group(1)), block, quote=weight_match.group(0))
            unit = "percent"
        elif points_match:
            weight = _item(int(points_match.group(1)), block, quote=points_match.group(0))
            unit = "points"
        else:
            weight = _unknown()
            unit = "unknown"
        out.append({
            "id": None,
            "title": title,
            "kind": _item(kind, block, quote=stripped[:120]),
            "due": due,
            "weight": weight,
            "weight_unit": unit,
            "week_ordinal": week_ordinal,
            "_block": block["id"],
        })
    return out


def _assessment_kind(line: str) -> str | None:
    lowered = line.lower()
    for kind, words in ASSESSMENT_KINDS:
        if any(word in lowered for word in words):
            return kind
    return None


def verify_anchors(document: dict[str, Any], blocks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Downgrade every item whose quote is not verbatim in the cited block.

    Returns ``{"items_total", "items_extracted", "anchor_mismatches", "state"}``. A document whose
    mismatch rate is over 20% is ``needs_review`` and cannot open the course path.
    """
    checked = 0
    mismatches = 0

    def visit(item: dict[str, Any]) -> None:
        nonlocal checked, mismatches
        if item.get("state") != "extracted":
            return
        checked += 1
        anchors = item.get("anchors") or []
        ok = False
        for anchor in anchors:
            block = blocks.get(str(anchor.get("block_id")))
            if block is None:
                continue
            quote = _norm_space(str(anchor.get("quote") or ""))
            if quote and quote in _norm_space(block["text"]):
                ok = True
                break
        if not ok:
            mismatches += 1
            item["value"] = None
            item["state"] = "unknown"
            item["anchors"] = []
            item["derivation"] = "unknown"
            item["reason"] = "anchor_mismatch"

    for entry in document.get("_items") or []:
        visit(entry["item"])
        # v13 H-26b: an assessment item carries its stated fields. The due/weight objects are shared
        # with document["assessments"], so this is the same pass, not a second verification, and
        # it also covers assessments that sit outside any week heading.
        fields = entry["item"].get("fields") or {}
        for name in ("due", "weight"):
            if isinstance(fields.get(name), dict):
                visit(fields[name])
    for week in document.get("weeks") or []:
        for field in ("ordinal", "label", "topic"):
            visit(week[field])
        for reading in week["readings"]:
            visit(reading)
    for assessment in document.get("assessments") or []:
        for field in ("title", "kind", "due", "weight"):
            visit(assessment[field])
    for item in document.get("learning_outcomes") or []:
        visit(item)
    for item in document.get("policies") or []:
        visit(item)
    matched_ratio = 0.0 if checked == 0 else mismatches / checked
    state = "needs_review" if matched_ratio > 0.20 else "parsed"
    return {"items_total": len(document.get("_items") or []), "items_checked": checked,
            "anchor_mismatches": mismatches, "state": state}


# ── persistence ────────────────────────────────────────────────────────────

def _syllabus_row(connection, syllabus_id: str, revision: int | None = None) -> Any:
    if revision is None:
        row = connection.execute("SELECT * FROM syllabi WHERE id = ?", (syllabus_id,)).fetchone()
    else:
        row = connection.execute(
            "SELECT * FROM syllabi WHERE id = ? AND revision = ?", (syllabus_id, revision)
        ).fetchone()
    if row is None or row["deleted_at"] is not None:
        raise RpcError.of("NOT_FOUND", f"syllabus {syllabus_id} does not exist.", syllabus_id=syllabus_id)
    return row


def _current_revision(connection, series_id: str) -> Any:
    return connection.execute(
        "SELECT * FROM syllabi WHERE series_id = ? AND deleted_at IS NULL ORDER BY revision DESC LIMIT 1",
        (series_id,),
    ).fetchone()


def _store_parse(connection, syllabus, blocks: list[dict[str, Any]], document: dict[str, Any]) -> str:
    run_id = _new_id("spr")
    verification = verify_anchors(document, {block["id"]: block for block in blocks})
    now = NOW()
    connection.execute(
        "UPDATE syllabi SET state = 'parsed' WHERE id = ?", (syllabus["id"],)
    )
    for block in blocks:
        connection.execute(
            "INSERT INTO syllabus_blocks (id, syllabus_id, ordinal, kind, label, page, line_start,"
            " line_end, text, text_sha256) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (block["id"], syllabus["id"], block["ordinal"], block["kind"], block["label"],
             block["page"], block["line_start"], block["line_end"], block["text"], _sha256(block["text"].encode())),
        )
    connection.execute(
        "INSERT INTO syllabus_parse_runs (id, syllabus_id, schema, state, provider, model,"
        " validation_json, coverage_json, created_at) VALUES (?, ?, 'syllabus.parse.v1', ?, NULL, NULL, ?, ?, ?)",
        (run_id, syllabus["id"], verification["state"], _json(verification),
         _json(document.get("coverage") or {}), now),
    )
    items = document.get("_items") or []
    for ordinal, entry in enumerate(items):
        item = entry["item"]
        connection.execute(
            "INSERT INTO syllabus_items (id, syllabus_id, parse_run_id, kind, ordinal, week_ordinal,"
            " title, value_json, value_state, anchors_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_new_id("sit"), syllabus["id"], run_id, entry["kind"], ordinal, entry["week_ordinal"],
             entry["title"], _json(item), item["state"], _json(item.get("anchors") or []), now),
        )
    return run_id


def parse_stored(connection, syllabus_id: str, revision: int) -> dict[str, Any]:
    """Extract + parse + persist one stored revision. Deterministic; no model call."""
    syllabus = _syllabus_row(connection, syllabus_id, revision)
    if syllabus["state"] == "parsed":
        return {"syllabus_id": syllabus_id, "revision": revision, "state": "parsed", "reused": True}
    file_row = connection.execute(
        "SELECT bytes FROM syllabus_files WHERE syllabus_id = ?", (syllabus_id,)
    ).fetchone()
    if file_row is None:
        raise RpcError.of("NOT_FOUND", "the stored syllabus bytes are gone; re-upload the file.", syllabus_id=syllabus_id)
    blocks = extract_blocks(str(syllabus["source_kind"]), bytes(file_row["bytes"]))
    for index, block in enumerate(blocks, start=1):
        block["id"] = _new_id("blk")
        block["ordinal"] = index
        if block["text"]:
            block["text"] = block["text"][:MAX_BLOCK_TEXT]
    document = parse_document(blocks, source_kind=str(syllabus["source_kind"]))
    if document["course"]["code"]["state"] == "unknown" and document["course"]["title"]["state"] == "unknown":
        raise SyllabusRefused(
            "SYLLABUS_REJECTED", "no recognizable course code or title; this is not a syllabus.",
            reason="not_a_syllabus",
        )
    run_id = _store_parse(connection, syllabus, blocks, document)
    return {"syllabus_id": syllabus_id, "revision": revision, "parse_run_id": run_id,
            "state": "parsed", "coverage": document.get("coverage")}


# ── alignment (deterministic rules; no model) ──────────────────────────────

def _tokens(text: str | None) -> set[str]:
    normalized = unicodedata.normalize("NFKD", str(text or "")).casefold()
    return {
        token for token in re.split(r"[^a-z0-9]+", normalized)
        if len(token) >= 3 and token not in STOPWORDS
    }


def _overlap(item_tokens: set[str], target_tokens: set[str]) -> float:
    if not item_tokens or not target_tokens:
        return 0.0
    return len(item_tokens & target_tokens) / max(1, len(item_tokens))


def _plan_targets(connection, plan_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT id, ordinal, title, evidence_target, unit_id FROM objectives WHERE plan_id = ? ORDER BY ordinal",
        (plan_id,),
    ).fetchall()
    # A v2 (blueprint) plan is organised in units; the unit is the schedule boundary the syllabus
    # week or assessment maps to (docs/STUDENT-MODE.md §4.3 maps week ordinals to units 1-12). A
    # legacy v1 plan has no units and maps to objectives through its authored sections.
    try:
        units = connection.execute(
            "SELECT id, ordinal, title FROM plan_units WHERE plan_id = ? ORDER BY ordinal",
            (plan_id,),
        ).fetchall()
    except Exception:  # noqa: BLE001 - a pre-0007 database has no unit table
        units = []
    if units:
        targets: list[dict[str, Any]] = []
        for unit in units:
            members = [row for row in rows if row["unit_id"] == unit["id"]]
            tokens = _tokens(unit["title"])
            for row in members:
                tokens |= _tokens(row["title"]) | _tokens(row["evidence_target"])
            targets.append({
                "target_kind": "unit",
                "target_id": str(unit["id"]),
                "title": str(unit["title"] or ""),
                "evidence_target": None,
                "section_ordinal": int(unit["ordinal"]),
                "tokens": tokens,
            })
        return targets
    section_of: dict[str, int] = {}
    try:
        sections = connection.execute(
            "SELECT ordinal, objective_refs_json FROM gen_plan_sections WHERE plan_id = ? ORDER BY ordinal",
            (plan_id,),
        ).fetchall()
    except Exception:  # noqa: BLE001 - a pre-v6 plan has no section table: no schedule evidence
        sections = []
    for section in sections:
        refs = _load(section["objective_refs_json"], [])
        for ref in refs if isinstance(refs, list) else []:
            try:
                ordinal = int(ref)
            except (TypeError, ValueError):
                continue
            for row in rows:
                if int(row["ordinal"]) == ordinal:
                    section_of[str(row["id"])] = int(section["ordinal"])
    return [
        {
            "target_kind": "objective",
            "target_id": str(row["id"]),
            "title": str(row["title"] or ""),
            "evidence_target": row["evidence_target"],
            "section_ordinal": section_of.get(str(row["id"])),
            "tokens": _tokens(row["title"]) | _tokens(row["evidence_target"]),
        }
        for row in rows
    ]


def _alignment_rows(connection, course_id: str, plan_id: str, syllabus_id: str, revision: int,
                    content_sha256: str) -> list[dict[str, Any]]:
    targets = _plan_targets(connection, plan_id)
    items = connection.execute(
        "SELECT * FROM syllabus_items WHERE syllabus_id = ? AND value_state = 'extracted'"
        " AND kind IN ('week', 'reading', 'assessment', 'learning_outcome')"
        " AND (title IS NULL OR title NOT LIKE '% (due)') ORDER BY ordinal",
        (syllabus_id,),
    ).fetchall()
    rows: list[dict[str, Any]] = []
    for item in items:
        value = _load(item["value_json"], {})
        title = str(item["title"] or (value.get("value") if isinstance(value.get("value"), str) else "") or "")
        item_tokens = _tokens(title)
        best: dict[str, Any] | None = None
        best_score = 0.0
        for target in targets:
            score = _overlap(item_tokens, target["tokens"])
            if score > best_score:
                best, best_score = target, score
        anchors = _load(item["anchors_json"], [])
        if best is None or best_score < 0.20:
            state, reason = "unmatched", "no_target"
            target_kind, target_id = "objective", "none"
            explanation = "no plan objective shares this item's title tokens"
        elif best_score >= 0.60:
            state, reason = "aligned", "title_tokens"
            target_kind, target_id = best["target_kind"], best["target_id"]
            explanation = f"title tokens map to {best['target_kind']} {best['target_id']}"
        else:
            state, reason = "partial", "weak_title_tokens"
            target_kind, target_id = best["target_kind"], best["target_id"]
            explanation = "only part of the item's title is covered by the objective"
        week = item["week_ordinal"]
        if (state in ("aligned", "partial") and item["kind"] == "assessment"
                and week is not None and best is not None and best["section_ordinal"] is not None
                and best["section_ordinal"] > int(week)):
            state, reason = "conflict", "scheduled_after_deadline"
            explanation = (
                f"the plan schedules this assessment's topic in {best['target_kind']} "
                f"{best['section_ordinal']}, after syllabus week {week}"
            )
        rows.append({
            "item_id": item["id"],
            "kind": item["kind"],
            "title": title or None,
            "value_state": item["value_state"],
            "state": state,
            "reason_code": reason,
            "target_kind": target_kind,
            "target_id": target_id,
            "anchors": anchors,
            "review_state": "pending",
            "stale": 0,
            "evidence": {
                "syllabus_sha256": content_sha256,
                "syllabus_anchors": anchors,
                "target_kind": target_kind,
                "target_id": target_id,
                "rule": "title_tokens" if state != "unmatched" else "none",
                "deterministic": True,
                "explanation": explanation,
            },
        })
    return rows


def align_plan(connection, *, syllabus_id: str, revision: int, course_id: str, plan_id: str) -> int:
    """Rebuild the deterministic mapping for the current revision. Returns alignment_revision."""
    syllabus = _syllabus_row(connection, syllabus_id, revision)
    if syllabus["superseded_at"] is not None:
        raise SyllabusRefused("SYLLABUS_STALE", "this syllabus revision is superseded.", revision=revision)
    run = connection.execute(
        "SELECT * FROM syllabus_parse_runs WHERE syllabus_id = ? ORDER BY created_at DESC LIMIT 1",
        (syllabus_id,),
    ).fetchone()
    if run is None:
        raise SyllabusRefused("SYLLABUS_UNREVIEWED", "the syllabus has not been parsed yet.", reason="not_parsed")
    binding = connection.execute("SELECT * FROM course_syllabi WHERE course_id = ?", (course_id,)).fetchone()
    if binding is None or binding["syllabus_id"] != syllabus_id:
        raise SyllabusRefused("SYLLABUS_UNREVIEWED", "this course is not bound to that syllabus.", reason="unbound")
    connection.execute(
        "UPDATE syllabus_alignments SET stale = 1 WHERE course_id = ? AND syllabus_revision <> ? AND stale = 0",
        (course_id, revision),
    )
    connection.execute(
        "DELETE FROM syllabus_alignments WHERE course_id = ? AND syllabus_revision = ? AND stale = 0",
        (course_id, revision),
    )
    rows = _alignment_rows(connection, course_id, plan_id, syllabus_id, revision, str(syllabus["content_sha256"]))
    now = NOW()
    for row in rows:
        connection.execute(
            "INSERT INTO syllabus_alignments (id, course_id, plan_id, syllabus_id, syllabus_revision,"
            " item_id, target_kind, target_id, state, reason_code, evidence_json, review_state, stale, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_new_id("sal"), course_id, plan_id, syllabus_id, revision, row["item_id"],
             row["target_kind"], row["target_id"], row["state"], row["reason_code"],
             _json(row["evidence"]), row["review_state"], 0, now),
        )
    alignment_revision = int(binding["alignment_revision"]) + 1
    connection.execute(
        "UPDATE course_syllabi SET syllabus_id = ?, syllabus_revision = ?, alignment_revision = ?,"
        " reviewed_revision = NULL, reviewed_at = NULL WHERE course_id = ?",
        (syllabus_id, revision, alignment_revision, course_id),
    )
    return alignment_revision


# ── handlers ───────────────────────────────────────────────────────────────

HANDLERS: dict[str, Any] = {}


def _handler(method: str):
    def decorator(fn):
        HANDLERS[method] = fn
        return fn

    return decorator


def _syllabus_view(row: Any, file_row: Any = None) -> dict[str, Any]:
    return {
        "syllabus_id": row["id"],
        "series_id": row["series_id"],
        "revision": int(row["revision"]),
        "supersedes_id": row["supersedes_id"],
        "content_sha256": row["content_sha256"],
        "file_name": row["file_name"],
        "mime": row["mime"],
        "source_kind": row["source_kind"],
        "state": row["state"],
        "created_at": row["created_at"],
        "superseded_at": row["superseded_at"],
        "bytes": int(file_row["size"]) if file_row is not None else None,
    }


@_handler("syllabus.intake.create")
def syllabus_intake_create(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Store bounded bytes and mint a revision. Nothing is parsed here, and nothing is written on refusal."""
    db.ensure_schema()
    method = "syllabus.intake.create"
    key = envelope.get("idempotency_key")
    try:
        validated = _validate_intake(payload)
    except SyllabusRefused as exc:
        raise _refusal(exc) from exc
    raw: bytes = validated["raw"]
    digest = "sha256:" + _sha256(raw)
    now = NOW()
    with db.transaction() as connection:
        replay = _idempotent_lookup(connection, key, method, _payload_hash(method, payload))
        if replay is not None:
            return replay
        supersedes = payload.get("supersedes_syllabus_id")
        if supersedes:
            prior = _syllabus_row(connection, str(supersedes))
            if prior["content_sha256"] == digest:
                result = {
                    "syllabus_id": prior["id"], "series_id": prior["series_id"],
                    "revision": int(prior["revision"]), "content_sha256": digest,
                    "bytes": len(raw), "state": prior["state"],
                    "extraction": {"source_kind": validated["source_kind"],
                                   "characters": len(validated["text"] or "")},
                }
                _remember(connection, key, method, _payload_hash(method, payload),
                          envelope.get("operation_id", ""), 0, result)
                return 0, result
            series_id = prior["series_id"]
        else:
            prior = None
            series_id = _new_id("sys")
            connection.execute(
                "INSERT INTO syllabus_series (id, learner_label, created_at) VALUES (?, ?, ?)",
                (series_id, payload.get("learner_label"), now),
            )
        current = _current_revision(connection, series_id)
        revision = int(current["revision"]) + 1 if current is not None else 1
        syllabus_id = _new_id("syl")
        connection.execute(
            "INSERT INTO syllabi (id, series_id, revision, supersedes_id, content_sha256, file_name,"
            " mime, source_kind, state, created_at, superseded_at, deleted_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'stored', ?, NULL, NULL)",
            (syllabus_id, series_id, revision, current["id"] if current is not None else None, digest,
             validated["file_name"], validated["mime"], validated["source_kind"], now),
        )
        connection.execute(
            "INSERT INTO syllabus_files (syllabus_id, bytes, size, sha256) VALUES (?, ?, ?, ?)",
            (syllabus_id, raw, len(raw), digest),
        )
        stale_rows = 0
        if current is not None:
            connection.execute(
                "UPDATE syllabi SET superseded_at = ? WHERE id = ?", (now, current["id"])
            )
            stale_rows = connection.execute(
                "UPDATE syllabus_alignments SET stale = 1 WHERE syllabus_id = ? AND stale = 0",
                (current["id"],),
            ).rowcount
        result = {
            "syllabus_id": syllabus_id, "series_id": series_id, "revision": revision,
            "content_sha256": digest, "bytes": len(raw), "state": "stored",
            "extraction": {"source_kind": validated["source_kind"],
                           "characters": len(validated["text"] or "")},
        }
        _remember(connection, key, method, _payload_hash(method, payload),
                  envelope.get("operation_id", ""), 0, result)
    return 0, result


@_handler("syllabus.get")
def syllabus_get(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    with db.read() as connection:
        row = _syllabus_row(connection, payload["syllabus_id"], payload.get("revision"))
        file_row = connection.execute(
            "SELECT size FROM syllabus_files WHERE syllabus_id = ?", (row["id"],)
        ).fetchone()
        blocks = []
        if payload.get("include_blocks"):
            for block in connection.execute(
                "SELECT * FROM syllabus_blocks WHERE syllabus_id = ? ORDER BY ordinal", (row["id"],)
            ):
                blocks.append({
                    "block_id": block["id"], "ordinal": int(block["ordinal"]), "kind": block["kind"],
                    "label": block["label"], "page": block["page"], "line_start": block["line_start"],
                    "line_end": block["line_end"], "text": block["text"],
                })
        run = connection.execute(
            "SELECT * FROM syllabus_parse_runs WHERE syllabus_id = ? ORDER BY created_at DESC LIMIT 1",
            (row["id"],),
        ).fetchone()
        items = []
        for item in connection.execute(
            "SELECT * FROM syllabus_items WHERE syllabus_id = ? ORDER BY ordinal", (row["id"],)
        ):
            value = _load(item["value_json"], {})
            items.append({
                **value,
                "item_id": item["id"],
                "kind": item["kind"],
                "title": item["title"],
                "ordinal": int(item["ordinal"]),
                "week_ordinal": item["week_ordinal"],
            })
        coverage = _load(run["coverage_json"], {}) if run is not None else {}
        validation = _load(run["validation_json"], {}) if run is not None else {}
        unknowns = [str(item.get("kind")) for item in items if item.get("state") == "unknown"]
        view = {
            "syllabus": _syllabus_view(row, file_row),
            "blocks": blocks,
            "items": items,
            "parse_run": ({"parse_run_id": run["id"], "schema": run["schema"], "state": run["state"],
                           "provider": run["provider"], "model": run["model"],
                           "created_at": run["created_at"], "validation": validation}
                          if run is not None else None),
            "coverage": coverage,
            "unknowns": unknowns,
        }
    return 0, view


@_handler("syllabus.parse")
def syllabus_parse(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Enqueue the parse stage. The stage is local and deterministic and sends no text anywhere."""
    db.ensure_schema()
    if payload.get("egress_acknowledged") is not True:
        raise RpcError.of(
            "VALIDATION_FAILED",
            "syllabus.parse requires egress_acknowledged: true after the disclosure.",
            field="egress_acknowledged",
        )
    with db.transaction() as connection:
        row = _syllabus_row(connection, payload["syllabus_id"], payload["revision"])
        result = job_service.create(
            "import",
            {
                "stage": "syllabus_parse", "syllabus_id": row["id"],
                "revision": int(row["revision"]), "egress_acknowledged": True,
            },
            operation_id=f"cb-syllabus-parse-{row['id']}-{int(row['revision'])}-{row['content_sha256']}",
            connection=connection,
        )
    return 0, {"job_id": result["job_id"], "state": result["state"]}


@_handler("syllabus.align")
def syllabus_align(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    with db.transaction() as connection:
        row = _syllabus_row(connection, payload["syllabus_id"], payload["revision"])
        binding = connection.execute(
            "SELECT * FROM course_syllabi WHERE course_id = ?", (payload["course_id"],)
        ).fetchone()
        if binding is None:
            raise RpcError.of("NOT_FOUND", "this course has no bound syllabus.", course_id=payload["course_id"])
        key = f"cb-syllabus-align-{payload['course_id']}-{row['id']}-{int(row['revision'])}-{payload['plan_id']}"
        existing = connection.execute(
            "SELECT id, state FROM jobs WHERE operation_id = ? ORDER BY created_at LIMIT 1", (key,)
        ).fetchone()
        if existing is not None:
            return 0, {"job_id": existing["id"], "state": existing["state"],
                       "alignment_revision": int(binding["alignment_revision"])}
        result = job_service.create(
            "import",
            {
                "stage": "syllabus_align", "syllabus_id": row["id"], "revision": int(row["revision"]),
                "course_id": payload["course_id"], "plan_id": payload["plan_id"],
            },
            operation_id=key,
            connection=connection,
        )
        alignment_revision = int(binding["alignment_revision"]) + 1
    return 0, {"job_id": result["job_id"], "state": result["state"],
               "alignment_revision": alignment_revision}


def _alignment_view(connection, course_id: str, syllabus_id: str, revision: int) -> dict[str, Any]:
    binding = connection.execute(
        "SELECT * FROM course_syllabi WHERE course_id = ?", (course_id,)
    ).fetchone()
    if binding is None:
        raise RpcError.of("NOT_FOUND", "this course has no bound syllabus.", course_id=course_id)
    rows = connection.execute(
        "SELECT * FROM syllabus_alignments WHERE course_id = ? AND syllabus_revision = ?"
        " ORDER BY rowid", (course_id, revision),
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        evidence = _load(row["evidence_json"], {})
        items.append({
            "item_id": row["item_id"], "kind": row["item_id"], "title": None,
            "value_state": "extracted", "state": row["state"], "reason_code": row["reason_code"],
            "target_kind": row["target_kind"], "target_id": row["target_id"],
            "anchors": _load(row["evidence_json"], {}).get("syllabus_anchors") or [],
            "review_state": row["review_state"], "stale": bool(row["stale"]), "evidence": evidence,
        })
    # Unknown-valued items are listed as unknown and never mapped to a target.
    mapped = {item["item_id"] for item in items}
    for item in connection.execute(
        "SELECT * FROM syllabus_items WHERE syllabus_id = ? AND value_state <> 'extracted' ORDER BY ordinal",
        (syllabus_id,),
    ):
        if item["id"] in mapped:
            continue
        items.append({
            "item_id": item["id"], "kind": item["kind"], "title": item["title"],
            "value_state": item["value_state"], "state": "unknown", "reason_code": "value_unknown",
            "target_kind": None, "target_id": None, "anchors": _load(item["anchors_json"], []),
            "review_state": "pending", "stale": False, "evidence": {},
        })
    # Fill kind/title from the item rows for mapped entries.
    details = {
        row["id"]: row
        for row in connection.execute("SELECT * FROM syllabus_items WHERE syllabus_id = ?", (syllabus_id,))
    }
    for item in items:
        source = details.get(item["item_id"])
        if source is not None:
            item["kind"] = source["kind"]
            item["title"] = source["title"]
            item["value_state"] = source["value_state"]
    counts = {state: 0 for state in ("aligned", "partial", "unmatched", "conflict", "unknown", "stale")}
    for item in items:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
        if item["stale"] and item["state"] != "stale":
            counts["stale"] += 1
    stale = any(item["stale"] for item in items) or int(binding["syllabus_revision"]) != int(revision)
    return {
        "alignment_revision": int(binding["alignment_revision"]),
        "reviewed_revision": binding["reviewed_revision"],
        "stale": bool(stale),
        "items": items,
        "counts": counts,
    }


@_handler("syllabus.alignment.get")
def syllabus_alignment_get(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    db.ensure_schema()
    with db.read() as connection:
        return 0, _alignment_view(connection, payload["course_id"], payload["syllabus_id"], payload["revision"])


@_handler("syllabus.alignment.review")
def syllabus_alignment_review(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Record the learner's decisions, fenced to the alignment revision. Never resolves a conflict."""
    db.ensure_schema()
    with db.transaction() as connection:
        row = _syllabus_row(connection, payload["syllabus_id"], payload["revision"])
        binding = connection.execute(
            "SELECT * FROM course_syllabi WHERE course_id = ?", (payload["course_id"],)
        ).fetchone()
        if binding is None:
            raise RpcError.of("NOT_FOUND", "this course has no bound syllabus.", course_id=payload["course_id"])
        if int(binding["alignment_revision"]) != int(payload["alignment_revision"]):
            raise RpcError.of(
                "STALE_REVISION", "the alignment moved on; re-read it before reviewing.",
                current_revision=int(binding["alignment_revision"]),
            )
        decisions = payload["decisions"]
        if not decisions:
            # v13 H-26b: an empty decision set is a checked claim, not a shortcut. It means "the
            # reviewed this mapping and accepted every row as aligned", so it is legal only when
            # there is no non-aligned, non-stale row left to acknowledge. ``unmatched`` and
            # ``partial`` do not block ``reviewed_revision`` below, so without this guard a caller
            # could claim review without ever seeing them.
            reviewable = connection.execute(
                "SELECT state, COUNT(*) AS n FROM syllabus_alignments WHERE course_id = ?"
                " AND syllabus_revision = ? AND stale = 0"
                " AND state IN ('partial', 'unmatched', 'conflict', 'stale') GROUP BY state",
                (payload["course_id"], row["revision"]),
            ).fetchall()
            owed = {str(entry["state"]): int(entry["n"]) for entry in reviewable}
            stale_rows = connection.execute(
                "SELECT COUNT(*) AS n FROM syllabus_alignments WHERE course_id = ? AND stale = 1",
                (payload["course_id"],),
            ).fetchone()["n"]
            if owed or int(stale_rows) > 0:
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    "this mapping has rows that need a decision; an empty decision set is only"
                    " allowed when every row is aligned.",
                    field="decisions",
                    alignment_revision=int(binding["alignment_revision"]),
                    conflict=owed.get("conflict", 0),
                    partial=owed.get("partial", 0),
                    unmatched=owed.get("unmatched", 0),
                    stale=int(owed.get("stale", 0)) + int(stale_rows),
                )
        plan_replan_required = False
        for decision in decisions:
            alignment = connection.execute(
                "SELECT * FROM syllabus_alignments WHERE course_id = ? AND syllabus_revision = ?"
                " AND item_id = ? ORDER BY rowid DESC LIMIT 1",
                (payload["course_id"], row["revision"], decision["item_id"]),
            ).fetchone()
            if alignment is None:
                raise RpcError.of(
                    "VALIDATION_FAILED", "that item has no alignment row in this revision.",
                    field="decisions", item_id=decision["item_id"],
                )
            action = decision["action"]
            if action == "request_replan":
                state, review_state = alignment["state"], "replan_requested"
                plan_replan_required = True
            elif action == "accept_divergence":
                if alignment["state"] not in ("conflict", "partial"):
                    raise RpcError.of(
                        "VALIDATION_FAILED", "accept_divergence applies to a conflict or partial row.",
                        item_id=decision["item_id"], state=alignment["state"],
                    )
                state, review_state = "partial", "accepted_divergence"
            elif action == "accept_partial":
                if alignment["state"] not in ("partial", "conflict"):
                    raise RpcError.of(
                        "VALIDATION_FAILED", "accept_partial applies to a partial row.",
                        item_id=decision["item_id"], state=alignment["state"],
                    )
                state, review_state = "partial", "accepted"
            else:  # accept_unmatched
                if alignment["state"] != "unmatched":
                    raise RpcError.of(
                        "VALIDATION_FAILED", "accept_unmatched applies to an unmatched row.",
                        item_id=decision["item_id"], state=alignment["state"],
                    )
                state, review_state = "unmatched", "accepted"
            connection.execute(
                "UPDATE syllabus_alignments SET state = ?, review_state = ? WHERE id = ?",
                (state, review_state, alignment["id"]),
            )
        pending = connection.execute(
            "SELECT COUNT(*) AS n FROM syllabus_alignments WHERE course_id = ? AND syllabus_revision = ?"
            " AND stale = 0 AND state IN ('conflict', 'stale') AND review_state = 'pending'",
            (payload["course_id"], row["revision"]),
        ).fetchone()["n"]
        pending += connection.execute(
            "SELECT COUNT(*) AS n FROM syllabus_alignments WHERE course_id = ? AND stale = 1",
            (payload["course_id"],),
        ).fetchone()["n"]
        reviewed: int | None = int(row["revision"]) if int(pending) == 0 and not plan_replan_required else None
        connection.execute(
            "UPDATE course_syllabi SET reviewed_revision = ?, reviewed_at = ? WHERE course_id = ?",
            (reviewed, NOW() if reviewed is not None else None, payload["course_id"]),
        )
        view = _alignment_view(connection, payload["course_id"], payload["syllabus_id"], payload["revision"])
    return 0, {
        "reviewed_revision": reviewed,
        "counts": view["counts"],
        "plan_replan_required": bool(plan_replan_required),
    }


@_handler("syllabus.delete")
def syllabus_delete(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Delete a syllabus and its derived rows. Refuses while a live companion course is bound."""
    db.ensure_schema()
    with db.transaction() as connection:
        row = _syllabus_row(connection, payload["syllabus_id"])
        bound = connection.execute(
            "SELECT c.id, c.status FROM course_syllabi cs JOIN courses c ON c.id = cs.course_id"
            " WHERE cs.syllabus_id = ? AND c.status NOT IN ('archived', 'deleted')",
            (row["id"],),
        ).fetchall()
        if bound:
            raise RpcError.of(
                "SYLLABUS_IN_USE",
                "this syllabus is bound to a live companion course; archive or delete the course first.",
                course_ids=[item["id"] for item in bound],
            )
        for table in ("syllabus_alignments", "course_syllabi", "syllabus_items",
                      "syllabus_parse_runs", "syllabus_blocks", "syllabus_files"):
            column = "syllabus_id"
            connection.execute(f"DELETE FROM {table} WHERE {column} = ?", (row["id"],))
        connection.execute("DELETE FROM syllabi WHERE id = ?", (row["id"],))
        remaining = connection.execute(
            "SELECT COUNT(*) AS n FROM syllabi WHERE series_id = ?", (row["series_id"],)
        ).fetchone()["n"]
        if int(remaining) == 0:
            connection.execute("DELETE FROM syllabus_series WHERE id = ?", (row["series_id"],))
    return 0, {"deleted": True}


def register() -> None:
    for method, handler in HANDLERS.items():
        api.register_handler(method, handler)


register()
