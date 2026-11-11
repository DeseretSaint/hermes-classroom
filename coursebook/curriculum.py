"""Research-backed curriculum design policy for Coursebook generation.

This module is deliberately deterministic: it does not decide the course. It turns the
declared goal, subject domain and target locale into a small, auditable brief that the plan
author and the independent validator must use. The actual sources still come from
``coursebook.research`` and are never promoted to support without a claim link.

Why this exists
---------------
A plan that merely lists topics is not a curriculum. The research base for sequencing is
consistent on a few points:

* starts from the performance the learner must be able to do (backward design);
* respects prerequisite dependencies before adding advanced material;
* for language learning, prioritises high-frequency vocabulary and core grammar, while
  treating coverage as a waypoint rather than comprehension;
* revisits core material through spaced retrieval and meaning-focused input/output.

No single ordering rule applies to every subject. This module therefore names the sequence
profile and the questions the author must answer, rather than inventing a universal order.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "CURRICULUM_PROFILES",
    "DOMAIN_SOURCES",
    "PERFORMANCE_FAMILIES",
    "curriculum_brief",
    "curriculum_prompt_lines",
    "curriculum_queries",
    "language_name",
    "performance_requirement",
    "resolve_domain",
]

#: The profiles are deliberately coarse. They choose the *kind* of sequence reasoning,
#: not a fixed syllabus; the plan author still has to use the research it is given.
CURRICULUM_PROFILES: dict[str, str] = {
    "language": "frequency_and_communication",
    "technical_procedure": "task_analysis_and_safety",
    "mathematics": "prerequisite_and_representation",
    "grammar": "prerequisite_and_contrast",
    "history": "chronology_and_evidence",
    "general": "backward_design_and_prerequisite",
}

_LANGUAGE_NAMES = {
    "ja": "Japanese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
}


def language_name(locale: str | None) -> str | None:
    """The human name of the target language, or ``None`` when no locale is declared."""
    if not locale or not str(locale).strip():
        return None
    primary = str(locale).split("-")[0].lower()
    return _LANGUAGE_NAMES.get(primary, primary)


def _profile(domain: str | None) -> str:
    key = str(domain or "").strip().lower()
    return CURRICULUM_PROFILES.get(key, CURRICULUM_PROFILES["general"])


# ── Physical-performance detection ─────────────────────────────────────────
#
# CP-015g/D1-F1: a plan for a goal the learner *carries out* must evidence the carrying out, not
# only knowledge about it. Two live runs authored four objectives about a telescope with every
# check a comprehension quiz, and the independent validator refused the plan for it. The fix is a
# typed requirement computed here (the same one the author and the validator are told about) plus
# a deterministic rule the plan is refused on.
#
# This is a goal detector, not a topic classifier: a match is a manual act the goal asks for, and
# a miss means the goal may still be about the subject without asking the learner to perform it.
# It deliberately does not fire on "understand/explain/analyse", and does not read the declared
# subject domain — an undeclared domain resolves to the locale default (`language`), which is the
# wrong answer for a hands-on goal.

#: Acts that are unambiguously performed with hands, tools or instruments. These are stems, not
#: whole words: "replacing" and "soldering" are the same act as "replace" and "solder".
_ALWAYS_PHYSICAL_ACT = re.compile(
    r"\b("
    r"set\s+up|assembl|disassembl|install|replac|refit|re-fit|repair|solder|desolder|"
    r"weld|drill|calibrat|collimat|align|tune"
    r")"
)

#: Acts that are only physical when the goal also names something you hold, point or stand at.
#: ``mount`` and ``wire`` sit here rather than above because both are also nouns ("telescope
#: mounts", "the wiring"), and the noun alone is a topic, not a performance.
_PHYSICAL_ACT = re.compile(
    r"\b("
    r"focus|observ|measur|weigh|inspect|sketch|record|operat|clean|lubricat|charge|prime|"
    r"find|check|test|build|use|mount|wire"
    r")"
)

#: The instruments, tools and objects a physical course is performed with or at.
_PHYSICAL_OBJECT = re.compile(
    r"\b("
    r"telescope|eyepiece|finder|tripod|mount|lens|filter|binoculars?|"
    r"board|pcb|circuit|solder|iron|meter|multimeter|probe|wiring|"
    r"bike|bicycle|wheel|tube|tyre|tire|brake|engine|carburett?or|chain|"
    r"drill|saw|blade|sandpaper|needle|thread|fabric|loom|"
    r"oven|pan|dough|knife|stove|"
    r"guitar|piano|violin|instrument|strings?|"
    r"antenna|radio|sensor|thermometer|scale|camera|microscope|"
    r"plant|soil|seed|compost|garden|"
    r"moons?|stars?|planets?|sky"
    r")\b"
)

#: The evidence families a performed objective can be evidenced by: an ordered performance, or
#: the same performance applied to a new case (a second night, a second board).
PERFORMANCE_FAMILIES: tuple[str, ...] = ("procedure", "transfer")

#: A goal that opens by asking for understanding is not a performance goal on its own. This does
#: not veto the strong acts above ("understand how to solder a joint" still asks for the act as
#: the exit performance only if the goal says so); it only stops the weak act list from firing.
_UNDERSTANDING_FRAME = re.compile(
    r"^\s*(?:understand|explain|learn\s+about|know|describe|analyse|analyze|appreciate|"
    r"the\s+history\s+of|what\s+is|why\s+is)\b",
    re.IGNORECASE,
)


def performance_requirement(goal: str | None) -> dict[str, Any] | None:
    """The typed performance rule for one goal, or ``None`` when the goal is not a performance.

    Deterministic, side-effect free and replayable: it reads the goal string only. The plan
    author and the independent validator are both told the same block, and
    ``generation.enforce_plan_rules`` refuses a plan that declares no performance objective for
    a performance goal.

    No subject fact is invented here. The block names the act the goal itself contains and the
    two evidence families that can carry it.
    """
    text = " ".join(str(goal or "").split())
    if not text:
        return None
    strong = _ALWAYS_PHYSICAL_ACT.search(text.casefold())
    weak = _PHYSICAL_ACT.search(text.casefold())
    object_match = _PHYSICAL_OBJECT.search(text.casefold())
    action: str | None = None
    if strong:
        action = strong.group(0)
    elif weak and object_match and not _UNDERSTANDING_FRAME.search(text):
        action = weak.group(0)
    if action is None:
        return None
    return {
        "required": True,
        "detected_action": action,
        "performance_families": list(PERFORMANCE_FAMILIES),
        "rule": (
            "The goal asks the learner to carry out a physical act "
            f"({action!r}), so the course must evidence the act, not only knowledge about it. "
            "An objective whose exit performance is that act declares evidence_target "
            "'procedure' (an ordered performance) or 'transfer' (the same performance applied "
            "to a new case or a second session). At least one objective in the plan, and at "
            "least one objective in the opening unit, must declare one of those families."
        ),
        "check_rule": (
            "A 'procedure' objective's check is a performance checklist (kind 'verification'); "
            "a 'transfer' objective's check is a recorded attempt or an observation log (kind "
            "'verification' or 'observation'). A quiz evidences recall, comprehension or "
            "discrimination only, so a quiz cannot evidence a performance."
        ),
    }


def _domain_key(domain: str | None) -> str:
    key = str(domain or "").strip().lower()
    return key if key in CURRICULUM_PROFILES else "general"


# ── Domain resolution ──────────────────────────────────────────────────────
#
# CP-015g/D1-F2: an undeclared subject domain used to fall through to the locale default, which
# was `language`. A hands-on goal ("set up a small backyard telescope and find and observe the
# moons of Jupiter") therefore got a language-course brief and language-course research queries,
# and the plan author had to ignore both. The fix is a single resolution rule, shared by the
# brief, the research queries and the caller's run record:
#
#   * a declared domain wins, always (``source: declared``);
#   * an undeclared domain is read from the goal text — a performed physical act is
#     ``technical_procedure``, and a goal that names a target language and asks the learner to
#     use or learn it is ``language`` (``source: inferred``);
#   * anything else is ``general`` (``source: default``), and the record says so.
#
# `language` is never reachable from the locale alone: a caller that omits the subject domain and
# the language in the goal gets `general`, not a language course. This supersedes H-44's
# no-inference choice (docs/COURSE-BLUEPRINT.md §15); the inference is recorded in the run record
# rather than passed off as a declaration.

#: How the resolved domain was chosen. Only ``declared`` is the caller's decision.
DOMAIN_SOURCES: tuple[str, ...] = ("declared", "inferred", "default")

#: Verbs and nouns that mark a goal as language learning rather than a subject taught in a
#: language. These are the only words that let an undeclared goal reach the ``language`` route.
_LANGUAGE_LEARNING = re.compile(
    r"\b("
    r"learn|learning|study|studying|practi[cs]e|practi[cs]ing|"
    r"speak|speaking|converse|conversation|pronounce|pronunciation|"
    r"vocabulary|grammar|conjugat\w*|fluen\w*|phrases?|dialog(?:ue)?s?|"
    r"kana|kanji|hiragana|katakana|romaji|alphabet"
    r")\b",
    re.IGNORECASE,
)

#: A named language. Only a language the learner can name makes an undeclared goal a language
#: course; "a language" on its own is handled by :data:`_GENERIC_LANGUAGE`.
_LANGUAGE_TARGET = re.compile(
    r"\b("
    + "|".join(
        sorted(
            {name.lower() for name in _LANGUAGE_NAMES.values()}
            | {
                "italian",
                "portuguese",
                "russian",
                "dutch",
                "swedish",
                "norwegian",
                "danish",
                "polish",
                "turkish",
                "hebrew",
                "greek",
                "latin",
                "hindi",
                "thai",
                "vietnamese",
                "indonesian",
                "english",
            }
        )
    )
    + r")\b",
    re.IGNORECASE,
)

#: "Learn a foreign language" without naming one. The study verb has to sit next to the noun, so
#: "build a language learning app" does not become a language course.
_GENERIC_LANGUAGE = re.compile(
    r"\b(?:learn|learning|study|studying|practi[cs]e|practi[cs]ing|speak|speaking)\b"
    r"[^.]{0,20}\blanguages?\b",
    re.IGNORECASE,
)

#: A goal about a culture or a country's past is a content course, not a language course, even
#: when it names a language ("read Spanish colonial history"). A language-learning word above
#: still wins, so "learn Spanish history vocabulary" stays a language goal.
_SUBJECT_FRAME = re.compile(
    r"\b("
    r"history|histories|culture|literature|politics|political|economy|economics|geography|"
    r"cuisine|cooking|war|film|cinema|art|music|poetry|religion|philosophy"
    r")\b",
    re.IGNORECASE,
)


def _declared_locale(locale: str | None) -> str | None:
    text = str(locale or "").strip()
    return text or None


def _language_goal(text: str) -> bool:
    """True when the goal itself asks for language learning or use of a target language."""
    if not text:
        return False
    if not (_LANGUAGE_TARGET.search(text) or _GENERIC_LANGUAGE.search(text)):
        return False
    if _LANGUAGE_LEARNING.search(text):
        return True
    return not _SUBJECT_FRAME.search(text)


def resolve_domain(
    *,
    goal: str | None = None,
    domain: str | None = None,
    locale: str | None = None,
) -> dict[str, Any]:
    """The one place an undeclared subject domain is decided, and how it was decided.

    Returns ``domain`` (a key of :data:`CURRICULUM_PROFILES`), ``source`` (one of
    :data:`DOMAIN_SOURCES`), the declared inputs, the target language (only for a resolved
    language course) and — for an inferred or default choice — a machine-readable
    ``inferred_from`` and/or a human ``note`` explaining it.

    Deterministic and side-effect free: it reads the goal, the declared domain and the declared
    locale, nothing else. Every caller (the brief, the research queries, the run record) must use
    this function so the profile the research uses and the profile the author is told about are
    the same profile.
    """
    declared = str(domain).strip() if domain is not None and str(domain).strip() else None
    declared_locale = _declared_locale(locale)
    if declared is not None:
        # One alias table for the whole product: `policy.normalise_subject_domain` owns the
        # spelling map ("repair" -> "technical_procedure"), so resolution never grows a second.
        from . import policy as capability_policy

        key = _domain_key(capability_policy.normalise_subject_domain(declared))
        return {
            "domain": key,
            "source": "declared",
            "declared_subject_domain": declared,
            "declared_locale": declared_locale,
            "target_language": language_name(declared_locale) if key == "language" else None,
        }
    text = " ".join(str(goal or "").split())
    performance = performance_requirement(text)
    if performance is not None:
        # A performed act is a procedure course whether or not a locale is declared: the act is
        # what the learner must do, and the delivery locale says nothing about the subject.
        return {
            "domain": "technical_procedure",
            "source": "inferred",
            "inferred_from": "goal_performance",
            "declared_subject_domain": None,
            "declared_locale": declared_locale,
            "target_language": None,
            "note": (
                f"no subject domain was declared; the goal asks the learner to carry out "
                f"{performance['detected_action']!r}, so this course is authored as "
                "technical_procedure. That domain is inferred from the goal, not declared."
            ),
        }
    if _language_goal(text):
        if declared_locale is not None:
            return {
                "domain": "language",
                "source": "inferred",
                "inferred_from": "goal_language",
                "declared_subject_domain": None,
                "declared_locale": declared_locale,
                "target_language": language_name(declared_locale),
                "note": (
                    "no subject domain was declared; the goal asks the learner to learn or use a "
                    "target language, so this course is authored as a language course. That "
                    "domain is inferred from the goal, not declared."
                ),
            }
        return {
            "domain": "general",
            "source": "default",
            "inferred_from": "goal_language_without_locale",
            "declared_subject_domain": None,
            "declared_locale": None,
            "target_language": None,
            "note": (
                "the goal asks for a language, but the brief declared no locale, so this course "
                "is authored as a general course: a language course needs a declared target "
                "language. Declare the locale and the subject domain to author a language course."
            ),
        }
    return {
        "domain": "general",
        "source": "default",
        "declared_subject_domain": None,
        "declared_locale": declared_locale,
        "target_language": None,
        "note": (
            "no subject domain was declared and the goal names neither a performed physical act "
            "nor a target language, so this course is authored as a general course: the domain "
            "is the default, not a content decision. Declare the subject domain to name it."
        ),
    }


def curriculum_queries(
    goal: str,
    *,
    domain: str | None,
    level: str | None = None,
    locale: str | None = None,
) -> list[str]:
    """Two bounded, deterministic questions that every real course must research.

    A survey pass stays one query; ``working`` and ``deep`` add these. They are placed
    before the generic reference/glossary queries so a small budget cannot truncate the
    curriculum question away. The domain is resolved with :func:`resolve_domain` from the same
    goal the brief is given, so a language research query is only ever derived for a course the
    brief also hands the author as a language course.
    """
    base = " ".join(str(goal).split())
    if not base:
        return []
    domain_key = resolve_domain(goal=base, domain=domain, locale=locale)["domain"]
    queries = [f"{base} how to teach curriculum sequence"]
    if domain_key == "language":
        target = language_name(locale)
        if target:
            queries.append(
                f"{target} beginner curriculum high frequency vocabulary grammar order"
            )
        else:
            queries.append(f"{base} high frequency core vocabulary grammar order")
    else:
        queries.append(f"{base} prerequisite knowledge learning progression")
    return queries


def curriculum_brief(
    *,
    domain: str | None,
    locale: str | None,
    level: str | None,
    recipe: str,
    goal: str | None = None,
) -> dict[str, Any]:
    """The typed curriculum brief passed into plan generation and validation.

    It is intentionally input-only: no field here is a learner-facing progress claim. The
    plan author must fill the actual sequence from the supplied sources and the goal.

    The subject domain is resolved by :func:`resolve_domain` from the declared value and the goal
    text, and the brief states how it was chosen (``domain_source``). A caller that declares no
    domain and gives no goal gets ``general`` — never the locale's language.
    """
    resolved = resolve_domain(goal=goal, domain=domain, locale=locale)
    key = resolved["domain"]
    target = language_name(locale)
    brief: dict[str, Any] = {
        "model": "backward_design_prerequisite_frequency",
        "profile": CURRICULUM_PROFILES[key],
        "domain": key,
        "domain_source": resolved["source"],
        "declared_subject_domain": resolved["declared_subject_domain"],
        "required_research": [
            "exit performance: what the learner must be able to do",
            "prerequisite map: what must be known or practised first",
            "core inventory: the highest-utility or highest-frequency elements",
            "common misconceptions and error patterns",
            "practice and assessment order, including retrieval and review",
        ],
        "sequence_rule": (
            "Order units by prerequisite dependency first, then by utility and frequency. "
            "Every unit after the first names the earlier unit(s) it builds on and its goal "
            "states why it comes at that point. Do not order by textbook tradition alone."
        ),
        "coverage_policy": (
            "Coverage is not comprehension. A claim that a number of words covers a percentage "
            "must cite the source and the corpus/modality; never present a hunch as measured."
        ),
        "recipe": str(recipe),
    }
    if level and str(level).strip():
        brief["level"] = str(level).strip()
    performance = performance_requirement(goal)
    if performance is not None:
        # CP-015g/D1-F1: the same typed block reaches the author and the validator, and the
        # deterministic rule set refuses a plan that declares no performance objective for it.
        brief["performance"] = performance
    if key == "language":
        brief["language"] = {
            "target_language": target,
            "frequency_first": True,
            "function_words_are_grammar": (
                "Particles, copulas and verb endings are high-frequency grammatical items; "
                "teach them as grammar in context, not as isolated vocabulary cards."
            ),
            "script_order": (
                "Teach pronunciation and the target script early enough to read the core "
                "material; introduce characters inside high-frequency words, not as an "
                "isolated list."
            ),
            "four_strands": (
                "Balance meaning-focused input, meaning-focused output, language-focused "
                "learning and fluency development; explicit language focus is a minority of "
                "the course, not the whole course."
            ),
            "coverage_targets": (
                "Use 95-98% comprehension coverage as the long-run reading/listening target "
                "where the sources support it; 80% leaves roughly one word in five unknown."
            ),
        }
    elif key == "technical_procedure":
        brief["procedure"] = {
            "task_analysis": "Identify the real task, tools, safety prerequisites and stop conditions before the steps.",
            "order": "Demonstrate a worked procedure, then guided practice, then independent performance with feedback.",
            "hazards": "A hazard or prerequisite is never moved later to make the sequence look tidy.",
        }
    elif key == "mathematics":
        brief["conceptual"] = {
            "representations": "Move from concrete or visual representation to symbolic procedure, then to transfer.",
            "worked_examples": "Use worked examples early and fade support; do not begin with unsupported problem sets.",
            "prerequisites": "A procedure that depends on an unmastered definition or operation is not ready to teach.",
        }
    elif key == "history":
        brief["historical"] = {
            "evidence": "Sequence chronology and causation together; use primary sources and distinguish evidence from interpretation.",
            "themes": "Revisit a theme at increasing depth rather than listing dates without a causal thread.",
        }
    return brief


def curriculum_prompt_lines(brief: dict[str, Any]) -> list[str]:
    """Prompt lines shared by the v1 and v2 plan authors.

    They are directives, not claims: the supplied research remains the evidence, and an
    unsupported sequence is labelled unverified by the normal claim policy.
    """
    lines = [
        "Before choosing units, answer the curriculum questions in the input's curriculum "
        "brief: exit performance, prerequisites, core inventory, common misconceptions, and "
        "practice/assessment order. Use the supplied sources; if a claim is not grounded, "
        "label it unverified rather than inventing a citation.",
        "Sequence units by prerequisite dependency first, then utility/frequency. Every unit "
        "after unit 1 must name the earlier unit(s) it builds on, and its goal must state why "
        "it comes at that point. Do not merely mirror a textbook's table of contents.",
        "A unit may not require a concept that is only taught in a later unit. Put review and "
        "retrieval where the learner will need the earlier material again; do not teach a "
        "core item once and abandon it.",
        "Coverage is not comprehension. If you state that a number of words or items covers a "
        "percentage, cite the supplied source and the corpus/modality; never turn a rule of "
        "thumb into a measured claim.",
    ]
    performance = brief.get("performance")
    if isinstance(performance, dict):
        # CP-015g/D1-F1: the goal is a performance, so the plan must evidence the performance.
        lines.append(str(performance.get("rule") or "").strip())
        lines.append(str(performance.get("check_rule") or "").strip())
    lines.extend(
        [
            "An objective's `evidence_target` is the performance the learner must demonstrate, "
            "not the subject the objective is about. A knowledge objective declares 'recall', "
            "'comprehension' or 'discrimination'; an objective the learner performs declares "
            "'procedure' (an ordered performance) or 'transfer' (the performance applied to a "
            "new case or a second session), and its check is a verification checklist or an "
            "observation log. A quiz evidences recall, comprehension or discrimination only.",
            "`source_ids` is a claim link, not a reading list. Set it only on an objective whose "
            "`support` is 'sourced', list only sources whose supplied excerpt carries that "
            "objective's claim, and copy the carrying words into `source_quote` verbatim. If no "
            "supplied excerpt carries the claim, leave `source_ids` empty and set `support` to "
            "'unverified' rather than citing a source that does not say it.",
            "Where a supplied excerpt does carry the claim, citing it is required: a plan that "
            "marks every objective 'unverified' while the excerpts contain its claims has not "
            "used the research it was given. Read each excerpt before deciding — page navigation, "
            "menus and cookie notices are not evidence, and neither is a claim the excerpt only "
            "mentions in passing.",
        ]
    )
    language = brief.get("language")
    if isinstance(language, dict):
        target = language.get("target_language") or "the target language"
        lines.extend(
            [
                f"This is a {target} course. Prioritise high-frequency vocabulary and core "
                "grammar patterns, but teach particles, copulas and verb endings as grammar in "
                "context, not as isolated word cards.",
                "Teach pronunciation and the target script early enough to read the core "
                "material; introduce characters inside high-frequency words rather than as an "
                "isolated character list.",
                "Use all four strands: meaning-focused input, meaning-focused output, "
                "language-focused learning and fluency development. Explicit language focus is "
                "a minority of the course, not the whole course.",
                "Use 95-98% comprehension coverage as the long-run reading/listening target "
                "where the sources support it; do not describe 80% coverage as comprehension.",
            ]
        )
    elif brief.get("domain") == "technical_procedure":
        lines.append(
            "For this procedure, perform a task analysis first: tools, safety prerequisites, "
            "stop conditions, then a worked demonstration, guided practice and independent "
            "performance. Never move a hazard or prerequisite later to make the outline tidy."
        )
    elif brief.get("domain") == "mathematics":
        lines.append(
            "For this mathematical course, start from the representation the learner can "
            "already use, move to the symbolic procedure with worked examples, then to "
            "independent transfer. Do not schedule practice before the prerequisite definition "
            "or operation is secure."
        )
    elif brief.get("domain") == "history":
        lines.append(
            "For this history course, sequence chronology and causation together and use "
            "primary sources; distinguish evidence from interpretation rather than listing "
            "dates without a causal thread."
        )
    return lines
