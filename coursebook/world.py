"""The course world: subject grammar, textless prompt construction, and the world media job.

A *world* is a small governed orientation kit attached to a course — three style boards, a hero,
a cover and up to six section cards. It is **not** instruction: no plate carries a procedure, a
torque value, a sequence, a measurement or an answer. Real type is DOM.

This module is split at the same boundary the plan draws:

* :class:`WorldPolicy` is a pure selector. It imports no provider and opens no database; the
  same brief always selects the same grammar.
* :data:`GRAMMARS` is the authored grammar table (motifs, composition, palette, illustration
  role, subject cues). The anti-generic rule lives here too, because a grammar that survives a
  subject swap is a skin.
* the prompt builder and the media job (``world_concepts`` / ``world_kit``) are added below the
  policy and reuse :mod:`coursebook.artifacts` and :mod:`coursebook.job_service`; this module
  never opens a second media path or a raw provider key.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .gm_contract import WORLD_PROMPT_FORBIDDEN

#: Bumped when a prompt changes in a way that must not reuse cached art.
#: v2 rewrites every grammar to the v3 art bible (one gouache medium, upper-left key, warm ink
#: contour, five-pigment ceiling) and adds the additive 3:2 ``card`` crop role.
PROMPT_VERSION = "world-prompt-v2"

#: The house style. A starting point, never permission to use lanterns for a head gasket.
DEFAULT_GRAMMAR = "field_atlas"

# ── the v3 art bible (docs/concept-parity/ART-BIBLE.md §1–§2) ──────────────
#
# Every runtime plate shares one medium, one line and one light. Grammars choose subject, motif
# and composition; they may not choose a different medium. The constants below are the single
# source those prompts read, so the bible and the generated art cannot drift apart silently.

#: Opaque gouache on a warm paper ground with the ink contour drawn last. The prompt text carries
#: no digits at all (GM-003: a digit in the body is a leaked measurement until proven otherwise),
#: so values live in ``ART_BIBLE_PIGMENTS`` for provenance and the plate speaks pigment names.
ART_BIBLE_MEDIUM = (
    "a storybook opaque gouache illustration, thick body colour on a warm paper "
    "ground, visible flat brush-shaped marks inside each mass, subtle paper tooth over the whole "
    "plate, a dark-brown ink contour drawn last over the paint, never black and never close to "
    "neutral black; matte paint with body, not vector art and not a flat digital cartoon"
)

#: One soft key from the upper left, about a third of the way above the horizon (ART-BIBLE §1).
ART_BIBLE_LIGHT = (
    "one soft key light from the upper left about a third of the way above the horizon; "
    "shade is a single darker tint of the same pigment, covering no more than a third of a mass, "
    "with one narrow cream highlight on the top-left edge of the head, shoulder and tail"
)

#: The one line rule: a contour is never black and never the colder body-text ink.
ART_BIBLE_LINE = (
    "a single dark-brown ink contour drawn last, never black and never the colder body-text ink"
)

#: The only pigments a plate may use (ART-BIBLE §2, bound to v3 roles). Values are provenance
#: metadata; the prompt body names the pigment without a hex so no digit reaches the plate.
ART_BIBLE_PIGMENTS: dict[str, str] = {
    "paper": "warm paper #f7f1e4 (canvas)",
    "ink": "dark brown ink #3a2318 (ink)",
    "fur": "fox fur #b7643d (identity/lamp family)",
    "fur-shade": "fox fur shade #8f4526 (identity shade)",
    "cream": "fox cream #efe0c2 (paper/lamp-soft family)",
    "sock": "dark brown cuff #2b1d14 (ink)",
    "field": "field green #2f6047 (forest)",
    "ochre": "ochre #7b4b0a (wood)",
    "lamp": "lamp #e8a93a (gold)",
    "coral": "coral #9c2e1c (terracotta)",
}

#: At most five pigments in one plate, plus the line (ART-BIBLE §2).
MAX_PLATE_PIGMENTS = 5

_SPOKEN_HEX = re.compile(r"\s*#[0-9a-fA-F]{6}")


def _spoken(pigment: str) -> str:
    """The pigment name as a model reads it: no hex, so no digit enters a prompt body."""
    return _SPOKEN_HEX.sub("", pigment).strip()


def _pigments(*keys: str) -> tuple[str, ...]:
    """Name pigments from the art-bible table only. An unknown key is a programming error."""
    return tuple(ART_BIBLE_PIGMENTS[key] for key in keys)


class WorldPolicyViolation(ValueError):
    """A world request the policy refuses. Carries a stable ``reason`` discriminator."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = str(reason)
        self.message = str(message)
        super().__init__(message)


@dataclass(frozen=True)
class WorldBrief:
    """The typed brief the backend builds from the approved plan (never from one keyword).

    Only the fields below exist. There is deliberately no ``answer_key``, ``checks``, ``rubric``
    or ``attempts`` field: the prompt builder cannot leak what it never receives.
    """

    course_id: str
    title: str
    subject_domain: str = "unknown_subject"
    end_capability: str = ""
    audience: str = "adult learner"
    level: str = "novice"
    locale: str = "en-US"
    tone: str = "practical, calm, competent"
    safety_class: str = "none"
    motifs: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    sections: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WorldBrief":
        sections = tuple(
            (str(item.get("id") or ""), str(item.get("title") or ""))
            for item in (value.get("sections") or ())
            if isinstance(item, Mapping) and item.get("id")
        )
        return cls(
            course_id=str(value.get("course_id") or ""),
            title=str(value.get("title") or ""),
            subject_domain=str(value.get("subject_domain") or "unknown_subject"),
            end_capability=str(value.get("end_capability") or ""),
            audience=str(value.get("audience") or "adult learner"),
            level=str(value.get("level") or "novice"),
            locale=str(value.get("locale") or "en-US"),
            tone=str(value.get("tone") or "practical, calm, competent"),
            safety_class=str(value.get("safety_class") or "none"),
            motifs=tuple(str(item) for item in (value.get("motifs") or ()) if str(item).strip()),
            forbidden=tuple(str(item) for item in (value.get("forbidden") or ()) if str(item).strip()),
            sections=sections,
        )

    def as_dict(self) -> dict[str, Any]:
        """The JSON-safe form stored in ``course_worlds.brief_json`` and the job brief."""
        return {
            "course_id": self.course_id,
            "title": self.title,
            "subject_domain": self.subject_domain,
            "end_capability": self.end_capability,
            "audience": self.audience,
            "level": self.level,
            "locale": self.locale,
            "tone": self.tone,
            "safety_class": self.safety_class,
            "motifs": list(self.motifs),
            "forbidden": list(self.forbidden),
            "sections": [{"id": sid, "title": title} for sid, title in self.sections],
        }

    @property
    def needs_service_grammar(self) -> bool:
        """Whether this brief describes hands-on technical work, whatever the caller typed."""
        if self.safety_class.strip().lower() in {"workshop", "lab", "site", "industrial"}:
            return True
        haystack = f"{self.subject_domain} {self.end_capability}".lower()
        return any(
            marker in haystack
            for marker in (
                "technical_procedure",
                "head gasket",
                "repair",
                "replace a",
                "wiring",
                "engine",
                "torque",
                "brake",
            )
        )

    @property
    def is_symbolic(self) -> bool:
        return self.subject_domain.strip().lower() in {
            "mathematics",
            "math",
            "maths",
            "logic",
            "symbolic",
        }


@dataclass(frozen=True)
class WorldGrammarRecord:
    """One subject visual grammar. A grammar without real subject cues is a skin."""

    name: str
    label: str
    best_fit: str
    motifs: tuple[str, ...]
    composition: str
    palette: tuple[str, ...]
    medium: str
    illustration_role: str
    subject_cues: tuple[str, ...]
    cannot_do: str
    decorative_only: bool = False


#: The authored grammar table (plan §4.3, GM-CONTRACT §3.1). Palettes use the Coursebook tokens:
#: paper/ink/ochre/coral are the house palette, and each grammar leans on one extra family.
GRAMMARS: dict[str, WorldGrammarRecord] = {
    "field_atlas": WorldGrammarRecord(
        name="field_atlas",
        label="Field atlas",
        best_fit="languages, humanities, general learning",
        motifs=(
            "lantern district",
            "cafe counter",
            "pocket map",
            "field notebook",
            "travel desk",
        ),
        composition=(
            "a wandering route through a lantern-lit street; the left third is a quiet parchment "
            "field reserved for the real headline and controls"
        ),
        palette=_pigments("paper", "ink", "ochre", "lamp", "field"),
        medium=ART_BIBLE_MEDIUM + "; street lanterns and café fittings painted as flat masses",
        illustration_role="place and mood only; a map is never geography evidence",
        subject_cues=("lantern district", "cafe counter", "notebook and pencil", "ticket stub"),
        cannot_do="pretend a map is a real geography lesson",
    ),
    "workshop_manual": WorldGrammarRecord(
        name="workshop_manual",
        label="Workshop manual",
        best_fit="auto repair, trades, engineering procedures",
        motifs=("service bay", "car on a lift", "tool wall", "component trays", "bench light"),
        composition=(
            "a centered bench under one overhead lamp; a wide quiet band above carries the "
            "headline, and the tool wall runs off the right edge"
        ),
        palette=_pigments("paper", "ink", "ochre", "coral", "sock"),
        medium=ART_BIBLE_MEDIUM + "; bench, tool wall and trays painted as flat masses",
        illustration_role=(
            "orientation only; never a torque value, clearance, part number or sequence"
        ),
        subject_cues=("torque wrench silhouette", "engine block cutaway", "pegboard", "shop rag"),
        cannot_do="show a torque value, clearance or sequence as art",
    ),
    "observatory": WorldGrammarRecord(
        name="observatory",
        label="Observatory",
        best_fit="astronomy, physics, natural science",
        motifs=("night sky", "star chart table", "brass instrument", "observation log", "dome slit"),
        composition=(
            "a dark sky over a low instrument bench; the upper half stays quiet for the headline, "
            "the horizon line anchors the composition"
        ),
        palette=_pigments("paper", "ink", "field", "lamp", "ochre"),
        medium=ART_BIBLE_MEDIUM + "; the night field is deep field green, the instrument brass ochre",
        illustration_role="orientation only; a sky image is never a measurement",
        subject_cues=("star chart table", "brass telescope", "dome slit", "observation log"),
        cannot_do="use an AI sky image as a measurement",
    ),
    "archive_desk": WorldGrammarRecord(
        name="archive_desk",
        label="Archive desk",
        best_fit="history, law, business, research",
        motifs=("document tray", "stamp", "index cards", "map drawer", "reading lamp"),
        composition=(
            "an overhead desk vignette with overlapping papers; a clean margin at the top left "
            "holds the headline"
        ),
        palette=_pigments("paper", "ink", "ochre", "coral", "field"),
        medium=ART_BIBLE_MEDIUM + "; papers, trays and stamps painted as flat masses",
        illustration_role="orientation only; never an invented source or quotation",
        subject_cues=("document tray", "wax stamp", "index cards", "map drawer"),
        cannot_do="invent a source or a quotation",
    ),
    "kitchen_table": WorldGrammarRecord(
        name="kitchen_table",
        label="Kitchen table",
        best_fit="cooking, home skills, food",
        motifs=("work surface", "ingredients", "recipe card stand", "linen", "ceramic bowl"),
        composition=(
            "a warm overhead table with ingredients along the lower edge and an empty board "
            "across the top for the headline"
        ),
        palette=_pigments("paper", "ink", "ochre", "lamp", "field"),
        medium=ART_BIBLE_MEDIUM + "; ingredients and crockery painted as flat masses",
        illustration_role="orientation only; a generated dish is never a tested recipe",
        subject_cues=("flour dust", "wooden spoon", "hob rings", "herb bundle"),
        cannot_do="imply a generated dish is a tested recipe",
    ),
    "instrument_board": WorldGrammarRecord(
        name="instrument_board",
        label="Instrument board",
        best_fit="mathematics, logic, symbolic work",
        motifs=("graph paper", "blackboard", "brass dividers", "ruler", "chalk tray"),
        composition=(
            "a quiet drafting board seen at a slight angle; the blueprint grid fades out under "
            "the headline field"
        ),
        palette=_pigments("paper", "ink", "field", "ochre", "coral"),
        medium=ART_BIBLE_MEDIUM + "; the board, dividers and grid painted as flat masses",
        illustration_role="quiet and optional; never an AI illustration of a symbolic concept",
        subject_cues=("graph grid", "brass dividers", "chalk dust", "set square"),
        cannot_do="make an AI illustration a required lesson visual",
    ),
    "studio_bench": WorldGrammarRecord(
        name="studio_bench",
        label="Studio bench",
        best_fit="art, music, design",
        motifs=("material swatches", "sketchbook", "instrument body", "cutting mat", "paint tins"),
        composition=(
            "a working bench with swatches fanning left and an open quiet field right for the "
            "headline"
        ),
        palette=_pigments("paper", "ink", "coral", "ochre", "field"),
        medium=ART_BIBLE_MEDIUM + "; swatches, sketchbook and tins painted as flat masses",
        illustration_role="orientation only; generated art is never a technique authority",
        subject_cues=("material swatches", "sketchbook", "cutting mat", "paint tins"),
        cannot_do="present generated art as a technique authority",
    ),
    "lab_bench": WorldGrammarRecord(
        name="lab_bench",
        label="Lab bench",
        best_fit="biology, chemistry, lab safety",
        motifs=("glassware", "lab notebook", "station markers", "safety goggles", "wash bottle"),
        composition=(
            "a clean bench with glassware receding right; the left half stays empty for the "
            "headline and hazard copy"
        ),
        palette=_pigments("paper", "ink", "field", "lamp", "ochre"),
        medium=ART_BIBLE_MEDIUM + "; glassware, notebook and goggles painted as flat masses",
        illustration_role="orientation only; never a safety or measurement reference",
        subject_cues=("glassware", "lab notebook", "safety goggles", "wash bottle"),
        cannot_do="use art as a safety or measurement reference",
    ),
}

