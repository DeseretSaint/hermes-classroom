"""Content-addressed artifacts and safe media policy.

``PREBUILD_SPEC.md`` §10/§12 and ``AUDIT.md`` R6 are the reasons this module is strict:

* bytes are cached by content hash, and the same spec/source hash reuses them instead of paying a
  provider twice;
* files land through staged write → fsync → atomic rename, then a DB commit — never a "
  write inside a transaction";
* SVG is an allowlisted safe subset (no script, no event handlers, no external references, no
  ``foreignObject``/``image``), PDFs come from a safe template with selectable text, and images
  and audio are sniffed rather than trusted by extension;
* an imported illustration is visibly labelled and never becomes a measurement/procedure
  authority;
* every artifact has a text equivalent. A TTS/image failure leaves the complete text lesson and
  reports an honest degraded state, never a fabricated file.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import textwrap
import unicodedata
import xml.etree.ElementTree as ET
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from . import db

POLICY_VERSION = "media-policy/1"

ILLUSTRATION_LABEL = (
    "Illustration — generated for context only. It is not a measurement, procedure, "
    "technical reference, or safety authority."
)
SCHEMATIC_LABEL = "Deterministic schematic rendered from structured facts."
REFERENCE_LABEL = "Sourced reference — see the cited source and its permission status."

#: Kinds the ``artifacts`` table accepts (``cb.db`` v2).
ARTIFACT_KINDS = ("visual", "audio", "pdf", "pack", "export", "other")

#: A caller-authored hard page break in :func:`make_pdf`. A line list carries it between
#: sections so a printed pack starts the learner page and the answer guide on their own pages.
PAGE_BREAK = "\x0c"

#: ``artifacts.content_hash`` holds a sha256 of the object bytes. Rows written by
#: :meth:`ArtifactStore.record` before H-210-R1 stored the bare 64-hex digest while
#: ``pack.export``/``course.export`` wrote the labelled ``sha256:<64 hex>`` form, so the column is
#: **mixed by history**. The invariant every reader must honour:
#:
#: * write new rows in the labelled form (:func:`labelled_hash`);
#: * read the column only through :func:`labelled_hash` / :func:`bare_hash`, never by string
#:   equality against one convention;
#: * look a row up by digest only through :func:`hash_forms`, so a legacy bare row and a labelled
#:   row still dedupe to one ``(content_hash, kind)`` record.
#:
#: Object files on disk stay named by the bare digest: :attr:`Staged.content_hash` is filesystem
#: identity, not the stored column value.
_SHA256_BARE = re.compile(r"^[a-f0-9]{64}$")


def bare_hash(value: Any) -> str:
    """The bare 64-hex digest of any accepted ``content_hash`` spelling."""
    text = str(value or "").strip()
    return text[7:] if text.startswith("sha256:") else text


def labelled_hash(value: Any) -> str:
    """``sha256:<64 hex>`` for any accepted spelling. Idempotent; never double-prefixes."""
    return "sha256:" + bare_hash(value)


def hash_forms(value: Any) -> tuple[str, str]:
    """Both accepted spellings of one digest, for a ``(content_hash, kind)`` lookup.

    A dedupe query must match either form: the same bytes written by the import media path
    (legacy bare) and by an export (labelled) have to resolve to one row.
    """
    return (bare_hash(value), labelled_hash(value))


#: Roles a media spec may declare. Role, not MIME, decides the honesty label.
MEDIA_ROLES = ("sourced_technical", "schematic", "illustration", "narration", "document", "export")

#: Text-equivalent is mandatory for every artifact a learner can see or hear.
_MIN_TEXT_EQUIVALENT = 1
_MAX_BYTES = {
    "visual": 8 * 1024 * 1024,
    "audio": 64 * 1024 * 1024,
    "pdf": 32 * 1024 * 1024,
    "pack": 64 * 1024 * 1024,
    "export": 64 * 1024 * 1024,
    "other": 64 * 1024 * 1024,
}

#: MIME → magic-byte test. Extensions and client-supplied types are never trusted alone.
_MAGIC: dict[str, tuple[bytes, ...]] = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/webp": (b"RIFF",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "audio/wav": (b"RIFF",),
    "audio/mpeg": (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
    "audio/ogg": (b"OggS",),
    "application/pdf": (b"%PDF-",),
}
_RENDERABLE_MIME = (
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "audio/wav",
    "audio/mpeg",
    "audio/ogg",
    "application/pdf",
    "image/svg+xml",
)

#: SVG allowlist. Anything else is removed (or rejects the document when it is structural).
SVG_ALLOWED_TAGS = {
    "svg", "g", "title", "desc", "defs", "symbol", "use",
    "rect", "circle", "ellipse", "line", "polyline", "polygon", "path",
    "text", "tspan", "linearGradient", "radialGradient", "stop", "clipPath",
}
SVG_FORBIDDEN_TAGS = {
    "script", "foreignObject", "iframe", "object", "embed", "audio", "video",
    "image", "animate", "animateTransform", "animateMotion", "set", "handler",
    "style", "link", "meta", "base",
}
SVG_ALLOWED_ATTRS = {
    "id", "class", "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2",
    "cx", "cy", "r", "rx", "ry", "d", "points", "fill", "fill-opacity", "fill-rule",
    "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray",
    "opacity", "transform", "font-family", "font-size", "font-weight", "text-anchor",
    "dominant-baseline", "role", "aria-label", "offset", "stop-color", "stop-opacity",
    "gradientUnits", "clipPathUnits", "href", "preserveAspectRatio", "xmlns",
}


class UnsafeMedia(ValueError):
    """Bytes violate the media policy. Never downgraded to a warning."""

    code = "POLICY_VIOLATION"


class MediaUnavailable(RuntimeError):
    """A provider/voice/model could not produce the artifact. Callers use the text fallback."""

    code = "GRADER_UNAVAILABLE"

    def __init__(self, reason: str, *, triage: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.triage = triage or {}


def _now(moment: datetime | None = None) -> datetime:
    return moment or datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def spec_hash(value: Any) -> str:
    """Hash of the request/spec that produced an artifact (cache key component)."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def source_hash(source_texts: Iterable[str]) -> str:
    """Hash of the ordered source material an artifact depends on (cache key component)."""
    digest = hashlib.sha256()
    for text in source_texts:
        digest.update(str(text).encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


# ── media policy ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MediaSpec:
    """What the author asked for. Validating this is cheaper than rejecting rendered bytes."""

    kind: str
    role: str
    text_equivalent: str
    prompt: str | None = None
    source_ids: tuple[str, ...] = ()
    permission: str | None = None
    voice: str | None = None
    language: str | None = None
    transcript: str | None = None
    technical: bool = False
    facts: dict[str, Any] = field(default_factory=dict)

    def as_cache_spec(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "role": self.role,
            "text_equivalent": self.text_equivalent,
            "prompt": self.prompt,
            "source_ids": list(self.source_ids),
            "permission": self.permission,
            "voice": self.voice,
            "language": self.language,
            "technical": self.technical,
            "facts": self.facts,
            "policy": POLICY_VERSION,
        }


def media_problems(spec: MediaSpec) -> list[str]:
    problems: list[str] = []
    if spec.kind not in ARTIFACT_KINDS:
        problems.append(f"unknown artifact kind {spec.kind!r}")
    if spec.role not in MEDIA_ROLES:
        problems.append(f"unknown media role {spec.role!r}")
    if len(spec.text_equivalent.strip()) < _MIN_TEXT_EQUIVALENT:
        problems.append("every artifact needs a text equivalent")
    if spec.role == "illustration" and spec.technical:
        problems.append("an illustration may not claim technical authority")
    if spec.role == "sourced_technical":
        if not spec.source_ids:
            problems.append("sourced technical reference needs at least one cited source")
        if spec.permission not in ("public_domain", "licensed", "linked", "unknown"):
            problems.append("sourced reference needs an explicit permission status")
        if spec.permission == "unknown":
            problems.append("unknown permission cannot be presented as a technical reference")
    if spec.role == "schematic" and not spec.facts:
        problems.append("a schematic must be rendered from structured facts, not free text")
    if spec.role == "narration":
        if not spec.transcript:
            problems.append("narration needs its transcript (the text equivalent)")
        if not spec.voice or not spec.language:
            problems.append("narration needs voice and language metadata")
    if spec.kind == "audio" and spec.role not in ("narration",):
        problems.append("audio is only supported as narration in this build")
    return problems


def assert_media_ok(spec: MediaSpec) -> None:
    problems = media_problems(spec)
    if problems:
        raise UnsafeMedia("; ".join(problems))


def honesty_label(spec: MediaSpec) -> str:
    if spec.role == "illustration":
        return ILLUSTRATION_LABEL
    if spec.role == "schematic":
        return SCHEMATIC_LABEL
    if spec.role == "sourced_technical":
        return REFERENCE_LABEL
    if spec.role == "narration":
        return "Narration — the transcript is the authoritative text; this is not pronunciation assessment."
    return "Coursebook-generated document."


# ── byte validation ─────────────────────────────────────────────────────────


def sniff_mime(data: bytes, declared: str | None = None) -> str:
    """Detect MIME from magic bytes; reject when the declared type contradicts the bytes."""
    head = data[:64]
    found = None
    if head.startswith(b"%PDF-"):
        found = "application/pdf"
    elif head.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        found = "image/webp"
    elif head.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WAVE":
        found = "audio/wav"
    else:
        for mime, magics in _MAGIC.items():
            if any(head.startswith(magic) for magic in magics):
                found = mime
                break
    if found is None and (declared == "image/svg+xml" or head.lstrip().startswith(b"<svg")):
        found = "image/svg+xml"
    if found is None:
        raise UnsafeMedia("bytes do not match any allowed media type")
    if declared and declared not in ("application/octet-stream", found):
        raise UnsafeMedia(f"declared {declared!r} but bytes are {found!r}")
    return found


def assert_render_safe(data: bytes, mime: str) -> None:
    """No active content is ever handed to a renderer."""
    if mime not in _RENDERABLE_MIME:
        raise UnsafeMedia(f"{mime} is not a render-safe media type")
    if mime == "image/svg+xml":
        sanitize_svg(data)


# ── SVG: safe subset only ───────────────────────────────────────────────────


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sanitize_svg(raw: bytes | str) -> bytes:
    """Return a sanitized SVG document or raise :class:`UnsafeMedia`.

    Rejecting is deliberate: rewriting an author's diagram into something that merely parses
    could silently change meaning. Only a structurally clean, allowlisted document is adopted.
    """
    text = raw.decode("utf-8", "strict") if isinstance(raw, bytes) else raw
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise UnsafeMedia("SVG must not declare a doctype or entities")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise UnsafeMedia(f"SVG does not parse: {exc}") from exc
    if _local(root.tag) != "svg":
        raise UnsafeMedia("root element is not <svg>")

    def walk(node: ET.Element) -> None:
        tag = _local(node.tag)
        if tag in SVG_FORBIDDEN_TAGS or tag not in SVG_ALLOWED_TAGS:
            raise UnsafeMedia(f"SVG element {tag!r} is not in the safe subset")
        for name, value in node.attrib.items():
            attr = _local(name)
            if attr.startswith("on"):
                raise UnsafeMedia(f"SVG event handler {attr!r} is active content")
            if attr not in SVG_ALLOWED_ATTRS:
                raise UnsafeMedia(f"SVG attribute {attr!r} is not allowlisted")
            lowered_value = str(value).lower()
            if attr == "href" and not str(value).startswith("#"):
                raise UnsafeMedia("SVG may only reference internal fragments")
            if "url(" in lowered_value and "url(#" not in lowered_value:
                raise UnsafeMedia("SVG may not reference external resources")
            if "javascript:" in lowered_value or lowered_value.strip().startswith(("http:", "https:", "data:")):
                raise UnsafeMedia("SVG contains an external or active reference")
        for child in list(node):
            walk(child)

    walk(root)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    return ET.tostring(root, encoding="utf-8", xml_declaration=False)


def make_schematic_svg(title: str, facts: Sequence[dict[str, Any]], *, width: int = 640) -> bytes:
    """Render structured facts as a deterministic, safe-subset SVG.

    Only typed facts are drawn; nothing is inferred from prose. ``facts`` items are
    ``{"label": str, "value": str, "row": int}``.
    """
    rows = sorted(facts, key=lambda item: (int(item.get("row", 0)), str(item.get("label", ""))))
    height = 90 + 34 * max(1, len(rows))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{_escape(title)}">',
        f"<title>{_escape(title)}</title>",
        f"<desc>{_escape(SCHEMATIC_LABEL)}</desc>",
        f'<text x="24" y="40" font-family="sans-serif" font-size="20" fill="#111">{_escape(title)}</text>',
        '<line x1="24" y1="56" x2="' + str(width - 24) + '" y2="56" stroke="#999" stroke-width="1"/>',
    ]
    for index, item in enumerate(rows):
        y = 86 + 34 * index
        parts.append(
            f'<text x="24" y="{y}" font-family="sans-serif" font-size="15" fill="#111">'
            f"{_escape(str(item.get('label', '')))}</text>"
        )
        parts.append(
            f'<text x="{width - 24}" y="{y}" text-anchor="end" font-family="sans-serif" '
            f'font-size="15" fill="#333">{_escape(str(item.get("value", "")))}</text>'
        )
    parts.append("</svg>")
    return sanitize_svg("".join(parts))


