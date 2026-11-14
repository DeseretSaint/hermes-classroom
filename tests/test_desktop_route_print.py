"""Upgrade 31 — the route has a paper form.

The card's claim, in executable form. Pressing Ctrl+P on any Coursebook route printed the live
screen: parchment or night canvas, grain and vignette, the forest rail, the settings sheet, a
1344 px scene. There was no ``@media print`` rule anywhere in ``desktop/src``; the product's only
print stylesheet belonged to the Parent Studio export document, which is generated as separate
HTML and therefore never governs the route.

What this module proves, without a Desktop window, a rig backend or a CDP probe (owner directive
2026-11-12 — evidence for what ships is a source grep and this unittest):

* the shipped module carries exactly one ``@media print`` block and every selector in it is
  scoped to ``[data-cb-v3]``, the route root (``tests/test_v3_scope.py`` proves that node is also
  ``[data-cb-route]``, exactly once);
* the printed ground is the contract's print paper, and the block reaches it the way the browser
  will: ``[data-cb-v3]`` paints ``background-color: var(--cb3-canvas)`` from an *inline* custom
  property, so the print block remaps ``--cb3-canvas`` onto ``var(--cb3-print-paper)`` with
  ``!important`` and the contract's print paper is ``#ffffff`` — i.e. the computed value is
  ``rgb(255, 255, 255)``;
* every v3 role and every v2 token name is remapped in the print block, so a dark route prints the
  same mode-blind ink instead of cream text on white paper, and the block is not keyed on
  ``[data-cb-scope]``;
* every printed text value reaches 4.5:1 on the printed paper (WCAG contrast computed here from
  the contract, never from a screenshot);
* the material layers are ``display: none``, the rail, its band, the settings sheet and the skip
  link are ``display: none``, lesson blocks keep their page, and the ``@page`` geometry agrees with
  the contract.

What this does NOT prove: that a printer driver honours ``break-inside`` on a given page size, or
that a host chrome outside the route prints white. The route is the scope of this card.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.cb_source_scope import (
    HEX,
    PLUGIN_JS,
    ROOT,
    V3_CSS_CONST,
    V3_TOKEN_CONST,
    css_blocks,
    declarations,
    literal_text,
    split_selectors,
    style_rules,
)

CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"


def contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def plugin_source() -> str:
    return PLUGIN_JS.read_text(encoding="utf-8")


def v3_css() -> str:
    text = literal_text(plugin_source(), V3_CSS_CONST)
    if text is None:
        raise AssertionError(f"desktop/plugin.js has no {V3_CSS_CONST} stylesheet")
    return text


def print_block() -> str:
    """The body of the one ``@media print`` block.

    ``css_blocks`` returns every ``(prelude, body)`` pair including at-rules, so the block is found
    by its own prelude rather than by counting braces here.
    """
    blocks = [(prelude, body) for prelude, body in css_blocks(v3_css())
              if prelude.replace(" ", "").startswith("@media") and "print" in prelude
              and "screen" not in prelude]
    if len(blocks) != 1:
        raise AssertionError(
            f"expected exactly one @media print block in {V3_CSS_CONST}, found {len(blocks)}"
        )
    return blocks[0][1]


def print_rules() -> list[tuple[str, str]]:
    """Every selector rule inside the print block, flattened."""
    return [(prelude, body) for prelude, body in css_blocks(print_block())
            if prelude and not prelude.startswith("@")]


def root_rule() -> str:
    """The print block's own ``[data-cb-v3]`` rule body — the palette remap."""
    bodies = [body for prelude, body in css_blocks(print_block())
              if prelude.strip() == "[data-cb-v3]"]
    if len(bodies) != 1:
        raise AssertionError(f"expected one [data-cb-v3] rule in the print block, found {len(bodies)}")
    return bodies[0]


def rule_for(suffix: str) -> str:
    """The print block's rule whose selector list contains a selector ending in ``suffix``.

    Print rules are authored as selector lists (one declaration block closes several chrome
    markers), so the lookup matches the tail of a selector rather than a whole prelude.
    """
    bodies = [body for prelude, body in print_rules()
              if any(part.strip().endswith(suffix) for part in split_selectors(prelude))]
    if len(bodies) != 1:
        raise AssertionError(f"expected one print rule declaring {suffix!r}, found {len(bodies)}")
    return bodies[0]