#: Grammar -> subject domains it is the recommended answer for. Pure data, order is tie-break only.
_DOMAIN_GRAMMAR: tuple[tuple[str, str], ...] = (
    ("language", "field_atlas"),
    ("languages", "field_atlas"),
    ("humanities", "field_atlas"),
    ("general", "field_atlas"),
    ("technical_procedure", "workshop_manual"),
    ("procedure", "workshop_manual"),
    ("repair", "workshop_manual"),
    ("auto_repair", "workshop_manual"),
    ("trades", "workshop_manual"),
    ("engineering", "workshop_manual"),
    ("mathematics", "instrument_board"),
    ("math", "instrument_board"),
    ("maths", "instrument_board"),
    ("logic", "instrument_board"),
    ("history", "archive_desk"),
    ("law", "archive_desk"),
    ("business", "archive_desk"),
    ("research", "archive_desk"),
    ("astronomy", "observatory"),
    ("physics", "observatory"),
    ("natural_science", "observatory"),
    ("cooking", "kitchen_table"),
    ("food", "kitchen_table"),
    ("home_skills", "kitchen_table"),
    ("art", "studio_bench"),
    ("music", "studio_bench"),
    ("design", "studio_bench"),
    ("biology", "lab_bench"),
    ("chemistry", "lab_bench"),
    ("lab_safety", "lab_bench"),
)

#: A technical procedure may not wear a decorative-only grammar. ``archive_desk`` is allowed
#: because service records are a real technical source; the others are fantasy for this brief.
_TECHNICAL_ALLOWED = frozenset({"workshop_manual", "archive_desk", "lab_bench"})

#: A symbolic course may not make an AI plate a required lesson visual.
_SYMBOLIC_ALLOWED = frozenset({"instrument_board", "archive_desk"})

_DECORATIVE_ONLY = frozenset({"field_atlas", "kitchen_table", "studio_bench"})


def grammar_record(name: str) -> WorldGrammarRecord:
    record = GRAMMARS.get(str(name))
    if record is None:
        raise WorldPolicyViolation("unknown_grammar", f"{name!r} is not a world grammar.")
    return record


class WorldPolicy:
    """Deterministic subject -> grammar selection. No provider call, no randomness."""

    @staticmethod
    def select(intent: WorldBrief | Mapping[str, Any] | str) -> str:
        brief = _as_brief(intent)
        if brief.needs_service_grammar:
            return "workshop_manual"
        if brief.is_symbolic:
            return "instrument_board"
        domain = brief.subject_domain.strip().lower()
        for candidate, grammar in _DOMAIN_GRAMMAR:
            if domain == candidate:
                return grammar
        # Containment is deliberately last: a declared exact domain always wins, so the selector
        # stays stable if a new precise alias is added later.
        for candidate, grammar in _DOMAIN_GRAMMAR:
            if candidate in domain:
                return grammar
        return DEFAULT_GRAMMAR

    @staticmethod
    def assert_allowed(brief: WorldBrief | Mapping[str, Any] | str, grammar: str) -> str:
        """Return *grammar* if this brief may use it; otherwise raise ``WorldPolicyViolation``."""
        record = grammar_record(grammar)
        typed = _as_brief(brief)
        # Derive the restriction from the selected grammar, not from a keyword list: a domain
        # alias (``trades``, ``engineering``, ...) that selects ``workshop_manual`` must be
        # fenced exactly like a declared technical procedure.
        needs_service = (
            typed.needs_service_grammar or WorldPolicy.select(typed) == "workshop_manual"
        )
        if needs_service and record.name not in _TECHNICAL_ALLOWED:
            raise WorldPolicyViolation(
                "technical_world_needs_service_grammar",
                f"a technical procedure cannot use the {record.name!r} grammar; "
                "choose a workshop, service-record or lab grammar.",
            )
        if typed.is_symbolic and record.name not in _SYMBOLIC_ALLOWED:
            raise WorldPolicyViolation(
                "symbolic_world_needs_instrument_grammar",
                f"a symbolic course cannot make {record.name!r} a required lesson visual.",
            )
        return record.name


def _as_brief(value: WorldBrief | Mapping[str, Any] | str) -> WorldBrief:
    if isinstance(value, WorldBrief):
        return value
    if isinstance(value, str):
        return WorldBrief(course_id="", title=value, subject_domain=value)
    if isinstance(value, Mapping):
        return WorldBrief.from_mapping(value)
    raise WorldPolicyViolation("invalid_brief", "a world brief must be a mapping or WorldBrief.")


#: Why a world is refused: the same motifs and the same grammar cannot serve two subjects.
GENERIC_SWAP_REASONS = (
    "shared_motifs_survive_subject_swap",
    "art_grammar_does_not_fit_swapped_subject",
    "same_grammar_survives_subject_swap",
)


def anti_generic_problems(
    original: WorldBrief | Mapping[str, Any],
    swapped: WorldBrief | Mapping[str, Any],
    *,
    grammar: str | None = None,
) -> tuple[str, ...]:
    """The anti-generic test: swap the subject, keep the art, and see whether it still passes.

    Returns a sorted tuple of reasons. Empty means the world is genuinely subject-specific:
    the visual grammar changed *and* fewer than two motifs survived the swap.
    """
    first = _as_brief(original)
    second = _as_brief(swapped)
    used = grammar or WorldPolicy.select(first)
    grammar_record(used)
    expected = WorldPolicy.select(second)
    shared = sorted(set(first.motifs) & set(second.motifs))
    problems: list[str] = []
    if len(shared) >= 2:
        problems.append("shared_motifs_survive_subject_swap")
    if grammar is not None:
        # We are testing one art direction against a swapped subject: the art must not fit.
        if used != expected:
            problems.append("art_grammar_does_not_fit_swapped_subject")
        else:
            problems.append("same_grammar_survives_subject_swap")
    return tuple(problems)


__all__ = [
    "ART_BIBLE_LIGHT",
    "ART_BIBLE_LINE",
    "ART_BIBLE_MEDIUM",
    "ART_BIBLE_PIGMENTS",
    "CARD_ASPECT",
    "DEFAULT_GRAMMAR",
    "GENERIC_SWAP_REASONS",
    "GRAMMARS",
    "MAX_PLATE_PIGMENTS",
    "PROMPT_VERSION",
    "WorldBrief",
    "WorldGrammarRecord",
    "WorldPolicy",
    "WorldPolicyViolation",
    "WorldPrompt",
    "anti_generic_problems",
    "build_kit_prompts",
    "build_prompt",
    "build_style_boards",
    "foreign_grammar_motifs",
    "grammar_record",
]


# ── textless prompt construction ────────────────────────────────────────────

#: Prompt roles. These are prompt labels, not the stored ``world_assets.role`` values: a style
#: board is a concept, never a kit asset, so it is deliberately absent from ``WorldRole``.
#: ``card`` is additive: a 3:2 mechanical card crop (SPEC-V3 §2), never a new kit spend.
PROMPT_ROLES = ("style_board", "hero", "cover", "section", "card")

#: Three real directions from the same brief — each one is still the art bible's single medium
#: (opaque gouache, warm paper, upper-left key, warm ink line). They change pigment family and
#: amount of quiet field, never the medium: v3 has one painted plate and no second technique.
STYLE_DIRECTIONS: tuple[dict[str, str], ...] = (
    {
        "id": "authored",
        "label": "authored palette",
        "palette_shift": "as authored",
        "medium_shift": "as authored",
        "light": ART_BIBLE_LIGHT,
    },
    {
        "id": "warm-paper",
        "label": "warm paper",
        "palette_shift": "warmed toward warm paper #f7f1e4, ochre #7b4b0a and lamp #e8a93a",
        "medium_shift": "one extra flat brush-shaped mark per mass, paper grain a little more visible",
        "light": (
            "one soft key light from the upper left about a third of the way above the horizon, "
            "warmer in temperature; the same single shade plane down-right in a darker tint"
        ),
    },
    {
        "id": "deep-pigment",
        "label": "deep pigment",
        "palette_shift": "deepened toward field green #2f6047, ochre #7b4b0a and coral #9c2e1c",
        "medium_shift": "the same opaque gouache, denser pigment and a wider quiet field",
        "light": (
            "one soft key light from the upper left about a third of the way above the horizon, "
            "dimmer; the same single shade plane down-right in a darker tint of the pigment"
        ),
    },
)

#: Roles whose aspect ratio the layout depends on. ``card`` is a 3:2 mechanical crop of the
#: approved plate (SPEC-V3: card art 214x143 at wide, never stretched), added additively so the
#: four shipped roles keep their exact ratios.
_ASPECT = {
    "style_board": "3:2",
    "hero": "16:9",
    "cover": "4:5",
    "section": "1:1",
    "card": "3:2",
}

#: The card art ratio, named for the layout and its contract test.
CARD_ASPECT = _ASPECT["card"]

#: Every prompt carries these. They restate ``WORLD_PROMPT_FORBIDDEN`` in imperative form, so a
#: model that reads only the main prompt still sees the textless rule. The art-bible negatives
#: (§5) are additive; the textless block and the fox rule are kept verbatim.
_NEGATIVE = (
    "no text",
    "no letters, words or labels",
    "no numbers or measurements",
    "no logos or brand marks",
    "no watermarks",
    "no UI chrome, buttons or frames",
    "no answer content, check text or rubric",
    "no typography or lettering of any kind",
    "no signage, poster text or hand-lettered mark",
    "no pseudo-text, gibberish lettering or symbols that resemble letters",
    "no signboards, wall signs or printed labels",
    "no course title, caption or label painted in the art",
    "no words copied from this prompt",
    "no mascot other than the fox",
    "no robots",
    "no gradient, glow or glass",
    "no drop shadow on the art object",
    "no black outline and no grey shade",
    "no off-palette colour",
    "no photorealism or photographic texture",
    "no star, rating, price or learner count",
)


@dataclass(frozen=True)
class WorldPrompt:
    """One textless plate request. The hash is what the cache and the approval fence use."""

    role: str
    prompt: str
    negative_prompt: str
    aspect_ratio: str
    prompt_hash: str
    prompt_version: str
    style_id: str
    section_id: str | None = None
    palette: tuple[str, ...] = ()
    medium: str = ""
    light: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "aspect_ratio": self.aspect_ratio,
            "prompt_hash": self.prompt_hash,
            "prompt_version": self.prompt_version,
            "style_id": self.style_id,
            "section_id": self.section_id,
            "palette": list(self.palette),
            "medium": self.medium,
            "light": self.light,
        }


def _prompt_hash(value: Mapping[str, Any]) -> str:
    import hashlib
    import json

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clamp_sections(brief: WorldBrief, max_sections: int) -> tuple[tuple[str, str], ...]:
    return tuple(brief.sections[: max(0, int(max_sections))])


