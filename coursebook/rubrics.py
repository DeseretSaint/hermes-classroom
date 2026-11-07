"""Rubric angles, keyed by construct: a registry plus a validator.

One generic rubric for every subject is a failure mode, not a convenience. A head-gasket
procedure is scored on ordered steps, a safety stop condition and verification; a Japanese
greeting on the target phrase, pronunciation, meaning and register; a history source analysis on
claim, evidence, provenance and contradiction handling. ``docs/VISUAL_MEDIA_PLAN.md`` §4 names
the six profiles this module owns:

``concept_explanation``, ``procedural``, ``language_production``, ``recall_accuracy``,
``source_analysis``, ``observation``.

The registry is declarative data: each profile carries 3-6 criteria, and each criterion is an
*observable aspect* with a one-sentence note on what a scorer watches for. Labels are exactly the
ones :mod:`coursebook.policy` records on a capability plan, so the plan, the prompt and the
validator cannot drift apart; ``registry_problems()`` proves the copy is in step and
``tests/test_rubrics.py`` fails if it is not.

The validator is deliberately conservative about what it can prove:

* it proves the shape (3-6 criteria), that criteria are distinct, that none is a mental-state
  claim ("understands", "knows", "mastery") rather than something a scorer can watch, and that the
  profile can score the objective's declared evidence target;
* it cannot prove the prose is true, that the criteria are well worded, or that a scored response
  is correct. A clean verdict is not a badge and never a claim of mastery.

A rubric is a scoring guide. It is not mastery, not a certificate and not a measurement of a
person; nothing here may be published as one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from .policy import (
    EVIDENCE_TARGETS,
    MIN_RUBRIC_CRITERIA,
    RUBRIC_PROFILE_CRITERIA,
    RUBRIC_PROFILES,
    CapabilityPolicyError,
    plan_lesson_capability,
)

#: The plan's ceiling: a scoring guide with more than six criteria stops being a guide.
MAX_RUBRIC_CRITERIA = 6


class RubricRejected(ValueError):
    """A rubric failed the registry's rules. Maps to a pack/generation rejection."""


@dataclass(frozen=True, slots=True)
class RubricCriterion:
    """One observable aspect of a response. ``observation`` says what the scorer watches for."""

    key: str
    label: str
    observation: str

    def to_dict(self) -> dict[str, str]:
        return {"key": self.key, "criterion": self.label, "observation": self.observation}


@dataclass(frozen=True, slots=True)
class RubricProfile:
    """A construct selector, not a template: the aspects are fixed, the wording is the check's."""

    name: str
    construct: str
    criteria: tuple[RubricCriterion, ...]
    evidence_targets: frozenset[str]
    limitation: str

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(criterion.label for criterion in self.criteria)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.name,
            "construct": self.construct,
            "criteria": [criterion.to_dict() for criterion in self.criteria],
            "evidence_targets": sorted(self.evidence_targets),
            "limitation": self.limitation,
        }


def _profile(
    name: str,
    construct: str,
    aspects: Sequence[tuple[str, str, str]],
    evidence_targets: Iterable[str],
    limitation: str,
) -> RubricProfile:
    return RubricProfile(
        name=name,
        construct=construct,
        criteria=tuple(RubricCriterion(*aspect) for aspect in aspects),
        evidence_targets=frozenset(evidence_targets),
        limitation=limitation,
    )


# ── The six profiles ────────────────────────────────────────────────────────
#
# Labels are copied from ``coursebook.policy.RUBRIC_PROFILE_CRITERIA`` (which in turn records the
# plan's §4 wording). ``registry_problems()`` checks the copy; do not "improve" a label here
# without changing the plan and the policy together.

