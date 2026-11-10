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

import json
import pathlib
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

    def test_prompt_version_is_v4(self) -> None:
        self.assertEqual(world.PROMPT_VERSION, "world-prompt-v4")

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


class NotationHazardContractTest(unittest.TestCase):
    """The notation/diagram class the OCR lettering gate cannot see.

    A staff, a chord box, a tick box or a single glyph is not a >=2-character word, so the
    CP-010 OCR gate passes it by construction. The prompt is the only fence; this class pins
    that every role of a brief whose subject makes notation natural names the hazard.
    """

    MUSIC = {
        "course_id": "course_cp016_music",
        "title": "Fingerpicking patterns for acoustic guitar",
        "subject_domain": "music",
        "end_capability": "Play three fingerpicking patterns in steady time",
        "audience": "adult beginner",
        "tone": "warm, unhurried, curious",
        "motifs": ["studio bench", "acoustic guitar", "open notebook"],
        "sections": [
            {"id": "s1", "title": "Thumb and finger independence"},
            {"id": "s2", "title": "A first travis pattern"},
        ],
    }

    def _all_prompts(self, mapping: dict) -> list[world.WorldPrompt]:
        brief = world.WorldBrief.from_mapping(mapping)
        grammar = world.WorldPolicy.select(brief)
        boards = world.build_style_boards(brief)
        kit = world.build_kit_prompts(
            brief, grammar, style_id=boards[0].style_id, style=boards[0]
        )
        return list(boards) + kit

    def test_music_prompts_refuse_notation_in_every_role(self) -> None:
        for prompt in self._all_prompts(self.MUSIC):
            with self.subTest(role=prompt.role, style=prompt.style_id):
                negative = prompt.negative_prompt.lower()
                self.assertIn("no musical notation", negative)
                self.assertIn("no chord diagrams", negative)
                self.assertIn("no tablature", negative)
                self.assertIn("no sheet music", negative)
                # The general printed-surface fence is on every plate, not only this domain.
                self.assertIn("no notation of any kind", negative)
                self.assertIn("no diagrams, charts, tables or grids", negative)

    def test_other_notation_domains_carry_their_own_class(self) -> None:
        cases = {
            "code": (
                {"subject_domain": "programming", "title": "Write a Python parser"},
                ("no code", "no terminals", "no flowcharts"),
            ),
            "maths": (
                {"subject_domain": "mathematics", "title": "Solve linear equations"},
                ("no equations", "no graphs", "no algebra tiles"),
            ),
            "checklist": (
                {"subject_domain": "compliance", "title": "Run a safety checklist"},
                ("no checklists", "no numbered steps", "no instruction cards"),
            ),
        }
        for group, (overrides, expected) in cases.items():
            with self.subTest(group=group):
                mapping = dict(BRIEF)
                mapping.update(overrides)
                prompt = world.build_prompt(
                    world.WorldBrief.from_mapping(mapping),
                    world.WorldPolicy.select(mapping),
                    role="hero",
                )
                negative = prompt.negative_prompt.lower()
                for phrase in expected:
                    self.assertIn(phrase, negative)
                self.assertIsNone(
                    re.search(r"\d", " ".join(expected)), "hazard text carries a digit"
                )

    def test_a_plain_brief_does_not_grow_a_music_fence(self) -> None:
        brief = world.WorldBrief.from_mapping(BRIEF)
        grammar = world.WorldPolicy.select(brief)
        negative = world.build_prompt(brief, grammar, role="hero").negative_prompt.lower()
        self.assertNotIn("no musical notation", negative)
        self.assertIn("no notation of any kind", negative)

    def test_every_section_prompt_carries_the_place_and_mood_fence(self) -> None:
        # Not service-only: a cooking or music section title also names an action, and a plate
        # showing hands mid-technique is the same defect as a plate showing a torque sequence.
        for mapping in (BRIEF, self.MUSIC):
            brief = world.WorldBrief.from_mapping(mapping)
            grammar = world.WorldPolicy.select(brief)
            for section_id, section_title in brief.sections:
                with self.subTest(grammar=grammar, section=section_id):
                    prompt = world.build_prompt(
                        brief,
                        grammar,
                        role="section",
                        section_id=section_id,
                        section_title=section_title,
                    )
                    body = prompt.prompt.lower()
                    self.assertIn("place and mood only", body)
                    self.assertIn("no procedure, sequence or tool action depicted", body)
                    negative = prompt.negative_prompt.lower()
                    self.assertIn("no depicted procedure", negative)
                    self.assertIn("no hands mid-technique", negative)
                    # The typed title travels only as a suppression instruction, never as prose.
                    self.assertIn(f"no lettering of the words {section_title.lower()}", body)
                    self.assertNotIn(f"section scene {section_id}: {section_title.lower()}", body)

    def test_section_prompt_identity_is_stable_and_section_scoped(self) -> None:
        brief = world.WorldBrief.from_mapping(BRIEF)
        grammar = world.WorldPolicy.select(brief)
        first = world.build_prompt(
            brief, grammar, role="section", section_id="s1", section_title="Feeding the starter"
        )
        again = world.build_prompt(
            brief, grammar, role="section", section_id="s1", section_title="Feeding the starter"
        )
        self.assertEqual(first.prompt_hash, again.prompt_hash)
        other_section = world.build_prompt(
            brief, grammar, role="section", section_id="s2", section_title="Feeding the starter"
        )
        self.assertNotEqual(first.prompt_hash, other_section.prompt_hash)


