"""Both progress indicators must carry a fill that separates from its own track by 3:1.

Upgrade 25 (`t_922e63d1`). Before this file both bars painted gold on a rule-coloured track:
gold #a1741f against rule #cdb894 is 2.16:1 in light, under the 3:1 non-text floor, so the
completed length of a 4 px bar could not be seen. Dark measured 5.59:1, which is exactly why a
dark-only review missed it. A screenshot review cannot hold this: the pair has to be recomputed
from the shipped declarations every time either role moves.

What is measured, and where it comes from:

  * **The Home scene card bar.** `desktop/plugin.js` carries the v3 stylesheet literal
    (`CB_V3_CSS`); this file reads the shipped `[data-cb-v3] [data-cb-home-scene-progress]`
    background-color and its `> i` fill, resolves each `var(--cb3-*)` name against
    `contracts/cb.tokens.v3.json`, and recomputes WCAG contrast per mode.
  * **The Game progress bar.** The same module builds it inline; the track's `backgroundColor` and
    the fill's `backgroundColor` inside the `data-cb3-game-progress` block are read the same way.

The deck the acceptance names is a computed pair, not a live window: `computed background-color`
is exactly the token each declaration resolves to, and reading it here keeps the gate runnable in
the suite instead of only in a rig. A negative control recomputes the gold-on-rule pair this card
replaced and requires it to fail, so the gate cannot pass by measuring two roles nobody ships.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.cb_source_scope import (
    PLUGIN_JS,
    V3_CSS_CONST,
    V3_TOKEN_CONST,
    declarations,
    literal_text,
    split_selectors,
    style_rules,
)

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"

SCENE_TRACK = "[data-cb-v3] [data-cb-home-scene-progress]"
SCENE_FILL = "[data-cb-v3] [data-cb-home-scene-progress] > i"

#: The floor WCAG 1.4.11 sets for a graphic that carries meaning (here: how much is done).
NON_TEXT_FLOOR = 3.0

#: The inline track of the Game progressbar: a 0.4 rem pill, full width, on the rule role.
GAME_TRACK = re.compile(
    r"height: '0\.4rem',\s*\n\s*width: '100%',\s*\n\s*backgroundColor: cb3Role\('([a-z-]+)'\)"
)
#: The inline fill: absolutely positioned, its width is the completed ratio, on its own role.
GAME_FILL = re.compile(
    r"width: `\$\{Math\.round\(ratio \* 100\)\}%`,\s*\n\s*backgroundColou?r: cb3Role\('([a-z-]+)'\)"
)
ROLE_NAME = re.compile(r"^\s*var\(--cb3-([a-z-]+)\)\s*$")


def plugin_source() -> str:
    return PLUGIN_JS.read_text(encoding="utf-8")


def v3_tokens(source: str | None = None) -> dict:
    text = literal_text(plugin_source() if source is None else source, V3_TOKEN_CONST)
    if text is None:
        raise AssertionError(f"desktop/plugin.js has no {V3_TOKEN_CONST} literal")
    return json.loads(text)


def v3_css(source: str | None = None) -> str:
    text = literal_text(plugin_source() if source is None else source, V3_CSS_CONST)
    if text is None:
        raise AssertionError(f"desktop/plugin.js has no {V3_CSS_CONST} literal")
    return text


def rule(css: str, selector: str) -> dict[str, str]:
    """The declarations of the one style rule whose selector list contains ``selector``."""
    found: list[tuple[str, str]] = []
    for prelude, body in style_rules(css):
        if selector in split_selectors(prelude):
            found.append((prelude, body))
    if not found:
        raise AssertionError(f"the built stylesheet carries no rule for {selector!r}")
    if len(found) > 1:
        raise AssertionError(f"{selector!r} is declared {len(found)} times: {[p for p, _ in found]}")
    return {prop: value for prop, value in declarations(found[0][1])}


def role_of(selector: str, css: str | None = None) -> str:
    """The token role behind a rule's ``background-color``."""
    value = rule(v3_css() if css is None else css, selector).get("background-color")
    if value is None:
        raise AssertionError(f"{selector} declares no background-color")
    match = ROLE_NAME.match(value)
    if match is None:
        raise AssertionError(f"{selector} background-color is {value!r}, not a var(--cb3-*) role")
    return match.group(1)


