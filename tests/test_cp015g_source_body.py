"""CP-015g: the excerpt a source offers must be the page's prose, not its furniture.

Three of eight sources in the CP-015g live run handed the plan author 600 characters of
navigation (skip links, subject menus, logo alt text). These tests pin the extraction contract:

* a page whose body is preceded by more than the excerpt budget of menu yields the body;
* a PDF whose extracted text starts with a document header yields the body under it;
* a page with no extractable body is recorded honestly as ``no_body`` (empty excerpt), never
  chrome dressed as an excerpt;
* a normal page is unchanged, and the excerpt budget is long enough to hold the claim's sentence.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from coursebook import generation as gen
from coursebook import research

NOW = datetime(2026, 11, 11, 13, 20, tzinfo=timezone.utc)

#: A navigation shell of the shape the live run hit: skip link, search box, subject menu, share
#: rail, logo alt text and cookie notice. Every block here is page furniture, not prose.
MENU = "\n\n".join(
    [
        "[Skip to content](https://www.example.org/article#main)",
        "Search",
        "## Suggested Searches",
        "- [Artemis](https://www.example.org/?search=Artemis)\n"
        "- [ISS](https://www.example.org/?search=ISS)\n"
        "- [Roman](https://www.example.org/?search=Roman)\n"
        "- [Webb](https://www.example.org/?search=Webb)\n"
        "- [Quesst](https://www.example.org/?search=Quesst)\n"
        "- [Moon Base](https://www.example.org/?search=Moon%20Base)",
        "- [Home](https://www.example.org/)\n"
        "- [Missions](https://www.example.org/missions/)\n"
        "- [Humans in Space](https://www.example.org/humans/)\n"
        "- [Earth](https://www.example.org/earth/)\n"
        "- [The Solar System](https://www.example.org/solar-system/)\n"
        "- [The Universe](https://www.example.org/universe/)",
        "![Site logo](https://www.example.org/theme/logo.svg)",
        "Share:",
        "- [Share on X](https://x.com/share?url=https://www.example.org/article)\n"
        "- [Share on Facebook](https://facebook.com/share?url=https://www.example.org/article)\n"
        "- [Share on LinkedIn](https://linkedin.com/share?url=https://www.example.org/article)",
        "We use cookies which are essential for you to access our website. "
        "Accept all cookies Accept only essential cookies [See our cookie notice](https://www.example.org/cookies)",
    ]
)

BODY = (
    "Jupiter is easy to observe at night with the unaided eye. It can be one of the brightest "
    "objects in our night sky, bested only by the Moon, Venus and occasionally Mars. Most "
    "telescopes will show the four Galilean moons as faint star-like objects lined up close to "
    "the bright planet. Sketching their positions over the course of an evening is a rewarding "
    "project. Io, Europa, Ganymede and Callisto orbit Jupiter quickly enough that their "
    "arrangement changes noticeably from night to night."
)

SECOND_PARAGRAPH = (
    "A small telescope will reveal all four moons when they are visible, but a moon can pass "
    "behind the planet or in front of it. The shadow of a moon crossing Jupiter's cloud tops is "
    "called a transit, and it is visible in even a modest instrument."
)


class RecordingSeam:
    """A seam that serves one page and records the window it was asked for."""

    def __init__(self, *, url: str, content: str, title: str = "Page") -> None:
        self.url = url
        self.content = content
        self.title = title
        self.windows: list[int] = []

    def search(self, query: str, limit: int) -> list[dict]:
        return [{"url": self.url, "title": self.title, "description": "snippet"}]

    def fetch(self, url: str, max_chars: int) -> dict:
        self.windows.append(max_chars)
        return {"url": url, "title": self.title, "content": self.content, "published_at": None}


def fetch_one(content: str) -> research.SourceRecord:
    seam = RecordingSeam(url="https://www.example.org/article", content=content)
    run = research.run_research("observe Jupiter's moons", recipe="casual", search=seam, now=NOW)
    assert run.status == "ok", run.reason
    assert len(run.sources) == 1
    return run.sources[0]


class SourceExcerptTest(unittest.TestCase):
    def test_the_body_after_a_long_menu_is_what_the_author_gets(self) -> None:
        source = fetch_one(MENU + "\n\n" + BODY)
        self.assertEqual(source.excerpt_state, "recorded")
        self.assertTrue(source.excerpt.startswith("Jupiter is easy to observe at night"), source.excerpt)
        for chrome in ("Skip to content", "Suggested Searches", "Share on", "cookies", "logo"):
            self.assertNotIn(chrome, source.excerpt)
        # The content hash covers the same kept text the excerpt is taken from.
        self.assertEqual(source.content_hash, research.sha256_of_text(source.excerpt))

    def test_the_article_past_the_page_bound_is_still_reached(self) -> None:
        # The article starts past the default 6000-character page bound: the seam must be asked
        # for a wider window than the stored body, or the body can never be seen.
        long_menu = "\n\n".join([MENU] * 6)
        self.assertGreater(len(long_menu), research.ResearchBudget().max_page_chars)
        seam = RecordingSeam(url="https://www.example.org/article", content=long_menu + "\n\n" + BODY)
        run = research.run_research("observe Jupiter's moons", recipe="casual", search=seam, now=NOW)
        self.assertEqual(run.status, "ok", run.reason)
        self.assertEqual(seam.windows, [research.EXTRACT_WINDOW_CHARS])
        self.assertTrue(run.sources[0].excerpt.startswith("Jupiter is easy to observe"))

    def test_a_pdf_header_is_not_the_excerpt(self) -> None:
        pdf = "\n\n".join(
            [
                "CESAR Science Case – Observing the planets and the Jupiter's moons",
                "Student's guide (v2.1)  |  ESA Education  |  Printed 2019",
                "# Student's guide",
                "## Introduction",
                "The scientist that first used the telescope and observed the night sky was "
                "Galileo Galilei. In the year of 1609 he pointed his telescope and saw things "
                "that were never seen before, including bodies orbiting Jupiter. He did all of "
                "this with a homemade telescope that magnified about eight or nine times, and "
                "the instrument he used was a refractor: a telescope built from magnifying lenses.",
                "Since then the telescope has been developed increasingly, and now they are more "
                "sophisticated than ever. There are earthbound telescopes, and even those that "
                "are in space, such as the Hubble Space Telescope, a huge reflector situated "
                "outside the Earth's atmosphere.",
            ]
        )
        source = fetch_one(pdf)
        self.assertEqual(source.excerpt_state, "recorded")
        self.assertTrue(source.excerpt.startswith("The scientist that first used the telescope"), source.excerpt)
        self.assertNotIn("CESAR Science Case", source.excerpt)
        self.assertNotIn("Printed 2019", source.excerpt)

    def test_a_page_with_no_extractable_body_is_not_citable_and_says_so(self) -> None:
        source = fetch_one(MENU)
        self.assertEqual(source.excerpt, "")
        self.assertEqual(source.excerpt_state, "no_body")
        # The record still carries provenance: a source was fetched, it just has no prose.
        self.assertEqual(source.url, "https://www.example.org/article")
        self.assertTrue(source.content_hash.startswith("sha256:"))
        # Nothing a model could quote: neither chrome nor invented body text links a claim.
        self.assertIsNotNone(
            research.claim_verdict_link_problem(
                {"support": "supported", "evidence_quote": "Skip to content"}, source
            )
        )
        self.assertIsNotNone(
            research.claim_verdict_link_problem(
                {"support": "supported", "evidence_quote": BODY[:60]}, source
            )
        )

    def test_a_normal_page_is_unchanged(self) -> None:
        source = fetch_one(BODY)
        self.assertEqual(source.excerpt_state, "recorded")
        self.assertEqual(source.excerpt, BODY)
        self.assertEqual(source.content_hash, research.sha256_of_text(BODY))

    def test_the_excerpt_budget_holds_the_sentence_that_states_the_claim(self) -> None:
        self.assertGreater(research._MAX_EXCERPT, 600)
        first = (
            "Observers should give binoculars and telescopes twenty to thirty minutes outside "
            "to reach the ambient temperature before beginning. A cold instrument will fog at "
            "the eyepiece and a warm one will shimmer, so patience here pays for itself. Choose "
            "a spot away from streetlights and let your eyes adapt to the dark for at least ten "
            "minutes before you judge what you can see."
        )
        second = (
            "Point the instrument at Jupiter, which should be the brightest steady object in "
            "that part of the sky, and focus carefully. Most binoculars will show at least one "
            "or two moons orbiting the planet, and a modest instrument shows all four Galilean "
            "moons when they are visible."
        )
        page = "\n\n".join([first, second, SECOND_PARAGRAPH])
        source = fetch_one(page)
        self.assertGreater(len(source.excerpt), 600)
        self.assertIn("a modest instrument shows all four Galilean moons", source.excerpt)
        self.assertIn("called a transit", source.excerpt)
        self.assertLessEqual(len(source.excerpt), research._MAX_EXCERPT)
        self.assertIsNone(
            research.claim_verdict_link_problem(
                {"support": "supported", "evidence_quote": "it is visible in even a modest instrument"},
                source,
            )
        )

    def test_the_source_brief_states_the_absence(self) -> None:
        source = fetch_one(MENU)
        brief = gen._source_brief([source])[0]
        self.assertEqual(brief["excerpt_state"], "no_body")
        self.assertNotIn("Skip to content", brief["untrusted_excerpt"])
        self.assertNotIn("Suggested Searches", brief["untrusted_excerpt"])

    def test_a_record_with_no_excerpt_is_typed_no_body(self) -> None:
        record = research.SourceRecord(
            source_id="s1",
            url="https://example.org/x",
            title="X",
            publisher="example.org",
            source_type="web_page",
            fetched_at="2026-11-11T00:00:00Z",
            published_at=None,
            content_hash="sha256:00",
        )
        self.assertEqual(record.excerpt_state, "no_body")
        with self.assertRaises(ValueError):
            research.SourceRecord(
                source_id="s2",
                url="https://example.org/y",
                title="Y",
                publisher="example.org",
                source_type="web_page",
                fetched_at="2026-11-11T00:00:00Z",
                published_at=None,
                content_hash="sha256:00",
                excerpt="text",
                excerpt_state="chrome",
            )


if __name__ == "__main__":
    unittest.main()