#: ART-BIBLE §Light, l.33: one soft key from the upper left. The clause every prompt must carry.
UPPER_LEFT_KEY = "one soft key light from the upper left"

#: ART-BIBLE §4.4, l.330: "No bloom, no halo, no radial glow around a light source ... A lit
#: lantern is a hard-edged lamp-yellow mass." A generic "no gradient, glow or glass" lost to the
#: model twice, so the emission class is named explicitly on every plate.
EMISSION_NEGATIVES = (
    "no light cone or visible beam",
    "no glowing bulb or lamp",
    "no bloom, halo or radial glow",
    "no second light source",
    "no key light from the right",
    "no lit fixture acting as a light source",
)

#: Phrases that make a fixture the light source. A grammar may paint a lantern, a lamp or a
#: ceiling fixture as an unlit hard-edged prop; it may never light the plate with one.
LIT_FIXTURE_PHRASES = (
    "overhead lamp",
    "overhead light",
    "ceiling lamp",
    "ceiling light",
    "lantern-lit",
    "lamp-lit",
    "bench light",
    "reading lamp",
    "lit by",
    "under one lamp",
    "glowing lamp",
    "glowing lantern",
)


class LightRuleContractTest(unittest.TestCase):
    """The light dimension of the art bible, which no gate measured until round four.

    CP-016 r4: every technical plate rendered a lit pendant casting a warm cone, because
    ``workshop_manual`` composed the scene "under one overhead lamp" while the same prompt asked
    for an upper-left key. This class pins the three things that let that happen: the grammar
    composition, the absence of an emission fence, and the prompt that carried both.
    """

    def test_no_composition_makes_a_fixture_the_light_source(self) -> None:
        for name, record in world.GRAMMARS.items():
            for field in ("composition", "medium"):
                text = getattr(record, field).lower()
                for phrase in LIT_FIXTURE_PHRASES:
                    with self.subTest(grammar=name, field=field, phrase=phrase):
                        self.assertNotIn(phrase, text, f"{name}.{field} names {phrase!r}")
            for motif in record.motifs:
                for phrase in LIT_FIXTURE_PHRASES:
                    with self.subTest(grammar=name, motif=motif, phrase=phrase):
                        self.assertNotIn(phrase, motif.lower())

    def test_the_rewritten_lit_grammars_name_the_key_as_the_only_light(self) -> None:
        # The two grammars that named a fixture as the light. "The only light" is the positive
        # half of the fix: a bare removal invites the model to invent a light source instead.
        for name in ("workshop_manual", "field_atlas"):
            with self.subTest(grammar=name):
                composition = world.GRAMMARS[name].composition.lower()
                self.assertIn("the only light is the single upper-left key", composition)
        # The fixture is still allowed as a prop, named as unlit, so the scene keeps its subject.
        self.assertIn("unlit", world.GRAMMARS["field_atlas"].composition.lower())
        self.assertIn("no ceiling fixture", world.GRAMMARS["workshop_manual"].composition.lower())

    def test_every_emitted_prompt_carries_the_key_and_the_emission_fence(self) -> None:
        brief = world.WorldBrief.from_mapping(BRIEF)
        for name in world.GRAMMARS:
            for role in world.PROMPT_ROLES:
                kwargs = {}
                if role == "section":
                    kwargs = {"section_id": "s1", "section_title": "Feeding the starter"}
                prompt = world.build_prompt(brief, name, role=role, **kwargs)
                body = prompt.prompt.lower()
                negative = prompt.negative_prompt.lower()
                with self.subTest(grammar=name, role=role):
                    self.assertIn(UPPER_LEFT_KEY, body)
                    for item in EMISSION_NEGATIVES:
                        self.assertIn(item, negative)
                    for phrase in LIT_FIXTURE_PHRASES:
                        self.assertNotIn(phrase, body, f"prompt body names {phrase!r}")

    def test_the_emission_fence_is_domain_independent(self) -> None:
        # Not a service-only or a technical-only rule: every plate in every grammar carries it.
        for domain, title in (
            ("cooking", "Sourdough starter at home"),
            ("music", "Fingerpicking patterns"),
            ("programming", "Write a Python parser"),
            ("history", "The Meiji restoration"),
        ):
            mapping = dict(BRIEF)
            mapping.update({"subject_domain": domain, "title": title})
            brief = world.WorldBrief.from_mapping(mapping)
            prompt = world.build_prompt(brief, world.WorldPolicy.select(brief), role="hero")
            with self.subTest(domain=domain):
                self.assertIn("no light cone or visible beam", prompt.negative_prompt.lower())
                self.assertIn("no second light source", prompt.negative_prompt.lower())


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