RUBRICS: Mapping[str, RubricProfile] = MappingProxyType(
    {
        "concept_explanation": _profile(
            "concept_explanation",
            "The learner explains a concept in their own words.",
            (
                (
                    "accurate_claim",
                    "accurate claim",
                    "States a claim that matches the taught model or source without adding an "
                    "unsupported detail.",
                ),
                (
                    "mechanism",
                    "mechanism",
                    "Explains how or why it happens, naming the parts or steps that produce the "
                    "result.",
                ),
                (
                    "example",
                    "example",
                    "Gives an example and says what the example demonstrates.",
                ),
                (
                    "limits",
                    "limits",
                    "Names a condition the claim depends on or a case where it does not hold.",
                ),
            ),
            ("comprehension", "transfer"),
            "Explaining a concept is not recalling a label and not performing a procedure.",
        ),
        "procedural": _profile(
            "procedural",
            "The learner performs or verifies a procedure.",
            (
                (
                    "ordered_steps",
                    "ordered steps",
                    "Performs the steps in the stated order and can say which step is current.",
                ),
                (
                    "safety_stop_condition",
                    "safety stop condition",
                    "Names the stop condition and stops or asks before continuing when it is met.",
                ),
                (
                    "verification",
                    "verification",
                    "Checks the finished result against the stated measurement or checklist.",
                ),
            ),
            ("procedure", "transfer"),
            "A procedure is not scored on describing it; the observed steps carry the evidence.",
        ),
        "language_production": _profile(
            "language_production",
            "The learner produces a spoken or written target phrase.",
            (
                (
                    "target_phrase",
                    "target phrase",
                    "Produces the target phrase, in the script or scaffold the level allows.",
                ),
                (
                    "pronunciation_or_fluency",
                    "pronunciation or fluency",
                    "Speaks with the modelled pronunciation, or reads with phrasing that does "
                    "not break the line.",
                ),
                (
                    "meaning",
                    "meaning",
                    "Conveys the meaning the phrase is for, not only its sound.",
                ),
                (
                    "register",
                    "register",
                    "Uses the register the addressee and setting call for.",
                ),
            ),
            ("production", "transfer"),
            "Reading comprehension is not production; a romaji-only answer is not script reading.",
        ),
        "recall_accuracy": _profile(
            "recall_accuracy",
            "The learner retrieves the answer without the key in view.",
            (
                (
                    "correct_answer",
                    "correct answer",
                    "Gives the reference answer or a declared accepted alternative.",
                ),
                (
                    "accepted_alternatives",
                    "accepted alternatives",
                    "Uses a declared alternative; an undeclared variant is recorded, never "
                    "silently accepted.",
                ),
                (
                    "no_cue_leakage",
                    "no cue leakage",
                    "Answers without the prompt or a scaffold giving the key away.",
                ),
            ),
            ("recall", "discrimination"),
            "Recognition is not production, and a cued answer is not unaided recall.",
        ),
        "source_analysis": _profile(
            "source_analysis",
            "The learner analyses a source's claim, evidence and provenance.",
            (
                (
                    "claim",
                    "claim",
                    "States what the source claims, in the source's own terms.",
                ),
                (
                    "evidence",
                    "evidence",
                    "Points to the specific passage, detail or feature that carries the claim.",
                ),
                (
                    "provenance",
                    "provenance",
                    "Names the author or publisher, date and context, with the citation.",
                ),
                (
                    "contradiction_handling",
                    "contradiction handling",
                    "Names a contradicting source or detail and says how it affects the claim.",
                ),
            ),
            ("comprehension", "transfer"),
            "A source analysis is not a summary; an assumed provenance is not a cited one.",
        ),
        "observation": _profile(
            "observation",
            "A parent records what a child actually did, without grading the child.",
            (
                (
                    "observable_behaviour",
                    "observable behaviour",
                    "Records what the child did or said, quoted or described, not an inference.",
                ),
                (
                    "context",
                    "context",
                    "Records when, where and with which materials it happened.",
                ),
                (
                    "note",
                    "note",
                    "Limits the note to what was seen: no score and no judgement about the child.",
                ),
                (
                    "follow_up",
                    "follow-up",
                    "Names one next thing to try and what would count as evidence then.",
                ),
            ),
            (
                "recall",
                "comprehension",
                "production",
                "discrimination",
                "procedure",
                "transfer",
            ),
            "Observation is a record, not a quiz, a grade or a claim about the child.",
        ),
    }
)

#: Which evidence targets each profile is allowed to score. A profile cannot score a construct
#: it never observes (e.g. ``recall_accuracy`` on a production target is off-profile).
PROFILE_EVIDENCE_TARGETS: Mapping[str, frozenset[str]] = MappingProxyType(
    {name: profile.evidence_targets for name, profile in RUBRICS.items()}
)

#: The profile a check gets when no construct was selected, keyed by its declared evidence target.
DEFAULT_PROFILE_BY_EVIDENCE_TARGET: Mapping[str, str] = MappingProxyType(
    {
        "recall": "recall_accuracy",
        "discrimination": "recall_accuracy",
        "comprehension": "concept_explanation",
        "transfer": "concept_explanation",
        "production": "language_production",
        "procedure": "procedural",
    }
)


# ── Criteria text and rules ─────────────────────────────────────────────────