def _escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ── PDF: safe template with selectable text ────────────────────────────────


class UnprintableText(ValueError):
    """Raised when a string cannot be represented in the built-in WinAnsi print font.

    The print template embeds no font program, so it can only draw the WinAnsi character set.
    Silently replacing other characters with ``?`` would corrupt the lesson; callers must handle
    this and refuse by name instead.
    """

    def __init__(self, value: str) -> None:
        self.value = str(value)
        self.characters = "".join(sorted({char for char in self.value if not _is_winansi(char)}))
        super().__init__(f"the print font cannot render {self.characters!r}")


def _is_winansi(char: str) -> bool:
    try:
        char.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return True


def _pdf_text(value: str, *, strict: bool = False) -> str:
    """WinAnsi text for the built-in Helvetica font.

    With ``strict`` the text is NFC-normalised and must encode through cp1252; anything outside
    that repertoire raises :class:`UnprintableText` rather than being replaced by ``?``. The
    take-home print path opts in to that refusal. Legacy callers keep the historical ASCII fold,
    so their existing bytes and behaviour are unchanged.
    """
    text = str(value)
    if strict:
        text = unicodedata.normalize("NFC", text)
        try:
            text.encode("cp1252")
        except UnicodeEncodeError as exc:
            raise UnprintableText(text) from exc
    else:
        text = unicodedata.normalize("NFKD", text).encode("ascii", "replace").decode("ascii")
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def _styled_body(lines: Sequence[str], *, max_chars: int) -> list[tuple[str, str, int]]:
    """Resolve Markdown heading markers to (text, font, size) print lines.

    ``#``/``##`` markers never reach the page: a level-1 heading is set in Helvetica-Bold 16,
    a deeper heading in Helvetica-Bold 12, and body copy in Helvetica 12. Wrapping accounts for
    the narrower character width of a larger face.
    """
    body: list[tuple[str, str, int]] = []
    for line in lines:
        text = str(line)
        if text == PAGE_BREAK:
            body.append((PAGE_BREAK, "", 0))
            continue
        if not text:
            body.append(("", "F1", 12))
            continue
        font, size = "F1", 12
        match = _MARKDOWN_HEADING.match(text)
        if match:
            text = match.group(2)
            font = "F2"
            size = 16 if len(match.group(1)) == 1 else 12
        width = max(8, int(max_chars * 12 / size))
        for chunk in textwrap.wrap(text, width=width, break_long_words=True,
                                   break_on_hyphens=False) or [""]:
            body.append((chunk, font, size))
    return body


