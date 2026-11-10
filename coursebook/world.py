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

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .gm_contract import WORLD_PROMPT_FORBIDDEN

#: Bumped when a prompt changes in a way that must not reuse cached art.
PROMPT_VERSION = "world-prompt-v1"

#: The house style. A starting point, never permission to use lanterns for a head gasket.
DEFAULT_GRAMMAR = "field_atlas"


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
        palette=("parchment", "ink", "lamp ochre", "muted indigo"),
        medium="ink and gouache on warm paper, fine line weight, single soft light source",
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
        palette=("steel grey", "oil-dark ink", "safety ochre", "parchment"),
        medium="technical ink wash with precise line work, cold overhead light",
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
        palette=("midnight ink", "moon parchment", "brass ochre", "faint indigo"),
        medium="drypoint etching with soft night washes, one cool light source",
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
        palette=("aged parchment", "sepia ink", "brick ochre", "slate"),
        medium="collage of paper textures with ink outlines, warm desk lamp",
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
        palette=("flour parchment", "walnut ink", "honey ochre", "herb green"),
        medium="soft gouache still life with a hand-drawn line, window light",
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
        palette=("blueprint parchment", "chalk white", "ink", "brass ochre"),
        medium="precise drafting line on paper, cool even light",
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
        palette=("raw canvas", "umber ink", "vermilion ochre", "slate"),
        medium="mixed-media collage with soft pencil line, north-window light",
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
        palette=("cool parchment", "graphite ink", "teal ochre", "amber"),
        medium="clean technical illustration in ink and light wash, even bench light",
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
    "DEFAULT_GRAMMAR",
    "GENERIC_SWAP_REASONS",
    "GRAMMARS",
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
PROMPT_ROLES = ("style_board", "hero", "cover", "section")

#: Three real directions from the same brief — not random noise. The first is the authored
#: grammar; the other two change palette/light without changing the subject.
STYLE_DIRECTIONS: tuple[dict[str, str], ...] = (
    {
        "id": "authored",
        "label": "authored palette",
        "palette_shift": "as authored",
        "medium_shift": "as authored",
        "light": "a single soft daylight source",
    },
    {
        "id": "warm-paper",
        "label": "warm paper",
        "palette_shift": "warmed toward parchment, honey ochre and umber ink",
        "medium_shift": "looser gouache with a visible paper grain",
        "light": "low afternoon window light",
    },
    {
        "id": "night-ink",
        "label": "night ink",
        "palette_shift": "deepened toward midnight ink, slate and brass highlights",
        "medium_shift": "fine drypoint etching with restrained wash",
        "light": "one cool overhead lamp against a dark ground",
    },
)

#: Roles whose aspect ratio the layout depends on.
_ASPECT = {"style_board": "3:2", "hero": "16:9", "cover": "4:5", "section": "1:1"}

#: Every prompt carries these. They restate ``WORLD_PROMPT_FORBIDDEN`` in imperative form, so a
#: model that reads only the main prompt still sees the textless rule.
_NEGATIVE = (
    "no text",
    "no letters, words or labels",
    "no numbers or measurements",
    "no logos or brand marks",
    "no watermarks",
    "no UI chrome, buttons or frames",
    "no answer content, check text or rubric",
    "no mascot other than the fox",
    "no robots",
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
) -> WorldPrompt:
    """Build one textless plate request. Pure: no provider, no database, no randomness."""
    typed = _as_brief(brief)
    record = grammar_record(grammar)
    if role not in PROMPT_ROLES:
        raise WorldPolicyViolation("unknown_prompt_role", f"{role!r} is not a world prompt role.")
    chosen_palette = tuple(palette or (style.palette if style else record.palette))
    chosen_medium = medium or (style.medium if style else record.medium)
    chosen_style = style_id or (style.style_id if style else f"{record.name}--authored")
    light = (style.light if style and style.light else "one soft daylight source")

    # One fence, every interpolation site. Course text is never a reason to refuse the course
    # (a legitimate title may contain digits, e.g. "Japanese 101"), but text typed by a caller
    # or derived from a plan never reaches the plate unfenced: `_plate_safe` substitutes the
    # grammar-appropriate fallback when the value names a value/answer instruction, a
    # procedure, or another art direction's scene. The same predicate (`_plate_text_problems`)
    # drives the refusal in `presentation_motif_problems()`, so the prompt and the fence agree
    # by construction. The stored WorldBrief stays verbatim and the cache key is unchanged.
    subject = _plate_safe(typed.title.strip(), record.name, fallback=record.label)
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
            # A section title is course text and reaches the plate verbatim, so it is held to
            # the same fence as every other interpolation site: an unsafe title (a number or
            # answer instruction, a procedure, or another art direction's scene) is dropped and
            # the scene falls back to the grammar's place cues. The section card itself gets
            # the real typed title from the UI.
            safe_title = _plate_safe(section_title, record.name, fallback=None)
            section_clause = (
                f" Section scene {section_id}"
                + (f" about {safe_title}" if safe_title else "")
                + "."
            )

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

    body = (
        f"Textless {role.replace('_', ' ')} plate, {record.label.lower()} visual grammar. "
        f"Course subject: {subject}"
        + (f" — the learner will {capability}." if capability else ".")
        + f"{section_clause} "
        f"Audience: {audience}. Tone: {tone}. "
        f"Subject-specific motifs: {motif_text}. "
        f"Composition: {record.composition}. "
        f"Palette: {', '.join(chosen_palette)}. Medium: {chosen_medium}. "
        f"Light: {light}. "
        f"Leave a quiet, low-detail field for the real typed headline and controls; "
        f"all type is supplied by the product UI, never by the image. "
        f"Illustration role: {record.illustration_role}. "
        f"Hard negatives: {'; '.join(negative)}."
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
        light=light,
    )