#: Mental-state claims. A rubric scores what someone *does*; "understands" is a conclusion, not
#: an observation, and a scorer cannot check it.
_GENERIC = re.compile(
    r"\b(?:"
    r"understands?|understanding|"
    r"knows?|knowledge(?:able)?|"
    r"appreciates?|appreciation|"
    r"(?:is|be|becomes?)\s+aware|awareness|"
    r"comprehends?|"
    r"grasps?|"
    r"(?:is|be)\s+familiar\s+with|familiarity|"
    r"enjoys?|"
    r"mastery|mastered|"
    r"(?:is|be)\s+comfortable\s+with|"
    r"has\s+a\s+sense\s+of"
    r")\b",
    re.IGNORECASE,
)

#: Verb stems are not used to grade prose. A criterion is rejected when it states a mental state;
#: the registry's own criteria are hand-written to name an observable action, but a caller's
#: wording is not policed beyond the generic rule (a synthetic pack may use placeholder criteria).

_TEXT_KEYS: tuple[str, ...] = ("description", "criterion", "label", "text", "criterion_text")


def criterion_text(item: Any) -> str:
    """The scored sentence of one criterion.

    Pack rubrics are strings; generated rubrics are ``{criterion, weight, description}`` records.
    The description is the scored sentence, so it is preferred when present.
    """
    if isinstance(item, str):
        return " ".join(item.split())
    if isinstance(item, Mapping):
        for key in _TEXT_KEYS:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return " ".join(value.split())
    return ""


def _criterion_label(item: Any) -> str:
    if isinstance(item, Mapping):
        value = item.get("criterion") or item.get("label")
        if isinstance(value, str):
            return " ".join(value.split())
    return ""


def _normalise(text: str) -> str:
    """Case, spacing and trailing punctuation do not make a criterion distinct."""
    folded = " ".join(str(text).casefold().split())
    return folded.strip(" .,;:!?…-—")


def _is_generic(text: str) -> bool:
    return bool(text) and _GENERIC.search(text) is not None


def registry_problems() -> list[str]:
    """Problems with the registry itself, not with a supplied rubric. Empty means consistent.

    Provenance guard: labels and evidence targets must stay inside the plan's vocabulary, every
    profile needs 3-6 distinct observable criteria, and no criterion may be generic.
    """
    problems: list[str] = []
    if tuple(RUBRICS) != tuple(RUBRIC_PROFILES):
        problems.append(f"registry profiles {tuple(RUBRICS)} do not match policy {tuple(RUBRIC_PROFILES)}")
    for name, profile in RUBRICS.items():
        if name not in RUBRIC_PROFILES:
            problems.append(f"profile {name!r} is not in the policy vocabulary")
        expected = tuple(RUBRIC_PROFILE_CRITERIA.get(name, ()))
        if profile.labels != expected:
            problems.append(f"profile {name!r} labels {profile.labels} drifted from policy {expected}")
        if not (MIN_RUBRIC_CRITERIA <= len(profile.criteria) <= MAX_RUBRIC_CRITERIA):
            problems.append(f"profile {name!r} has {len(profile.criteria)} criteria; expected 3-6")
        keys = [criterion.key for criterion in profile.criteria]
        if len(keys) != len(set(keys)):
            problems.append(f"profile {name!r} repeats a criterion key")
        for criterion in profile.criteria:
            if _is_generic(criterion.label) or _is_generic(criterion.observation):
                problems.append(f"profile {name!r} criterion {criterion.key!r} states a mental state")
        unknown = sorted(profile.evidence_targets - set(EVIDENCE_TARGETS))
        if unknown:
            problems.append(f"profile {name!r} claims unknown evidence targets {unknown}")
        if not profile.evidence_targets:
            problems.append(f"profile {name!r} serves no evidence target")
    for target, name in DEFAULT_PROFILE_BY_EVIDENCE_TARGET.items():
        if target not in EVIDENCE_TARGETS:
            problems.append(f"default profile table names unknown evidence target {target!r}")
        elif name not in RUBRICS:
            problems.append(f"default profile table names unknown profile {name!r}")
        elif target not in RUBRICS[name].evidence_targets:
            problems.append(f"default profile {name!r} cannot serve evidence target {target!r}")
    return problems


def get_profile(name: str) -> RubricProfile:
    profile = RUBRICS.get(str(name))
    if profile is None:
        raise RubricRejected(f"unknown rubric profile {name!r}; expected one of {RUBRIC_PROFILES}")
    return profile


def serves(profile: str, evidence_target: str) -> bool:
    """True when ``profile`` can score a check that declares ``evidence_target``."""
    entry = RUBRICS.get(str(profile))
    return entry is not None and str(evidence_target) in entry.evidence_targets


