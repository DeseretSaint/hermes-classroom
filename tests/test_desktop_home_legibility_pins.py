"""LEG-01 pins — the two wide-Home legibility fixes are gates now, not audit prose.

LEG-01 (`t_741c08dd`, `6c1e66d1`, shipped by the merge `05cd1c06` on module `f750d8d4`) fixed two
real defects:

  * the 74 px tag's copy turned onto the plate's *tilted* luggage-tag face
    (``translateX(-2.7px) rotate(-30deg)``), measured 5.271:1 / 5.918:1 with 0 of 67 / 41
    glyph-core pixels under 3.0:1;
  * the two CTA labels moved from ``--cb3-text-body`` (16 px) to ``--cb3-text-lead`` (20 px),
    a measured 13.20 / 11.79 px cap.

Before this file the only record of either number was
``docs/concept-parity/text-legibility-2026-11.json`` — probe-generated evidence, not a gate. A
later edit to the token or the transform could revert both fixes and the suite stayed green, because
no test read either declaration.

What is pinned, and where the numbers come from:

  * **The tag's turn.** The built module (``desktop/plugin.js``, the artifact the proof page is
    rendered from) must carry a non-zero rotation on the tag's word rule, and a translate that puts
    the ink back on the box centre. The centring is recomputed here from the audited geometry
    ("New" 30.4 px, "course" 44.8 px at 14 px, line-height 1.05): turning that unequal two-line
    block swings its ink 3.12 px right, so the shipped -2.7 px translate leaves 0.42 px — 0.56 % of
    the 74 px box, inside CP-TEXT-GATE's 4 % (2.96 px). Removing the translate puts the run at
    3.12 px (4.2 %) and this pin fails, which is the point.
  * **The CTA cap.** Both labels must resolve to ``--cb3-text-lead``. The cap is *measured* the way
    the audit measured it — the token's px value (read from ``CB_TOKENS_V3_JSON``, never hardcoded)
    times that width's scene scale times the UI face's cap ratio — and must clear 11 px at 1344 and
    at 1200. Forcing the token back to the body step is a negative control that must fail with the
    cap it measures (10.56 / 9.43 px).
  * **The exception ledger.** The five runs the audit still lists under the cap floor are explicit
    per-run exceptions in ``tests/fixtures/scene-text/legibility-exceptions.json``, each carrying its
    measured cap and clip at each width. The exception ids must equal the audit's
    ``summary.runs_under_cap_floor`` exactly, so a new under-floor run cannot pass by quoting an old
    exception, and an exception cannot outlive the defect it describes.

This file adds no product pixel and no geometry: it reads the built module and the audit.
"""

from __future__ import annotations

import json
import math
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
AUDIT = ROOT / "docs" / "concept-parity" / "text-legibility-2026-11.json"
EXCEPTIONS = ROOT / "tests" / "fixtures" / "scene-text" / "legibility-exceptions.json"

#: The audit's floor and the gate's centring tolerance (tests/test_desktop_scene_text_containment.py).
CAP_FLOOR_PX = 11.0
CENTRING_TOLERANCE = 0.04

TAG_OBJECT = "[data-cb-v3] [data-cb-home-scene-tag]"
TAG_WORD = "[data-cb-v3] [data-cb-home-scene-tag] [data-cb-home-scene-tag-word]"
CTA_BUTTON = "[data-cb-v3] [data-cb-home-scene-cta] button"

#: The audited geometry of the tag's copy at its meta step (14 px, line-height 1.05). The line
#: widths are LEG-01's measured pair, quoted in the rule's own comment; the cap height is the
#: audit's display-face cap for a 14 px run (ratio 0.7).
TAG_LINES_PX = (("New", 30.4), ("course", 44.8))
TAG_FONT_PX = 14.0
TAG_LINE_HEIGHT = 1.05
TAG_CAP_RATIO = 0.7

#: The face axis LEG-01 measured on the master (assets/objects/tag.webp): the strip the words must
#: lie on. The shipped -30 deg is the angle that keeps every glyph core on the light kraft.
TAG_FACE_AXIS_DEG = -35.5

#: The two CTA runs the audit measures, and the two widths it measures them at.
CTA_RUNS = ("hero-lettering#2", "hero-lettering#3")
WIDTHS = (1344, 1200)
DESIGN_WIDTH = 1344.0

ROOT_REM_PX = 16.0


# --------------------------------------------------------------------------------------------
# Reading the built module
# --------------------------------------------------------------------------------------------

