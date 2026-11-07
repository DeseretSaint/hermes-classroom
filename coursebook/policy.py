"""Lesson capability policy: decide what kind of lesson this is before anything is generated.

The harness must not ask a model to invent media or a rubric and then hope the result fits the
task. This module is the deterministic, side-effect-free answer to one question:

    given the recipe, the objective's evidence target, the authored lesson intent, the learner's
    locale/level and an advisory subject domain, what may this lesson carry?

It returns a typed :class:`LessonCapabilityPlan`, never prose. The plan is immutable, contains no
provider or database access, and can be replayed: the same inputs always produce the same plan.

Design boundary (``docs/VISUAL_MEDIA_PLAN.md`` §4):

* Default is ``none`` for images and audio. Media is added only when the lesson intent names a
  genuinely visual or oral construct that the media has to carry.
* A symbolic lesson (mathematics, grammar) gets no AI illustration and no narration. A diagram or
  graph named by the intent may become a deterministic schematic; an illustration never can.
* A language production lesson is not automatically a listening lesson. Narration exists only when
  the intent names a spoken or listening construct, never because a locale is set.
* A technical procedure may require a schematic or a permissioned source image. An AI illustration
  is context only and can never be *required* or be a measurement, sequence or safety authority.
* ``one_off`` is verified, not quizzed; ``parent`` is observed, not quizzed. Their check angle and
  rubric profile are fixed by the recipe even when the objective declares another evidence target.

The enums mirrored here (``RECIPES``, ``EVIDENCE_TARGETS``) are owned by
:mod:`coursebook.generation`, and ``MIN_RUBRIC_CRITERIA`` by :mod:`coursebook.packs`. They are
copied rather than imported so this module stays importable by ``generation`` without a cycle;
``tests/test_capability_policy.py`` asserts that the copies cannot drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

# ── Mirrored enums (drift is caught by tests, not by a circular import) ──────

#: Mirrors ``coursebook.generation.RECIPES``.
RECIPES: tuple[str, ...] = ("one_off", "casual", "committed", "companion", "parent")

#: Mirrors ``coursebook.generation.EVIDENCE_TARGETS``.
EVIDENCE_TARGETS: tuple[str, ...] = (
    "recall",
    "comprehension",
    "production",
    "discrimination",
    "procedure",
    "transfer",
)

#: Mirrors ``coursebook.packs.MIN_RUBRIC_CRITERIA``. Every profile below carries at least this
#: many distinct observable criteria; "understands" is never one of them.
MIN_RUBRIC_CRITERIA = 3

Recipe = Literal["one_off", "casual", "committed", "companion", "parent"]
EvidenceTarget = Literal["recall", "comprehension", "production", "discrimination", "procedure", "transfer"]
MediaLevel = Literal["none", "optional", "required"]
ImageRole = Literal["illustration", "schematic", "sourced_reference"]
AudioRole = Literal["narration", "pronunciation_reference"]
CheckAngle = Literal[
    "recall",
    "comprehension",
    "production",
    "discrimination",
    "procedure",
    "transfer",
    "verification",
    "observation",
]
RubricProfile = Literal[
    "concept_explanation",
    "procedural",
    "language_production",
    "recall_accuracy",
    "source_analysis",
    "observation",
]

MEDIA_LEVELS: tuple[str, ...] = ("none", "optional", "required")
IMAGE_ROLES: tuple[str, ...] = ("illustration", "schematic", "sourced_reference")
AUDIO_ROLES: tuple[str, ...] = ("narration", "pronunciation_reference")
CHECK_ANGLES: tuple[str, ...] = (
    "recall",
    "comprehension",
    "production",
    "discrimination",
    "procedure",
    "transfer",
    "verification",
    "observation",
)
RUBRIC_PROFILES: tuple[str, ...] = (
    "concept_explanation",
    "procedural",
    "language_production",
    "recall_accuracy",
    "source_analysis",
    "observation",
)

#: The observable aspects each rubric profile must cover, in the order a rubric reads.
#: A profile is a construct selector, not a template: P2/P3 render these as criteria, and the
#: check still has to describe *this* response. ``MIN_RUBRIC_CRITERIA`` is the floor.
RUBRIC_PROFILE_CRITERIA: dict[str, tuple[str, ...]] = {
    "concept_explanation": ("accurate claim", "mechanism", "example", "limits"),
    "procedural": ("ordered steps", "safety stop condition", "verification"),
    "language_production": ("target phrase", "pronunciation or fluency", "meaning", "register"),
    "recall_accuracy": ("correct answer", "accepted alternatives", "no cue leakage"),
    "source_analysis": ("claim", "evidence", "provenance", "contradiction handling"),
    "observation": ("observable behaviour", "context", "note", "follow-up"),
}

#: Domains where an AI illustration is never evidence. A named diagram or graph may still become
#: a deterministic schematic.
SYMBOLIC_DOMAINS: frozenset[str] = frozenset({"mathematics", "grammar"})

#: The lesson schema's media-role vocabulary, keyed by the policy's role. ``sourced_reference``
#: is stored as ``sourced_technical`` because the artifact layer names the cited-reference role
#: that way; a pronunciation reference is rendered as narration whose transcript is the
#: authoritative text, never as a second source.
IMAGE_SPEC_ROLE: dict[str, str] = {
    "illustration": "illustration",
    "schematic": "schematic",
    "sourced_reference": "sourced_technical",
}
AUDIO_SPEC_ROLE: dict[str, str] = {
    "narration": "narration",
    "pronunciation_reference": "narration",
}

#: The media kinds a lesson spec may declare. Anything else is not a media item at all.
SPEC_MEDIA_KINDS: tuple[str, ...] = ("visual", "audio")

#: The plan's typed media declaration. The planner writes one per section; the policy validates
#: and adopts it instead of guessing a construct from incidental ``lesson_intent`` prose. ``role``
#: uses the literal ``"none"`` at the plan boundary (a JSON-friendly value) and is normalised to
#: ``None`` here, so a plan never has to emit a null union.
MEDIA_DECLARATION_KEYS: frozenset[str] = frozenset({"construct", "image", "audio"})
MEDIA_DECLARATION_PART_KEYS: frozenset[str] = frozenset({"level", "role"})
MAX_CONSTRUCT_CHARS = 160


@dataclass(frozen=True, slots=True)
class MediaNeed:
    """One section's declared media need, exactly as the plan wrote it.

    ``construct`` is the named thing the media has to carry (a torque sequence, a cited poster,
    a spoken phrase). It is empty only when both media are ``none``; the policy refuses a
    declaration that names a construct but no media, or media but no construct.
    """

    construct: str
    image: str
    image_role: str | None
    audio: str
    audio_role: str | None

    @property
    def declares_media(self) -> bool:
        return self.image != "none" or self.audio != "none"

    def to_dict(self) -> dict[str, object]:
        return {
            "construct": self.construct,
            "image": {"level": self.image, "role": self.image_role or "none"},
            "audio": {"level": self.audio, "role": self.audio_role or "none"},
        }


def parse_media_need(declaration: object) -> MediaNeed:
    """Validate the plan's typed ``media_need`` object and normalise it.

    This is shape and boundedness only. Whether the declared role is possible for this domain is
    decided by :func:`plan_lesson_capability`, which is the permission authority. Raises
    :class:`CapabilityPolicyError` with a concrete reason on any malformed declaration.
    """
    if not isinstance(declaration, dict):
        raise CapabilityPolicyError(
            "media_need must be an object with construct/image/audio; got "
            f"{type(declaration).__name__}"
        )
    unknown = set(declaration) - MEDIA_DECLARATION_KEYS
    if unknown:
        raise CapabilityPolicyError(f"media_need has unknown fields {sorted(unknown)}")
    construct = declaration.get("construct")
    if not isinstance(construct, str):
        raise CapabilityPolicyError("media_need.construct must be a string (empty when no media)")
    construct = " ".join(construct.split())
    if len(construct) > MAX_CONSTRUCT_CHARS:
        raise CapabilityPolicyError(
            f"media_need.construct is {len(construct)} characters; the bound is {MAX_CONSTRUCT_CHARS}"
        )

    def part(kind: str, allowed_roles: tuple[str, ...]) -> tuple[str, str | None]:
        value = declaration.get(kind)
        if not isinstance(value, dict):
            raise CapabilityPolicyError(f"media_need.{kind} must be an object with level/role")
        extra = set(value) - MEDIA_DECLARATION_PART_KEYS
        if extra:
            raise CapabilityPolicyError(f"media_need.{kind} has unknown fields {sorted(extra)}")
        level = value.get("level")
        role = value.get("role")
        if role == "none":
            role = None
        _check_media(kind, str(level), role, allowed_roles)
        return str(level), role

    image, image_role = part("image", IMAGE_ROLES)
    audio, audio_role = part("audio", AUDIO_ROLES)
    need = MediaNeed(construct, image, image_role, audio, audio_role)
    if need.declares_media and not construct:
        raise CapabilityPolicyError(
            "media_need declares media but names no construct; media must carry a named construct"
        )
    if not need.declares_media and construct:
        raise CapabilityPolicyError(
            f"media_need names construct {construct!r} but declares no media; a construct is only "
            "for a media item the lesson needs"
        )
    return need


_DOMAIN_ALIASES: dict[str, str] = {
    "language": "language",
    "languages": "language",
    "linguistics": "language",
    "technical_procedure": "technical_procedure",
    "technical": "technical_procedure",
    "procedure": "technical_procedure",
    "procedural": "technical_procedure",
    "trade": "technical_procedure",
    "trades": "technical_procedure",
    "maintenance": "technical_procedure",
    "engineering": "technical_procedure",
    "mathematics": "mathematics",
    "math": "mathematics",
    "maths": "mathematics",
    "algebra": "mathematics",
    "geometry": "mathematics",
    "statistics": "mathematics",
    "grammar": "grammar",
    "history": "history",
}

# ── Intent construct detectors ──────────────────────────────────────────────
#
# These are construct detectors, not topic classifiers. A match is a named thing the lesson has
# to show or say; a miss means the media would be decoration and therefore stays ``none``.

_VISUAL_DENIAL = re.compile(
    r"\b(?:no|not|without|never|omit|skip)\s+(?:any\s+)?"
    r"(?:diagrams?|images?|pictures?|illustrations?|photos?|photographs?|schematics?|visuals?)\b"
)
_ORAL_DENIAL = re.compile(
    r"\b(?:no|not|without|never|omit|skip)\s+(?:any\s+)?"
    r"(?:speaking|speech|audio|narration|pronunciation|oral(?:\s+\w+)?)\b"
)

#: Constructs that a deterministic schematic can carry: sequence, torque, wiring, labelled parts,
#: measurement, orientation, clearance, or a named graph/plot/chart/diagram.
_SCHEMATIC_VISUAL = re.compile(
    r"\b("
    r"torque(?:\s+sequence)?|wiring|wires?|circuit|schematic|diagram|exploded\s+view|"
    r"clearance|tolerance|part\s+orientation|orientation\s+of|labell?ed|labell?ing|labeling|"
    r"parts?\s+(?:diagram|list)|assembly\s+(?:order|sequence)|sequence\s+of\s+(?:steps|operations)|"
    r"measurements?|gap\s+(?:size|spec|of)|graph|plot|chart|map"
    r")\b"
)

#: Constructs that only a cited, permissioned source image can carry. Never generated.
_SOURCED_VISUAL = re.compile(
    r"\b("
    r"photographs?|photos?|posters?|paintings?|cartoons?|maps?|artefacts?|artifacts?|facsimiles?|"
    r"scans?|engravings?|manuscripts?|primary[- ]source\s+(?:image|document)|document\s+image|"
    r"field\s+guide|plate"
    r")\b"
)

#: Context-only visuals. They may become an optional generated illustration, never required and
#: never in a symbolic domain.
_ILLUSTRATION_VISUAL = re.compile(
    r"\b(pictures?|illustrations?|flash\s?cards?|scenes?|visual\s+aid|visual\s+context|"
    r"image\s+for\s+context|artwork)\b"
)

#: Source-analysis constructs. They make a named source image the evidence, not decoration.
_SOURCE_ANALYSIS = re.compile(
    r"\b("
    r"source\s+analys[ie]s|primary\s+source|provenance|corroborat\w*|author'?s\s+purpose|bias|"
    r"claim\s+and\s+evidence|contradiction|interpret\w*"
    r")\b"
)

#: Spoken-production constructs. "Read" alone is not one of them; "read aloud" is. The phrase
#: patterns allow the object between the verb and "aloud" ("read each kana aloud").
_PRONUNCIATION = re.compile(
    r"\b("
    r"pronounc\w*|say(?:ing|s)?\b[^.;]{0,40}?\baloud|read\b[^.;]{0,40}?\b(?:aloud|out\s+loud)|"
    r"repeat\b[^.;]{0,30}?\b(?:aloud|after)|spoken\s+(?:phrase|greeting)|speak\w*|oral(?:ly)?|"
    r"recite\w*|greet\w*|introduc\w*"
    r")\b"
)

#: The subset of spoken constructs that cannot be satisfied in writing. "Write a greeting card"
#: is writing even though it contains the word "greeting"; it must not pull narration.
_STRONG_ORAL = re.compile(
    r"\b("
    r"pronounc\w*|say(?:ing|s)?\b[^.;]{0,40}?\baloud|read\b[^.;]{0,40}?\b(?:aloud|out\s+loud)|"
    r"repeat\b[^.;]{0,30}?\b(?:aloud|after)|spoken\s+(?:phrase|greeting)|speak\w*|oral(?:ly)?|"
    r"recite\w*|introduc\w+\s+(?:yourself|oneself)"
    r")\b"
)

#: Listening constructs. A listening lesson cannot be valid without the audio it listens to.
_LISTENING = re.compile(
    r"\b(listen\w*|spoken\s+(?:passage|announcement|dialogue|story)|announcement|dialogue|"
    r"audio\s+(?:passage|clip))\b"
)

#: Reading and writing constructs. These explicitly deny narration when no oral construct is named.
_READING_WRITING = re.compile(
    r"\b(read|reads|reading|write|writes|writing|written|recogni[sz]e|recogni[sz]ing|"
    r"translat\w*|transcrib\w*|copy|trace|spell\w*|handwrit\w*)\b"
)

#: Unambiguous technical words. They let a caller that omitted the advisory domain still get the
#: schematic a torque or wiring lesson needs.
_STRONG_TECHNICAL = re.compile(
    r"\b(torque|wiring|wire|circuit|schematic|exploded\s+view|clearance|tolerance)\b"
)


class CapabilityPolicyError(ValueError):
    """The policy was called with an input it cannot decide (unknown recipe or target)."""


@dataclass(frozen=True, slots=True)
class LessonCapabilityPlan:
    """The immutable capability decision for one lesson section.

    ``image_role`` and ``audio_role`` are ``None`` exactly when the matching level is ``none``;
    a plan never claims a role it does not use. ``reasons`` is the audit trail: it names the
    construct that justified the media (or the constructs that were absent), never a preference.
    """

    recipe: str
    evidence_target: str
    check_angle: str
    rubric_profile: str
    image: str
    image_role: str | None
    audio: str
    audio_role: str | None
    locale: str | None = None
    level: str | None = None
    subject_domain: str | None = None
    reasons: tuple[str, ...] = ()
    #: True when the plan declared the need and the policy adopted it, rather than inferring a
    #: construct from the authored intent. A declared plan is the product path; the inference path
    #: remains only for a legacy/hand-built section with no declaration.
    declared: bool = False
    construct: str | None = None

    def __post_init__(self) -> None:
        if self.recipe not in RECIPES:
            raise CapabilityPolicyError(f"unknown recipe {self.recipe!r}")
        if self.evidence_target not in EVIDENCE_TARGETS:
            raise CapabilityPolicyError(f"unknown evidence target {self.evidence_target!r}")
        if self.check_angle not in CHECK_ANGLES:
            raise CapabilityPolicyError(f"unknown check angle {self.check_angle!r}")
        if self.rubric_profile not in RUBRIC_PROFILES:
            raise CapabilityPolicyError(f"unknown rubric profile {self.rubric_profile!r}")
        _check_media("image", self.image, self.image_role, IMAGE_ROLES)
        _check_media("audio", self.audio, self.audio_role, AUDIO_ROLES)
        if self.image == "required" and self.image_role == "illustration":
            raise CapabilityPolicyError(
                "an AI illustration is context only and can never be required evidence"
            )
        if not self.reasons:
            raise CapabilityPolicyError("a capability plan must record why it chose its media")
        if self.declared:
            if self.construct is None:
                raise CapabilityPolicyError("a declared capability plan must carry its construct")
            if (self.image != "none" or self.audio != "none") and not self.construct.strip():
                raise CapabilityPolicyError(
                    "a declared capability plan with media must name the construct it carries"
                )
        elif self.construct is not None:
            raise CapabilityPolicyError("construct is only recorded for a declared media need")

    @property
    def carries_media(self) -> bool:
        """True when the lesson has at least one required or optional media item."""
        return self.image != "none" or self.audio != "none"

    @property
    def required_media(self) -> tuple[str, ...]:
        """The roles the generator must produce; used by P2/P3, not by this module."""
        roles: list[str] = []
        if self.image == "required":
            roles.append(str(self.image_role))
        if self.audio == "required":
            roles.append(str(self.audio_role))
        return tuple(roles)

    def to_dict(self) -> dict[str, object]:
        """A JSON-safe projection for plan/lesson records. No behaviour, no hidden state."""
        return {
            "recipe": self.recipe,
            "evidence_target": self.evidence_target,
            "check_angle": self.check_angle,
            "rubric_profile": self.rubric_profile,
            "image": self.image,
            "image_role": self.image_role,
            "audio": self.audio,
            "audio_role": self.audio_role,
            "locale": self.locale,
            "level": self.level,
            "subject_domain": self.subject_domain,
            "reasons": list(self.reasons),
            "declared": self.declared,
            "construct": self.construct,
        }


def _check_media(kind: str, level: str, role: str | None, allowed_roles: tuple[str, ...]) -> None:
    if level not in MEDIA_LEVELS:
        raise CapabilityPolicyError(f"unknown {kind} level {level!r}")
    if level == "none":
        if role is not None:
            raise CapabilityPolicyError(f"{kind} is none but declares role {role!r}")
        return
    if role not in allowed_roles:
        raise CapabilityPolicyError(f"{kind} level {level!r} needs a role from {allowed_roles}")


def _normalise_domain(subject_domain: str | None, locale: str | None) -> str:
    if subject_domain is None or not str(subject_domain).strip():
        return "language" if locale else "general"
    domain = str(subject_domain).strip().lower().replace("-", "_").replace(" ", "_")
    return _DOMAIN_ALIASES.get(domain, domain)


def _normalise_intent(lesson_intent: str) -> str:
    text = " ".join(str(lesson_intent).lower().split())
    # "no speaking" or "without a diagram" must not register as a request for the construct.
    text = _VISUAL_DENIAL.sub(" ", text)
    text = _ORAL_DENIAL.sub(" ", text)
    return text


def _match(pattern: re.Pattern[str], text: str) -> str | None:
    found = pattern.search(text)
    return found.group(0) if found else None


def _none_image_reason(domain: str, recipe: str) -> str:
    if recipe == "parent":
        return (
            "the lesson names no source image or schematic the parent must examine; a generated "
            "picture is not evidence, so the image level stays none"
        )
    if domain in SYMBOLIC_DOMAINS:
        return (
            f"{domain} is symbolic and the intent names no diagram or graph; an AI illustration "
            "of a derivation is not evidence, so the image level stays none"
        )
    if domain == "language":
        return (
            "the language intent names no visual construct (picture, labelled object or source "
            "image); a decorative image would not carry the evidence, so the image level stays none"
        )
    if domain == "technical_procedure":
        return (
            "the procedure intent names no sequence, labelled part, measurement, wiring, schematic "
            "or permissioned source image; the image level stays none rather than decorate the steps"
        )
    if domain == "history":
        return (
            "the intent names no source image (poster, photograph, map, artefact or document scan); "
            "the image level stays none rather than illustrate the argument"
        )
    return (
        "the intent names no visual construct (diagram, schematic, source image or picture); both "
        "media stay none"
    )


def _image_decision(
    *,
    domain: str,
    recipe: str,
    check_angle: str,
    evidence_target: str,
    text: str,
) -> tuple[str, str | None, str]:
    schematic = _match(_SCHEMATIC_VISUAL, text)
    sourced = _match(_SOURCED_VISUAL, text)
    illustration = _match(_ILLUSTRATION_VISUAL, text)

    if recipe == "parent":
        # The parent is the presenter and the observer. Only reference material the parent must
        # look at can be media, and it is optional because the observation is the evidence.
        if sourced:
            return (
                "optional",
                "sourced_reference",
                f"the intent names a reference image ({sourced!r}) the parent examines; it is a "
                "cited source, not a generated illustration",
            )
        if schematic:
            return (
                "optional",
                "schematic",
                f"the intent names a visual construct ({schematic!r}) the parent can check against; "
                "it is optional because the observation is the evidence",
            )
        return "none", None, _none_image_reason(domain, recipe)

    if domain in SYMBOLIC_DOMAINS:
        if schematic:
            return (
                "optional",
                "schematic",
                f"the intent names a visual construct ({schematic!r}); only a deterministic "
                "schematic from structured facts is allowed in a symbolic lesson",
            )
        return "none", None, _none_image_reason(domain, recipe)

    if domain == "technical_procedure":
        if schematic:
            required = check_angle in ("procedure", "verification")
            return (
                "required" if required else "optional",
                "schematic",
                f"the intent names a technical visual construct ({schematic!r}); a deterministic "
                "schematic carries it and an AI illustration can never be the procedure authority",
            )
        if sourced:
            required = check_angle in ("procedure", "verification")
            return (
                "required" if required else "optional",
                "sourced_reference",
                f"the intent names a permissioned source image ({sourced!r}); it is cited, never "
                "synthesized",
            )
        if illustration and recipe != "one_off":
            return (
                "optional",
                "illustration",
                f"the intent names context artwork ({illustration!r}); it is optional context only, "
                "never a measurement, sequence or safety authority",
            )
        return "none", None, _none_image_reason(domain, recipe)

    if domain == "history":
        if sourced:
            required = bool(_SOURCE_ANALYSIS.search(text))
            return (
                "required" if required else "optional",
                "sourced_reference",
                f"the intent names a source image ({sourced!r}); the analysis is performed on that "
                "cited image, so it is a sourced reference and never a generated illustration",
            )
        if schematic:
            return (
                "optional",
                "schematic",
                f"the intent names a visual construct ({schematic!r}); a deterministic schematic may "
                "clarify it",
            )
        if illustration and recipe != "one_off":
            return (
                "optional",
                "illustration",
                f"the intent names context artwork ({illustration!r}); it is optional context only",
            )
        return "none", None, _none_image_reason(domain, recipe)

    if domain == "language":
        if illustration and recipe != "one_off":
            return (
                "optional",
                "illustration",
                f"the intent names a visual aid ({illustration!r}); it is optional context, and the "
                "language evidence stays in the phrase",
            )
        return "none", None, _none_image_reason(domain, recipe)

    # Advisory domain is general or unknown: the intent's named construct still decides.
    if recipe == "one_off":
        if schematic and (evidence_target == "procedure" or _STRONG_TECHNICAL.search(text)):
            required = evidence_target == "procedure" or check_angle == "verification"
            return (
                "required" if required else "optional",
                "schematic",
                f"the one-off brief names a technical construct ({schematic!r}); a deterministic "
                "schematic is the checklist anchor, and a one-off brief gets no decorative media",
            )
        return "none", None, _none_image_reason(domain, recipe)
    if schematic:
        return (
            "optional",
            "schematic",
            f"the intent names a visual construct ({schematic!r}); a deterministic schematic may "
            "carry it",
        )
    if sourced:
        return (
            "optional",
            "sourced_reference",
            f"the intent names a reference image ({sourced!r}); it must be cited rather than "
            "generated",
        )
    if illustration:
        return (
            "optional",
            "illustration",
            f"the intent names context artwork ({illustration!r}); it is optional context only",
        )
    return "none", None, _none_image_reason(domain, recipe)


def _audio_decision(
    *,
    domain: str,
    recipe: str,
    check_angle: str,
    evidence_target: str,
    text: str,
    locale: str | None,
) -> tuple[str, str | None, str]:
    if recipe == "parent":
        return (
            "none",
            None,
            "recipe parent: the parent presents and observes, so no generated narration is added",
        )
    if domain != "language":
        if domain in SYMBOLIC_DOMAINS:
            return (
                "none",
                None,
                f"the lesson is symbolic ({domain}); generated audio stays none because there is "
                "no oral construct to render",
            )
        return (
            "none",
            None,
            f"domain {domain!r} names no language oral construct; generated audio stays none",
        )

    oral = _match(_PRONUNCIATION, text)
    listening = _match(_LISTENING, text)
    reading = _match(_READING_WRITING, text)
    strong = _STRONG_ORAL.search(text) is not None

    if reading and not strong and not listening:
        return (
            "none",
            None,
            f"intent names reading or writing ({reading!r}) and no explicit spoken construct; no "
            f"narration is added merely because locale {locale!r} is set",
        )

    if oral is None and listening is None:
        if reading:
            return (
                "none",
                None,
                f"intent names reading or writing ({reading!r}); no narration is added merely "
                f"because locale {locale!r} is set",
            )
        return (
            "none",
            None,
            "the language intent names no spoken or listening construct; audio stays none even "
            "though the course has a locale",
        )

    if listening and oral is None:
        return (
            "required",
            "narration",
            f"the intent names a listening construct ({listening!r}); the spoken passage has to "
            "exist for the comprehension check to be answerable",
        )

    # An oral construct is present. Pronunciation is required when the lesson measures production
    # or the intent explicitly asks the learner to say/read/pronounce something.
    required = check_angle == "production" or evidence_target == "production" or strong
    return (
        "required" if required else "optional",
        "pronunciation_reference",
        f"the intent names a spoken construct ({oral!r}); the transcript is authoritative and the "
        "recording is a pronunciation reference, not a second text",
    )


def _declared_image_decision(
    *, domain: str, recipe: str, need: MediaNeed
) -> tuple[str, str | None, str]:
    """Adopt a declared visual need, or reject a role this lesson cannot carry.

    The construct text is the planner's own declaration, not incidental intent prose. It still has
    to name the construct the declared role exists for; the domain rules still decide whether that
    role is possible at all.
    """
    if need.image == "none" or need.image_role is None:
        return "none", None, "the plan declares no visual need for this section"

    role = need.image_role
    text = _normalise_intent(need.construct)
    if role == "illustration":
        if need.image == "required":
            raise CapabilityPolicyError(
                "an AI illustration is context only and can never be a required visual need"
            )
        if domain in SYMBOLIC_DOMAINS:
            raise CapabilityPolicyError(
                f"a {domain} lesson is symbolic; an AI illustration is never evidence there, so "
                "the declared illustration role is not permitted"
            )
        if recipe == "one_off":
            raise CapabilityPolicyError(
                "a one-off brief gets no decorative media; a declared illustration is not permitted"
            )
        if not _ILLUSTRATION_VISUAL.search(text):
            raise CapabilityPolicyError(
                f"the declared illustration need {need.construct!r} names no visual-aid construct"
            )
    elif role == "schematic":
        if domain == "language":
            raise CapabilityPolicyError(
                "a language lesson may carry a visual aid but not a schematic; the declared "
                "schematic role is not permitted"
            )
        if not _SCHEMATIC_VISUAL.search(text):
            raise CapabilityPolicyError(
                f"the declared schematic need {need.construct!r} names no sequence, wiring, "
                "measurement, labelling or graph construct"
            )
    elif role == "sourced_reference":
        if domain == "language" or domain in SYMBOLIC_DOMAINS:
            raise CapabilityPolicyError(
                f"a {domain} lesson cannot carry a cited source image; the declared "
                "sourced_reference role is not permitted"
            )
        if not _SOURCED_VISUAL.search(text):
            raise CapabilityPolicyError(
                f"the declared sourced_reference need {need.construct!r} names no photograph, "
                "poster, map, artefact or document image"
            )
    if recipe == "parent" and need.image == "required":
        raise CapabilityPolicyError(
            "recipe parent: the observation is the evidence, so a visual need can be optional but "
            "never required"
        )
    return (
        need.image,
        role,
        f"the plan declared a {need.image} {role} need for {need.construct!r}; the policy accepts "
        f"that role for {domain}",
    )


def _declared_audio_decision(
    *, domain: str, recipe: str, need: MediaNeed
) -> tuple[str, str | None, str]:
    """Adopt a declared audio need, or reject one this lesson cannot carry."""
    if need.audio == "none" or need.audio_role is None:
        return "none", None, "the plan declares no audio need for this section"
    if recipe == "parent":
        raise CapabilityPolicyError(
            "recipe parent: the parent presents and observes, so a declared audio need is not "
            "permitted"
        )
    if domain != "language":
        raise CapabilityPolicyError(
            f"domain {domain!r} is not a language lesson; generated audio is not permitted, so the "
            "declared audio need is rejected"
        )
    text = _normalise_intent(need.construct)
    if need.audio_role == "narration":
        if not _LISTENING.search(text):
            raise CapabilityPolicyError(
                f"the declared narration need {need.construct!r} names no listening construct"
            )
    elif not _PRONUNCIATION.search(text):
        raise CapabilityPolicyError(
            f"the declared pronunciation_reference need {need.construct!r} names no spoken "
            "construct"
        )
    return (
        need.audio,
        need.audio_role,
        f"the plan declared a {need.audio} {need.audio_role} need for {need.construct!r}; the "
        "transcript stays authoritative",
    )


def _rubric_profile(
    *,
    domain: str,
    recipe: str,
    evidence_target: str,
    check_angle: str,
    text: str,
) -> tuple[str, str]:
    if recipe == "parent":
        return (
            "observation",
            "recipe parent: the rubric is observation (observable behaviour, context, note, "
            "follow-up), not a child quiz",
        )
    if check_angle == "verification":
        if domain == "language" and (
            evidence_target == "production" or _PRONUNCIATION.search(text) or _LISTENING.search(text)
        ):
            return (
                "language_production",
                "the one-off brief still measures a spoken or written phrase; the rubric is "
                "language production (target phrase, pronunciation or fluency, meaning, register)",
            )
        return (
            "procedural",
            "check angle verification selects the procedural rubric (ordered steps, safety stop "
            "condition, verification)",
        )
    if domain == "language" and (check_angle == "production" or _PRONUNCIATION.search(text)):
        return (
            "language_production",
            "a language production construct selects the language_production rubric (target phrase, "
            "pronunciation or fluency, meaning, register)",
        )
    if domain == "history" and _SOURCE_ANALYSIS.search(text):
        return (
            "source_analysis",
            "the intent names a source-analysis construct; the rubric is source_analysis (claim, "
            "evidence, provenance, contradiction handling)",
        )
    if check_angle == "procedure":
        return (
            "procedural",
            "check angle procedure selects the procedural rubric (ordered steps, safety stop "
            "condition, verification)",
        )
    if check_angle == "recall" or (domain == "grammar" and check_angle == "discrimination"):
        return (
            "recall_accuracy",
            "a recall or grammar-discrimination construct selects the recall_accuracy rubric "
            "(correct answer, accepted alternatives, no cue leakage)",
        )
    return (
        "concept_explanation",
        "the check measures an explanation construct; the rubric is concept_explanation (accurate "
        "claim, mechanism, example, limits)",
    )


def plan_lesson_capability(
    *,
    recipe: str,
    evidence_target: str,
    lesson_intent: str,
    locale: str | None = None,
    level: str | None = None,
    subject_domain: str | None = None,
    media_need: object = None,
) -> LessonCapabilityPlan:
    """Map one lesson's declared facts to an immutable capability plan.

    When ``media_need`` is supplied (the plan's typed per-section declaration), the policy adopts
    it and only decides whether each declared role is possible; it does not re-guess the construct
    from ``lesson_intent``. Without a declaration the legacy construct detectors run, which is the
    hand-built/legacy path, not the generated-plan path.

    Raises :class:`CapabilityPolicyError` for an unknown recipe or evidence target, and for a
    declaration that names a role this lesson cannot carry. It never raises for an ordinary
    lesson: the fallback is no media, never invented media.
    """
    if recipe not in RECIPES:
        raise CapabilityPolicyError(f"unknown recipe {recipe!r}; expected one of {RECIPES}")
    if evidence_target not in EVIDENCE_TARGETS:
        raise CapabilityPolicyError(
            f"unknown evidence target {evidence_target!r}; expected one of {EVIDENCE_TARGETS}"
        )

    domain = _normalise_domain(subject_domain, locale)
    text = _normalise_intent(lesson_intent)

    forced_angle, angle_reason = recipe_check_angle(recipe)
    check_angle: str = forced_angle if forced_angle is not None else evidence_target

    need = parse_media_need(media_need) if media_need is not None else None
    if need is not None:
        image, image_role, image_reason = _declared_image_decision(
            domain=domain, recipe=recipe, need=need
        )
        audio, audio_role, audio_reason = _declared_audio_decision(
            domain=domain, recipe=recipe, need=need
        )
    else:
        image, image_role, image_reason = _image_decision(
            domain=domain,
            recipe=recipe,
            check_angle=check_angle,
            evidence_target=evidence_target,
            text=text,
        )
        audio, audio_role, audio_reason = _audio_decision(
            domain=domain,
            recipe=recipe,
            check_angle=check_angle,
            evidence_target=evidence_target,
            text=text,
            locale=locale,
        )
    profile, profile_reason = _rubric_profile(
        domain=domain,
        recipe=recipe,
        evidence_target=evidence_target,
        check_angle=check_angle,
        text=text,
    )

    reasons = (angle_reason, image_reason, audio_reason, profile_reason)
    return LessonCapabilityPlan(
        recipe=recipe,
        evidence_target=evidence_target,
        check_angle=check_angle,
        rubric_profile=profile,
        image=image,
        image_role=image_role,
        audio=audio,
        audio_role=audio_role,
        locale=locale,
        level=level,
        subject_domain=domain,
        reasons=reasons,
        declared=need is not None,
        construct=need.construct if need is not None else None,
    )


# ── Projection onto the lesson schema's media vocabulary ────────────────────


def recipe_check_angle(recipe: str) -> tuple[str | None, str]:
    """The check angle a recipe forces, or ``None`` when the objective's target stands.

    This is the single place the "one-off verifies, parent observes" rule lives so the plan
    builder, the lesson builder and the prompt cannot disagree about it.
    """
    if recipe == "one_off":
        return "verification", "recipe one_off: the check is a verification checklist, not a quiz"
    if recipe == "parent":
        return "observation", "recipe parent: the check is parent observation, not a child quiz"
    if recipe not in RECIPES:
        raise CapabilityPolicyError(f"unknown recipe {recipe!r}; expected one of {RECIPES}")
    return None, f"recipe {recipe!r}: the check keeps the objective's evidence target"


def permitted_image_roles(plan: LessonCapabilityPlan) -> tuple[str, ...]:
    """The visual media roles a lesson spec may declare under ``plan``. Empty means no visual."""
    if plan.image == "none" or plan.image_role is None:
        return ()
    return (IMAGE_SPEC_ROLE[plan.image_role],)


def permitted_audio_roles(plan: LessonCapabilityPlan) -> tuple[str, ...]:
    """The audio media roles a lesson spec may declare under ``plan``. Empty means no audio."""
    if plan.audio == "none" or plan.audio_role is None:
        return ()
    return (AUDIO_SPEC_ROLE[plan.audio_role],)


def _media_reason(plan: LessonCapabilityPlan, index: int) -> str:
    """The plan reason that justifies (or refuses) the media kind at ``index``."""
    # ``reasons`` is built as (angle, image, audio, profile); fall back to the joined trail when a
    # caller hands in a hand-built plan rather than one from ``plan_lesson_capability``.
    if len(plan.reasons) > index:
        return plan.reasons[index]
    return "; ".join(plan.reasons)


def media_policy_problems(plan: LessonCapabilityPlan, media: object) -> list[str]:
    """Every way ``media`` contradicts ``plan``. Empty means the specs are permitted.

    This is the permission half of the policy: it decides whether a lesson may carry a given
    kind/role at all. The content half (text equivalent, transcript, source and permission,
    structured facts, illustration-never-technical) lives in ``artifacts.media_problems`` and is
    applied alongside this function — a spec has to pass both.
    """
    problems: list[str] = []
    items = list(media) if isinstance(media, (list, tuple)) else []
    image_roles = permitted_image_roles(plan)
    audio_roles = permitted_audio_roles(plan)
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            problems.append(f"media item {index} is not a declarative spec object")
            continue
        kind = str(item.get("kind") or "")
        role = item.get("role")
        if kind not in SPEC_MEDIA_KINDS:
            problems.append(
                f"media item {index}: unknown media kind {kind!r}; expected one of {SPEC_MEDIA_KINDS}"
            )
            continue
        if kind == "visual":
            if plan.image == "none":
                problems.append(
                    f"media item {index}: the capability policy sets image to 'none' "
                    f"({_media_reason(plan, 1)}), so a visual spec is not permitted"
                )
            elif role not in image_roles:
                problems.append(
                    f"media item {index}: visual role {role!r} is not permitted; this lesson may "
                    f"use {image_roles} (image level {plan.image!r})"
                )
            continue
        if plan.audio == "none":
            problems.append(
                f"media item {index}: the capability policy sets audio to 'none' "
                f"({_media_reason(plan, 2)}), so an audio spec is not permitted"
            )
        elif role not in audio_roles:
            problems.append(
                f"media item {index}: audio role {role!r} is not permitted; this lesson may use "
                f"{audio_roles} (audio level {plan.audio!r})"
            )
    return problems


def missing_required_media(plan: LessonCapabilityPlan, media: object) -> list[str]:
    """Every required media item the lesson did not produce.

    The permission half refuses an item the policy does not allow; this is the other direction:
    a plan that declared a required visual or audio need must be honored by the authored lesson.
    A ``none``/``optional`` level never produces a problem here.
    """
    items = [item for item in (media if isinstance(media, (list, tuple)) else []) if isinstance(item, dict)]
    problems: list[str] = []
    for kind, level, role, spec_role in (
        ("visual", plan.image, plan.image_role, IMAGE_SPEC_ROLE.get(plan.image_role or "")),
        ("audio", plan.audio, plan.audio_role, AUDIO_SPEC_ROLE.get(plan.audio_role or "")),
    ):
        if level != "required":
            continue
        present = any(
            str(item.get("kind") or "") == kind and item.get("role") == spec_role for item in items
        )
        if present:
            continue
        construct = f" for {plan.construct!r}" if plan.construct else ""
        problems.append(
            f"the capability policy requires a {kind} item with role {spec_role!r}{construct}; "
            "the lesson did not produce one"
        )
    return problems

