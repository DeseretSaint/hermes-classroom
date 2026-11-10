"""CP-038 — addressable destinations, click and scroll hooks in the capture door.

The CP-000 door could only ever photograph Home: it reloaded before setting the hash, the plugin's
destination is product state (not a hash), and no destination/click/scroll argument existed. These
tests exercise the real `scripts/cp-capture.mjs` against recorded fixture pages that publish the
same DOM contract the plugin renders (`[data-cb-route]`, `[data-cb-destination]`, nav items, shelf
cards, section rows). Chromium is used for the same crop the live path uses; the tests skip when
node or chromium is unavailable.

Covered here:
  * Home still works and its stamp is unchanged in shape (backwards compatibility).
  * A non-Home destination is reached through its product control and the stamp records that route.
  * A course destination opens that course's own surface.
  * A destination with no addressable control exits non-zero and writes no frame.
  * A destination control that renders a different route exits non-zero and writes no frame.
  * A lazy offscreen route image is forced to decode before the decoded-images gate.
  * `--click` and `--scroll` are applied, resolved and recorded in the stamp.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cp-capture.mjs"
FIXTURES = ROOT / "tests" / "fixtures" / "cp-capture"
VALID_SHA = "a" * 64

STAMP_KEYS = {
    "stamp_version", "tool", "mode", "name", "captured_at", "ok", "gates", "plugin",
    "backend", "route", "console", "capture", "page_url", "zoom",
    "destination", "clicks", "scroll",
}
DESTINATION_KEYS = {
    "requested", "normalized", "rendered", "rendered_course_home", "rendered_lesson_view",
    "match", "controls",
}


def run_capture(tmp: Path, fixture: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "node", str(SCRIPT), "--name", Path(fixture).stem, "--out", str(tmp),
            "--fixture", str(FIXTURES / fixture), "--expect-sha", VALID_SHA, *extra,
        ],
        capture_output=True, text=True, timeout=120, cwd=str(ROOT),
    )


@unittest.skipUnless(shutil.which("node") and shutil.which("chromium"),
                     "node + chromium are required for the capture door route tests")
class CaptureRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cp038-route-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stamp(self, fixture: str) -> dict:
        return json.loads((self.tmp / f"{Path(fixture).stem}.stamp.json").read_text())

    def test_home_capture_is_unchanged(self) -> None:
        completed = run_capture(self.tmp, "ok.html", "--require-v3")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stamp = self._stamp("ok.html")
        self.assertTrue(STAMP_KEYS.issubset(stamp), sorted(STAMP_KEYS - set(stamp)))
        # No destination requested is not a mismatch: the stamp says so explicitly.
        self.assertIsNone(stamp["destination"]["requested"])
        self.assertIsNone(stamp["destination"]["match"])
        self.assertEqual(stamp["destination"]["rendered"], "home")
        self.assertEqual(stamp["route"]["destination"], "home")
        self.assertEqual(stamp["clicks"], [])
        self.assertIsNone(stamp["scroll"])
        self.assertTrue(all(stamp["gates"].values()))

    def test_non_home_destination_renders_that_route(self) -> None:
        completed = run_capture(self.tmp, "dest-nav.html", "--destination", "#/workshop")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stamp = self._stamp("dest-nav.html")
        self.assertTrue(DESTINATION_KEYS.issubset(stamp["destination"]))
        self.assertEqual(stamp["destination"]["requested"], "#/workshop")
        self.assertEqual(stamp["destination"]["normalized"], "workshop")
        self.assertEqual(stamp["destination"]["rendered"], "workshop")
        self.assertEqual(stamp["route"]["destination"], "workshop")
        self.assertTrue(stamp["destination"]["match"])
        # The destination was reached by clicking the product's own control.
        self.assertEqual(stamp["destination"]["controls"][0]["selector"], '[data-cb-nav-item="workshop"]')
        self.assertTrue(stamp["destination"]["controls"][0]["found"])
        png = self.tmp / stamp["capture"]["file"]
        self.assertTrue(png.is_file())

    def test_course_destination_opens_that_course(self) -> None:
        completed = run_capture(self.tmp, "dest-nav.html", "--destination", "#/course/course-1")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stamp = self._stamp("dest-nav.html")
        self.assertEqual(stamp["destination"]["normalized"], "course/course-1")
        self.assertEqual(stamp["route"]["course_home"], "course-1")
        self.assertEqual(stamp["destination"]["rendered_course_home"], "course-1")
        self.assertTrue(stamp["destination"]["match"])

    def test_wrong_destination_refuses_without_a_frame(self) -> None:
        # This surface has no control that reaches Workshop. The door must not photograph the Home
        # frame under a Workshop name.
        completed = run_capture(self.tmp, "dest-home-only.html", "--destination", "workshop")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "dest-home-only.refused.json").read_text())
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["stage"], "destination")
        self.assertTrue(any("no addressable control" in reason for reason in refused["reasons"]))
        self.assertFalse((self.tmp / "dest-home-only.png").exists())
        self.assertFalse((self.tmp / "dest-home-only.stamp.json").exists())

    def test_click_that_renders_a_different_destination_is_refused(self) -> None:
        # The CP-021 defect itself: the Workshop control exists and is clicked, but the surface
        # stays on Home. This is the card's central guarantee — never save a Home frame under a
        # Workshop name — so the refusal record must show the click and the mismatch.
        completed = run_capture(self.tmp, "dest-mismatch.html", "--destination", "workshop")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "dest-mismatch.refused.json").read_text())
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["stage"], "destination")
        self.assertTrue(any("was not rendered" in reason for reason in refused["reasons"]))
        destination = refused["destination"]
        self.assertEqual(destination["requested"], "workshop")
        self.assertEqual(destination["normalized"], "workshop")
        self.assertIs(destination["match"], False)
        self.assertEqual(destination["rendered"]["route"], "home")
        # The control was really clicked: the refusal proves the mismatch, not a missing control.
        self.assertEqual(len(destination["controls"]), 1)
        self.assertEqual(destination["controls"][0]["selector"], '[data-cb-nav-item="workshop"]')
        self.assertTrue(destination["controls"][0]["found"])
        self.assertFalse((self.tmp / "dest-mismatch.png").exists())
        self.assertFalse((self.tmp / "dest-mismatch.stamp.json").exists())

    def test_lazy_offscreen_image_is_forced_to_decode(self) -> None:
        # The Workshop's non-hero covers are loading="lazy" and sit below the capture viewport, so a
        # passive wait polls `{total:1,pending:1}` forever and the frame can never be captured.
        # This fixture puts its cover ~20000px down the page, where Chromium will not load it on
        # its own (the previous door refused this exact fixture); the door must force it.
        completed = run_capture(self.tmp, "lazy-image.html", "--image-wait", "6000")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stamp = self._stamp("lazy-image.html")
        self.assertEqual(stamp["route"]["images_total"], 1)
        self.assertEqual(stamp["route"]["images_decoded"], 1)
        self.assertTrue(stamp["gates"]["images_decoded"])

    def test_success_clears_a_stale_refusal_record(self) -> None:
        # A refusal for the same name must not survive a later success: the packet would carry
        # both "REFUSED" and "OK" for one still.
        stale = self.tmp / "ok.refused.json"
        stale.write_text('{"ok": false}\n')
        completed = run_capture(self.tmp, "ok.html", "--require-v3")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(stale.exists())

    def test_appearance_setting_produces_a_real_light_frame(self) -> None:
        # B3: the palette is a product setting, not prefers-color-scheme. The door drives the
        # settings sheet, the route repaints, and the stamp records both the request and the paint.
        completed = run_capture(self.tmp, "appearance.html", "--appearance", "light")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stamp = self._stamp("appearance.html")
        self.assertEqual(stamp["route"]["theme"], "light")
        self.assertEqual(stamp["appearance"]["requested"], "light")
        self.assertEqual(stamp["appearance"]["before"], "system")
        self.assertTrue(stamp["appearance"]["applied"])
        self.assertEqual(stamp["appearance"]["rendered_scope"], "light")
        self.assertTrue(stamp["gates"]["appearance_applied"])
        self.assertIsNone(stamp["emulated_media"])  # nothing was emulated
        self.assertEqual(
            [click["purpose"] for click in stamp["appearance"]["clicks"]],
            ["appearance-open", "appearance-light", "appearance-close"],
        )
        self.assertFalse((self.tmp / "appearance.refused.json").exists())

    def test_unknown_appearance_refuses(self) -> None:
        completed = run_capture(self.tmp, "appearance.html", "--appearance", "sepia")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "appearance.refused.json").read_text())
        self.assertEqual(refused["stage"], "appearance")
        self.assertTrue(any("unknown --appearance" in reason for reason in refused["reasons"]))
        self.assertFalse((self.tmp / "appearance.png").exists())
        self.assertFalse((self.tmp / "appearance.stamp.json").exists())

    def test_unknown_destination_refuses(self) -> None:
        completed = run_capture(self.tmp, "dest-nav.html", "--destination", "#/nowhere")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "dest-nav.refused.json").read_text())
        self.assertEqual(refused["stage"], "destination")
        self.assertTrue(any("unknown --destination" in reason for reason in refused["reasons"]))
        self.assertFalse((self.tmp / "dest-nav.png").exists())
        self.assertFalse((self.tmp / "dest-nav.stamp.json").exists())

    def test_click_and_scroll_are_applied_and_stamped(self) -> None:
        completed = run_capture(
            self.tmp, "dest-nav.html",
            "--destination", "workshop",
            "--click", "[data-cb-open-check]",
            "--scroll", "300",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        stamp = self._stamp("dest-nav.html")
        self.assertEqual(len(stamp["clicks"]), 1)
        self.assertEqual(stamp["clicks"][0]["selector"], "[data-cb-open-check]")
        self.assertTrue(stamp["clicks"][0]["found"])
        # The click-through state is observable in the route's own markers, not merely dispatched.
        self.assertIn("data-cb-check-open", stamp["route"]["marker_names"])
        self.assertEqual(stamp["scroll"]["kind"], "px")
        self.assertEqual(stamp["scroll"]["target"], "300")
        self.assertEqual(stamp["scroll"]["y"], 300)
        # The scroll happened inside the route, so the crop still frames the route itself.
        self.assertEqual(stamp["scroll"]["scroller"], "route-descendant")

    def test_click_selector_that_matches_nothing_refuses(self) -> None:
        completed = run_capture(self.tmp, "dest-nav.html", "--click", "[data-cb-does-not-exist]")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "dest-nav.refused.json").read_text())
        self.assertEqual(refused["stage"], "click")
        self.assertTrue(any("matched no element" in reason for reason in refused["reasons"]))
        self.assertFalse((self.tmp / "dest-nav.png").exists())
        self.assertFalse((self.tmp / "dest-nav.stamp.json").exists())

    def test_scroll_selector_that_matches_nothing_refuses(self) -> None:
        completed = run_capture(self.tmp, "dest-nav.html", "--scroll", "[data-cb-not-there]")
        self.assertEqual(completed.returncode, 2, completed.stderr)
        refused = json.loads((self.tmp / "dest-nav.refused.json").read_text())
        self.assertEqual(refused["stage"], "scroll")
        self.assertTrue(any("matched no element" in reason for reason in refused["reasons"]))
        self.assertFalse((self.tmp / "dest-nav.png").exists())


if __name__ == "__main__":
    unittest.main()