class ProofPacketIntegrityTest(unittest.TestCase):
    """The live proof packet must agree with the code that built it.

    A repair pass is the one place where a proof can quietly stop proving anything: the render
    path looks a prompt up by role, and every style board shares ``role="style_board"``, so a
    lookup keyed by role alone hands the last direction's prompt to any board it re-renders.
    The packet then records a prompt the plate was never made from. These tests read the
    committed ``provenance.json`` files and rebuild every prompt from the recorded brief with
    the shipping builders, so a mislabelled or duplicated plate fails here rather than in
    review.
    """

    OUT = pathlib.Path(__file__).resolve().parents[1] / "docs/concept-parity/art/cp016"
    TOPICS = ("technical-brake-bleed", "creative-fingerpicking")

    def _provenance(self, topic: str) -> dict:
        path = self.OUT / topic / "provenance.json"
        self.assertTrue(path.is_file(), f"missing proof provenance: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _rebuilt(self, provenance: dict) -> dict[tuple, world.WorldPrompt]:
        brief = world.WorldBrief.from_mapping(provenance["brief"])
        boards = world.build_style_boards(brief)
        chosen = boards[0]
        kit = world.build_kit_prompts(
            brief, provenance["grammar"], style_id=chosen.style_id, style=chosen
        )
        return {(item.style_id, item.role, item.section_id): item for item in boards + kit}

    def test_each_topic_proves_three_distinct_directions(self) -> None:
        for topic in self.TOPICS:
            with self.subTest(topic=topic):
                boards = [
                    row
                    for row in self._provenance(topic)["plates"]
                    if row["role"] == "style_board"
                ]
                self.assertEqual(3, len(boards), f"{topic}: expected three style boards")
                hashes = [row["prompt_hash"] for row in boards]
                self.assertEqual(
                    3,
                    len(set(hashes)),
                    f"{topic}: style boards share a prompt_hash {hashes}; the render lookup "
                    "keyed by (role, section_id) handed one direction's prompt to another",
                )
                self.assertEqual(
                    3,
                    len({row["style_id"] for row in boards}),
                    f"{topic}: style boards are not three distinct directions",
                )

    def test_current_version_plates_rebuild_to_their_recorded_prompt(self) -> None:
        checked = 0
        for topic in self.TOPICS:
            provenance = self._provenance(topic)
            rebuilt = self._rebuilt(provenance)
            for row in provenance["plates"]:
                if row.get("prompt_version") != world.PROMPT_VERSION:
                    continue  # documented mixed-version packet; identity is pinned by hash
                key = (row["style_id"], row["role"], row["section_id"])
                with self.subTest(topic=topic, plate=row["file"]):
                    self.assertIn(key, rebuilt, f"no prompt in code for {key}")
                    prompt = rebuilt[key]
                    self.assertEqual(
                        row["style_id"],
                        prompt.style_id,
                        "the row's style_id is not the direction its prompt was built for",
                    )
                    self.assertEqual(prompt.prompt_hash, row["prompt_hash"])
                    self.assertEqual(prompt.prompt, row["prompt"])
                    self.assertEqual(prompt.negative_prompt, row["negative_prompt"])
                    checked += 1
        self.assertGreaterEqual(
            checked, 4, "the packet no longer carries current-version plates to check"
        )

    def test_a_clean_notation_verdict_carries_its_evidence(self) -> None:
        for topic in self.TOPICS:
            for row in self._provenance(topic)["plates"]:
                notation = row.get("notation") or {}
                if notation.get("verdict") != "clean":
                    continue
                with self.subTest(topic=topic, plate=row["file"]):
                    evidence = str(notation.get("evidence") or "").strip()
                    self.assertTrue(
                        evidence and evidence.lower() != "none",
                        "a 'clean' notation verdict with no evidence is an unchecked read; "
                        "it must be recorded as unchecked, not counted as clean",
                    )


if __name__ == "__main__":
    unittest.main()