def build_prompt(
    brief: WorldBrief | Mapping[str, Any],
    grammar: str,
    *,
    role: str,
    style_id: str | None = None,
    style: WorldPrompt | None = None,
    section_id: str | None = None,
    section_title: str | None = None,
    palette: Sequence[str] | None = None,
    medium: str | None = None,
    light: str | None = None,
) -> WorldPrompt:
    """Build one textless plate request. Pure: no provider, no database, no randomness."""
    typed = _as_brief(brief)
    record = grammar_record(grammar)
    if role not in PROMPT_ROLES:
        raise WorldPolicyViolation("unknown_prompt_role", f"{role!r} is not a world prompt role.")
    chosen_palette = tuple(palette or (style.palette if style else record.palette))
    chosen_medium = medium or (style.medium if style else record.medium)
    chosen_style = style_id or (style.style_id if style else f"{record.name}--authored")
    chosen_light = light or (style.light if style and style.light else ART_BIBLE_LIGHT)

    # One fence, every interpolation site. Course text is never a reason to refuse the course
    # (a legitimate title may contain digits, e.g. "Japanese 101"), but text typed by a caller
    # or derived from a plan never reaches the plate unfenced: `_plate_safe` substitutes the
    # grammar-appropriate fallback when the value names a value/answer instruction, a
    # procedure, or another art direction's scene. The same predicate (`_plate_text_problems`)
    # drives the refusal in `presentation_motif_problems()`, so the prompt and the fence agree
    # by construction. The stored WorldBrief stays verbatim and the cache key is unchanged.
    subject = _plate_safe(typed.title.strip(), record.name, fallback="")
    capability = _plate_safe(typed.end_capability.strip(), record.name, fallback="")
    # Authored grammar cues are trusted text; a caller's or a plan's motif is fenced. Dropping
    # one unsafe motif leaves the grammar's own place cues carrying the scene.
    candidate_motifs = list(typed.motifs) or list(record.subject_cues)
    motifs = [
        motif
        for motif in candidate_motifs
        if _plate_safe(motif, record.name, fallback=None) is not None
    ]
    motif_text = ", ".join(motifs[:6]) if motifs else ", ".join(record.motifs)
    tone = _plate_safe(typed.tone, record.name, fallback="practical, calm, competent")
    audience = _plate_safe(typed.audience, record.name, fallback="adult learner")
    # A service world is the grammar's business, not a keyword in the caller's text: 'trades'
    # selects workshop_manual and must keep the workshop hard negatives even if safety_class is
    # reported as none.
    service = typed.needs_service_grammar or record.name == "workshop_manual"
    section_clause = ""
    section_lettering_negative = ""
    if role == "section":
        if not section_id:
            raise WorldPolicyViolation(
                "section_prompt_needs_section_id", "a section card prompt needs a section id."
            )
        if record.name == "workshop_manual":
            # Section titles in a service course name procedures ("Removing the head"). A plate
            # is orientation, never the procedure, so the scene is place and mood only.
            section_clause = (
                f" Section scene {section_id}: place and mood only, no procedure, "
                "sequence or tool action depicted."
            )
        else:
            # A section title is course text. Carry it only as a suppression instruction: a
            # positive clause is painted as a heading by the image model, which breaks the
            # textless rule. The section card gets the real typed title from the UI.
            safe_title = _plate_safe(section_title, record.name, fallback=None)
            section_clause = f" Section scene {section_id}."
            if safe_title:
                section_lettering_negative = f"no lettering of the words {safe_title.lower()}"

    negative: list[str] = list(_NEGATIVE)
    for item in WORLD_PROMPT_FORBIDDEN:
        negative.append(f"no {item}")
    if service:
        negative.extend(
            (
                "no depicted procedure, no torque value, no torque sequence",
                "no clearance, part number or measurement",
                "no wiring diagram and no hazard callout as art",
            )
        )
    if typed.forbidden:
        # The same predicate as every other interpolation site: a negative may suppress this
        # world's own scene, but never carry a value, an answer instruction, a procedure step or
        # another art direction's scene into the plate request.
        for item in typed.forbidden:
            if _plate_safe(item, record.name, fallback=None) is not None:
                negative.append(f"no {item}")
    # The GM-003 fence requires the grammar label to survive a fenced title. Carry it only as a
    # suppression instruction: a positive "workshop manual" line reads as a sign to the model.
    negative.append(f"no {record.label.lower()} lettering or sign")
    if section_lettering_negative:
        negative.append(section_lettering_negative)

    body = (
        f"Textless painted {role.replace('_', ' ')} plate. "
        + (f"The picture shows {subject.lower()}. " if subject else "")
        + f"{section_clause} "
        f"The scene includes {motif_text}. "
        f"It is composed as {record.composition}. "
        f"The pigments are {', '.join(_spoken(item) for item in chosen_palette)}, and there are "
        f"at most five of them plus the drawn line; no pigment outside the art-bible table. "
        f"It is painted as {chosen_medium}. "
        f"Light comes from {chosen_light}. "
        f"The contour is {ART_BIBLE_LINE}. "
        f"Leave a quiet, low-detail field for the real typed headline and controls; "
        f"all type is supplied by the product UI, never by the image. "
        f"The plate contains no words at all: no title, no caption, no sign, no label, "
        f"no lettering, no typography and no pseudo-text. "
        f"Keep the background plain warm paper; no signboards and no printed surfaces. "
        f"This art is only for orientation and mood; {record.illustration_role}. "
        f"This plate is for {audience.lower()}, and the mood is {tone.lower()}. "
        f"Avoid everything in this list: {'; '.join(negative)}."
    )
    payload = {
        "prompt_version": PROMPT_VERSION,
        "role": role,
        "style_id": chosen_style,
        "section_id": section_id,
        "grammar": record.name,
        "subject": subject,
        "capability": capability,
        "audience": audience,
        "tone": tone,
        "motifs": motifs,
        "palette": list(chosen_palette),
        "medium": chosen_medium,
        "light": chosen_light,
        "composition": record.composition,
        "negative": negative,
    }
    return WorldPrompt(
        role=role,
        prompt=body,
        negative_prompt=", ".join(negative),
        aspect_ratio=_ASPECT[role],
        prompt_hash=_prompt_hash(payload),
        prompt_version=PROMPT_VERSION,
        style_id=chosen_style,
        section_id=section_id,
        palette=chosen_palette,
        medium=chosen_medium,
        light=chosen_light,
    )


def build_style_boards(brief: WorldBrief | Mapping[str, Any]) -> list[WorldPrompt]:
    """Three textless concept boards from one brief, each a different palette/medium path."""
    typed = _as_brief(brief)
    grammar = WorldPolicy.select(typed)
    record = grammar_record(grammar)
    boards: list[WorldPrompt] = []
    for direction in STYLE_DIRECTIONS:
        palette = _DIRECTION_PIGMENTS.get(direction["id"], tuple(record.palette))
        shift = direction["medium_shift"]
        medium = record.medium if shift == "as authored" else f"{record.medium}; {shift}"
        style_id = f"{grammar}--{direction['id']}"
        board = build_prompt(
            typed,
            grammar,
            role="style_board",
            style_id=style_id,
            palette=palette,
            medium=medium,
            light=direction["light"],
        )
        # Fold the direction label into the prompt so the three boards are genuinely distinct
        # requests, not the same prompt with a different id.
        directed_prompt = f"{board.prompt} Direction: {direction['label']}."
        board = WorldPrompt(
            role=board.role,
            prompt=directed_prompt,
            negative_prompt=board.negative_prompt,
            aspect_ratio=board.aspect_ratio,
            prompt_hash=_prompt_hash(
                {
                    "kind": "world_style_board",
                    "prompt_version": PROMPT_VERSION,
                    "role": board.role,
                    "style_id": style_id,
                    "grammar": grammar,
                    "direction": direction["id"],
                    "direction_light": direction["light"],
                    # The full prompt identity: a changed negative prompt (forbidden motifs) or a
                    # changed tone is a different plate, so it must not inherit this hash or the
                    # cache entry keyed from it.
                    "base_prompt_hash": board.prompt_hash,
                    "prompt": directed_prompt,
                    "negative": board.negative_prompt,
                }
            ),
            prompt_version=PROMPT_VERSION,
            style_id=style_id,
            section_id=None,
            palette=board.palette,
            medium=board.medium,
            light=direction["light"],
        )
        boards.append(board)
    return boards


#: The two non-authored style boards stay inside the art-bible pigment table and its five-pigment
#: ceiling. The authored board keeps the grammar's own palette.
_DIRECTION_PIGMENTS: dict[str, tuple[str, ...]] = {
    "warm-paper": _pigments("paper", "ink", "ochre", "lamp", "cream"),
    "deep-pigment": _pigments("paper", "ink", "field", "ochre", "coral"),
}


def build_kit_prompts(
    brief: WorldBrief | Mapping[str, Any],
    grammar: str,
    *,
    style_id: str,
    style: WorldPrompt | None = None,
    max_sections: int = 6,
) -> list[WorldPrompt]:
    """The actual kit: one hero, one cover, and one card per section (capped at six)."""
    typed = _as_brief(brief)
    chosen = WorldPolicy.assert_allowed(typed, grammar)
    prompts = [
        build_prompt(typed, chosen, role="hero", style_id=style_id, style=style),
        build_prompt(typed, chosen, role="cover", style_id=style_id, style=style),
    ]
    for section_id, section_title in _clamp_sections(typed, max_sections):
        prompts.append(
            build_prompt(
                typed,
                chosen,
                role="section",
                style_id=style_id,
                style=style,
                section_id=section_id,
                section_title=section_title,
            )
        )
    return prompts


# ── cache identity ──────────────────────────────────────────────────────────


