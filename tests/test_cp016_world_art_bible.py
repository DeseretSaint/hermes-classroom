"""CP-016: the runtime world prompts speak the v3 art bible.

The bible (`docs/concept-parity/ART-BIBLE.md` §1–§2) fixes one painted medium for every plate:
opaque gouache on a warm paper ground, a dark-brown ink contour drawn last, one soft key light
from the upper left, and at most five pigments from the bible table. The v3 contract
(`contracts/cb.tokens.v3.json`) binds those pigments to the roles the UI paints with.

These tests are the contract between the bible and `coursebook/world.py`. They fail if a grammar
drifts back to drypoint etching, an off-palette pigment, a black contour, a second light source,
or a sixth pigment; if the textless negatives or the fox rule lose a line; and if the additive 3:2
card role ever changes one of the four shipped aspect ratios.
"""

from __future__ import annotations

import re
import unittest

from coursebook import gm_contract, world

HEX = re.compile(r"#[0-9a-fA-F]{6}")

#: The four shipped roles keep these exact ratios. Never edit this tuple to add a role.
LEGACY_ASPECTS = {
    "style_board": "3:2",
    "hero": "16:9",
    "cover": "4:5",
    "section": "1:1",
}

#: The textless block and the fox rule, kept verbatim from the pre-v3 prompt.
KEPT_NEGATIVES = (
    "no text",
    "no letters, words or labels",
    "no numbers or measurements",
    "no logos or brand marks",
    "no watermarks",
    "no ui chrome, buttons or frames",
    "no answer content, check text or rubric",
    "no mascot other than the fox",
    "no robots",
)

#: ART-BIBLE §5, in imperative negative form.
BIBLE_NEGATIVES = (
    "no gradient, glow or glass",
    "no drop shadow on the art object",
    "no black outline and no grey shade",
    "no off-palette colour",
    "no photorealism or photographic texture",
    "no star, rating, price or learner count",
)

#: A medium that is not the bible's painted plate. The v3 direction has exactly one technique.
FORBIDDEN_MEDIA = (
    "etching",
    "drypoint",
    "airbrush",
    "watercolour wash",
    "watercolor wash",
    "gradient",
    "glow",
    "glass",
    "3d render",
    "photograph",
)

BRIEF = {
    "course_id": "course_cp016",
    "title": "Sourdough starter at home",
    "subject_domain": "cooking",
    "end_capability": "Keep a starter alive and bake a first loaf",
    "audience": "adult learner",
    "tone": "warm, practical",
    "motifs": ["work surface", "ceramic bowl"],
    "sections": [
        {"id": "s1", "title": "Feeding the starter"},
        {"id": "s2", "title": "Shaping the loaf"},
    ],
}


def _hexes(value: str) -> set[str]:
    return {item.lower() for item in HEX.findall(value)}


def _bible_hexes() -> set[str]:
    found: set[str] = set()
    for value in world.ART_BIBLE_PIGMENTS.values():
        found |= _hexes(value)
    return found