def game_region(source: str | None = None) -> str:
    text = plugin_source() if source is None else source
    marker = "'data-cb3-game-progress'"
    index = text.find(marker)
    if index < 0:
        raise AssertionError(f"the built module has no {marker} block")
    if text.find(marker, index + len(marker)) >= 0:
        raise AssertionError(f"the built module declares {marker} more than once")
    return text[index:index + 4000]


def game_roles(source: str | None = None) -> tuple[str, str]:
    region = game_region(source)
    track = GAME_TRACK.findall(region)
    fill = GAME_FILL.findall(region)
    if len(track) != 1:
        raise AssertionError(f"the Game progress track is not one backgroundColor: {track!r}")
    if len(fill) != 1:
        raise AssertionError(f"the Game progress fill is not one backgroundColor: {fill!r}")
    return track[0], fill[0]


def _relative_luminance(hex_value: str) -> float:
    raw = hex_value.lstrip("#")
    channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(channels[0]) + 0.7152 * linear(channels[1]) + 0.0722 * linear(channels[2])


def contrast_ratio(foreground: str, background: str) -> float:
    first = _relative_luminance(foreground)
    second = _relative_luminance(background)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


def role_contrast(contract: dict, fill: str, track: str) -> dict[str, float]:
    measured = {}
    for mode in ("light", "dark"):
        table = contract["modes"][mode]
        if fill not in table:
            raise AssertionError(f"{mode} mode has no role {fill!r}")
        if track not in table:
            raise AssertionError(f"{mode} mode has no role {track!r}")
        measured[mode] = contrast_ratio(table[fill], table[track])
    return measured


class ProgressFillContrastTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = v3_tokens()
        self.css = v3_css()

    def test_the_home_scene_progress_fill_clears_the_non_text_floor(self) -> None:
        track = role_of(SCENE_TRACK, self.css)
        fill = role_of(SCENE_FILL, self.css)
        self.assertNotEqual(fill, track, "the fill and the track are the same role")
        measured = role_contrast(self.contract, fill, track)
        for mode, value in measured.items():
            with self.subTest(mode=mode):
                self.assertGreaterEqual(
                    value, NON_TEXT_FLOOR,
                    f"Home scene progress fill {fill} on track {track} is {value:.2f}:1 in {mode}",
                )

    def test_the_game_progress_fill_clears_the_non_text_floor(self) -> None:
        track, fill = game_roles()
        self.assertNotEqual(fill, track, "the Game progress fill and track are the same role")
        measured = role_contrast(self.contract, fill, track)
        for mode, value in measured.items():
            with self.subTest(mode=mode):
                self.assertGreaterEqual(
                    value, NON_TEXT_FLOOR,
                    f"Game progress fill {fill} on track {track} is {value:.2f}:1 in {mode}",
                )

    def test_the_two_bars_agree_on_their_pairing(self) -> None:
        # One product, one gauge treatment: two role pairs that mean the same thing drift apart the
        # first time a token moves and only one site is updated.
        self.assertEqual(
            (role_of(SCENE_FILL, self.css), role_of(SCENE_TRACK, self.css)),
            (game_roles()[1], game_roles()[0]),
        )

    def test_the_gold_on_rule_pair_this_card_replaced_still_fails_the_floor(self) -> None:
        # Negative control: the measurement is of the shipped roles, and the pair that shipped
        # before this card is still under the floor in light. If someone restores gold on rule, the
        # two tests above fail with these numbers instead of passing on a mis-read declaration.
        measured = role_contrast(self.contract, "gold", "rule")
        self.assertLess(measured["light"], NON_TEXT_FLOOR)
        self.assertGreaterEqual(measured["dark"], NON_TEXT_FLOOR)


if __name__ == "__main__":
    unittest.main()