def cache_key(
    brief: WorldBrief | Mapping[str, Any],
    grammar: str,
    role: str,
    style_id: str,
    section_id: str | None = None,
    *,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    """Content-addressed identity for one plate request.

    Every field that can change the bytes is in the key: the course intent (title, subject,
    end capability, motifs), the grammar, the selected style, the role, the section id and the
    prompt version. The same key means the same plate, so a retry reuses it instead of paying
    the provider twice.
    """
    typed = _as_brief(brief)
    intent = {
        "course_id": typed.course_id,
        "title": typed.title,
        "subject_domain": typed.subject_domain,
        "end_capability": typed.end_capability,
        "audience": typed.audience,
        "tone": typed.tone,
        "motifs": list(typed.motifs),
        "forbidden": list(typed.forbidden),
        "level": typed.level,
        "locale": typed.locale,
        "safety_class": typed.safety_class,
    }
    return _prompt_hash(
        {
            "kind": "world_plate",
            "prompt_version": prompt_version,
            "grammar": grammar,
            "role": role,
            "style_id": style_id,
            "section_id": section_id,
            "intent": intent,
        }
    )


def _clip(value: str, limit: int) -> str:
    """Clamp a display string to a contract ``maxLength`` without cutting mid-word."""
    text = str(value)
    if len(text) <= limit:
        return text
    head = text[: max(1, limit - 1)].rsplit(" ", 1)[0].rstrip(" ,;")
    return (head or text[: max(1, limit - 1)]) + "…"


def _style_hash(board: WorldPrompt) -> str:
    return _prompt_hash(
        {
            "kind": "world_style",
            "style_id": board.style_id,
            "prompt_hash": board.prompt_hash,
            "palette": list(board.palette),
            "medium": board.medium,
        }
    )


# ── media seam and typed failures ───────────────────────────────────────────

#: The one provider seam. ``None`` means "ask the host"; a test binds a fake here.
_WORLD_MEDIA: Any = None

#: A concept generation always produces exactly three boards.
MAX_CONCEPTS = 3

#: The kit budget: one hero, one cover and at most six section cards.
MAX_KIT_SECTIONS = 6


class WorldMediaFailure(RuntimeError):
    """The host has no usable image provider, or the provider refused a plate."""

    code = "HOST_UNAVAILABLE"


class WorldPartialFailure(RuntimeError):
    """Some plates were produced and some were not. Never a fabricated placeholder."""

    code = "POLICY_VIOLATION"

    def __init__(self, missing_roles: Sequence[str]) -> None:
        self.missing_roles = tuple(str(item) for item in missing_roles)
        super().__init__(
            "the world kit is incomplete; missing roles: " + ", ".join(self.missing_roles)
        )

    def to_checkpoint(self) -> dict[str, Any]:
        return {"missing_roles": list(self.missing_roles), "reason": "partial_world"}


class WorldBudgetExceeded(RuntimeError):
    """A request would exceed the declared world asset budget."""

    code = "POLICY_VIOLATION"


def bind_media(seam: Any) -> None:
    """Bind the image seam used by the world job. ``None`` restores the host seam."""
    global _WORLD_MEDIA
    _WORLD_MEDIA = seam


def _media_seam() -> Any:
    if _WORLD_MEDIA is not None:
        return _WORLD_MEDIA
    from . import media as media_mod

    return media_mod.host_media()


def _generate_plate(prompt: WorldPrompt) -> tuple[bytes, str, int]:
    """One provider call, outside every transaction. Returns bytes, mime and duration."""
    seam = _media_seam()
    if seam is None:
        raise WorldMediaFailure("image generation is not configured on this host")
    started = _monotonic()
    try:
        data, mime = seam.image(prompt.prompt, aspect_ratio=prompt.aspect_ratio)
    except WorldMediaFailure:
        raise
    except Exception as exc:  # noqa: BLE001 - a provider failure is a typed capability failure
        raise WorldMediaFailure(f"image generation failed: {type(exc).__name__}") from exc
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise WorldMediaFailure("image generation returned no bytes")
    return bytes(data), str(mime or "image/png"), int((_monotonic() - started) * 1000)


def _monotonic() -> float:
    import time

    return time.monotonic()


def _provenance(
    *, cache: str, prompt: WorldPrompt, grammar: str, style_hash: str, duration_ms: int
) -> dict[str, Any]:
    return {
        "role": "orientation",
        "provider": "host.image_generate",
        "model": None,
        "prompt_hash": prompt.prompt_hash,
        "style_hash": style_hash,
        "spec_hash": cache,
        "prompt_version": prompt.prompt_version,
        "grammar": grammar,
        "generation_ms": duration_ms,
        "textless": True,
    }


# ── world rows ──────────────────────────────────────────────────────────────


def _json_dump(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _json_load(value: Any, default: Any) -> Any:
    import json

    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _now() -> str:
    from . import db

    return db.utcnow()


def _latest_world(connection: Any, course_id: str) -> Any:
    return connection.execute(
        "SELECT * FROM course_worlds WHERE course_id = ? ORDER BY revision DESC LIMIT 1",
        (course_id,),
    ).fetchone()


def _world_revision(row: Any) -> int:
    return int(row["revision"]) if row is not None else 0


def _course_row(connection: Any, course_id: str) -> Any:
    row = connection.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    if row is None:
        from .api import RpcError

        raise RpcError.of("NOT_FOUND", f"course {course_id} does not exist in this scope.")
    return row


def _derive_brief(connection: Any, course_id: str) -> WorldBrief:
    """Build the typed brief from the stored course and its approved-plan objectives."""
    course = _course_row(connection, course_id)
    plan = connection.execute(
        "SELECT * FROM plans WHERE course_id = ? ORDER BY version DESC LIMIT 1", (course_id,)
    ).fetchone()
    objectives: list[Any] = []
    if plan is not None:
        objectives = connection.execute(
            "SELECT id, title FROM objectives WHERE plan_id = ? ORDER BY ordinal", (plan["id"],)
        ).fetchall()
    titles = [str(row["title"]) for row in objectives if row["title"]]
    subject = str(course["subject_domain"] or "unknown_subject")
    grammar = WorldPolicy.select({"subject_domain": subject, "end_capability": course["goal"] or ""})
    record = grammar_record(grammar)
    motifs: list[str] = []
    if grammar == "workshop_manual":
        # A service world is orientation only. Section titles name procedures ("removing the
        # head"), so they are never promoted to image motifs; the grammar's place and object
        # cues carry the scene instead.
        cues = list(record.motifs) + list(record.subject_cues)
    else:
        cues = list(record.subject_cues)
        for title in titles:
            cleaned = title.strip().rstrip(".").lower()
            # A promoted objective title becomes positive prompt content. Never promote one
            # that names a torque value, unit, part number or answer instruction: the grammar
            # cues still carry the scene (I1b / plan §10C).
            if (
                cleaned
                and cleaned not in motifs
                and len(cleaned) <= 64
                and not _names_procedure_or_spelled_value(cleaned)
            ):
                motifs.append(cleaned)
    for cue in cues:
        if cue not in motifs:
            motifs.append(cue)
    safety = "workshop" if grammar == "workshop_manual" else "none"
    return WorldBrief(
        course_id=str(course["id"]),
        title=str(course["title"] or "Course"),
        subject_domain=subject,
        end_capability=str(course["goal"] or ""),
        level=str(course["level"] or "novice"),
        locale=str(course["locale"] or "en-US"),
        safety_class=safety,
        motifs=tuple(motifs[:6]),
        sections=tuple(
            (str(row["id"]), str(row["title"] or f"Section {index}"))
            for index, row in enumerate(objectives[:MAX_KIT_SECTIONS], start=1)
        ),
    )


#: ``brief_patch`` may change presentation only. ``subject_domain``, ``end_capability`` and
#: ``safety_class`` are re-derived from the course row on every generate; reclassifying a course
#: is a course mutation (GM-002 ``course.mode.set`` / course.edit), never a world request.
CLASSIFICATION_BRIEF_FIELDS: tuple[str, ...] = (
    "subject_domain",
    "end_capability",
    "safety_class",
)

#: The closed set of keys a caller may patch in a ``world.generate`` request. ``level`` is not
#: here: changing a learner's level is a course mutation, and a level-only patch that never
#: renders would buy identical plates for a new cache key (H5).
BRIEF_PATCH_FIELDS: frozenset[str] = frozenset(
    {"tone", "motifs", "forbidden", "audience"}
)

#: Tokens that appear in several grammars' vocabulary or are generic mood/lighting words. They
#: never prove ownership on their own, so a legal presentation word ("cold overhead light") is
#: not mistaken for another subject's scene.
_GENERIC_VOCABULARY_TOKENS: frozenset[str] = frozenset(
    {
        "and",
        "the",
        "with",
        "from",
        "into",
        "over",
        "under",
        "one",
        "two",
        "light",
        "lamp",
        "warm",
        "cool",
        "cold",
        "soft",
        "quiet",
        "low",
        "line",
        "open",
        "work",
        "field",
        "paper",
        "desk",
        "table",
        "wall",
        "sky",
        "night",
        "day",
        "source",
        "single",
        "left",
        "right",
        "top",
        "body",
        "note",
        "book",
        "card",
        "stand",
    }
)

#: Mood/lighting vocabulary a caller may use for ``tone``. Free text is not interpolated into a
#: scene description: only these words reach the prompt, so a paraphrase of another art
#: direction (or a procedure/answer instruction) cannot ride a whitelisted field into the plate.
MOOD_TOKENS: frozenset[str] = frozenset(
    {
        "calm",
        "practical",
        "competent",
        "warm",
        "everyday",
        "unhurried",
        "wry",
        "coastal",
        "cold",
        "cool",
        "quiet",
        "bright",
        "soft",
        "precise",
        "patient",
        "curious",
        "playful",
        "serious",
        "energetic",
        "gentle",
        "confident",
        "grounded",
        "focused",
        "airy",
        "dark",
        "moody",
        "minimal",
        "documentary",
        "editorial",
        "handmade",
        "analog",
        "natural",
        "clean",
        "restrained",
        "vivid",
        "muted",
        "crisp",
        "steady",
        "measured",
        "brisk",
        "spare",
        "rich",
        "overhead",
        "window",
        "daylight",
        "evening",
        "morning",
        "neutral",
        "rustic",
        "industrial",
        "light",
    }
)

#: Role vocabulary a caller may use for ``audience``.
AUDIENCE_TOKENS: frozenset[str] = frozenset(
    {
        "adult",
        "learner",
        "apprentice",
        "technician",
        "nurse",
        "night",
        "shift",
        "hobbyist",
        "student",
        "professional",
        "parent",
        "beginner",
        "commuter",
        "cook",
        "reader",
        "traveller",
        "traveler",
        "researcher",
        "engineer",
        "operator",
        "enthusiast",
        "audience",
        "newcomer",
        "veteran",
        "practitioner",
        "staff",
        "crew",
        "regular",
        "local",
        "visitor",
    }
)

_TONE_LEXICON = MOOD_TOKENS
_AUDIENCE_LEXICON = AUDIENCE_TOKENS

#: Unit and instruction vocabulary that must never reach a plate request (plan §4.4 rules 1/5).
_UNIT_TOKENS: frozenset[str] = frozenset(
    {
        "ft",
        "lb",
        "lbs",
        "nm",
        "mm",
        "cm",
        "psi",
        "kg",
        "mph",
        "amp",
        "volt",
        "degree",
        "degrees",
        "foot",
        "pound",
        "pounds",
        "inch",
        "inches",
    }
)

_INSTRUCTION_TOKENS: frozenset[str] = frozenset(
    {
        "ignore",
        "render",
        "draw",
        "drawn",
        "write",
        "spell",
        "say",
        "label",
        "letter",
        "caption",
        "title",
        "answer",
        "key",
        "instruction",
        "sequence",
        "step",
        "torque",
        "measurement",
        "part",
        "number",
        "bolt",
        "order",
        "instead",
        "solution",
        "textless",
    }
)

#: Spelled-out values are the same content as digits: "tighten to seventy five" is a torque
#: value, and "a quarter turn" is a sequence step. A plate never carries either (plan §4.4
#: rules 1 and 5). Matching is token-level, so "quarter turn" and "hand tight plus a quarter
#: turn" are both refused.
_SPELLED_NUMBER_TOKENS: frozenset[str] = frozenset(
    {
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "thousand",
        "quarter",
        "half",
        "dozen",
        "twice",
        "thrice",
    }
)

#: Imperative procedure verbs. A plate is orientation, never an instruction, so a motif that
#: *starts* with one of these ("remove the intake manifold", "lift the cylinder head") is
#: refused. The check is verb-initial on purpose: the native place cue "car on a lift" is a
#: scene, not the instruction "lift the car", and must stay legal.
_PROCEDURE_VERB_TOKENS: frozenset[str] = frozenset(
    {
        "add",
        "adjust",
        "apply",
        "assemble",
        "attach",
        "bleed",
        "bolt",
        "check",
        "clamp",
        "close",
        "connect",
        "cut",
        "detach",
        "disconnect",
        "dismount",
        "drain",
        "drill",
        "ensure",
        "fill",
        "fit",
        "flush",
        "grease",
        "hold",
        "install",
        "inspect",
        "jack",
        "lift",
        "loosen",
        "lower",
        "mark",
        "measure",
        "mount",
        "open",
        "place",
        "position",
        "press",
        "pry",
        "pull",
        "push",
        "raise",
        "refit",
        "reinstall",
        "release",
        "remove",
        "replace",
        "rotate",
        "route",
        "sand",
        "screw",
        "seat",
        "secure",
        "slide",
        "snap",
        "soak",
        "spray",
        "support",
        "tag",
        "tighten",
        "torque",
        "turn",
        "unbolt",
        "unclip",
        "unfasten",
        "unplug",
        "unscrew",
        "verify",
        "weld",
        "wipe",
    }
)

#: Imperative procedure verbs that are also ordinary scene words ("a clean service bay", "the
#: break room", "a polish rag", "the refill station"). They are refused only when they take an
#: object ("clean the head"), never by the verb-initial test, so the native scene stays legal
#: (M1). The frozen §4.4 list names ``clean``; ``refill``/``break``/``polish`` were the same hole.
_DETERMINER_ONLY_PROCEDURE_VERBS: frozenset[str] = frozenset(
    {
        "break",
        "clean",
        "polish",
        "refill",
    }
)

#: Discourse words that may precede an imperative without changing it: "First, remove the
#: intake manifold" is the same procedure as "remove the intake manifold". They are skipped
#: before the verb-initial test (L1).
_LEADING_DISCOURSE_TOKENS: frozenset[str] = frozenset(
    {
        "after",
        "afterward",
        "afterwards",
        "also",
        "always",
        "before",
        "carefully",
        "finally",
        "first",
        "firstly",
        "gently",
        "immediately",
        "lastly",
        "never",
        "next",
        "now",
        "once",
        "please",
        "quickly",
        "second",
        "secondly",
        "slowly",
        "subsequently",
        "then",
        "third",
        "thirdly",
    }
)

#: Determiners that give a procedure verb an object wherever it sits in the phrase
#: ("... remove the intake manifold", "Open the hood"). A native place cue such as
#: "car on a lift" has no determiner after its noun, so it stays legal.
_PROCEDURE_OBJECT_DETERMINERS: frozenset[str] = frozenset(
    {
        "a",
        "all",
        "an",
        "another",
        "any",
        "both",
        "each",
        "every",
        "her",
        "his",
        "its",
        "that",
        "the",
        "their",
        "these",
        "this",
        "those",
        "your",
    }
)

#: Be-auxiliaries that open a passive construction. A plate is orientation, never a completed
#: action on the equipment, so "the head is removed" is a procedure outcome even though it
#: carries no imperative verb (GM-019). ``get``/``got`` are included because "the head gets
#: removed" names the same procedure.
_PASSIVE_AUXILIARY_TOKENS: frozenset[str] = frozenset(
    {"am", "are", "be", "been", "being", "get", "gets", "got", "is", "was", "were"}
)

#: Irregular past participles a passive auxiliary can take. Regular participles are recognised
#: by their ``-ed`` shape, so this is only the closed set morphology cannot derive from the
#: present stem ("the head is taken off"). It is a closed form class, not a synonym list a
#: caller can outgrow by choosing a different verb (GM-019).
_IRREGULAR_PAST_PARTICIPLES: frozenset[str] = frozenset(
    {
        "beaten",
        "bent",
        "bled",
        "bound",
        "brought",
        "built",
        "burnt",
        "caught",
        "chosen",
        "done",
        "drawn",
        "driven",
        "fed",
        "felt",
        "found",
        "frozen",
        "given",
        "held",
        "hidden",
        "hung",
        "kept",
        "laid",
        "led",
        "left",
        "lit",
        "lost",
        "made",
        "paid",
        "put",
        "sent",
        "set",
        "shaken",
        "shown",
        "spun",
        "struck",
        "swept",
        "taken",
        "thrown",
        "torn",
        "worn",
        "wound",
    }
)

#: Closed-class words that may stand between a passive auxiliary and its participle
#: ("was not drained", "was carefully drained"). They carry no procedure of their own.
_PASSIVE_INTERVENING_TOKENS: frozenset[str] = frozenset(
    {
        "already",
        "also",
        "carefully",
        "completely",
        "fully",
        "gently",
        "immediately",
        "just",
        "never",
        "not",
        "now",
        "partially",
        "quickly",
        "recently",
        "slowly",
        "still",
        "then",
    }
)

#: Closed-class prepositions/adverbs that may follow a scene noun. They are skipped before the
#: object-taking-clause test so "bench under the lamp" is a place, not a verb with an object
#: (GM-019).
_SCENE_RELATION_TOKENS: frozenset[str] = frozenset(
    {
        "above",
        "across",
        "against",
        "along",
        "among",
        "around",
        "at",
        "behind",
        "below",
        "beneath",
        "beside",
        "between",
        "beyond",
        "by",
        "down",
        "during",
        "for",
        "from",
        "in",
        "inside",
        "into",
        "near",
        "of",
        "off",
        "on",
        "onto",
        "outside",
        "over",
        "past",
        "through",
        "under",
        "until",
        "up",
        "upon",
        "with",
        "within",
        "without",
    }
)


#: Grammars whose subject *is* a procedure, so the plate bar is "never a procedure" rather than
#: "never a number or answer" (GM-019). ``technical_procedure``/``trades`` select this grammar.
_PROCEDURE_GRAMMARS: frozenset[str] = frozenset({"workshop_manual"})


def _grammar_vocabulary_tokens(grammar: str) -> frozenset[str]:
    return frozenset(
        token for phrase in _grammar_phrase_tokens(grammar) for token in phrase
    )


def _distinctive_tokens(grammar: str) -> frozenset[str]:
    """Tokens that identify a grammar's subject vocabulary after generic words are removed."""
    return _grammar_vocabulary_tokens(grammar) - _GENERIC_VOCABULARY_TOKENS


def _motif_owner_grammars(motif: str) -> frozenset[str]:
    """Which grammar(s) author this motif.

    Exact authored vocabulary always counts. A paraphrase also counts when it uses a token that
    is distinctive to another grammar's vocabulary: ``paper lanterns`` owns ``lantern``, so it is
    the field atlas, not an unknown subject cue. Unknown but subject-specific motifs own none.
    """
    normalized = str(motif).strip().lower()
    tokens = set(_phrase_tokens(motif))
    owners: set[str] = set()
    for name, record in GRAMMARS.items():
        vocabulary = {item.lower() for item in (*record.motifs, *record.subject_cues)}
        if normalized in vocabulary:
            owners.add(name)
            continue
        if tokens & _distinctive_tokens(name):
            owners.add(name)
    return frozenset(owners)



def foreign_grammar_motifs(
    brief: WorldBrief | Mapping[str, Any], grammar: str
) -> list[tuple[str, tuple[str, ...]]]:
    """Motifs recognisably authored by a different grammar than the selected one.

    A patch may add course-specific motifs (unknown vocabulary), but it must not graft another
    subject's art direction onto this course: 'lantern district' on a service bay is exactly the
    generic-world failure F7 forbids.
    """
    return foreign_motifs_in(_as_brief(brief).motifs, grammar)


def foreign_motifs_in(
    motifs: Sequence[Any], grammar: str
) -> list[tuple[str, tuple[str, ...]]]:
    """The same ownership check over a raw motif list (a caller's presentation patch)."""
    problems: list[tuple[str, tuple[str, ...]]] = []
    for motif in motifs:
        owners = _motif_owner_grammars(motif)
        if owners and grammar not in owners:
            problems.append((str(motif), tuple(sorted(owners))))
    return problems


def _phrase_tokens(value: Any) -> tuple[str, ...]:
    """Lower-case words, punctuation flattened, regular plurals singularised.

    'Cafe counters' -> ('cafe', 'counter'), 'lantern-district' -> ('lantern', 'district').
    This is deliberately shallow: it catches paraphrases of authored grammar vocabulary without
    pretending to understand language.
    """
    import re

    text = re.sub(r"[^a-z0-9]+", " ", str(value).lower())
    tokens: list[str] = []
    for token in text.split():
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.append(token)
    return tuple(tokens)


def _grammar_phrase_tokens(grammar: str) -> frozenset[tuple[str, ...]]:
    record = grammar_record(grammar)
    return frozenset(
        _phrase_tokens(item) for item in (*record.motifs, *record.subject_cues)
    )


def _is_native_motif(motif: Any, grammar: str) -> bool:
    return _phrase_tokens(motif) in _grammar_phrase_tokens(grammar)


#: Presentation fields that are interpolated into the image prompt.
PRESENTATION_TEXT_FIELDS: tuple[str, ...] = ("tone", "audience")

#: Lexicon each presentation field is restricted to. Unknown words are refused rather than
#: interpolated, so free text cannot smuggle a scene, a number or an answer instruction in.
_PRESENTATION_LEXICON: dict[str, frozenset[str]] = {
    "tone": _TONE_LEXICON,
    "audience": _AUDIENCE_LEXICON,
}


def _names_numbers_or_answer_content(value: Any) -> bool:
    """Digits, units, or an imperative that names text/labels/answer content."""
    import re

    text = str(value)
    if re.search(r"\d", text):
        return True
    tokens = set(_phrase_tokens(text))
    return bool(tokens & (_UNIT_TOKENS | _INSTRUCTION_TOKENS))


#: Quantity words that, hyphenated, are still a value or a sequence step: "quarter-turn" is an
#: instruction, "half-inch" a measurement, "dozen-count" a quantity, "two-thirds" a fraction.
#: They never earn the descriptive-compound exemption (K1/L2). Ordinals are listed so a plural
#: fraction tail ("thirds", "fifths") is refused once singularised.
_QUANTITY_COMPOUND_TOKENS: frozenset[str] = frozenset(
    {
        "quarter",
        "half",
        "dozen",
        "third",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
        "eleventh",
        "twelfth",
        "hundredth",
        "thousandth",
        "percent",
    }
)

#: Irregular plurals that a plain trailing-"s" strip cannot singularise.
_IRREGULAR_PLURALS: dict[str, str] = {"halves": "half"}

#: The boundary of the ``four-cylinder`` carve-out: only a spelled number followed by a plain
#: noun is a descriptive compound ("four-cylinder block", "two-stroke engine"). A number
#: followed by another number ("seventy-five") is a written value and stays refused.
_HYPHEN_COMPOUND_UNIT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

#: Function words that carry no scene ownership. A section title ("Ordering a drink") must not
#: be mistaken for the workshop's "car on a lift" merely because both contain "a".
_SCENE_TEXT_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "over",
        "that",
        "the",
        "this",
        "to",
        "under",
        "with",
        "you",
        "your",
    }
)


