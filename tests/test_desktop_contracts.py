"""The Desktop half mirrors contract enums; those copies must not drift.

`desktop/plugin.js` may not import the Python contract loader, so the small enum sets it needs to
render a form (recipe choices, dial filters, course dials) are written as literals. This test reads
those literals back out of the module and compares them with the frozen JSON contracts, so a
contract amendment fails here instead of shipping a form that offers a value the backend refuses.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "desktop" / "plugin.js"


def _source() -> str:
    return PLUGIN.read_text(encoding="utf-8")


def _contract(name: str) -> dict:
    return json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))


def _string_list(source: str, marker: str) -> list[str]:
    """The single-quoted string literals of the array literal that follows `marker`."""
    start = source.index(marker)
    end = source.index("]", start)
    return re.findall(r"'([a-z_]+)'", source[start:end])


def _dial_options(source: str, dial: str) -> list[str]:
    start = source.index(f"{dial}: {{")
    end = source.index("]", start)
    return re.findall(r"id: '([a-z_]+)'", source[start:end])


class DesktopContractMirrorTest(unittest.TestCase):
    def test_recipes_match_the_vocabulary(self) -> None:
        vocabulary = _contract("vocabulary.v1.json")
        expected = vocabulary["$defs"]["recipe"]["enum"]
        self.assertEqual(_string_list(_source(), "const RECIPES = ["), expected)

    def test_dial_options_match_course_create(self) -> None:
        rpc = _contract("rpc.v2.json")
        request = rpc["$defs"]["methods"]["properties"]["course.create"]["request"]
        dials = request["properties"]["dials"]["properties"]
        source = _source()
        for dial, schema in dials.items():
            with self.subTest(dial=dial):
                self.assertEqual(_dial_options(source, dial), schema["enum"])

    def test_library_filters_match_the_request_enum(self) -> None:
        rpc = _contract("rpc.v2.json")
        request = rpc["$defs"]["methods"]["properties"]["library.list"]["request"]
        expected = request["properties"]["filter"]["enum"]
        self.assertEqual(_string_list(_source(), "const FILTERS = ["), expected)

    def test_filtered_empty_accounts_for_a_search_query(self) -> None:
        # With courses on the profile, an empty result set caused by the search box must render the
        # filtered-empty state (which offers Clear search), never first-run. `applied_filter` alone
        # missed the search case and told a learner with courses that they had none.
        source = _source()
        start = source.index("const filteredEmpty =")
        block = source[start : source.index("\n\n", start)]
        self.assertIn("applied_filter", block)
        self.assertIn("query", block, "the search term must count as a filter")

    def test_navigation_uses_the_contributed_route_and_one_segment(self) -> None:
        source = _source()
        self.assertIn("const ROUTE_PATH = '/coursebook'", source)
        # One static segment: no nested or parameterised coursebook route literal.
        self.assertNotRegex(source, r"'/coursebook[/:]")

    def test_every_gated_control_names_a_contract_method(self) -> None:
        # A control gated on a method that the contract does not define could never light up.
        rpc = _contract("rpc.v2.json")
        methods = set(rpc["$defs"]["method"]["enum"])
        source = _source()
        named = set(re.findall(r"supports\('([a-z_]+\.[a-z_]+)'\)", source))
        named |= set(re.findall(r"implemented\.has\('([a-z_]+\.[a-z_]+)'\)", source))
        named |= set(re.findall(r"backendSupports\('([a-z_]+\.[a-z_]+)'\)", source))
        self.assertTrue(named, "no gated controls found")
        self.assertEqual(sorted(named - methods), [])


if __name__ == "__main__":
    unittest.main()
