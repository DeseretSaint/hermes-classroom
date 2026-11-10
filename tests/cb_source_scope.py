"""The version seam between the v2 module and the v3 stylesheet.

CP-003's job is to let v3 surfaces exist without deleting a v2 protection. The one mechanical
problem is that a handful of v2 gates read ``desktop/plugin.js`` as a single blob: "no raw hex",
"no decorative gradient", "no box shadow", "no font size outside the six steps", "one motion
ladder". Those claims were true when the file was one material system (Atlas Lamp v2). They stop
being true the moment CP-020a appends the v3 stylesheet, which legitimately carries its own token
literal (hex), its own elevation (``box-shadow: var(--cb3-elev-*)``), the named parchment vignette
(the one gradient v3 permits) and its own motion table. A v2 gate that fails on v3 paint would
either block v3 forever or be deleted, and deleting it is the weakening this card exists to stop.

So the file is treated as two regions, not one:

- **v2 region** — everything outside the v3 literals/markers. This is the module that ships today:
  inline style objects, ``CB_TOKENS_JSON``, ``CB_MOTION``, ``CB_TYPE_SCALE_JSON``.
- **v3 region** — the ``CB_TOKENS_V3_JSON`` string literal, the ``CB_V3_CSS`` string literal, and
  anything between the optional ``CB-V3-BEGIN`` / ``CB-V3-END`` comment markers.

``v2_source()`` returns the module with the v3 region cut out. v2 gates scan that; v3 gates scan
the v3 region (``test_desktop_tokens_v3.py``) or the whole file with both token literals allowed.

A marker region is **not** a paint exemption. Cut from the v2 region, its content would otherwise
belong to no gate at all — a hole both gates would report PASS through. Paint literals are legal
only inside the two literal constants that actually ship, so the v3 shadow/gradient scans mask
``CB_V3_CSS`` alone (``stylesheet_spans``) and leave marker content inside the scanned text. Markers
may carry v3 control-flow scaffolding; they may not carry hex, a shadow or a gradient.

The seam is only worth anything if it is load-bearing in both directions, so
``tests/test_desktop_gate_scope.py`` proves it with negative controls: a violation injected into
the v2 region is still caught while a legitimate v3 declaration is not, and stripping the v3 region
never mutates the rest of the file.

Nothing here edits the plugin. CP-003 does not own ``desktop/plugin.js``.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

#: The v2 token literal. Hex inside this string is the v2 palette, not a stray colour.
V2_TOKEN_CONST = "CB_TOKENS_JSON"
#: The v3 token literal CP-020a adds. Hex inside this string is the v3 palette.
V3_TOKEN_CONST = "CB_TOKENS_V3_JSON"
#: The v3 stylesheet CP-020a adds, scoped to ``[data-cb-v3]``.
V3_CSS_CONST = "CB_V3_CSS"
#: The only two literals allowed to carry a raw hex once v3 exists.
TOKEN_LITERAL_CONSTS = (V2_TOKEN_CONST, V3_TOKEN_CONST)

#: Optional human markers; if a builder wraps more v3 code than the two literals, it is cut too.
V3_BEGIN = "CB-V3-BEGIN"
V3_END = "CB-V3-END"


def literal_span(source: str, name: str) -> tuple[int, int] | None:
    """Byte span of the string literal assigned to ``const <name> =``.

    Handles a single-quoted, double-quoted or template literal, including escaped quotes. Returns
    ``None`` when the constant does not exist yet — which is the state before CP-020a, and must be
    reported honestly rather than treated as an empty literal.
    """
    match = re.search(r"\bconst\s+" + re.escape(name) + r"\s*=\s*", source)
    if match is None:
        return None
    start = match.end()
    while start < len(source) and source[start].isspace():
        start += 1
    if start >= len(source) or source[start] not in "'\"`":
        return None
    quote = source[start]
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return (start, index + 1)
        index += 1
    return None


def _unescape(raw: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == "\\" and index + 1 < len(raw):
            following = raw[index + 1]
            out.append({"n": "\n", "t": "\t"}.get(following, following))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def literal_text(source: str, name: str) -> str | None:
    """The decoded body of the constant's literal, or ``None`` when it is absent."""
    span = literal_span(source, name)
    if span is None:
        return None
    return _unescape(source[span[0] + 1:span[1] - 1])