def make_pdf(title: str, lines: Sequence[str], *, page_width: int = 612, page_height: int = 792,
             max_chars: int = 88, headings: bool = False, strict_font: bool = False) -> bytes:
    """Build a minimal, valid PDF from a fixed template. Text is selectable/extractable.

    ``max_chars`` bounds one drawn line so it fits inside the printable width for the chosen
    page size; the default keeps the historical Letter handout behaviour, and a caller printing
    a narrower page or a denser document passes a smaller value. This intentionally supports
    only what a lesson handout needs: a title and wrapped body lines, plus an explicit
    :data:`PAGE_BREAK` marker. No JavaScript, no attachments, no external references, no
    auto-open links.

    With ``headings=True`` a leading Markdown ``#``/``##`` marker is converted into a real
    typographic heading (Helvetica-Bold, stepped size) instead of printing the marker literally.
    ``strict_font=True`` makes unrepresentable characters raise :class:`UnprintableText` instead
    of being folded to ``?``; the take-home print path opts in.
    """
    margin = 56
    leading = 16
    if headings:
        # The title is a real H1: set in bold 16 pt and wrapped through the same width-aware path
        # as the body so a long pack title never runs off the printable edge.
        title_text = " ".join(str(title).split())
        title_width = max(8, int(max_chars * 12 / 16))
        body: list[tuple[str, str, int]] = [
            (chunk, "F2", 16)
            for chunk in textwrap.wrap(
                title_text, width=title_width, break_long_words=True, break_on_hyphens=False
            )
            or [""]
        ]
        body.extend(_styled_body(lines, max_chars=max_chars))
    else:
        raw: list[str] = [title]
        for line in lines:
            text = str(line)
            if text == PAGE_BREAK:
                raw.append(PAGE_BREAK)
                continue
            if not text:
                raw.append("")
                continue
            # Wrap on word boundaries so a printed handout never splits a word across lines. A
            # word longer than the line is broken (there is no choice), but ordinary prose is not.
            for chunk in textwrap.wrap(text, width=max_chars, break_long_words=True,
                                       break_on_hyphens=False) or [""]:
                raw.append(chunk)
        body = [(line, "F1", 12) for line in raw]

    pages: list[list[tuple[str, str, int]]] = []
    current: list[tuple[str, str, int]] = []
    per_page = (page_height - 2 * margin) // leading
    for item in body:
        if item[0] == PAGE_BREAK:
            if current:
                pages.append(current)
            current = []
            continue
        if len(current) >= per_page:
            pages.append(current)
            current = []
        current.append(item)
    if current:
        pages.append(current)
    if not pages:
        pages = [[("", "F1", 12)]]

    objects: list[str] = []
    # 1 catalog, 2 pages, 3 body font, optionally 4 bold font, then each page + content pair.
    page_ids = []
    next_id = 5 if headings else 4
    for _page in pages:
        page_ids.append(next_id)
        next_id += 2
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    if headings:
        objects.append(
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        )
        resources = "/Font << /F1 3 0 R /F2 4 0 R >>"
    else:
        resources = "/Font << /F1 3 0 R >>"
    for index, page in enumerate(pages):
        page_id = page_ids[index]
        content_id = page_id + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << {resources} >> /Contents {content_id} 0 R >>"
        )
        if headings:
            commands = ["BT", f"{leading} TL", f"{margin} {page_height - margin} Td"]
            for text, font, size in page:
                commands.append(f"/{font} {size} Tf")
                commands.append(f"({_pdf_text(text, strict=strict_font)}) Tj")
                commands.append("T*")
        else:
            commands = ["BT", f"/F1 12 Tf", f"{leading} TL", f"{margin} {page_height - margin} Td"]
            for text, _font, _size in page:
                commands.append(f"({_pdf_text(text, strict=strict_font)}) Tj")
                commands.append("T*")
        commands.append("ET")
        stream = "\n".join(commands)
        objects.append(f"<< /Length {len(stream.encode('cp1252'))} >>\nstream\n{stream}\nendstream")

    out = io.StringIO()
    out.write("%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for number, body_text in enumerate(objects, start=1):
        offsets.append(len(out.getvalue().encode("cp1252")))
        out.write(f"{number} 0 obj\n{body_text}\nendobj\n")
    xref = len(out.getvalue().encode("cp1252"))
    out.write(f"xref\n0 {len(objects) + 1}\n")
    out.write("0000000000 65535 f \n")
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n")
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    )
    data = out.getvalue().encode("cp1252")
    if not data.startswith(b"%PDF-"):
        raise UnsafeMedia("PDF template produced invalid bytes")
    return data


