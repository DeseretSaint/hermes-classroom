"""Static guard: no ``key`` may be spread inside a ``jsx()``/``jsxs()`` props object.

React 19.3 dev builds warn (to stderr) whenever a props object containing ``key`` is
spread into JSX, and every render harness here treats non-empty stderr as a failure.
Keys belong in the third positional argument:

    jsx('rect', { x: 4, y: 4 }, 'frame')     # right
    jsx('rect', { x: 4, y: 4, key: 'frame' })  # warns

This test is lexical: it masks JS strings, comments and template-literal text (keeping
``${...}`` substitution code), then walks balanced parentheses to isolate the second
argument of each ``jsx``/``jsxs`` call. It needs no React render, so it runs everywhere.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


def _prev_significant(src: str, i: int) -> str | None:
    j = i - 1
    while j >= 0 and src[j] in " \t\r\n":
        j -= 1
    return None if j < 0 else src[j]


def mask_source(src: str) -> str:
    """Blank out strings, comments and template text; keep code inside ``${...}``."""
    out = list(src)
    n = len(src)
    i = 0
    mode = ["code"]
    depth = [0]

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]
        if mode[-1] == "code":
            if src.startswith("//", i):
                j = src.find("\n", i)
                j = n if j < 0 else j
                blank(i, j)
                i = j
                continue
            if src.startswith("/*", i):
                j = src.find("*/", i + 2)
                j = n if j < 0 else j + 2
                blank(i, j)
                i = j
                continue
            if c in "\"'":
                quote = c
                j = i + 1
                while j < n:
                    if src[j] == "\\":
                        j += 2
                        continue
                    if src[j] == quote:
                        j += 1
                        break
                    if src[j] == "\n":
                        break
                    j += 1
                blank(i, j)
                i = j
                continue
            if c == "/":
                prev = _prev_significant(src, i)
                if prev is None or prev in "(,=:[!&|?{};+-*%<>~^":
                    j = i + 1
                    in_class = False
                    while j < n:
                        ch = src[j]
                        if ch == "\\":
                            j += 2
                            continue
                        if ch == "[":
                            in_class = True
                        elif ch == "]":
                            in_class = False
                        elif ch == "/" and not in_class:
                            j += 1
                            break
                        elif ch == "\n":
                            break
                        j += 1
                    while j < n and src[j].isalpha():
                        j += 1
                    blank(i, j)
                    i = j
                    continue
            if c == "`":
                out[i] = " "
                mode.append("template")
                i += 1
                continue
            if len(mode) > 1:
                if c == "{":
                    depth[-1] += 1
                elif c == "}":
                    if depth[-1] == 0:
                        out[i] = " "
                        mode.pop()
                        depth.pop()
                        i += 1
                        continue
                    depth[-1] -= 1
            i += 1
            continue
        # template text
        if c == "\\":
            blank(i, i + 2)
            i += 2
            continue
        if c == "`":
            out[i] = " "
            mode.pop()
            i += 1
            continue
        if c == "$" and i + 1 < n and src[i + 1] == "{":
            blank(i, i + 2)
            mode.append("code")
            depth.append(0)
            i += 2
            continue
        blank(i, i + 1)
        i += 1
    return "".join(out)


def find_matching(masked: str, start: int, opener: str, closer: str) -> int:
    level = 0
    for i in range(start, len(masked)):
        if masked[i] == opener:
            level += 1
        elif masked[i] == closer:
            level -= 1
            if level == 0:
                return i
    return len(masked) - 1


def split_args(masked: str, start: int, end: int) -> list[tuple[int, int]]:
    spans = []
    level = 0
    arg_start = start
    for i in range(start, end):
        c = masked[i]
        if c in "([{":
            level += 1
        elif c in ")]}":
            level -= 1
        elif c == "," and level == 0:
            spans.append((arg_start, i))
            arg_start = i + 1
    if masked[arg_start:end].strip():
        spans.append((arg_start, end))
    return spans


def top_level_key_lines(masked: str, obj_start: int, obj_end: int) -> list[int]:
    lines = []
    level = 0
    i = obj_start + 1
    while i < obj_end:
        c = masked[i]
        if c in "([{":
            level += 1
            i += 1
            continue
        if c in ")]}":
            level -= 1
            i += 1
            continue
        if level == 0 and (c.isalpha() or c in "_$"):
            match = IDENT.match(masked, i)
            assert match is not None
            name = match.group(0)
            j = match.end()
            k = j
            while k < obj_end and masked[k] in " \t\r\n":
                k += 1
            if name == "key" and k < obj_end and masked[k] == ":":
                lines.append(masked.count("\n", 0, i) + 1)
            i = j
            continue
        i += 1
    return lines


def key_spread_lines(src: str) -> list[int]:
    """Return the line of every top-level ``key`` in a jsx/jsxs props object."""
    masked = mask_source(src)
    bad: list[int] = []
    for match in re.finditer(r"(?<![\w$.])(jsxs?)\(", masked):
        open_paren = masked.index("(", match.start())
        close = find_matching(masked, open_paren, "(", ")")
        args = split_args(masked, open_paren + 1, close)
        if len(args) < 2:
            continue
        a_start, a_end = args[1]
        while a_start < a_end and masked[a_start] in " \t\r\n":
            a_start += 1
        if a_start >= a_end or masked[a_start] != "{":
            continue
        obj_end = find_matching(masked, a_start, "{", "}")
        bad.extend(top_level_key_lines(masked, a_start, obj_end))
    return bad


class JsxKeySpreadGuardTest(unittest.TestCase):
    def test_the_plugin_never_puts_key_inside_a_jsx_props_object(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        lines = key_spread_lines(source)
        self.assertEqual(
            lines,
            [],
            "key inside a jsx()/jsxs() props object at desktop/plugin.js line(s): "
            + ", ".join(str(line) for line in lines)
            + " — pass the key as the third positional argument instead",
        )

    def test_the_guard_catches_the_shapes_it_claims_to(self) -> None:
        source = "\n".join(
            [
                "const a = jsx('rect', { x: 4, key: 'frame' })",
                "const b = jsxs('div', { children: [], key: `k-${i}` })",
                "const c = jsx('div', { className: 'ok' }, 'k')",
                "const d = jsx('div', { style: { key: 'data' } })",
                "const e = jsxs('div', { children: [`key: 'no'`] })",
                "// jsx('div', { key: 'comment' })",
                "const f = jsx('div', { title: `x ${a ? `k: ${b}` : ''}` })",
            ]
        )
        self.assertEqual(key_spread_lines(source), [1, 2])


if __name__ == "__main__":
    unittest.main()