def marker_spans(source: str) -> list[tuple[int, int]]:
    """Spans of ``CB-V3-BEGIN`` … ``CB-V3-END`` comment regions, if a builder uses them."""
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"(?m)^\s*//.*" + re.escape(V3_BEGIN) + r".*$", source):
        end_match = re.search(r"(?m)^\s*//.*" + re.escape(V3_END) + r".*$", source[match.end():])
        if end_match is None:
            # An unterminated region is a defect in the source, not something to guess about:
            # cut from the marker to end-of-file so a v2 gate can never silently read half of it.
            spans.append((match.start(), len(source)))
        else:
            spans.append((match.start(), match.end() + end_match.end()))
    return spans


def v3_spans(source: str) -> list[tuple[int, int]]:
    """Every span that belongs to the v3 material, merged and sorted."""
    spans = [span for span in (literal_span(source, V3_TOKEN_CONST), literal_span(source, V3_CSS_CONST))
             if span is not None]
    spans.extend(marker_spans(source))
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def v2_source(source: str | None = None) -> str:
    """``desktop/plugin.js`` with the v3 material removed: the v2 surfaces only."""
    text = PLUGIN_JS.read_text(encoding="utf-8") if source is None else source
    out: list[str] = []
    cursor = 0
    for start, end in v3_spans(text):
        out.append(text[cursor:start])
        # Keep a newline so line numbers after the cut do not collapse onto one another.
        out.append("\n")
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def stylesheet_spans(source: str) -> list[tuple[int, int]]:
    """The one span whose paint declarations are exempt: the ``CB_V3_CSS`` literal.

    Deliberately narrower than :func:`v3_spans`. ``test_box_shadow_only_inside_the_stylesheet...``
    and ``test_the_only_gradient_is_the_named_vignette`` (and audit V-07/V-08) use this so a
    ``CB-V3-BEGIN`` … ``CB-V3-END`` region cannot smuggle a raw shadow or a decorative gradient
    past both gates. Hex is masked by the two token literals separately; v3 paint belongs in the
    stylesheet, not in a marker.
    """
    span = literal_span(source, V3_CSS_CONST)
    return [span] if span is not None else []


def v3_source(source: str | None = None) -> str:
    """Just the v3 material: the token literal, the stylesheet, and any marked region."""
    text = PLUGIN_JS.read_text(encoding="utf-8") if source is None else source
    return "\n".join(text[start:end] for start, end in v3_spans(text))


# --------------------------------------------------------------------------------------------
# CSS analysis shared by the v3 gate and the v3 audit.
# --------------------------------------------------------------------------------------------

def _matching_brace(text: str, open_index: int, end: int) -> int:
    depth = 1
    index = open_index + 1
    while index < end:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return end


def _collect(text: str, start: int, end: int, out: list[tuple[str, str]]) -> None:
    index = start
    prelude_start = start
    while index < end:
        char = text[index]
        if char == "{":
            prelude = text[prelude_start:index].strip()
            close = _matching_brace(text, index, end)
            out.append((prelude, text[index + 1:close]))
            _collect(text, index + 1, close, out)
            index = close + 1
            prelude_start = index
        elif char == "}":
            index += 1
            prelude_start = index
        else:
            index += 1


def css_blocks(css: str) -> list[tuple[str, str]]:
    """Every ``(prelude, body)`` pair in a stylesheet, at any nesting depth.

    ``@media``/``@supports`` preludes come back too; a caller that wants only style rules filters
    on the leading ``@``. Comments are stripped first so a commented-out declaration never counts.
    """
    text = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    blocks: list[tuple[str, str]] = []
    _collect(text, 0, len(text), blocks)
    return blocks


def declarations(body: str) -> list[tuple[str, str]]:
    """Top-level ``(property, value)`` pairs of a declaration block."""
    if "{" in body:
        # A container block (@media) has no declarations of its own.
        return []
    chunks: list[str] = []
    depth = 0
    piece: list[str] = []
    for char in body:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == ";" and depth == 0:
            chunks.append("".join(piece))
            piece = []
        else:
            piece.append(char)
    chunks.append("".join(piece))
    pairs: list[tuple[str, str]] = []
    for chunk in chunks:
        if ":" not in chunk:
            continue
        prop, value = chunk.split(":", 1)
        pairs.append((prop.strip().lower(), value.strip()))
    return pairs