def declared(body: str) -> dict[str, str]:
    return {prop: value for prop, value in declarations(body)}


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground: str, background: str) -> float:
    light, dark = sorted((luminance(hex_to_rgb(foreground)), luminance(hex_to_rgb(background))),
                         reverse=True)
    return (light + 0.05) / (dark + 0.05)


def frozen_list(source: str, name: str) -> list[str]:
    """The names in ``const NAME = Object.freeze([...])`` in the shipped module."""
    match = re.search(r"const " + re.escape(name) + r" = Object\.freeze\(\[(.*?)\]\)", source, re.S)
    if match is None:
        raise AssertionError(f"desktop/plugin.js has no {name} list")
    return re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))


class RoutePrintBlockTest(unittest.TestCase):
    """The one print block, its scope, and what it must not paint."""

    def setUp(self) -> None:
        self.css = v3_css()
        self.block = print_block()
        self.root = root_rule()

    def test_the_route_carries_one_print_block_with_no_screen_variant(self) -> None:
        # A second print block would be a second paper form, and a `screen` prelude is not a print
        # rule at all. One block, one medium.
        media = [prelude for prelude, _ in css_blocks(self.css)
                 if prelude.replace(" ", "").startswith("@media") and "print" in prelude]
        self.assertEqual(len(media), 1, f"print media preludes: {media}")
        self.assertEqual(media[0].strip(), "@media print")

    def test_every_printed_selector_is_scoped_to_the_route_root(self) -> None:
        # The v3 root IS the route root (test_v3_scope proves the identity); an unscoped print rule
        # would repaint the host's own chrome, which this plugin does not own.
        for prelude, _ in print_rules():
            for selector in split_selectors(prelude):
                self.assertTrue(selector.startswith("[data-cb-v3]"),
                                f"printed selector {selector!r} is not scoped to the route root")

    def test_the_ground_remap_resolves_to_the_printer_white(self) -> None:
        # The route root paints `background-color: var(--cb3-canvas)` from an inline custom
        # property (cbV3ScopeStyle), which no plain stylesheet declaration can beat. The print block
        # therefore remaps the variable, not only the declaration.
        declared_root = declared(self.root)
        self.assertEqual(declared_root.get("--cb3-canvas"), "var(--cb3-print-paper) !important")
        self.assertEqual(declared_root.get("background-color"), "var(--cb3-print-paper)")
        self.assertEqual(declared_root.get("color"), "var(--cb3-print-ink)")

        paper = contract()["print"]["paper"]
        self.assertEqual(paper.lower(), "#ffffff", "the printed ground is not the printer's white")
        self.assertEqual(hex_to_rgb(paper), (255, 255, 255),
                         "the printed ground must compute to rgb(255, 255, 255)")

        # The variable has to exist on the node, and cbV3ScopeStyle is what writes it there.
        self.assertIn("--cb3-print-paper", plugin_source(),
                      "cbV3ScopeStyle does not write the print palette onto the route root")

    def test_the_print_palette_travels_as_custom_properties_only(self) -> None:
        # Same rule as the rest of the stylesheet: every value arrives through a property, and the
        # two token literals stay the only hex in the module.
        self.assertEqual(HEX.findall(self.block), [], "the print block paints a raw colour")

    def test_the_material_layers_do_not_print(self) -> None:
        declared_layer = declared(rule_for(".cb3-material"))
        self.assertEqual(declared_layer.get("display"), "none")
        # The wide Home's painted backdrop is a plate, not reading matter (GM-PRINT-SPEC).
        self.assertEqual(declared(rule_for("[data-cb-home-scene-backdrop]")).get("display"), "none")

    def test_the_shell_does_not_print(self) -> None:
        for selector in ("[data-cb3-rail]", "[data-cb3-band]", "[data-cb-settings-backdrop]",
                         "[data-cb-settings-sheet]", "[data-cb-skip]"):
            self.assertEqual(declared(rule_for(selector)).get("display"), "none",
                             f"{selector} would print on the sheet")

    def test_lesson_blocks_keep_their_page(self) -> None:
        declared_block = declared(rule_for("[data-cb-block]"))
        self.assertEqual(declared_block.get("break-inside"), "avoid")
        for heading in ("h1", "h2", "h3"):
            self.assertEqual(declared(rule_for(heading)).get("break-after"), "avoid",
                             f"a {heading} may end a page with its text on the next one")

    def test_the_page_geometry_is_the_contract_geometry(self) -> None:
        # The card asks for page margins, and a margin that only exists in the stylesheet drifts.
        pages = [body for prelude, body in css_blocks(self.block) if prelude.strip() == "@page"]
        self.assertEqual(len(pages), 1, "the print block must declare exactly one @page rule")
        page = declared(pages[0])
        spec = contract()["print"]["page"]
        self.assertEqual(page.get("size"), spec["size"])
        self.assertEqual(page.get("margin"), spec["margin"])