def default_profile_for(evidence_target: str) -> str:
    """The profile a check gets when no construct is selected (e.g. a pack manifest)."""
    name = DEFAULT_PROFILE_BY_EVIDENCE_TARGET.get(str(evidence_target))
    if name is None:
        raise RubricRejected(
            f"unknown evidence target {evidence_target!r}; expected one of {EVIDENCE_TARGETS}"
        )
    return name


def resolve_profile(preferred: str | None, evidence_target: str) -> str:
    """Keep an advisory construct when it can score this target; otherwise use the default.

    The declared evidence target is the authority. A capability plan is advisory about the
    construct, so an incompatible preference falls back to the target's default profile rather
    than failing a lesson that its author described differently.
    """
    if preferred is not None and serves(str(preferred), str(evidence_target)):
        return str(preferred)
    return default_profile_for(evidence_target)


def profile_for_lesson(
    *,
    recipe: str,
    evidence_target: str,
    lesson_intent: str,
    locale: str | None = None,
) -> str:
    """Resolve the rubric profile for one lesson from the capability policy's advisory choice."""
    target = str(evidence_target)
    try:
        plan = plan_lesson_capability(
            recipe=str(recipe),
            evidence_target=target,
            lesson_intent=str(lesson_intent or ""),
            locale=locale,
        )
    except CapabilityPolicyError:
        return default_profile_for(target)
    return resolve_profile(plan.rubric_profile, target)


def rubric_template(profile: str) -> list[dict[str, str]]:
    """The profile's criteria as declarative records, for a prompt or a reviewer's checklist.

    This is a template of *aspects*, not a filled rubric: the author still has to describe this
    response, and no criterion here may be copied as a verdict.
    """
    entry = get_profile(profile)
    return [criterion.to_dict() for criterion in entry.criteria]


def validate_rubric(
    profile: str,
    criteria: Any,
    evidence_target: str,
    *,
    max_criteria: int = MAX_RUBRIC_CRITERIA,
) -> list[str]:
    """Return every rule the rubric breaks; an empty list means it may be used.

    The rules, in order:

    1. the profile and the evidence target are known;
    2. the profile can score that evidence target (off-profile constructs are rejected);
    3. the rubric holds ``MIN_RUBRIC_CRITERIA`` to ``max_criteria`` criteria;
    4. every criterion is non-empty and no criterion states a mental state;
    5. no two criteria restate the same criterion.
    """
    problems: list[str] = []
    entry = RUBRICS.get(str(profile))
    if entry is None:
        return [f"unknown rubric profile {profile!r}; expected one of {RUBRIC_PROFILES}"]
    target = str(evidence_target)
    if target not in EVIDENCE_TARGETS:
        problems.append(f"unknown evidence target {target!r}; expected one of {EVIDENCE_TARGETS}")
    elif target not in entry.evidence_targets:
        problems.append(
            f"rubric profile {profile!r} does not score the objective's declared evidence target "
            f"{target!r}; it serves {sorted(entry.evidence_targets)}"
        )

    items = list(criteria or ()) if isinstance(criteria, (list, tuple)) else []
    count = len(items)
    if count < MIN_RUBRIC_CRITERIA:
        problems.append(
            f"has {count} rubric criteria; minimum is {MIN_RUBRIC_CRITERIA} "
            f"(distinct observable criteria, not one restated aspect)"
        )
    if count > max_criteria:
        problems.append(
            f"rubric criteria: {count} declared; a scoring guide has at most {max_criteria}"
        )

    seen: dict[str, int] = {}
    for index, item in enumerate(items, start=1):
        text = criterion_text(item)
        if not text:
            problems.append(f"rubric criterion {index} is empty or unreadable")
            continue
        label = _criterion_label(item)
        if _is_generic(text) or _is_generic(label):
            problems.append(
                f"rubric criterion {index} ({text!r}) is a mental-state claim, not an "
                f"observable criterion; score what the response does"
            )
        key = _normalise(text)
        if key in seen:
            problems.append(
                f"rubric criteria {seen[key]} and {index} restate the same criterion ({text!r})"
            )
        else:
            seen[key] = index
    return problems


def assert_valid_rubric(
    profile: str,
    criteria: Any,
    evidence_target: str,
    *,
    max_criteria: int = MAX_RUBRIC_CRITERIA,
) -> None:
    """Raise :class:`RubricRejected` with every problem, or return normally."""
    problems = validate_rubric(profile, criteria, evidence_target, max_criteria=max_criteria)
    if problems:
        raise RubricRejected("; ".join(problems))