def plugin_source() -> str:
    return PLUGIN_JS.read_text(encoding="utf-8")


def v3_css(source: str | None = None) -> str:
    text = literal_text(plugin_source() if source is None else source, V3_CSS_CONST)
    if text is None:
        raise AssertionError(f"desktop/plugin.js has no {V3_CSS_CONST} literal")
    return text


def v3_tokens(source: str | None = None) -> dict:
    text = literal_text(plugin_source() if source is None else source, V3_TOKEN_CONST)
    if text is None:
        raise AssertionError(f"desktop/plugin.js has no {V3_TOKEN_CONST} literal")
    return json.loads(text)


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
    prelude, body = found[0]
    return {prop: value for prop, value in declarations(body)}


def token_px(value: str) -> float:
    """A type-step value in px: ``1.25rem`` -> 20, ``1rem`` -> 16, ``14px`` -> 14."""
    match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)(rem|px)\s*", value)
    if match is None:
        raise AssertionError(f"type step {value!r} is not a plain rem or px length")
    number, unit = float(match.group(1)), match.group(2)
    return number * ROOT_REM_PX if unit == "rem" else number


def rotation_deg(transform: str) -> float:
    match = re.search(r"rotate\(\s*(-?[0-9]*\.?[0-9]+)deg\s*\)", transform or "")
    if match is None:
        raise AssertionError(f"no rotate() in transform {transform!r}")
    return float(match.group(1))


def translate_x_px(transform: str) -> float:
    match = re.search(r"translateX\(\s*(-?[0-9]*\.?[0-9]+)px\s*\)", transform or "")
    if match is None:
        raise AssertionError(f"no translateX() in transform {transform!r}")
    return float(match.group(1))


# --------------------------------------------------------------------------------------------
# The geometry the pins rest on
# --------------------------------------------------------------------------------------------

def ink_swing_px(lines: tuple[tuple[str, float], ...], line_height_px: float,
                 cap_height_px: float, angle_deg: float) -> float:
    """How far a centred multi-line block's rotated ink bbox moves off the element centre.

    Each line's ink is a rectangle centred on the block's x axis and centred in its own line box.
    Rotating every corner by ``angle_deg`` and taking the bbox's x midpoint reproduces LEG-01's
    measured swing: 3.12 px for ("New", "course") at -30 deg, which is what the -2.7 px translate
    exists to cancel.
    """
    theta = math.radians(angle_deg)
    xs: list[float] = []
    count = len(lines)
    for index, (_word, width) in enumerate(lines):
        centre_y = (index - (count - 1) / 2.0) * line_height_px
        for dx in (-width / 2.0, width / 2.0):
            for dy in (-cap_height_px / 2.0, cap_height_px / 2.0):
                xs.append(dx * math.cos(theta) - (centre_y + dy) * math.sin(theta))
    return (max(xs) + min(xs)) / 2.0


def cap_px(token_value: str, width: int, cap_ratio: float) -> float:
    """The rendered cap of a type step at a measured width: token px x scene scale x face ratio."""
    return token_px(token_value) * (width / DESIGN_WIDTH) * cap_ratio


# The audit, read once: it is evidence, so every pin compares the module against it rather than
# against a number typed into this file.
def audit() -> dict:
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def audit_run(document: dict, run_id: str) -> dict:
    for run in document["runs"]:
        if run["run_id"] == run_id:
            return run
    raise AssertionError(f"the audit has no run {run_id!r}")


def under_floor_widths(run: dict) -> set[int]:
    return {int(width) for width in run["under_floor"]["cap"]}


# --------------------------------------------------------------------------------------------
# Pin 1 — the tag's copy is turned onto its face
# --------------------------------------------------------------------------------------------

