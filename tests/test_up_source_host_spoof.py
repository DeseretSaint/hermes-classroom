"""A ``.gov`` substring must not decide who publishes a source.

``_classify_source`` ranks the type it returns against ``SOURCE_TYPE_RANK``, where ``government``
sorts first and therefore wins the page budget. A host that merely *contains* ``.gov.`` anywhere —
``foo.gov.attacker.example`` — is not published by a government, so it must classify as the
ordinary ``web_page`` it is. The decision is made on the host's public suffix from the vendored
Public Suffix List (``coursebook/data/public_suffix_list.dat``, read from disk so the lookup is
offline and needs no install), never on a substring.
"""

from __future__ import annotations

import unittest

from coursebook import research


class SourceHostSpoofTest(unittest.TestCase):
    def test_a_gov_substring_is_not_government(self) -> None:
        """The lookalike is a web page; a real ``.gov`` host is still government."""
        self.assertEqual(research._classify_source("https://foo.gov.attacker.example/x"), "web_page")
        self.assertEqual(research._classify_source("https://www.nasa.gov/x"), "government")

    def test_a_government_lookalike_does_not_win_the_page_budget(self) -> None:
        """Ranking is what the learner sees: the spoof must not outrank a real source."""
        spoof = research._classify_source("https://foo.gov.attacker.example/x")
        real = research._classify_source("https://www.nasa.gov/x")
        self.assertGreater(research.SOURCE_TYPE_RANK[spoof], research.SOURCE_TYPE_RANK[real])

    def test_real_government_suffixes_still_classify(self) -> None:
        for url in (
            "https://www.nasa.gov/x",
            "https://www.gov.uk/government/statistics",
            "https://www.defense.mil/news",
            "https://www.nato.int/cps/en/natohq",
        ):
            with self.subTest(url=url):
                self.assertEqual(research._classify_source(url), "government")

    def test_other_trusted_suffixes_are_not_spoofed(self) -> None:
        """The same substring bug applies to ``.edu``, ``.org`` and the reference works."""
        cases = {
            "https://foo.edu.attacker.example/x": "web_page",
            "https://foo.org.attacker.example/x": "web_page",
            "https://foo.ac.attacker.example/x": "web_page",
            "https://wikipedia.org.attacker.example/x": "web_page",
            "https://cs.stanford.edu/x": "academic",
            "https://www.britschool.ac.uk/x": "academic",
            "https://www.mozilla.org/x": "organization",
            "https://en.wikipedia.org/wiki/Japan": "reference",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(research._classify_source(url), expected)

    def test_classification_survives_a_port_and_userinfo(self) -> None:
        """The host test reads the host name, not the netloc with its port."""
        self.assertEqual(research._classify_source("https://www.nasa.gov:443/x"), "government")
        self.assertEqual(
            research._classify_source("https://user@foo.gov.attacker.example:8443/x"), "web_page"
        )


if __name__ == "__main__":
    unittest.main()