# ── store ───────────────────────────────────────────────────────────────────


@dataclass
class Staged:
    data: bytes
    kind: str
    mime: str
    content_hash: str
    path: Path
    adopted_path: Path | None = None

    @property
    def bytes(self) -> int:
        return len(self.data)


def default_root() -> Path:
    return db.database_path().parent / "artifacts"


def read_root() -> Path:
    """The artifact store root resolved **without creating anything**.

    Read paths (preview, download containment) use this one: a refused or missing artifact must
    leave the filesystem exactly as it found it. Same directory as :func:`default_root`.
    """
    return db.store_root() / "artifacts"


class ArtifactStore:
    """Content-addressed object store plus the DB rows that make it discoverable."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_root()
        self.staging_dir = self.root / "staging"
        self.objects_dir = self.root / "objects"

    # -- writes (always outside a transaction) -------------------------------

    def stage(self, data: bytes, *, kind: str, mime: str) -> Staged:
        if kind not in ARTIFACT_KINDS:
            raise UnsafeMedia(f"unknown artifact kind {kind!r}")
        if len(data) > _MAX_BYTES[kind]:
            raise UnsafeMedia(f"{kind} artifact exceeds its size ceiling")
        detected = sniff_mime(data, mime)
        if kind == "visual" and detected not in ("image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml"):
            raise UnsafeMedia(f"{detected} is not a visual artifact type")
        if kind == "audio" and detected not in ("audio/wav", "audio/mpeg", "audio/ogg"):
            raise UnsafeMedia(f"{detected} is not an audio artifact type")
        if kind == "pdf" and detected != "application/pdf":
            raise UnsafeMedia("pdf artifacts must be real PDF bytes")
        assert_render_safe(data, detected)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        staged_path = self.staging_dir / f"{uuid.uuid4().hex}.part"
        with open(staged_path, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return Staged(
            data=data,
            kind=kind,
            mime=detected,
            content_hash=sha256_bytes(data),
            path=staged_path,
        )

    def adopt(self, staged: Staged) -> Path:
        """Atomic rename into the content-addressed tree. Idempotent by hash."""
        target_dir = self.objects_dir / staged.content_hash[:2]
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / staged.content_hash
        if target.exists():
            existing = target.read_bytes()
            if sha256_bytes(existing) != staged.content_hash:
                raise UnsafeMedia("content-addressed object collided with different bytes")
            staged.path.unlink(missing_ok=True)
        else:
            os.replace(staged.path, target)
            self._fsync_dir(target_dir)
        staged.adopted_path = target
        return target

    @staticmethod
    def _fsync_dir(directory: Path) -> None:
        try:
            handle = os.open(directory, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(handle)
        finally:
            os.close(handle)

    def discard(self, staged: Staged) -> None:
        staged.path.unlink(missing_ok=True)

    # -- DB rows -------------------------------------------------------------

    def record(
        self,
        connection,
        *,
        course_id: str | None,
        staged: Staged,
        provenance: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Insert the artifact metadata in the caller's transaction.

        The bytes are already adopted, so a rollback leaves an unreferenced object that startup
        reconciliation removes; the reverse order would leave a row pointing at no file.
        """
        stamp = _iso(_now(now))
        bare = bare_hash(staged.content_hash)
        if not _SHA256_BARE.match(bare):
            raise UnsafeMedia("artifact content hash is not a sha256 digest")
        # A legacy row holds the bare digest; new rows hold the labelled form. Match both so the
        # same bytes never become two rows on a store written across the H-210-R1 repair.
        existing = connection.execute(
            "SELECT * FROM artifacts WHERE content_hash IN (?, ?) AND kind = ?",
            (*hash_forms(bare), staged.kind),
        ).fetchone()
        if existing is not None:
            connection.execute(
                "UPDATE artifacts SET ref_count = ref_count + 1 WHERE id = ?", (existing["id"],)
            )
            return artifact_view(existing, ref_bump=1)
        artifact_id = f"art_{uuid.uuid4().hex}"
        path = str(staged.adopted_path)
        connection.execute(
            "INSERT INTO artifacts (id, course_id, kind, content_hash, path, bytes, mime,"
            " provenance_json, ref_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
            (
                artifact_id,
                course_id,
                staged.kind,
                labelled_hash(bare),
                path,
                staged.bytes,
                staged.mime,
                json.dumps(provenance, ensure_ascii=False, sort_keys=True),
                stamp,
            ),
        )
        row = connection.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return artifact_view(row)

    def save(
        self,
        *,
        course_id: str | None,
        kind: str,
        data: bytes,
        mime: str,
        provenance: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Stage + adopt (no transaction), then record metadata in one transaction."""
        staged = self.stage(data, kind=kind, mime=mime)
        try:
            self.adopt(staged)
        except BaseException:
            self.discard(staged)
            raise
        with db.transaction() as connection:
            return self.record(connection, course_id=course_id, staged=staged, provenance=provenance, now=now)

    # -- cache ---------------------------------------------------------------

    def lookup(
        self,
        connection,
        *,
        kind: str,
        content_hash: str | None = None,
        spec_fingerprint: str | None = None,
        source_fingerprint: str | None = None,
    ) -> dict[str, Any] | None:
        """Find a reusable artifact by content, spec, or source hash.

        A spec/source match without the same content hash is only returned when the caller asked
        for it explicitly (``content_hash is None``), so a changed spec can never silently reuse
        stale bytes.
        """
        row = None
        if content_hash:
            # ``content_hash`` may arrive bare (a legacy caller) or labelled (a digest). Match both
            # stored spellings; see the module invariant above.
            row = connection.execute(
                "SELECT * FROM artifacts WHERE content_hash IN (?, ?) AND kind = ?",
                (*hash_forms(content_hash), kind),
            ).fetchone()
        if row is None and spec_fingerprint and source_fingerprint:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE kind = ?"
                " AND json_extract(provenance_json, '$.spec_hash') = ?"
                " AND json_extract(provenance_json, '$.source_hash') = ?"
                " ORDER BY created_at DESC LIMIT 1",
                (kind, spec_fingerprint, source_fingerprint),
            ).fetchone()
        if row is None and spec_fingerprint and not source_fingerprint:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE kind = ? AND json_extract(provenance_json, '$.spec_hash') = ?"
                " ORDER BY created_at DESC LIMIT 1",
                (kind, spec_fingerprint),
            ).fetchone()
        if row is None and source_fingerprint and not spec_fingerprint:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE kind = ? AND json_extract(provenance_json, '$.source_hash') = ?"
                " ORDER BY created_at DESC LIMIT 1",
                (kind, source_fingerprint),
            ).fetchone()
        return artifact_view(row) if row is not None else None

    # -- reconciliation ------------------------------------------------------

    def reconcile(self, *, now: datetime | None = None, max_age_seconds: int = 3600) -> dict[str, int]:
        """Remove stale staging files and unreferenced objects. Never touches a referenced file."""
        moment = _now(now)
        removed_staging = 0
        removed_objects = 0
        if self.staging_dir.is_dir():
            for path in self.staging_dir.iterdir():
                if not path.is_file():
                    continue
                age = moment.timestamp() - path.stat().st_mtime
                if age >= max_age_seconds:
                    path.unlink(missing_ok=True)
                    removed_staging += 1
        referenced: set[Path] = set()
        with db.read() as connection:
            for row in connection.execute("SELECT path FROM artifacts"):
                referenced.add(Path(str(row["path"])).resolve())
        if self.objects_dir.is_dir():
            for path in self.objects_dir.rglob("*"):
                if not path.is_file():
                    continue
                if path.resolve() in referenced:
                    continue
                age = moment.timestamp() - path.stat().st_mtime
                if age >= max_age_seconds:
                    path.unlink(missing_ok=True)
                    removed_objects += 1
        return {"staging": removed_staging, "objects": removed_objects}


def artifact_view(row: Any, *, ref_bump: int = 0) -> dict[str, Any]:
    provenance = json.loads(row["provenance_json"] or "{}")
    return {
        "artifact_id": row["id"],
        "course_id": row["course_id"],
        "kind": row["kind"],
        "content_hash": labelled_hash(row["content_hash"]),
        "bytes": int(row["bytes"]),
        "mime": row["mime"],
        "provenance": provenance,
        "ref_count": int(row["ref_count"]) + ref_bump,
        "created_at": row["created_at"],
    }


# ── render + fallback integration ──────────────────────────────────────────


def media_marker(artifact: dict[str, Any], *, path: str | None = None) -> str:
    """The one line a renderer area consumes. Relative-by-handle, never a channel to arbitrary I/O."""
    if artifact["mime"] not in _RENDERABLE_MIME:
        raise UnsafeMedia(f"{artifact['mime']} is not renderable")
    location = path or artifact.get("path")
    if not location:
        raise UnsafeMedia("artifact has no adopted path to render")
    return f"MEDIA: {location}"


@dataclass
class MediaOutcome:
    artifact: dict[str, Any] | None
    text_equivalent: str
    degraded: bool
    reason: str | None = None
    triage: dict[str, Any] = field(default_factory=dict)
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact": self.artifact,
            "text_equivalent": self.text_equivalent,
            "degraded": self.degraded,
            "reason": self.reason,
            "triage": self.triage,
            "label": self.label,
        }


VOICE_TRIAGE_OPTIONS = (
    "keep_cached_original",
    "use_text_fallback",
    "choose_new_voice",
)


def voice_triage(voice: str | None, language: str | None, reason: str) -> dict[str, Any]:
    """Offer the three honest recovery choices; never substitute a narrator silently."""
    return {
        "voice": voice,
        "language": language,
        "reason": reason,
        "options": list(VOICE_TRIAGE_OPTIONS),
        "silent_substitution": False,
    }


def produce_with_fallback(
    store: ArtifactStore,
    spec: MediaSpec,
    producer: Callable[[], bytes],
    *,
    course_id: str | None,
    mime: str,
    provenance: dict[str, Any] | None = None,
    cached: dict[str, Any] | None = None,
) -> MediaOutcome:
    """Generate media, or return the complete text fallback with an honest reason.

    A cached original is reused when the provider is unavailable and the caller has one
    (``keep_cached_original``); otherwise the text equivalent is the artifact.
    """
    assert_media_ok(spec)
    label = honesty_label(spec)
    metadata = dict(provenance or {})
    metadata.update(
        {
            "role": spec.role,
            "label": label,
            "text_equivalent": spec.text_equivalent,
            "spec_hash": spec_hash(spec.as_cache_spec()),
            "policy": POLICY_VERSION,
            "source_ids": list(spec.source_ids),
            "permission": spec.permission,
            "voice": spec.voice,
            "language": spec.language,
        }
    )
    try:
        data = producer()
    except MediaUnavailable as exc:
        triage = exc.triage or voice_triage(spec.voice, spec.language, str(exc))
        if cached is not None:
            return MediaOutcome(
                artifact=cached,
                text_equivalent=spec.text_equivalent,
                degraded=True,
                reason=f"provider unavailable ({exc}); kept the cached original",
                triage=triage,
                label=label,
            )
        return MediaOutcome(
            artifact=None,
            text_equivalent=spec.text_equivalent,
            degraded=True,
            reason=f"provider unavailable ({exc}); delivered as text",
            triage=triage,
            label=label,
        )
    except Exception as exc:  # noqa: BLE001 - any provider failure degrades, never fabricates
        return MediaOutcome(
            artifact=None,
            text_equivalent=spec.text_equivalent,
            degraded=True,
            reason=f"media generation failed ({type(exc).__name__}); delivered as text",
            triage=voice_triage(spec.voice, spec.language, str(exc)),
            label=label,
        )
    artifact = store.save(
        course_id=course_id,
        kind=spec.kind,
        data=data,
        mime=mime,
        provenance=metadata,
    )
    return MediaOutcome(
        artifact=artifact,
        text_equivalent=spec.text_equivalent,
        degraded=False,
        reason=None,
        triage={},
        label=label,
    )


def renderer_manifest(artifacts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the Desktop media area is allowed to render: inert types with descriptions."""
    manifest = []
    for artifact in artifacts:
        if artifact["mime"] not in _RENDERABLE_MIME:
            continue
        manifest.append(
            {
                "artifact_id": artifact["artifact_id"],
                "mime": artifact["mime"],
                "content_hash": artifact["content_hash"],
                "description": artifact["provenance"].get("text_equivalent", ""),
                "label": artifact["provenance"].get("label", ""),
                "active_content": False,
            }
        )
    return manifest