class TagOnItsFaceTest(unittest.TestCase):
    """The 74 px tag's words lie on the tilted kraft strip, not across its edges."""

    def setUp(self) -> None:
        self.css = v3_css()
        self.word = rule(self.css, TAG_WORD)
        self.transform = self.word.get("transform", "")
        self.angle = rotation_deg(self.transform)
        self.translate = translate_x_px(self.transform)
        self.box_px = token_px(rule(self.css, TAG_OBJECT)["width"])
        self.document = audit()
        self.tag_run = audit_run(self.document, "tag-lettering#4")

    def test_the_tag_word_rule_turns_the_run_onto_the_face(self) -> None:
        # A pin, not a preference: 0 deg is the horizontal run whose last letters leave the face,
        # and a cosmetic tilt (the box's own -3 deg) is not a turn onto a -35.5 deg strip.
        self.assertNotEqual(self.angle, 0.0, "the tag's copy is not rotated at all")
        self.assertGreaterEqual(
            abs(self.angle), 15.0,
            f"the tag's copy is rotated {self.angle} deg — too shallow to lie on the "
            f"{TAG_FACE_AXIS_DEG} deg kraft face (5.271:1 / 5.918:1 is measured at -30 deg)",
        )
        self.assertAlmostEqual(
            self.angle, -30.0, delta=0.05,
            msg=(
                "the tag's copy is rotated "
                f"{self.angle} deg, not the measured -30 deg: at the face axis "
                f"({TAG_FACE_AXIS_DEG} deg) one glyph core lands on the fold edge "
                "(min 2.10:1 at 1344)"
            ),
        )

    def test_the_translate_holds_ink_centring_inside_the_gate_tolerance(self) -> None:
        cap_height = TAG_FONT_PX * TAG_CAP_RATIO
        swing = ink_swing_px(
            TAG_LINES_PX, TAG_FONT_PX * TAG_LINE_HEIGHT, cap_height, self.angle,
        )
        residual = swing + self.translate
        limit = CENTRING_TOLERANCE * self.box_px
        self.assertLess(self.translate, 0.0, "the swing is rightward; the translate must cancel it")
        self.assertLessEqual(
            abs(residual), limit,
            (
                f"the tag's ink centre sits {residual:.3f} px off the box centre "
                f"({abs(residual) / self.box_px * 100:.2f} % of {self.box_px:g} px, limit "
                f"{limit:.2f} px): turned {self.angle} deg the block's ink swings {swing:.3f} px "
                f"and translateX is {self.translate:g} px."
            ),
        )
        # The audit/LEG-01 record is 0.42 px on a 74 px box.
        self.assertLessEqual(abs(residual), 0.5,
                             f"the centring drifted to {residual:.3f} px from the measured 0.42 px")

    def test_the_audited_contrast_still_describes_the_shipped_run(self) -> None:
        # The audit is the evidence for the turn; if the run's own recorded contrast ever falls back
        # under the floor, the pin above is describing a tree that no longer ships.
        contrast = self.tag_run["measurements"]
        for width in WIDTHS:
            measured = contrast[str(width)]["contrast"]
            self.assertGreaterEqual(
                measured["min"], 3.0,
                f"tag run at {width} px: worst glyph-core pixel {measured['min']}:1",
            )
            self.assertEqual(
                measured["pixels_below_floor"], 0,
                f"tag run at {width} px: {measured['pixels_below_floor']} glyph-core pixels "
                f"under 3.0:1",
            )

    def test_a_reverted_translate_breaks_the_centring_pin(self) -> None:
        # Negative control: the same arithmetic with the translate removed must exceed 4 %.
        cap_height = TAG_FONT_PX * TAG_CAP_RATIO
        swing = ink_swing_px(TAG_LINES_PX, TAG_FONT_PX * TAG_LINE_HEIGHT, cap_height, self.angle)
        limit = CENTRING_TOLERANCE * self.box_px
        self.assertGreater(
            abs(swing), limit,
            f"without translateX the ink centre sits {swing:.3f} px off centre "
            f"({abs(swing) / self.box_px * 100:.2f} %), inside the {limit:.2f} px limit — "
            "the translate pin would have no teeth",
        )


# --------------------------------------------------------------------------------------------
# Pin 2 — the two CTA labels clear the cap floor at both measured widths
# --------------------------------------------------------------------------------------------

def cta_font_step(css: str) -> str:
    """The token name the CTA label rule resolves its ``font-size`` to (``--cb3-text-lead``)."""
    value = rule(css, CTA_BUTTON).get("font-size", "")
    match = re.fullmatch(r"var\(\s*(--cb3-text-[a-z]+)\s*\)", value)
    if match is None:
        raise AssertionError(
            f"the CTA label's font-size is {value!r}: the cap floor is only reachable through a "
            "type-step token, never a literal"
        )
    return match.group(1)