def _singular_compound_tail(tail: str) -> str:
    """Singularise a hyphenated compound's tail so quantity/ordinal plurals are recognised.

    ``thirds`` -> ``third``, ``halves`` -> ``half``. Without this, ``two-thirds`` read as a
    number+noun descriptive compound and slipped through the K1 carve-out (L2).
    """
    if tail in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[tail]
    if len(tail) > 3 and tail.endswith("s") and not tail.endswith("ss"):
        return tail[:-1]
    return tail


def _descriptive_number_compound(unit: str) -> bool:
    """True for a hyphenated spelled number that describes a thing, not a value.

    ``four-cylinder`` and ``two-stroke`` are compound adjectives and legal scene words. A
    number followed by another number (``seventy-five``) is a written value; a quantity or
    fraction word (``quarter-turn``, ``half-inch``, ``two-thirds``) is a sequence step or a
    measurement. Both stay refused (K1/L2). Multi-part compounds are not granted the
    exemption.
    """
    parts = unit.split("-")
    if len(parts) != 2:
        return False
    head, tail = parts
    if head not in _SPELLED_NUMBER_TOKENS or head in _QUANTITY_COMPOUND_TOKENS:
        return False
    tail = _singular_compound_tail(tail)
    return tail not in _SPELLED_NUMBER_TOKENS and tail not in _QUANTITY_COMPOUND_TOKENS


def _procedure_verb_base(token: str, verbs: frozenset[str] | None = None) -> str | None:
    """The procedure verb a token realises, if any (bare, gerund, or doubled-consonant gerund).

    ``remove``, ``removing`` and ``installing`` all name a procedure. A gerund base is
    compared against the same verb set so a sequence step cannot hide behind "-ing".
    ``verbs`` defaults to the whole procedure vocabulary; the verb-initial test passes only
    :data:`_PROCEDURE_VERB_TOKENS` so a scene word like ``clean service bay`` stays legal (M1).
    """
    vocabulary = (
        _PROCEDURE_VERB_TOKENS | _DETERMINER_ONLY_PROCEDURE_VERBS
        if verbs is None
        else verbs
    )
    if token in vocabulary:
        return token
    if len(token) > 5 and token.endswith("ing"):
        stem = token[:-3]
        candidates = [stem, stem + "e"]
        if len(stem) > 1 and stem[-1] == stem[-2]:
            candidates.append(stem[:-1])
        for candidate in candidates:
            if candidate in vocabulary:
                return candidate
    return None


def _names_procedure_or_spelled_value(value: Any) -> bool:
    """A plate is orientation, never a procedure or a value written out in words.

    Digits, units and label/answer wording are already covered by
    :func:`_names_numbers_or_answer_content`; this adds the two holes a reviewer could drive a
    procedure through (J1/L1, plan §4.4 rules 1 and 5):

    * a spelled-out value ("tighten to seventy five", "seventy-five", "two-thirds"), and
    * imperative procedure phrasing ("remove the intake manifold", "First, remove the intake
      manifold", "Open the hood").

    A leading discourse word never cancels an imperative, so it is skipped before the
    verb-initial test. A procedure verb followed by a determiner ("remove **the** manifold")
    is refused wherever it sits, including the ambiguous scene verbs ``clean``/``break``/
    ``polish``/``refill`` (M1). Native place cues ("car on a lift", "a clean service bay",
    "the break room") stay legal: their noun is not followed by a determiner. The
    ``four-cylinder`` carve-out is deliberately narrow: only a spelled number followed by a
    plain noun is descriptive. Hyphenation must not shelter a value, a fraction or a
    sequence step (K1/L2).
    """
    if _names_numbers_or_answer_content(value):
        return True
    raw_tokens = _phrase_tokens(value)
    if not raw_tokens:
        return False
    exposed = set()
    for unit in _HYPHEN_COMPOUND_UNIT.findall(str(value).lower()):
        if _descriptive_number_compound(unit):
            continue
        exposed.update(_phrase_tokens(unit))
    for token in raw_tokens:
        if token in _SPELLED_NUMBER_TOKENS and token in exposed:
            return True
    index = 0
    while index < len(raw_tokens) and raw_tokens[index] in _LEADING_DISCOURSE_TOKENS:
        index += 1
    if index < len(raw_tokens) and _procedure_verb_base(
        raw_tokens[index], _PROCEDURE_VERB_TOKENS
    ):
        return True
    for position, token in enumerate(raw_tokens[:-1]):
        if (
            _procedure_verb_base(token)
            and raw_tokens[position + 1] in _PROCEDURE_OBJECT_DETERMINERS
        ):
            return True
    return False


def _names_foreign_scene(value: Any, grammar: str) -> bool:
    """True when text uses another grammar's distinctive vocabulary.

    Used to sanitise prompt-local course text (a title, a capability clause, a section title)
    that reaches a plate verbatim: a workshop course titled "A lantern district at night" must
    fall back to the grammar label, the same way I2 falls back for numbers (J3). Function words
    are excluded so an ordinary sentence is not mistaken for another art direction.
    """
    tokens = set(_phrase_tokens(value)) - _SCENE_TEXT_STOPWORDS
    if not tokens:
        return False
    selected = grammar_record(grammar).name
    return any(
        tokens & _distinctive_tokens(name) for name in GRAMMARS if name != selected
    )


def _names_grammar_owned_scene(value: Any, grammar: str) -> bool:
    """True when the text contains a selected grammar's motif as a contiguous token run.

    Only the ambiguous scene verbs consult this: ``clean service bay`` is a place cue for
    ``workshop_manual``, while ``Clean head`` is an instruction with a bare object (N1).
    Matching is token-level against the authored motif table, so it cannot invent ownership.
    """
    tokens = _phrase_tokens(value)
    if not tokens:
        return False
    for motif in grammar_record(grammar).motifs:
        cue = _phrase_tokens(motif)
        width = len(cue)
        if not width:
            continue
        for start in range(len(tokens) - width + 1):
            if tokens[start : start + width] == cue:
                return True
    return False


def _leading_content_index(tokens: tuple[str, ...]) -> int:
    """Index of the first content word, skipping discourse words and leading adverbs.

    A leading adverb never cancels an imperative ("Then scrub the head", "Probably scrub the
    head"), and ``-ly`` is a closed English adverb shape, so it is skipped structurally rather
    than by adding each adverb to a list (GM-019).
    """
    index = 0
    while index < len(tokens) and (
        tokens[index] in _LEADING_DISCOURSE_TOKENS
        or (len(tokens[index]) > 4 and tokens[index].endswith("ly"))
    ):
        index += 1
    return index


def _verb_initial_bare_object(value: Any) -> bool:
    """A determiner-only scene verb opens the phrase and takes a bare object ("Clean head").

    Leading discourse words do not cancel it (N1/L1). Only the ambiguous verbs are tested:
    every unambiguous imperative verb is already refused verb-initial anywhere in the phrase.
    """
    tokens = _phrase_tokens(value)
    index = _leading_content_index(tokens)
    return index < len(tokens) and (
        _procedure_verb_base(tokens[index], _DETERMINER_ONLY_PROCEDURE_VERBS) is not None
    )


def _object_taking_clause(value: Any, grammar: str) -> bool:
    """An opening word takes a determiner/possessive object ("Scrub the head", "Scrub his hands").

    This is the shape of an imperative procedure sentence, independent of any verb list: a
    content word followed by a determiner and a noun. Closed-class function words are never the
    opening content word, so a place cue ("bench under the lamp", "the break room", "a clean
    service bay") cannot match: its second word is a relation word, a determiner or a bare noun,
    not a determiner followed by a noun (GM-019).

    The shape is scoped to the procedure grammar (:data:`_PROCEDURE_GRAMMARS`). Elsewhere the
    same shape is how a course names its lesson ("Cook a simple meal at home", "Ordering a
    drink"), and a plate may carry that title; the frozen verb vocabulary still refuses a
    procedure verb in every grammar. The passive shape below is not scoped, because no authored
    scene or lesson title is a be-auxiliary + participle and a passive always names a completed
    action.
    """
    if grammar not in _PROCEDURE_GRAMMARS:
        return False
    tokens = _phrase_tokens(value)
    index = _leading_content_index(tokens)
    if index + 2 >= len(tokens):
        return False
    head, middle, tail = tokens[index], tokens[index + 1], tokens[index + 2]
    if head in _PROCEDURE_OBJECT_DETERMINERS or head in _SCENE_RELATION_TOKENS:
        return False
    if middle not in _PROCEDURE_OBJECT_DETERMINERS:
        return False
    if tail in _PROCEDURE_OBJECT_DETERMINERS or tail in _SCENE_RELATION_TOKENS:
        return False
    return True


def _past_participle_shape(token: str) -> bool:
    """A token shaped like a past participle: regular ``-ed`` or a closed irregular form."""
    if token in _IRREGULAR_PAST_PARTICIPLES:
        return True
    return len(token) >= 4 and token.endswith("ed")


def _passive_construction(value: Any) -> bool:
    """A be-auxiliary followed by a past participle ("the head is removed", "was drained").

    A passive names a completed action on the equipment, so it is a procedure outcome even
    when no imperative verb is present. Closed-class adverbs may stand between the auxiliary and
    the participle ("was not drained", "The head is now removed"); the participle test is
    morphological, so a verb outside the frozen list is caught the same way a listed one is
    (GM-019).
    """
    tokens = _phrase_tokens(value)
    for position, token in enumerate(tokens[:-1]):
        if token not in _PASSIVE_AUXILIARY_TOKENS:
            continue
        following = position + 1
        while (
            following < len(tokens)
            and tokens[following] in _PASSIVE_INTERVENING_TOKENS
        ):
            following += 1
        if following < len(tokens) and _past_participle_shape(tokens[following]):
            return True
    return False