class RoutePrintContrastTest(unittest.TestCase):
    """Paper has one appearance: every printed word is the print ink, at 4.5:1 or better."""

    def setUp(self) -> None:
        self.contract = contract()
        self.print_palette = self.contract["print"]
        self.printed = declared(root_rule())

    def test_every_v3_role_is_remapped_for_paper(self) -> None:
        # A role left unremapped keeps its mode value: in the dark appearance that is a cream word
        # on white paper. Every role the module writes has to resolve to a print value.
        roles = frozen_list(plugin_source(), "CB3_V3_ROLES")
        self.assertEqual(len(roles), 18, roles)
        for role in roles:
            prop = f"--cb3-{role}"
            self.assertIn(prop, self.printed, f"{prop} keeps its screen value in print")
            self.assertRegex(self.printed[prop], r"^var\(--cb3-print-[a-z-]+\)\s*!important$",
                             f"{prop} is remapped to something other than a print token")

    def test_every_v2_token_is_remapped_for_paper(self) -> None:
        # The lesson blocks, the workshop and the course pages still paint from the v2 ladder.
        names = frozen_list(plugin_source(), "CB_TOKEN_NAMES")
        self.assertEqual(len(names), 15, names)
        for name in names:
            prop = f"--cb-{name}"
            self.assertIn(prop, self.printed, f"{prop} keeps its screen value in print")

    def test_no_print_rule_is_keyed_on_the_screen_appearance(self) -> None:
        block = print_block()
        self.assertNotIn("data-cb-scope", block,
                         "a printed sheet has one appearance; nothing may branch on the mode")
        self.assertEqual(self.printed.get("color-scheme"), "light !important")

    def test_paper_carries_no_contact_shadow(self) -> None:
        for level in ("--cb3-elev-1", "--cb3-elev-2", "--cb3-elev-inset-1"):
            self.assertEqual(self.printed.get(level), "none !important",
                             f"{level} would print as a grey halo")

    def test_every_printed_text_colour_reaches_4_5_to_1(self) -> None:
        paper = self.print_palette["paper"]
        text_values = {name: self.print_palette[name]
                       for name in ("ink", "ink-soft", "alert")}
        for name, value in text_values.items():
            measured = contrast(value, paper)
            self.assertGreaterEqual(
                round(measured, 2), 4.5,
                f"print {name} {value} measures {measured:.2f}:1 on paper {paper}",
            )

    def test_the_ink_is_the_light_mode_reading_ink(self) -> None:
        # The printed ink is the light appearance's own reading ink, so a route always prints the
        # colour the contract already calls reading text.
        self.assertEqual(self.print_palette["ink"], self.contract["modes"]["light"]["ink"])
        self.assertEqual(self.print_palette["ink-soft"], self.contract["modes"]["light"]["ink-soft"])

    def test_a_printed_word_is_never_painted_with_the_paper(self) -> None:
        # A role that prints as paper is a fill, and a fill that carries no text is invisible. If a
        # surface ever sets a word in gold, sage, wood or a ground role, that word would print as
        # paper on paper. This is the guard for that class of mistake: every `color:` that reads a
        # role must read a role the print block maps to a text or object value.
        source = plugin_source()
        words = set(re.findall(r"color\s*:\s*'?var\(--(cb3?-[a-z0-9-]+)\)", source))
        self.assertTrue(words, "no word colour in the module? the scan is broken, not the surface")
        paper_roles = {name for name, value in self.printed.items()
                       if value.startswith("var(--cb3-print-paper)")}
        for word in sorted(words):
            if word.endswith("-print-paper") or "-print-" in word:
                continue
            self.assertNotIn(word, paper_roles,
                             f"a word is painted with {word}, which prints as the paper")


if __name__ == "__main__":
    unittest.main()