def check_cta_cap_floor(css: str, tokens: dict, document: dict) -> dict[int, float]:
    """Every measured width must clear the floor; otherwise fail naming the caps it measured."""
    step = cta_font_step(css)
    name = step[len("--cb3-text-"):]
    scale = tokens["type"]["scale"]
    if name not in scale:
        raise AssertionError(f"token {step} is not in the module's type scale: {sorted(scale)}")
    ratio = document["type_ladder"]["ui_face_cap_ratio_of_em"]
    measured = {width: cap_px(scale[name], width, ratio) for width in WIDTHS}
    short = {width: cap for width, cap in measured.items() if cap < CAP_FLOOR_PX}
    if short:
        detail = ", ".join(f"{width}: {cap:.2f} px" for width, cap in sorted(short.items()))
        raise AssertionError(
            f"the CTA labels resolve to {step} ({token_px(scale[name]):g} px) and measure "
            f"{detail} — under the {CAP_FLOOR_PX:g} px cap floor (every width: "
            + ", ".join(f"{w}: {c:.2f} px" for w, c in sorted(measured.items()))
            + ")"
        )
    return measured


class CtaCapFloorTest(unittest.TestCase):
    """Both CTA labels sit on the lead step, and their measured cap clears 11 px."""

    def setUp(self) -> None:
        self.source = plugin_source()
        self.css = v3_css(self.source)
        self.tokens = v3_tokens(self.source)
        self.document = audit()

    def test_the_two_cta_labels_resolve_to_the_lead_step(self) -> None:
        step = cta_font_step(self.css)
        self.assertEqual(
            step, "--cb3-text-lead",
            f"the CTA labels resolve to {step}; LEG-01 raised them body -> lead and that is the "
            "fix this pin holds",
        )
        # The audit's own two CTA runs must agree that the step is what renders: read the token,
        # never hardcode 20.
        px = token_px(self.tokens["type"]["scale"][step[len("--cb3-text-"):]])
        for run_id in CTA_RUNS:
            run = audit_run(self.document, run_id)
            self.assertEqual(
                run["measurements"]["1344"]["cap"]["font_size_css_px"], px,
                f"{run_id}: the audit measured a {run['measurements']['1344']['cap']['font_size_css_px']} px "
                f"run, the module's {step} is {px:g} px",
            )
            self.assertEqual(
                run["measurements"]["1200"]["cap"]["font_size_css_px"], px,
                f"{run_id}: the 1200 px capture measured a "
                f"{run['measurements']['1200']['cap']['font_size_css_px']} px run for a {px:g} px step",
            )

    def test_the_measured_cap_clears_the_floor_at_1344_and_1200(self) -> None:
        measured = check_cta_cap_floor(self.css, self.tokens, self.document)
        for width, cap in sorted(measured.items()):
            self.assertGreaterEqual(
                cap, CAP_FLOOR_PX,
                f"CTA cap at {width} px is {cap:.2f} px, under the {CAP_FLOOR_PX:g} px floor",
            )
        # The scene scale the audit recorded is the one this arithmetic assumes.
        ratio = self.document["type_ladder"]["ui_face_cap_ratio_of_em"]
        for width in WIDTHS:
            recorded = audit_run(self.document, CTA_RUNS[0])["measurements"][str(width)]["cap"]
            self.assertAlmostEqual(recorded["scene_scale"], width / DESIGN_WIDTH, delta=1e-6)
            self.assertAlmostEqual(recorded["cap_ratio_of_em"], ratio, delta=1e-9)
            self.assertAlmostEqual(
                recorded["cap_from_ratio_px"], cap_px(self.tokens["type"]["scale"]["lead"], width, ratio),
                delta=0.005,
                msg=(
                    f"at {width} px the audit measured a {recorded['cap_from_ratio_px']} px cap; "
                    "the module's lead step gives a different one — the token or the scene changed"
                ),
            )
        self.assertGreaterEqual(measured[1344], 13.0,
                                f"1344 px cap is {measured[1344]:.2f} px, LEG-01 measured 13.20")
        self.assertGreaterEqual(measured[1200], 11.7,
                                f"1200 px cap is {measured[1200]:.2f} px, LEG-01 measured 11.79")

    def test_the_body_step_would_fail_with_the_cap_it_measures(self) -> None:
        # Negative control on the same code path: force the rule back to the body step and the
        # floor check must fail, naming the cap it measured (10.56 / 9.43 px).
        forced = self.css.replace(
            f"font-size: var({cta_font_step(self.css)});",
            "font-size: var(--cb3-text-body);",
        )
        self.assertNotEqual(forced, self.css, "the CTA rule does not carry a type-step font-size")
        with self.assertRaises(AssertionError) as caught:
            check_cta_cap_floor(forced, self.tokens, self.document)
        message = str(caught.exception)
        self.assertIn("--cb3-text-body", message)
        self.assertIn("10.56 px", message, message)
        self.assertIn("9.43 px", message, message)
        self.assertIn("under the 11 px cap floor", message, message)