class ArtBibleMediumTest(unittest.TestCase):
    def test_every_grammar_speaks_one_painted_medium(self) -> None:
        for name, record in world.GRAMMARS.items():
            with self.subTest(grammar=name):
                medium = record.medium.lower()
                self.assertIn("opaque gouache", medium)
                self.assertIn("warm paper ground", medium)
                self.assertIn("dark-brown ink contour", medium)
                self.assertIn("never black", medium)
                self.assertIsNone(re.search(r"\d", medium), "medium text carries a digit")
                for banned in FORBIDDEN_MEDIA:
                    self.assertIsNone(
                        re.search(rf"\b{re.escape(banned)}\b", medium),
                        f"{name} medium names {banned!r}",
                    )

    def test_every_grammar_palette_is_inside_the_bible_table(self) -> None:
        allowed = _bible_hexes()
        self.assertTrue(allowed)
        for name, record in world.GRAMMARS.items():
            with self.subTest(grammar=name):
                self.assertLessEqual(len(record.palette), world.MAX_PLATE_PIGMENTS)
                used = set().union(*(_hexes(item) for item in record.palette))
                self.assertTrue(used)
                self.assertTrue(used <= allowed, f"{name} uses {sorted(used - allowed)}")
                # Paper ground and the ink line are on every plate.
                self.assertIn("#f7f1e4", used)
                self.assertIn("#3a2318", used)

    def test_style_directions_share_the_medium_and_stay_on_palette(self) -> None:
        self.assertEqual(len(world.STYLE_DIRECTIONS), 3)
        self.assertEqual(len({item["id"] for item in world.STYLE_DIRECTIONS}), 3)
        allowed = _bible_hexes()
        for direction in world.STYLE_DIRECTIONS:
            with self.subTest(direction=direction["id"]):
                shift = direction["medium_shift"].lower()
                if direction["id"] != "authored":
                    self.assertNotIn("as authored", shift)
                for banned in FORBIDDEN_MEDIA:
                    self.assertIsNone(
                        re.search(rf"\b{re.escape(banned)}\b", shift),
                        f"{direction['id']} medium names {banned!r}",
                    )
                light = direction["light"].lower()
                self.assertIn("upper left", light)
                self.assertIn("above the horizon", light)
                self.assertIsNone(re.search(r"\d", light), "direction light carries a digit")
                used = _hexes(direction["palette_shift"])
                self.assertTrue(used <= allowed, sorted(used - allowed))

    def test_prompt_body_carries_the_bible(self) -> None:
        brief = world.WorldBrief.from_mapping(BRIEF)
        grammar = world.WorldPolicy.select(brief)
        for role in world.PROMPT_ROLES:
            with self.subTest(role=role):
                kwargs = {}
                if role == "section":
                    kwargs = {"section_id": "s1", "section_title": "Feeding the starter"}
                prompt = world.build_prompt(brief, grammar, role=role, **kwargs)
                body = prompt.prompt.lower()
                self.assertIn("opaque gouache", body)
                self.assertIn("dark-brown ink contour", body)
                self.assertIn("upper left", body)
                self.assertIn("above the horizon", body)
                self.assertIn("at most five of them plus the drawn line", body)
                self.assertIn("quiet", body)
                self.assertIn("never by the image", body)
                # GM-003: the prompt body is digit-free; a hex or a measurement is a leak. The
                # section id is an opaque stored key ("s1"), not course text, and predates v2.
                if role != "section":
                    self.assertIsNone(
                        re.search(r"\d", prompt.prompt), f"{role} body carries a digit"
                    )

    def test_negatives_keep_textless_and_the_fox_rule(self) -> None:
        brief = world.WorldBrief.from_mapping(BRIEF)
        grammar = world.WorldPolicy.select(brief)
        prompt = world.build_prompt(brief, grammar, role="hero")
        negative = prompt.negative_prompt.lower()
        for kept in KEPT_NEGATIVES:
            self.assertIn(kept, negative)
        for added in BIBLE_NEGATIVES:
            self.assertIn(added, negative)
        # The GM manifest's own hard negatives are folded in, not replaced.
        for item in gm_contract.WORLD_PROMPT_FORBIDDEN:
            self.assertIn(f"no {item}".lower(), negative)


class PromptHashContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.brief = world.WorldBrief.from_mapping(BRIEF)
        self.grammar = world.WorldPolicy.select(self.brief)

    def test_prompt_version_is_v2(self) -> None:
        self.assertEqual(world.PROMPT_VERSION, "world-prompt-v2")

    def test_hash_is_stable_for_the_same_request(self) -> None:
        first = world.build_prompt(self.brief, self.grammar, role="hero")
        second = world.build_prompt(self.brief, self.grammar, role="hero")
        self.assertEqual(first.prompt_hash, second.prompt_hash)
        self.assertTrue(first.prompt_hash.startswith("sha256:"))
        self.assertEqual(first.prompt_version, world.PROMPT_VERSION)

    def test_medium_light_and_palette_change_the_hash(self) -> None:
        base = world.build_prompt(self.brief, self.grammar, role="hero")
        other_medium = world.build_prompt(
            self.brief,
            self.grammar,
            role="hero",
            medium=base.medium + "; one extra flat brush mark",
        )
        other_light = world.build_prompt(
            self.brief,
            self.grammar,
            role="hero",
            light="one soft key light from the upper left at 20 degrees",
        )
        other_palette = world.build_prompt(
            self.brief,
            self.grammar,
            role="hero",
            palette=world._pigments("paper", "ink", "coral"),
        )
        self.assertEqual(len({base.prompt_hash, other_medium.prompt_hash}), 2)
        self.assertEqual(len({base.prompt_hash, other_light.prompt_hash}), 2)
        self.assertEqual(len({base.prompt_hash, other_palette.prompt_hash}), 2)

    def test_style_board_hashes_are_three_distinct_directions(self) -> None:
        boards = world.build_style_boards(self.brief)
        self.assertEqual(len(boards), 3)
        self.assertEqual(len({board.prompt_hash for board in boards}), 3)
        for board in boards:
            self.assertIn("direction:", board.prompt.lower())
            self.assertIn("opaque gouache", board.prompt.lower())
            self.assertEqual(board.prompt_version, world.PROMPT_VERSION)

    def test_cache_key_tracks_the_prompt_version(self) -> None:
        default = world.cache_key(self.brief, self.grammar, "hero", "x--authored")
        explicit = world.cache_key(
            self.brief,
            self.grammar,
            "hero",
            "x--authored",
            prompt_version=world.PROMPT_VERSION,
        )
        old = world.cache_key(
            self.brief, self.grammar, "hero", "x--authored", prompt_version="world-prompt-v1"
        )
        self.assertEqual(default, explicit)
        self.assertNotEqual(default, old)


class ConceptDisplayContractTest(unittest.TestCase):
    """The RPC `world_concept` caps `medium` at 200 and each palette item at 32."""

    def test_display_fields_fit_the_world_concept_schema(self) -> None:
        brief = world.WorldBrief.from_mapping(BRIEF)
        for board in world.build_style_boards(brief):
            with self.subTest(style_id=board.style_id):
                medium = world._clip(board.medium, 200)
                self.assertLessEqual(len(medium), 200)
                for item in board.palette:
                    self.assertLessEqual(len(world._clip(item, 32)), 32)
        # A long word without spaces is still clamped, never over the cap.
        self.assertLessEqual(len(world._clip("x" * 300, 200)), 200)
        self.assertLessEqual(len(world._clip("word " * 100, 32)), 32)


class AspectRoleContractTest(unittest.TestCase):
    def test_shipped_aspects_are_unchanged_and_card_is_additive(self) -> None:
        for role, ratio in LEGACY_ASPECTS.items():
            with self.subTest(role=role):
                self.assertEqual(world._ASPECT[role], ratio)
        self.assertEqual(world.CARD_ASPECT, "3:2")
        self.assertEqual(world._ASPECT["card"], world.CARD_ASPECT)
        self.assertIn("card", world.PROMPT_ROLES)

    def test_card_prompt_is_a_textless_3_2_crop(self) -> None:
        brief = world.WorldBrief.from_mapping(BRIEF)
        grammar = world.WorldPolicy.select(brief)
        card = world.build_prompt(brief, grammar, role="card")
        self.assertEqual(card.role, "card")
        self.assertEqual(card.aspect_ratio, "3:2")
        self.assertIn("textless", card.prompt.lower())
        self.assertIn("no text", card.negative_prompt.lower())
        self.assertEqual(card.as_dict()["aspect_ratio"], "3:2")

    def test_card_adds_no_kit_spend_and_no_stored_role(self) -> None:
        brief = world.WorldBrief.from_mapping(BRIEF)
        grammar = world.WorldPolicy.select(brief)
        boards = world.build_style_boards(brief)
        kit = world.build_kit_prompts(
            brief, grammar, style_id=boards[0].style_id, style=boards[0]
        )
        roles = [item.role for item in kit]
        self.assertNotIn("card", roles)
        self.assertEqual(roles.count("hero"), 1)
        self.assertEqual(roles.count("cover"), 1)
        self.assertEqual(roles.count("section"), len(BRIEF["sections"]))
        self.assertNotIn("card", {role.value for role in gm_contract.WorldRole})


if __name__ == "__main__":
    unittest.main()