def _plate_text_problems(value: Any, grammar: str) -> tuple[str, ...]:
    """Every reason a free-text value must not be interpolated into a plate prompt.

    This is the single predicate behind both the prompt fence (:func:`_plate_safe`) and the
    patch refusal (:func:`presentation_motif_problems`), so what a caller may store and what a
    plate may say cannot drift apart. Reasons are stable identifiers, not prose.
    """
    text = str(value or "").strip()
    if not text:
        return ()
    problems: list[str] = []
    if _names_numbers_or_answer_content(text):
        problems.append("presentation_names_number_or_answer_content")
    elif _names_procedure_or_spelled_value(text):
        problems.append("presentation_names_procedure_or_value")
    elif _object_taking_clause(text, grammar) or _passive_construction(text):
        # GM-019: the frozen verb list was a lexical tail — "Scrub the head" and "the head is
        # removed" are the same procedure with a verb the list never named. The object-clause
        # shape is scoped to the procedure grammar and the passive shape is not; both are
        # vocabulary-independent. Authored motifs and native place cues do not match either
        # shape (their opening word is a determiner/relation word, or no determiner follows the
        # noun), so the grammar-owned-scene carve-outs stay legal without a carve-out branch
        # here that a procedure-bearing motif could also claim.
        problems.append("presentation_names_procedure_or_value")
    elif _verb_initial_bare_object(text) and not _names_grammar_owned_scene(text, grammar):
        # N1: a determiner-only scene verb with a bare object is an instruction
        # ("Clean head"), unless the phrase names a selected-grammar place cue
        # ("clean service bay"). The refusal and the prompt gate share this predicate.
        problems.append("presentation_names_procedure_or_value")
    if _names_foreign_scene(text, grammar):
        problems.append("presentation_names_foreign_grammar")
    return tuple(problems)


def _plate_safe(value: Any, grammar: str, *, fallback: Any) -> Any:
    """Return ``value`` only when it may appear on a plate, else the grammar fallback.

    Applied at every interpolation site in :func:`build_prompt`: subject, capability, motif,
    tone, audience and section title. A blank value also takes the fallback, so a fixture
    without a tone still gets a neutral mood line. The stored brief is never rewritten.
    """
    text = str(value or "").strip()
    if text and not _plate_text_problems(text, grammar):
        return text
    return fallback


def foreign_presentation_text(
    fields: Mapping[str, Any], grammar: str
) -> list[tuple[str, str, tuple[str, ...]]]:
    """Presentation text that names another grammar's scene (token-level ownership).

    ``tone`` and ``audience`` reach the image prompt, so they are part of the same fence as
    ``motifs``: a workshop world may describe a calm, practical mood but not a lantern district.
    Matching is case/plural-normalised and token-based, so a paraphrase ("paper lanterns",
    "night market") is refused instead of only the exact authored phrase.
    """
    selected = grammar_record(grammar).name
    problems: list[tuple[str, str, tuple[str, ...]]] = []
    for field in PRESENTATION_TEXT_FIELDS:
        if field not in fields:
            continue
        tokens = set(_phrase_tokens(fields[field]))
        for name in GRAMMARS:
            if name == selected:
                continue
            hits = sorted(tokens & _distinctive_tokens(name))
            if hits:
                problems.append((field, hits[0], (name,)))
                break
    return problems


def presentation_text_problems(
    fields: Mapping[str, Any], grammar: str
) -> list[tuple[str, str, str]]:
    """Validate free-text presentation fields before they reach a prompt.

    Returns ``(field, reason, detail)`` triples. The fences, in order:

    1. ``presentation_names_number_or_answer_content`` — digits, units or label/answer wording.
    2. ``presentation_names_foreign_grammar`` — another grammar's distinctive vocabulary.
    3. ``presentation_text_not_mood_vocabulary`` — anything outside the mood/role lexicon.

    Rule 3 is the one that makes the fence finite: a block-list of every paraphrase of every
    other art direction does not exist, but a mood lexicon does.
    """
    problems: list[tuple[str, str, str]] = []
    for field in PRESENTATION_TEXT_FIELDS:
        if field not in fields:
            continue
        value = fields[field]
        found = _plate_text_problems(value, grammar)
        if found:
            reason = found[0]
            if reason == "presentation_names_foreign_grammar":
                _field, detail, _owners = foreign_presentation_text({field: value}, grammar)[0]
            else:
                detail = str(value)
            problems.append((field, reason, detail))
            continue
        tokens = set(_phrase_tokens(value))
        unknown = sorted(tokens - _PRESENTATION_LEXICON[field] - _SCENE_TEXT_STOPWORDS)
        if unknown:
            problems.append(
                (field, "presentation_text_not_mood_vocabulary", ", ".join(unknown))
            )
    return problems


def forbidden_presentation_problems(
    items: Sequence[Any], grammar: str
) -> list[tuple[str, str]]:
    """Validate "motifs to avoid" with the same predicate the prompt uses.

    A negative is a suppression instruction, so naming *this world's own* scene is legal and
    useful ("no lantern district" on a field atlas). Carrying a number, part number, answer
    instruction, procedure step or another art direction's scene is not: the latter would put
    foreign vocabulary in the plate request through the back door.
    """
    problems: list[tuple[str, str]] = []
    for item in items:
        found = _plate_text_problems(item, grammar)
        if found:
            problems.append((str(item), found[0]))
    return problems


def presentation_motif_problems(
    motifs: Sequence[Any], grammar: str
) -> tuple[str, ...]:
    """The runtime form of the anti-generic rule for a caller-supplied motif set.

    Plan §4.4 rule 2: a patched motif set may add subject-specific cues, but two or more
    non-native motifs is already a generic swap — the project's own ``anti_generic_problems()``
    fails at two shared motifs — so the patch threshold must not be looser than the test.
    One genuine subject addition is allowed.

    Before ownership, a motif is content-scanned with the same predicate the prompt uses
    (``_plate_text_problems``): a plate is orientation only, so a caller motif may never name a
    value, an answer instruction or a procedure step (plan §4.4 rules 1 and 5). Foreign-grammar
    ownership has its own refusal (``motif_not_in_grammar``) so it is not reported here.
    """
    for reason in (
        "presentation_names_number_or_answer_content",
        "presentation_names_procedure_or_value",
    ):
        for motif in motifs:
            if reason in _plate_text_problems(motif, grammar):
                return (reason,)
    native_vocabulary = _grammar_phrase_tokens(grammar)
    native = sum(1 for motif in motifs if _phrase_tokens(motif) in native_vocabulary)
    non_native = len(motifs) - native
    if non_native >= 2:
        return ("presentation_motifs_not_subject_specific",)
    return ()


def _merged_brief(connection: Any, course_id: str, row: Any, patch: Any) -> WorldBrief:
    """Merge presentation overrides over the course-derived brief.

    The course row is authoritative for classification (``subject_domain``, ``end_capability``,
    ``safety_class``), title and sections: a client cannot turn a head-gasket course into a
    language course by patching the request. Only ``BRIEF_PATCH_FIELDS`` are honoured.
    """
    authoritative = _derive_brief(connection, course_id)
    stored = _json_load(row["brief_json"], None) if row is not None else None
    presentation: dict[str, Any] = {}
    if isinstance(stored, Mapping):
        for field in BRIEF_PATCH_FIELDS:
            if field in stored:
                presentation[field] = stored[field]
    if isinstance(patch, Mapping):
        for field in BRIEF_PATCH_FIELDS:
            if field in patch:
                presentation[field] = patch[field]
    merged = authoritative.as_dict()
    merged.update(presentation)
    if "motifs" in presentation:
        # Plan §4.4 rule 2: at least two motifs come from the grammar's own vocabulary. A
        # patched set may add subject-specific cues, but it never replaces every native cue.
        record = grammar_record(WorldPolicy.select(authoritative))
        current = [str(item) for item in (merged.get("motifs") or []) if str(item).strip()]
        present = {item.lower() for item in current}
        native_needed = 2 - sum(1 for item in record.motifs if item.lower() in present)
        for cue in record.motifs:
            if native_needed <= 0 or len(current) >= 6:
                break
            if cue.lower() not in present:
                current.append(cue)
                present.add(cue.lower())
                native_needed -= 1
        merged["motifs"] = current[:6]
        if isinstance(patch, Mapping) and "motifs" in patch:
            # Native cues lead the merged list: a caller's additions follow them, so a
            # paraphrased decorative cluster cannot sit in front of the grammar's own scene.
            merged["motifs"] = sorted(
                merged["motifs"],
                key=lambda item: 0 if _is_native_motif(item, record.name) else 1,
            )
    return WorldBrief.from_mapping(merged)


def _world_view(connection: Any, row: Any) -> dict[str, Any]:
    return {
        "world_id": str(row["id"]),
        "state": str(row["state"]),
        "revision": int(row["revision"]),
        "brief": _json_load(row["brief_json"], {}),
        "concepts": _json_load(row["concepts_json"], []),
        "selected_concept_id": row["selected_concept_id"],
        "style_hash": row["style_hash"],
        "kit_hash": row["kit_hash"],
        "approved_hash": row["approved_hash"],
        "approved_at": row["approved_at"],
        "error": _json_load(row["error_json"], None),
        "updated_at": row["updated_at"],
        "assets": _asset_views(connection, str(row["id"])),
    }


def _asset_views(connection: Any, world_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM world_assets WHERE world_id = ? ORDER BY role, section_key", (world_id,)
    ).fetchall()
    return [
        {
            "role": str(row["role"]),
            "section_id": row["section_id"],
            "section_key": str(row["section_key"]),
            "artifact_id": str(row["artifact_id"]),
            "style_hash": str(row["style_hash"]),
            "prompt_hash": str(row["prompt_hash"]),
            "textless": bool(row["textless"]),
        }
        for row in rows
    ]


def _concept_views(row: Any) -> list[dict[str, Any]]:
    return list(_json_load(row["concepts_json"], []) or [])


# ── job stages ──────────────────────────────────────────────────────────────


def _set_world_state(
    connection: Any,
    world_id: str,
    *,
    state: str,
    revision: int | None = None,
    **fields: Any,
) -> None:
    assignments = ["state = ?", "updated_at = ?"]
    params: list[Any] = [state, _now()]
    for key, value in fields.items():
        assignments.append(f"{key} = ?")
        params.append(_json_dump(value) if isinstance(value, (dict, list)) else value)
    if revision is not None:
        assignments.append("revision = ?")
        params.append(int(revision))
    params.append(world_id)
    connection.execute(
        f"UPDATE course_worlds SET {', '.join(assignments)} WHERE id = ?", tuple(params)
    )


def _concept_stage(payload: Mapping[str, Any]) -> Any:  # -> job_service.Stage
    from . import artifacts as artifacts_mod
    from . import job_service

    brief = WorldBrief.from_mapping(payload["brief"])
    world_id = str(payload["world_id"])
    grammar = WorldPolicy.select(brief)

    def run(lease: Any) -> Any:
        if job_service.cancel_requested(lease.job_id):
            raise job_service.JobCancelled("cancelled before world concepts")
        boards = build_style_boards(brief)
        if len(boards) > MAX_CONCEPTS:
            raise WorldBudgetExceeded("a concept generation is capped at three boards")
        seam = _media_seam()
        if seam is None:
            with db_transaction() as connection:
                _set_world_state(
                    connection,
                    world_id,
                    state="unavailable",
                    error_json={"reason": "provider_unavailable"},
                )
            raise WorldMediaFailure("image generation is not configured on this host")
        store = artifacts_mod.ArtifactStore()
        entries: list[dict[str, Any]] = []
        artifact_ids: list[str] = []
        usage: list[Any] = []
        missing: list[str] = []
        failure: WorldMediaFailure | None = None
        for board in boards:
            key = cache_key(
                brief, grammar, "style_board", board.style_id, None,
                prompt_version=board.prompt_version,
            )
            with db_read() as connection:
                existing = store.lookup(connection, kind="visual", spec_fingerprint=key)
            style_hash = _style_hash(board)
            if existing is not None:
                artifact_id = str(existing["artifact_id"])
                generation_ms = 0
            else:
                try:
                    data, mime, generation_ms = _generate_plate(board)
                except WorldMediaFailure as exc:
                    # A refused board is a named missing role, not a fabricated plate. Boards
                    # that did succeed are kept so a retry reuses them from the cache.
                    missing.append(f"style_board:{board.style_id.split('--')[-1]}")
                    failure = failure or exc
                    continue
                record = store.save(
                    course_id=brief.course_id,
                    kind="visual",
                    data=data,
                    mime=mime,
                    provenance=_provenance(
                        cache=key,
                        prompt=board,
                        grammar=grammar,
                        style_hash=style_hash,
                        duration_ms=generation_ms,
                    ),
                )
                artifact_id = str(record["artifact_id"])
                usage.append(
                    job_service.UsageRecord(
                        provider="image_generate",
                        model=None,
                        duration_ms=generation_ms,
                        artifact_count=1,
                    )
                )
            artifact_ids.append(artifact_id)
            entries.append(
                {
                    "style_id": board.style_id,
                    "label": board.style_id.split("--")[-1],
                    "prompt_hash": board.prompt_hash,
                    "style_hash": style_hash,
                    "artifact_id": artifact_id,
                    "palette": [_clip(item, 32) for item in board.palette],
                    "medium": _clip(board.medium, 200),
                    "role": "orientation",
                    "textless": True,
                }
            )
        if missing:
            with db_transaction() as connection:
                _set_world_state(
                    connection,
                    world_id,
                    state="failed",
                    concepts_json=_json_dump(entries),
                    error_json=_json_dump(
                        {"reason": "provider_unavailable", "missing_roles": missing}
                    ),
                )
            raise failure or WorldMediaFailure("no concept board could be produced")
        with db_transaction() as connection:
            _set_world_state(
                connection,
                world_id,
                state="concepts_ready",
                concepts_json=_json_dump(entries),
                error_json="{}",
            )
        return job_service.StageResult(
            artifacts=artifact_ids,
            usage=usage,
            message=f"{len(entries)} textless concept boards ready",
            checkpoint={"state": "concepts_ready", "concepts": entries},
        )

    return job_service.Stage("world_concepts", run)