# --------------------------------------------------------------------------------------------
# Pin 3 — the exception ledger and the audit agree on run ids
# --------------------------------------------------------------------------------------------

class ExceptionLedgerTest(unittest.TestCase):
    """The five under-floor runs are explicit exceptions, and no exception outlives its run."""

    def setUp(self) -> None:
        self.document = audit()
        self.ledger = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))

    def _entries(self) -> dict[str, dict]:
        entries: dict[str, dict] = {}
        for entry in self.ledger["exceptions"]:
            run_id = entry["run_id"]
            self.assertNotIn(run_id, entries, f"{run_id} is in the ledger twice")
            entries[run_id] = entry
        return entries

    def test_the_ledger_covers_every_under_floor_run_and_only_those(self) -> None:
        entries = self._entries()
        audited = set(self.document["summary"]["runs_under_cap_floor"])
        # Also read the per-run verdict, so a hand-edited summary cannot vouch for the ledger.
        per_run = {run["run_id"] for run in self.document["runs"] if under_floor_widths(run)}
        self.assertEqual(audited, per_run,
                         "the audit's summary and its per-run under_floor verdicts disagree")
        self.assertEqual(
            set(entries), audited,
            "the exception ledger and the audit disagree on which runs are under the cap floor: "
            f"only in the ledger {sorted(set(entries) - audited)}, "
            f"only in the audit {sorted(audited - set(entries))}",
        )

    def test_each_exception_carries_the_audited_cap_and_clip_at_each_width(self) -> None:
        floor = self.ledger["floor_cap_px"]
        self.assertEqual(floor, CAP_FLOOR_PX, "the ledger's floor is not the audit's floor")
        self.assertEqual(floor, self.document["floors"]["cap_px"])
        for run_id, entry in sorted(self._entries().items()):
            run = audit_run(self.document, run_id)
            widths = {int(width) for width in entry["widths"]}
            self.assertEqual(
                widths, under_floor_widths(run),
                f"{run_id}: the ledger claims widths {sorted(widths)} but the audit measures it "
                f"under the floor at {sorted(under_floor_widths(run))}",
            )
            self.assertGreaterEqual(
                len(entry["why_it_cannot_absorb_an_11px_cap"].strip()), 40,
                f"{run_id}: the exception names no reason the object cannot absorb the cap",
            )
            for width in sorted(widths):
                measured = run["measurements"][str(width)]
                cap = measured["cap"]["cap_from_ratio_px"]
                self.assertLess(cap, floor, f"{run_id} at {width} px clears the floor at {cap} px")
                self.assertAlmostEqual(
                    entry["measured_cap_px"][str(width)], cap, delta=0.005,
                    msg=(
                        f"{run_id} at {width} px: the ledger quotes "
                        f"{entry['measured_cap_px'][str(width)]} px, the audit measured {cap} px"
                    ),
                )
                probe = run["remedy"]["cap_floor"]["probe_by_width"][str(width)]
                clip = max((item.get("dy", 0) for item in probe.get("clipping") or []), default=0)
                self.assertEqual(
                    entry["measured_clip_px"][str(width)], clip,
                    f"{run_id} at {width} px: the ledger quotes {entry['measured_clip_px'][str(width)]} px "
                    f"of clip, the probe measured {clip} px",
                )
                self.assertAlmostEqual(
                    entry["needed_font_px"], run["remedy"]["cap_floor"]["needed_font_size_css_px"],
                    delta=0.01,
                    msg=(
                        f"{run_id}: the ledger quotes {entry['needed_font_px']} px as the floor size, "
                        f"the audit measured {run['remedy']['cap_floor']['needed_font_size_css_px']} px"
                    ),
                )

    def test_the_ledger_points_at_the_audit_it_agrees_with(self) -> None:
        self.assertEqual(self.ledger["audit"], str(AUDIT.relative_to(ROOT)))
        self.assertTrue(AUDIT.exists(), "the audit the ledger names is gone")
        self.assertEqual(
            self.document["schema"], "coursebook.text-legibility/1",
            "the audit's schema changed: re-read its run ids before trusting the ledger",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