def build_style_boards(brief: WorldBrief | Mapping[str, Any]) -> list[WorldPrompt]:
    """Three textless concept boards from one brief, each a different palette/medium path."""
    typed = _as_brief(brief)
    grammar = WorldPolicy.select(typed)
    record = grammar_record(grammar)
    boards: list[WorldPrompt] = []
    for direction in STYLE_DIRECTIONS:
        palette = tuple(record.palette)
        if direction["id"] == "warm-paper":
            palette = ("warm parchment",) + tuple(record.palette[1:]) + ("honey ochre",)
        elif direction["id"] == "night-ink":
            palette = ("midnight ink", "slate") + tuple(record.palette[-2:])
        medium = f"{record.medium}; {direction['medium_shift']}"
        style_id = f"{grammar}--{direction['id']}"
        board = build_prompt(
            typed,
            grammar,
            role="style_board",
            style_id=style_id,
            palette=palette,
            medium=medium,
        )
        # Fold the direction's light into the prompt so the three boards are genuinely distinct
        # requests, not the same prompt with a different id.
        board = WorldPrompt(
            role=board.role,
            prompt=f"{board.prompt} Direction: {direction['label']}, {direction['light']}.",
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
                    # The full prompt identity: a changed negative prompt (forbidden motifs) or a
                    # changed tone is a different plate, so it must not inherit this hash or the
                    # cache entry keyed from it.
                    "base_prompt_hash": board.prompt_hash,
                    "prompt": f"{board.prompt} Direction: {direction['label']}, {direction['light']}.",
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
        "connect",
        "cut",
        "detach",
        "dismount",
        "drain",
        "drill",
        "fill",
        "fit",
        "flush",
        "grease",
        "install",
        "inspect",
        "lift",
        "loosen",
        "measure",
        "mount",
        "press",
        "pull",
        "push",
        "refit",
        "reinstall",
        "remove",
        "replace",
        "rotate",
        "sand",
        "screw",
        "secure",
        "slide",
        "snap",
        "tighten",
        "torque",
        "turn",
        "unbolt",
        "unclip",
        "unfasten",
        "unplug",
        "unscrew",
        "weld",
        "wipe",
    }
)


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


def _names_procedure_or_spelled_value(value: Any) -> bool:
    """A plate is orientation, never a procedure or a value written out in words.

    Digits, units and label/answer wording are already covered by
    :func:`_names_numbers_or_answer_content`; this adds the two holes a reviewer could drive a
    procedure through (J1, plan §4.4 rules 1 and 5):

    * a spelled-out value ("tighten to seventy five", "another quarter turn"), and
    * imperative procedure phrasing ("remove the intake manifold", "drain the coolant").

    Only *verb-initial* phrasing is refused: "car on a lift" is the workshop's native place cue,
    not the instruction "lift the car". A hyphenated compound is a descriptive, not a value:
    "four-cylinder block" stays legal while "seventy five" does not.
    """
    if _names_numbers_or_answer_content(value):
        return True
    tokens = _phrase_tokens(value)
    if not tokens:
        return False
    lowered = str(value).lower()
    for token in tokens:
        if token not in _SPELLED_NUMBER_TOKENS:
            continue
        if f"{token}-" in lowered or f"-{token}" in lowered:
            continue  # "four-cylinder", "two-stroke": a compound adjective, not a value
        return True
    return tokens[0] in _PROCEDURE_VERB_TOKENS


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
        unknown = sorted(tokens - _PRESENTATION_LEXICON[field])
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
                    "palette": list(board.palette),
                    "medium": board.medium,
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