def _style_board_for(brief: WorldBrief, style_id: str) -> WorldPrompt:
    for board in build_style_boards(brief):
        if board.style_id == style_id:
            return board
    raise WorldPolicyViolation(
        "style_not_selected", f"{style_id!r} is not a concept board for this course."
    )


def _kit_stage(payload: Mapping[str, Any]) -> Any:
    from . import artifacts as artifacts_mod
    from . import job_service

    brief = WorldBrief.from_mapping(payload["brief"])
    world_id = str(payload["world_id"])
    style_id = str(payload["style_id"])
    grammar = WorldPolicy.select(brief)
    style = _style_board_for(brief, style_id)
    style_hash = _style_hash(style)

    def run(lease: Any) -> Any:
        if job_service.cancel_requested(lease.job_id):
            raise job_service.JobCancelled("cancelled before world kit")
        if _media_seam() is None:
            with db_transaction() as connection:
                _set_world_state(
                    connection,
                    world_id,
                    state="unavailable",
                    error_json={"reason": "provider_unavailable"},
                )
            raise WorldMediaFailure("image generation is not configured on this host")
        prompts = build_kit_prompts(
            brief, grammar, style_id=style_id, style=style, max_sections=MAX_KIT_SECTIONS
        )
        if len(prompts) > 2 + MAX_KIT_SECTIONS:
            raise WorldBudgetExceeded("the world kit exceeds its declared asset budget")
        store = artifacts_mod.ArtifactStore()
        produced: list[tuple[WorldPrompt, str, str]] = []
        artifact_ids: list[str] = []
        usage: list[Any] = []
        missing: list[str] = []
        for prompt in prompts:
            name = (
                f"section:{prompt.section_id}"
                if prompt.role == "section"
                else str(prompt.role)
            )
            key = cache_key(
                brief, grammar, prompt.role, style_id, prompt.section_id,
                prompt_version=prompt.prompt_version,
            )
            with db_read() as connection:
                existing = store.lookup(connection, kind="visual", spec_fingerprint=key)
            if existing is not None:
                produced.append((prompt, str(existing["artifact_id"]), key))
                artifact_ids.append(str(existing["artifact_id"]))
                continue
            try:
                data, mime, generation_ms = _generate_plate(prompt)
            except WorldMediaFailure:
                missing.append(name)
                continue
            record = store.save(
                course_id=brief.course_id,
                kind="visual",
                data=data,
                mime=mime,
                provenance=_provenance(
                    cache=key,
                    prompt=prompt,
                    grammar=grammar,
                    style_hash=style_hash,
                    duration_ms=generation_ms,
                ),
            )
            artifact_id = str(record["artifact_id"])
            produced.append((prompt, artifact_id, key))
            artifact_ids.append(artifact_id)
            usage.append(
                job_service.UsageRecord(
                    provider="image_generate",
                    model=None,
                    duration_ms=generation_ms,
                    artifact_count=1,
                )
            )
        if missing:
            with db_transaction() as connection:
                # The plates that *did* succeed are real and are kept, so a retry reuses them
                # instead of paying twice. A missing role is named; nothing is fabricated.
                _persist_assets(connection, world_id, produced, style_hash)
                _set_world_state(
                    connection,
                    world_id,
                    state="failed",
                    error_json=_json_dump(
                        {"reason": "partial_world", "missing_roles": missing}
                    ),
                )
            raise WorldPartialFailure(missing)
        kit_hash = _prompt_hash(
            {
                "kind": "world_kit",
                "style_hash": style_hash,
                "plates": sorted(
                    f"{prompt.role}:{prompt.section_id or ''}:{prompt.prompt_hash}"
                    for prompt, _, _ in produced
                ),
            }
        )
        with db_transaction() as connection:
            _persist_assets(connection, world_id, produced, style_hash)
            _set_world_state(
                connection,
                world_id,
                state="kit_ready",
                kit_hash=kit_hash,
                style_hash=style_hash,
                error_json="{}",
            )
        return job_service.StageResult(
            artifacts=artifact_ids,
            usage=usage,
            message=f"world kit ready ({len(produced)} plates)",
            checkpoint={"state": "kit_ready", "kit_hash": kit_hash, "assets": len(produced)},
        )

    return job_service.Stage("world_kit", run)


def _persist_assets(
    connection: Any,
    world_id: str,
    produced: Sequence[tuple[WorldPrompt, str, str]],
    style_hash: str,
) -> None:
    for prompt, artifact_id, key in produced:
        role = prompt.role
        section_key = prompt.section_id if role == "section" else ""
        connection.execute(
            "INSERT INTO world_assets (id, world_id, role, section_id, section_key,"
            " artifact_id, style_hash, prompt_hash, textless, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)"
            " ON CONFLICT(world_id, role, section_key) DO UPDATE SET"
            " artifact_id = excluded.artifact_id, style_hash = excluded.style_hash,"
            " prompt_hash = excluded.prompt_hash, textless = 1",
            (
                f"was_{_uuid_hex()}",
                world_id,
                role,
                prompt.section_id,
                section_key,
                artifact_id,
                style_hash,
                prompt.prompt_hash,
                _now(),
            ),
        )


def _uuid_hex() -> str:
    import uuid

    return uuid.uuid4().hex


def _db_transaction_ctx() -> Any:
    from . import db

    return db.transaction()


def db_transaction() -> Any:
    return _db_transaction_ctx()


def db_read() -> Any:
    from . import db

    return db.read()


def resolvers(*, now: Any = None) -> dict[str, Any]:
    """The ``kind=media`` resolver for the world job stages."""
    from . import job_service

    def resolve(brief: Mapping[str, Any]) -> Sequence[Any]:
        stage = str((brief or {}).get("stage") or "")
        typed = dict(brief or {})
        if stage == "world_concepts":
            return [_concept_stage(typed)]
        if stage == "world_kit":
            return [_kit_stage(typed)]
        return [job_service.Stage(stage or "invalid", _rejecting_stage(stage))]

    return {WORLD_JOB_KIND: resolve}


def _rejecting_stage(stage: str) -> Any:
    from . import job_service

    def run(lease: Any) -> Any:
        raise WorldPolicyViolation("unknown_world_stage", f"unknown world stage {stage!r}")

    return run


#: The job family a world generation uses. ``cb.jobs`` already has ``media``; no new kind.
WORLD_JOB_KIND = "media"

#: ``method -> handler(payload, envelope)``; registration is filtered by the live contract.
HANDLERS: dict[str, Any] = {}


def _handler(method: str) -> Any:
    def decorator(fn: Any) -> Any:
        HANDLERS[method] = fn
        return fn

    return decorator


def _canonical(value: Any) -> str:
    return _json_dump(value)


def _payload_hash(method: str, payload: Mapping[str, Any]) -> str:
    return _prompt_hash({"method": method, "payload": dict(payload)})


def _require_revision(envelope: Mapping[str, Any]) -> int:
    from .api import RpcError

    expected = envelope.get("expected_revision")
    if expected is None:
        raise RpcError.of(
            "VALIDATION_FAILED",
            "this command requires expected_revision in the envelope.",
            field="expected_revision",
        )
    return int(expected)


def _stale(current: int) -> Any:
    from .api import RpcError

    error = RpcError.of(
        "STALE_REVISION", "the world moved on; reconcile against current_revision.",
        current_revision=current,
    )
    error.error["current_revision"] = current
    return error


def _replay(connection: Any, key: Any, method: str, payload_hash: str) -> Any:
    from .api import RpcError

    if not key:
        return None
    row = connection.execute(
        "SELECT payload_hash, method, response_json FROM idempotency_keys WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    if row["payload_hash"] != payload_hash or row["method"] != method:
        raise RpcError.of(
            "IDEMPOTENCY_CONFLICT",
            "this idempotency key was already used with a different payload.",
            key=key, method=row["method"],
        )
    stored = _json_load(row["response_json"], {})
    return int(stored.get("revision", 0)), dict(stored.get("result") or {})


def _remember_world(
    connection: Any, key: Any, method: str, payload_hash: str, operation_id: str,
    revision: int, result: Mapping[str, Any],
) -> None:
    if not key:
        return
    connection.execute(
        "INSERT INTO idempotency_keys (key, payload_hash, method, operation_id, response_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            key,
            payload_hash,
            method,
            operation_id or f"op-{method}",
            _canonical({"revision": int(revision), "result": dict(result)}),
            _now(),
        ),
    )


def _policy_error(reason: str, message: str, **details: Any) -> Any:
    from .api import RpcError

    return RpcError.of("POLICY_VIOLATION", message, reason=reason, **details)


