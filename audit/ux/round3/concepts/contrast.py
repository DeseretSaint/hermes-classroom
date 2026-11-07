#!/usr/bin/env python3
"""Reproducible WCAG contrast proof for the Atlas Lamp token proposal (v2).

Read-only design artifact, not product code. Run from the repo root:

    python3 audit/ux/round3/concepts/contrast.py

Every value below is the proposed shipping value. The product table must stay
inside one JSON literal; this script only proves the pairs.
"""

LIGHT = {
    "paper": "#F7F1E4",
    "paper-raised": "#FFFCF3",
    "ink": "#1A1713",
    "ink-soft": "#5C5347",
    "rule": "#D7CBB4",
    "accent": "#2C4A8C",
    "accent-soft": "#E2E8F7",
    "field": "#2F6047",
    "ochre": "#7B4B0A",
    "coral": "#9C2E1C",
    "lamp": "#E8A93A",
    "lamp-soft": "#FBEBCB",
    "on-lamp": "#1A1713",
    "plum": "#6A3E74",
    "plum-soft": "#F0E6F3",
}
DARK = {
    "paper": "#131210",
    "paper-raised": "#1D1B16",
    "ink": "#F5EFE1",
    "ink-soft": "#B9AE9A",
    "rule": "#3D382D",
    "accent": "#A8C0F2",
    "accent-soft": "#222A3B",
    "field": "#9FC69A",
    "ochre": "#E0B25C",
    "coral": "#EA9480",
    "lamp": "#EFC06B",
    "lamp-soft": "#33290F",
    "on-lamp": "#131210",
    "plum": "#CDA0D8",
    "plum-soft": "#2E2434",
}

# (foreground, background, floor, why)
GATES = [
    ("ink", "paper", 7.0, "reading text, AAA body"),
    ("ink", "paper-raised", 7.0, "reading text in a raised frame"),
    ("ink-soft", "paper", 4.5, "secondary text and captions"),
    ("ink-soft", "paper-raised", 4.5, "secondary text in a raised frame"),
    ("accent", "paper", 4.5, "path, links, Textbook mode"),
    ("field", "paper", 4.5, "evidence, Guided mode, notes"),
    ("ochre", "paper", 4.5, "review due, Field Quest, checkpoints"),
    ("coral", "paper", 4.5, "attention text, never decoration"),
    ("plum", "paper", 4.5, "Parent Studio identity"),
    ("on-lamp", "lamp", 4.5, "label on the primary action"),
    ("ink", "accent-soft", 4.5, "text on a selected row"),
    ("ink", "lamp-soft", 4.5, "text on the hero and checkpoint field"),
    ("ink", "plum-soft", 4.5, "text on a Parent Studio panel"),
    ("ink-soft", "accent-soft", 4.5, "caption on a selected row"),
    ("ink-soft", "lamp-soft", 4.5, "caption on the hero field"),
    ("ink-soft", "plum-soft", 4.5, "caption on a Parent Studio panel"),
    ("paper", "field", 4.5, "glyph on a done node"),
    ("paper", "accent", 4.5, "glyph on an active node"),
    ("rule", "paper", 1.25, "hairline visibility, non-text"),
    ("rule", "paper-raised", 1.25, "hairline on a raised frame, non-text"),
    ("lamp", "paper", 1.25, "primary fill edge, supported by a 1px on-lamp border"),
]


def _channel(value: float) -> float:
    value = value / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(hex_value: str) -> float:
    raw = hex_value.lstrip("#")
    r, g, b = (int(raw[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def main() -> int:
    failures = 0
    print("| Pair | Light | Dark | Floor | Verdict | Why |")
    print("|---|---|---|---|---|---|")
    for fg, bg, floor, why in GATES:
        light = contrast(LIGHT[fg], LIGHT[bg])
        dark = contrast(DARK[fg], DARK[bg])
        ok = light >= floor and dark >= floor
        if not ok:
            failures += 1
        print(
            f"| `{fg}` on `{bg}` | {light:.2f} | {dark:.2f} | {floor:.2f} | "
            f"{'PASS' if ok else 'FAIL'} | {why} |"
        )
    print()
    print(f"Failing pairs: {failures}")
    print(f"Tokens: light={len(LIGHT)} dark={len(DARK)}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