def style_rules(css: str) -> list[tuple[str, str]]:
    """Only the blocks whose prelude is a selector list (not an at-rule)."""
    return [(prelude, body) for prelude, body in css_blocks(css)
            if prelude and not prelude.startswith("@")]


def split_selectors(prelude: str) -> list[str]:
    """Split a selector list on commas that are not inside ``()`` or ``[]``."""
    selectors: list[str] = []
    depth = 0
    piece: list[str] = []
    for char in prelude:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == "," and depth == 0:
            selectors.append("".join(piece).strip())
            piece = []
        else:
            piece.append(char)
    selectors.append("".join(piece).strip())
    return [selector for selector in selectors if selector]


GRADIENT = re.compile(r"[a-z-]*gradient\(", re.I)
#: A CSS ``<number>`` in every spelling the CSS grammar allows: ``1``, ``1.5``, ``.5`` and an
#: optional scientific exponent (``1e3``, ``1E+3``, ``2.5e-2``). D6: a numeric scan built only from
#: ``\d+(\.\d+)?`` silently skips ``.9s`` / ``1e3ms`` / ``.5vw``, which are legal values, so the
#: declaration is never seen and the owning claim reports PASS. Callers still require the unit, so
#: a bare number is not a duration or a measurement, and the shared negative lookbehind keeps
#: ``1.5rem`` / ``12px`` out.
CSS_NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
#: A duration with an ASCII case-insensitive unit: CSS units are case-insensitive, so ``900MS`` and
#: ``0.9S`` must be seen exactly like ``900ms``.
DURATION = re.compile(r"(?<![\w.-])(" + CSS_NUMBER + r")(ms|s)\b", re.I)
#: A viewport measurement on the same numeric grammar and the same ASCII case-insensitive unit
#: rule: `100VW` / `1E3Vw` are the declarations a browser paints, so the gate and the audit must
#: see them exactly like `100vw`. Without `re.I` the uppercase spellings were skipped and both
#: implementations reported PASS on a viewport measurement (CP-003c, R1).
VW = re.compile(r"(?<![\w.-])" + CSS_NUMBER + r"vw\b", re.I)
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# --------------------------------------------------------------------------------------------
# Normalised banned-token scans, shared by the v3 gate and the v3 audit.
#
# Reviewer round 3, D5: CSS property names, function names and units are ASCII case-insensitive,
# and vendor prefixes are valid and paint. A case-sensitive string search for exactly
# ``backdrop-filter`` / ``box-shadow`` / ``900ms`` therefore reports PASS on stylesheets that do
# render a glass blur, a raw shadow or an out-of-table duration. Both gates import these patterns
# so the two cannot drift apart.
# --------------------------------------------------------------------------------------------

#: Glass: ``backdrop-filter``, ``backdropFilter`` (the camel form), any casing, and ``blur(``.
GLASS = re.compile(r"backdrop-?filter|blur\(", re.I)
#: Any shadow property, optional vendor prefix, any casing; also the camel ``boxShadow`` form.
SHADOW = re.compile(r"(?:-(?:webkit|moz|ms|o)-)?box-?shadow", re.I)
#: A single declaration's property is a shadow declaration (``-webkit-box-shadow`` included).
SHADOW_PROPERTY = re.compile(r"^(?:-(?:webkit|moz|ms|o)-)?box-shadow$", re.I)
#: Animation / loop tokens, any casing (``@KEYFRAMES``, ``ANIMATION: spin INFINITE``).
ANIMATION = re.compile(r"@keyframes|animation-name|animation\s*:|infinite", re.I)


def is_shadow_property(prop: str) -> bool:
    """True for ``box-shadow`` and every vendor-prefixed/case-varied spelling of it."""
    return SHADOW_PROPERTY.match(prop.strip()) is not None


def shadow_declaration_count(text: str) -> int:
    """How many shadow declarations (any prefix, any casing) the text carries."""
    return len(SHADOW.findall(text))


#: GM-VISUAL-SPEC §2.5's shelf edge fade: a mask declaration, not a gradient surface. The v2 gate
#: exempts exactly this one declaration, and a v3 gradient scan must not read it as a v3 gradient
#: either. Shared so the exemption cannot drift between the two gates.
SHELF_MASK = re.compile(r"\n\s*const maskImage = `[^`]*`\n")


def without_shelf_edge_mask(source: str) -> str:
    return SHELF_MASK.sub("\n", source, count=1)