@_handler("world.read")
def world_read(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    from . import db
    from .gm_contract import read_presentation_mode

    db.ensure_schema()
    course_id = str(payload["course_id"])
    with db.read() as connection:
        course = _course_row(connection, course_id)
        row = _latest_world(connection, course_id)
        world = _world_view(connection, row) if row is not None else None
    mode = read_presentation_mode(course["presentation_mode"])
    fallback = None if (world and world["state"] == "approved") else "textbook"
    return 0, {
        "course_id": course_id,
        "presentation_mode": mode,
        "world": world,
        "fallback": fallback,
        "revision": _world_revision(row),
    }


@_handler("course.mode.set")
def course_mode_set(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The durable Textbook/Game switch. Game needs an approved world; Textbook is immediate.

    The fence is the world revision the caller last read (`world.read.revision`), because the
    precondition this command protects is the world's state, not a lesson hash. A refused switch
    changes nothing: no objective, check, attempt, evidence row or lesson document is touched, and
    the stored mode stays where it was. Switching to Textbook keeps the world and its assets; the
    UI hides them, and switching back reuses the approved world when it is still valid.
    """
    from .api import RpcError
    from . import db
    from .gm_contract import read_presentation_mode

    db.ensure_schema()
    method = "course.mode.set"
    mode = str(payload["mode"])
    if mode not in ("game", "textbook"):
        raise RpcError.of(
            "VALIDATION_FAILED", "mode must be 'game' or 'textbook'.", field="mode", mode=mode
        )
    expected = _require_revision(envelope)
    key = envelope.get("idempotency_key")
    payload_hash = _payload_hash(method, payload)
    course_id = str(payload["course_id"])
    with db.transaction() as connection:
        replay = _replay(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        course = _course_row(connection, course_id)
        row = _latest_world(connection, course_id)
        current = _world_revision(row)
        if expected != current:
            raise _stale(current)
        world_state = str(row["state"]) if row is not None else "not_requested"
        approved = world_state == "approved"
        if mode == "game" and not approved:
            # The course remains Textbook until final visual approval: this is a refusal with a
            # reason, never a silent mode change and never a fabricated world.
            result = {
                "mode": read_presentation_mode(course["presentation_mode"]),
                "world_state": world_state,
                "requires_world": True,
            }
            _remember_world(
                connection, key, method, payload_hash,
                str(envelope.get("operation_id") or ""), current, result,
            )
            return current, result
        connection.execute(
            "UPDATE courses SET presentation_mode = ?, updated_at = ? WHERE id = ?",
            (mode, _now(), course_id),
        )
        result = {"mode": mode, "world_state": world_state, "requires_world": False}
        _remember_world(
            connection, key, method, payload_hash,
            str(envelope.get("operation_id") or ""), current, result,
        )
    return current, result


@_handler("world.style.preview")
def world_style_preview(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    from .api import RpcError
    from . import db

    db.ensure_schema()
    course_id = str(payload["course_id"])
    world_id = str(payload["world_id"])
    with db.read() as connection:
        _course_row(connection, course_id)
        row = _latest_world(connection, course_id)
        if row is None or str(row["id"]) != world_id:
            raise RpcError.of("NOT_FOUND", f"world {world_id} does not exist for this course.")
        concepts = _concept_views(row)
        selected = row["selected_concept_id"]
        revision = int(row["revision"])
    return 0, {
        "course_id": course_id,
        "world_id": world_id,
        "concepts": concepts,
        "selected_concept_id": selected,
        "revision": revision,
    }


@_handler("world.generate")
def world_generate(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Queue one ``kind=media`` job: three concept boards or the actual kit."""
    from .api import RpcError
    from . import db, job_service

    db.ensure_schema()
    method = "world.generate"
    expected = _require_revision(envelope)
    key = envelope.get("idempotency_key")
    payload_hash = _payload_hash(method, payload)
    course_id = str(payload["course_id"])
    stage = str(payload["stage"])
    if stage not in ("concepts", "kit"):
        raise RpcError.of(
            "VALIDATION_FAILED", "stage must be 'concepts' or 'kit'.", field="stage", stage=stage
        )
    raw_patch = payload.get("brief_patch")
    if raw_patch is not None and not isinstance(raw_patch, Mapping):
        raise RpcError.of(
            "VALIDATION_FAILED",
            "brief_patch must be an object of presentation fields.",
            field="brief_patch",
        )
    patched_motifs: list[str] = []
    patched_text: dict[str, str] = {}
    if isinstance(raw_patch, Mapping):
        reclassifying = [field for field in CLASSIFICATION_BRIEF_FIELDS if field in raw_patch]
        unknown = reclassifying or sorted(set(raw_patch) - BRIEF_PATCH_FIELDS)
        if unknown:
            raise RpcError.of(
                "VALIDATION_FAILED",
                "brief_patch may only change presentation fields; classification is a course "
                "mutation, not a world request.",
                field=unknown[0],
                allowed=sorted(BRIEF_PATCH_FIELDS),
            )
        if "motifs" in raw_patch:
            raw_motifs = raw_patch.get("motifs") or []
            if not isinstance(raw_motifs, (list, tuple)):
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    "brief_patch.motifs must be a list of motif strings.",
                    field="motifs",
                )
            patched_motifs = [str(item) for item in raw_motifs if str(item).strip()]
        for field in PRESENTATION_TEXT_FIELDS:
            if field not in raw_patch:
                continue
            value = raw_patch.get(field)
            if not isinstance(value, str):
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    f"brief_patch.{field} must be a string.",
                    field=field,
                )
            patched_text[field] = value
    with db.transaction() as connection:
        replay = _replay(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        _course_row(connection, course_id)
        row = _latest_world(connection, course_id)
        current = _world_revision(row)
        if expected != current:
            raise _stale(current)
        brief = _merged_brief(connection, course_id, row, payload.get("brief_patch"))
        grammar = WorldPolicy.select(brief)
        WorldPolicy.assert_allowed(brief, grammar)
        # The ownership fence covers caller presentation only (G4): a derived objective title
        # is course content, not a caller patching a different art direction onto this world.
        foreign = foreign_motifs_in(patched_motifs, grammar)
        if foreign:
            motif, owners = foreign[0]
            raise _policy_error(
                "motif_not_in_grammar",
                f"{motif!r} belongs to the {owners[0]!r} art direction, not {grammar!r}; "
                "a world may add its own subject motifs but never another subject's grammar.",
                motif=motif,
                grammar=grammar,
                owner_grammars=list(owners),
            )
        foreign_text = presentation_text_problems(patched_text, grammar)
        if foreign_text:
            field, reason, detail = foreign_text[0]
            if reason == "presentation_names_foreign_grammar":
                owner = grammar
                for name in GRAMMARS:
                    if name != grammar and detail in _distinctive_tokens(name):
                        owner = name
                        break
                message = (
                    f"brief_patch.{field} names the {owner!r} art direction, not {grammar!r}; "
                    "presentation text may describe this world's mood but never another "
                    "subject's scene."
                )
            elif reason in (
                "presentation_names_number_or_answer_content",
                "presentation_names_procedure_or_value",
            ):
                message = (
                    f"brief_patch.{field} names a value, a label/answer instruction or a "
                    "procedure step; a plate is orientation only, never a procedure, "
                    "measurement or answer."
                )
            else:
                message = (
                    f"brief_patch.{field} uses words outside the mood/role vocabulary "
                    f"({detail!r}); a world may set a mood, never a scene description."
                )
            raise _policy_error(
                reason,
                message,
                field=field,
                phrase=detail,
                grammar=grammar,
            )
        patched_forbidden = []
        if isinstance(raw_patch, Mapping) and "forbidden" in raw_patch:
            raw_forbidden = raw_patch.get("forbidden") or ()
            if not isinstance(raw_forbidden, (list, tuple)) or any(
                not isinstance(item, str) for item in raw_forbidden
            ):
                # A bare string here was iterated per character ("brand logos" → eleven
                # negatives), so the shape is validated before spend like motifs.
                raise RpcError.of(
                    "VALIDATION_FAILED",
                    "brief_patch.forbidden must be a list of string motifs.",
                    field="forbidden",
                )
            patched_forbidden = [item for item in raw_forbidden if item.strip()]
        forbidden_problems = forbidden_presentation_problems(patched_forbidden, grammar)
        if forbidden_problems:
            item, reason = forbidden_problems[0]
            if reason == "presentation_names_foreign_grammar":
                message = (
                    "a 'motifs to avoid' entry may name this world's own scene, never another "
                    "art direction's scene."
                )
            elif reason == "presentation_names_procedure_or_value":
                message = (
                    "a 'motifs to avoid' entry may name a scene, never a value or a "
                    "procedure step."
                )
            else:
                message = (
                    "a 'motifs to avoid' entry may name a scene, never a number, unit, label "
                    "or answer instruction."
                )
            raise _policy_error(
                reason,
                message,
                field="forbidden",
                phrase=item,
                grammar=grammar,
            )
        if patched_motifs:
            # Plan §4.4 rule 2 at runtime, for every grammar including the default: a patch may
            # add one genuine subject cue, but two or more non-native motifs is already the
            # generic swap the project's own anti-generic test rejects.
            problems = presentation_motif_problems(patched_motifs, grammar)
            if problems:
                reason = problems[0]
                if reason in (
                    "presentation_names_number_or_answer_content",
                    "presentation_names_procedure_or_value",
                ):
                    message = (
                        "a brief_patch.motifs entry names a value, a label/answer instruction "
                        "or a procedure step; a plate is orientation only, never a procedure, "
                        "measurement or answer."
                    )
                else:
                    message = (
                        "a patched motif set may add one subject-specific cue but not a second "
                        "non-native motif; a generic swap is refused before spend."
                    )
                raise _policy_error(
                    reason,
                    message,
                    field="motifs",
                    grammar=grammar,
                    motifs=patched_motifs,
                )
        if row is None:
            if stage != "concepts":
                raise RpcError.of(
                    "NOT_FOUND", "this course has no world yet; generate concepts first."
                )
            world_id = f"wld_{_uuid_hex()}"
            stamp = _now()
            connection.execute(
                "INSERT INTO course_worlds (id, course_id, revision, state, brief_json,"
                " concepts_json, created_at, updated_at)"
                " VALUES (?, ?, 0, 'not_requested', ?, '[]', ?, ?)",
                (world_id, course_id, _canonical(brief.as_dict()), stamp, stamp),
            )
        else:
            world_id = str(row["id"])

        style_id = payload.get("style_id")
        selected_concept = None
        if stage == "kit":
            concepts = _concept_views(row) if row is not None else []
            if not concepts:
                raise _policy_error(
                    "style_not_selected",
                    "generate and choose a concept board before requesting the kit.",
                )
            wanted = str(style_id or "")
            state = str(row["state"]) if row is not None else ""
            chosen_id = str(row["selected_concept_id"] or "") if row is not None else ""
            # A kit is spendable only after the style choice that hash-fenced a board. A failed
            # kit may be retried with the same selection; a never-approved world may not.
            if state not in ("style_selected", "kit_generating", "failed") or chosen_id != wanted:
                raise _policy_error(
                    "style_not_selected",
                    "approve one concept board before requesting the kit.",
                    state=state,
                    style_id=wanted,
                )
            selected_concept = next(
                (item for item in concepts if str(item.get("style_id")) == wanted), None
            )
            if selected_concept is None:
                raise _policy_error(
                    "style_not_selected",
                    "style_id is not one of this world's concept boards.",
                    style_id=wanted,
                )
            new_state = "kit_generating"
            job_stage = "world_kit"
        else:
            new_state = "concepts_generating"
            job_stage = "world_concepts"

        job_brief = {
            "stage": job_stage,
            "course_id": course_id,
            "world_id": world_id,
            "style_id": style_id,
            "brief": brief.as_dict(),
            "prompt_version": PROMPT_VERSION,
        }
        created = job_service.create(
            WORLD_JOB_KIND,
            job_brief,
            operation_id=envelope.get("operation_id"),
            connection=connection,
        )
        revision = current + 1
        connection.execute(
            "UPDATE course_worlds SET state = ?, revision = ?, brief_json = ?, style_hash = ?,"
            " selected_concept_id = ?, error_json = '{}', updated_at = ? WHERE id = ?",
            (
                new_state,
                revision,
                _canonical(brief.as_dict()),
                (str(selected_concept["style_hash"]) if selected_concept else None),
                (str(selected_concept["style_id"]) if selected_concept else None),
                _now(),
                world_id,
            ),
        )
        result = {"job_id": str(created["job_id"]), "state": new_state, "world_id": world_id}
        _remember_world(
            connection, key, method, payload_hash,
            str(envelope.get("operation_id") or ""), revision, result,
        )
    return revision, result


@_handler("world.approve")
def world_approve(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Hash-fenced approval: a style choice, then the actual kit. Never a partial world."""
    from .api import RpcError
    from . import db

    db.ensure_schema()
    method = "world.approve"
    expected = _require_revision(envelope)
    key = envelope.get("idempotency_key")
    payload_hash = _payload_hash(method, payload)
    course_id = str(payload["course_id"])
    world_id = str(payload["world_id"])
    stage = str(payload["stage"])
    approved_hash = str(payload["approved_hash"])
    if stage not in ("style", "final"):
        raise RpcError.of(
            "VALIDATION_FAILED", "stage must be 'style' or 'final'.", field="stage", stage=stage
        )
    with db.transaction() as connection:
        replay = _replay(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        _course_row(connection, course_id)
        row = _latest_world(connection, course_id)
        if row is None or str(row["id"]) != world_id:
            raise RpcError.of("NOT_FOUND", f"world {world_id} does not exist for this course.")
        current = int(row["revision"])
        if expected != current:
            raise _stale(current)
        state = str(row["state"])
        revision = current + 1
        if stage == "style":
            if state not in ("concepts_ready", "style_selected"):
                raise _policy_error(
                    "world_not_ready", "the concept boards are not ready to choose from.",
                    state=state,
                )
            concepts = _concept_views(row)
            chosen = next(
                (item for item in concepts if str(item.get("style_hash")) == approved_hash),
                None,
            )
            if chosen is None:
                raise _policy_error(
                    "style_hash_not_a_concept",
                    "approved_hash is not one of the generated concept boards.",
                )
            connection.execute(
                "UPDATE course_worlds SET state = 'style_selected', selected_concept_id = ?,"
                " style_hash = ?, revision = ?, updated_at = ? WHERE id = ?",
                (str(chosen["style_id"]), approved_hash, revision, _now(), world_id),
            )
        else:
            if state not in ("kit_ready", "approved"):
                raise _policy_error(
                    "world_not_ready", "the world kit is not ready for final approval.", state=state
                )
            kit_hash = row["kit_hash"]
            if not kit_hash or approved_hash != str(kit_hash):
                raise _policy_error(
                    "kit_hash_mismatch",
                    "the kit changed since it was previewed; re-read before approving.",
                    current_kit_hash=kit_hash,
                )
            assets = _asset_views(connection, world_id)
            missing = _missing_kit_roles(
                WorldBrief.from_mapping(_json_load(row["brief_json"], {})), assets
            )
            if missing:
                raise _policy_error(
                    "partial_world",
                    "this world is partial; no approval is possible until the missing roles exist.",
                    missing_roles=missing,
                )
            connection.execute(
                "UPDATE course_worlds SET state = 'approved', approved_hash = ?, approved_at = ?,"
                " revision = ?, updated_at = ? WHERE id = ?",
                (approved_hash, _now(), revision, _now(), world_id),
            )
        refreshed = connection.execute(
            "SELECT * FROM course_worlds WHERE id = ?", (world_id,)
        ).fetchone()
        assets = _asset_views(connection, world_id)
        world = _world_json(refreshed, assets)
        result = {
            "world": world,
            "state": str(refreshed["state"]),
            "style_hash": refreshed["style_hash"],
            "kit_hash": refreshed["kit_hash"],
            "approved_hash": refreshed["approved_hash"],
            "assets": assets,
        }
        _remember_world(
            connection, key, method, payload_hash,
            str(envelope.get("operation_id") or ""), revision, result,
        )
    return revision, result


def _world_json(row: Any, assets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "world_id": str(row["id"]),
        "state": str(row["state"]),
        "revision": int(row["revision"]),
        "brief": _json_load(row["brief_json"], {}),
        "concepts": _json_load(row["concepts_json"], []),
        "selected_concept_id": row["selected_concept_id"],
        "style_hash": row["style_hash"],
        "kit_hash": row["kit_hash"],
        "approved_hash": row["approved_hash"],
        "approved_at": row["approved_at"],
        "error": _json_load(row["error_json"], None),
        "updated_at": row["updated_at"],
        "assets": list(assets),
    }


def _missing_kit_roles(
    brief: WorldBrief, assets: Sequence[Mapping[str, Any]]
) -> list[str]:
    present = {(str(item["role"]), str(item.get("section_key") or "")) for item in assets}
    missing: list[str] = []
    if ("hero", "") not in present:
        missing.append("hero")
    if ("cover", "") not in present:
        missing.append("cover")
    for section_id, _ in brief.sections[:MAX_KIT_SECTIONS]:
        if ("section", section_id) not in present:
            missing.append(f"section:{section_id}")
    return missing


def ensure_registered() -> tuple[str, ...]:
    """Register every world handler whose name the live ``cb.rpc`` contract carries."""
    from . import api
    from .contracts import method_names

    available = set(method_names())
    registered: list[str] = []
    for method, handler in HANDLERS.items():
        if method in available:
            api.register_handler(method, handler)
            registered.append(method)
    return tuple(sorted(registered))


def world_job_on_create(presentation_mode: str | None) -> bool:
    """Whether creating a course in this mode queues a world job.

    A Textbook course is plan-first (plan §6.2): no world job, no image spend and no world art.
    A Game course starts its concepts once its draft plan exists. This is the creation gate; an
    explicit ``world.generate`` from World Studio is a separate, deliberate action.
    """
    from .gm_contract import read_presentation_mode

    return read_presentation_mode(presentation_mode) == "game"
