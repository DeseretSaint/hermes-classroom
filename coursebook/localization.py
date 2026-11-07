"""Locale-aware scaffolds and text direction.

The lesson contract used to carry exactly ``romaji``, ``furigana`` and ``english_meaning`` for
every locale. That is a Japanese fixture pretending to be a contract: a French lesson was forced
to declare Japanese scaffolds, and an Arabic lesson had no way to say it reads right-to-left.

This module replaces the Japanese triple with two bounded decisions:

* **scaffolds** are a small vocabulary keyed by primary language *and* declared level. A locale
  declares only the kinds its beginner rule names; a locale with no rule declares none. A
  scaffold is a task-mandated accessibility aid (decoding help), never a learning-style
  diagnosis and never evidence of unaided skill.
* **direction** is a property of the text, not of the learner: a script that reads right-to-left
  produces ``rtl``; everything else is ``ltr``. It is recorded at the document/page level so
  every view renders the same text in the same direction without changing evidence semantics.

The legacy ``{"romaji": bool, "furigana": bool, "english_meaning": bool}`` object is still read
(``normalize_scaffolds``) so every page authored before this change keeps working. New lessons
write the open form: ``[{"kind": ..., "script"?: ..., "gloss"?: ..., "direction"?: ...}]``.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

__all__ = [
    "LTR",
    "RTL",
    "TEXT_DIRECTIONS",
    "SCAFFOLD_KINDS",
    "SCAFFOLD_SCRIPTS",
    "LEGACY_SCAFFOLD_KEYS",
    "RTL_PRIMARY_LANGUAGES",
    "ScaffoldError",
    "primary_language",
    "normalize_locale",
    "direction_for_locale",
    "scaffold_requirements",
    "normalize_scaffolds",
    "declared_scaffold_kinds",
    "copy_scaffolds",
    "scaffold_note",
]

LTR = "ltr"
RTL = "rtl"
TEXT_DIRECTIONS = (LTR, RTL)

#: Bounded scaffold vocabulary. A kind names the *aid* (romaji, furigana, an English gloss, a
#: transliteration, vowel diacritics, pinyin, a script guide), never a learner trait.
SCAFFOLD_KINDS = (
    "romaji",
    "furigana",
    "gloss",
    "transliteration",
    "diacritics",
    "pinyin",
    "script_guide",
)

#: The scripts a scaffold item may name. Bounded so an author cannot smuggle a free-text script
#: claim into a learner-facing check.
SCAFFOLD_SCRIPTS = (
    "latin",
    "kana",
    "kanji",
    "han",
    "hangul",
    "arabic",
    "cyrillic",
    "devanagari",
)

#: The pre-H-18 fixed triple, still accepted on read. ``english_meaning`` is the legacy spelling
#: of the open ``gloss`` kind.
LEGACY_SCAFFOLD_KEYS = {
    "romaji": "romaji",
    "furigana": "furigana",
    "english_meaning": "gloss",
}

#: Primary language subtags whose script runs right-to-left. This is a property of the writing
#: system, not a judgment about the learner.
RTL_PRIMARY_LANGUAGES = frozenset(
    {"ar", "arc", "dv", "fa", "he", "ku", "ps", "sd", "ug", "ur", "yi"}
)

#: Declared levels that count as beginner. L0/L1 are Coursebook's declared learner levels;
#: A1/A2/BEGINNER are the CEFR-equivalent beginner labels already used by the v10 brief.
BEGINNER_LEVELS = frozenset({"L0", "L1", "A1", "A2", "BEGINNER"})

#: Locale-keyed, level-keyed mandate table. The Japanese L0/L1 rule is the explicit one the
#: scaffold contract has always meant: romaji, furigana and an English meaning. Arabic beginner
#: material carries vowel diacritics (harakat). French has no mandated scaffold: a French course
#: is never asked to declare romaji or furigana.
SCAFFOLD_RULES: dict[str, dict[str, Any]] = {
    "ja": {"levels": BEGINNER_LEVELS, "kinds": ("romaji", "furigana", "gloss")},
    "zh": {"levels": BEGINNER_LEVELS, "kinds": ("pinyin", "gloss")},
    "ar": {"levels": BEGINNER_LEVELS, "kinds": ("diacritics",)},
}


class ScaffoldError(ValueError):
    """A scaffold value is not in the bounded vocabulary or names an unknown field."""


def primary_language(locale: Any) -> str:
    """The lowercase primary subtag of a BCP-47-ish locale (``ja-JP`` -> ``ja``)."""
    text = str(locale or "").strip()
    if not text:
        return ""
    return text.split("-")[0].split("_")[0].lower()


def normalize_locale(locale: Any) -> str | None:
    """A bounded text language tag, or ``None`` when the brief declared none.

    The tag is kept verbatim (minus surrounding whitespace) so ``pt-BR`` and ``pt-BR`` hash the
    same while remaining readable in the document. Direction is derived from the primary subtag.
    """
    text = str(locale or "").strip()
    if not text or len(text) > 35:
        return None
    return text


def direction_for_locale(locale: Any) -> str | None:
    """``rtl`` for a right-to-left script, ``ltr`` for a known locale, ``None`` when unknown.

    ``None`` matters: a document projected from a page that never recorded its locale must not
    claim a direction it was never told. Old pages therefore keep their bytes and gain no field.
    """
    primary = primary_language(locale)
    if not primary:
        return None
    return RTL if primary in RTL_PRIMARY_LANGUAGES else LTR


def scaffold_requirements(locale: Any, dials: Mapping[str, Any] | None) -> dict[str, bool]:
    """The scaffold kinds this locale/level mandates, as ``{kind: True}``.

    Only mandated kinds appear. An empty result means "declare nothing"; it does not mean
    "declare the Japanese triple as false".
    """
    primary = primary_language(locale)
    if not primary:
        return {}
    level = str((dials or {}).get("level") or "").upper()
    required: dict[str, bool] = {}
    rule = SCAFFOLD_RULES.get(primary)
    if rule is not None and level in rule["levels"]:
        required.update({kind: True for kind in rule["kinds"]})
    # A brief may still ask for romaji explicitly regardless of level; that is the one override
    # the old policy had and it stays additive rather than turning into a second rule engine.
    if primary == "ja" and (dials or {}).get("romaji") is True:
        required["romaji"] = True
    return required


def _normalize_item(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ScaffoldError(f"scaffolds[{index}] is not an object")
    unknown = set(raw) - {"kind", "script", "gloss", "direction"}
    if unknown:
        raise ScaffoldError(
            f"scaffolds[{index}] has unknown field(s): {', '.join(sorted(unknown))}"
        )
    kind = str(raw.get("kind") or "")
    if kind not in SCAFFOLD_KINDS:
        raise ScaffoldError(
            f"scaffolds[{index}].kind {kind!r} is not one of {', '.join(SCAFFOLD_KINDS)}"
        )
    item: dict[str, Any] = {"kind": kind}
    if raw.get("script") is not None:
        script = str(raw.get("script"))
        if script not in SCAFFOLD_SCRIPTS:
            raise ScaffoldError(
                f"scaffolds[{index}].script {script!r} is not one of "
                f"{', '.join(SCAFFOLD_SCRIPTS)}"
            )
        item["script"] = script
    if raw.get("gloss") is not None:
        gloss = normalize_locale(raw.get("gloss"))
        if gloss is None:
            raise ScaffoldError(f"scaffolds[{index}].gloss is not a bounded language tag")
        item["gloss"] = gloss
    if raw.get("direction") is not None:
        direction = str(raw.get("direction"))
        if direction not in TEXT_DIRECTIONS:
            raise ScaffoldError(
                f"scaffolds[{index}].direction {direction!r} is not one of ltr, rtl"
            )
        item["direction"] = direction
    return item


def normalize_scaffolds(raw: Any) -> list[dict[str, Any]]:
    """Read either authored shape into the open list form.

    * ``None`` / ``{}`` -> ``[]`` (nothing declared)
    * legacy triple object -> one item per true flag, ``english_meaning`` -> ``gloss``
    * open list -> validated items

    Raises :class:`ScaffoldError` for an unknown field, kind, script or direction. The JSON
    schema already rejects those for a model response; this is the same bounded vocabulary for
    page data and for callers that build a lesson in code.
    """
    if raw is None or raw == {}:
        return []
    if isinstance(raw, Mapping):
        unknown = set(raw) - set(LEGACY_SCAFFOLD_KEYS)
        if unknown:
            raise ScaffoldError(
                "scaffolds has unknown field(s): " + ", ".join(sorted(str(k) for k in unknown))
            )
        items: list[dict[str, Any]] = []
        for key, value in raw.items():
            if not isinstance(value, bool):
                raise ScaffoldError(f"scaffolds.{key} must be a boolean")
            if value:
                items.append({"kind": LEGACY_SCAFFOLD_KEYS[key]})
        return items
    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
        items = [_normalize_item(entry, index) for index, entry in enumerate(raw)]
        seen: set[str] = set()
        for item in items:
            if item["kind"] in seen:
                raise ScaffoldError(f"scaffolds repeats kind {item['kind']!r}")
            seen.add(item["kind"])
        return items
    raise ScaffoldError("scaffolds must be an object or an array")


def declared_scaffold_kinds(raw: Any) -> set[str]:
    """The set of scaffold kinds an authored value declares."""
    return {item["kind"] for item in normalize_scaffolds(raw)}


def copy_scaffolds(raw: Any) -> list[dict[str, Any]]:
    """A page-safe copy in the open form; legacy triples are preserved as the open list."""
    return [dict(item) for item in normalize_scaffolds(raw)]


def scaffold_note(requirements: Mapping[str, bool], locale: Any) -> str:
    """The one sentence a lesson prompt gets about mandated scaffolds and text direction."""
    kinds = [kind.replace("_", " ") for kind, needed in sorted(requirements.items()) if needed]
    direction = direction_for_locale(locale)
    parts: list[str] = []
    if kinds:
        parts.append(
            "Task-mandated scaffolds for this learner: "
            + ", ".join(kinds)
            + ". Declare exactly these kinds in check.scaffolds as [{kind, script?, gloss?, "
            "direction?}] and never treat a scaffold as unaided-skill evidence."
        )
    if direction == RTL:
        parts.append(
            "This locale reads right-to-left: order the lesson text for an rtl reader; the "
            "document records direction and lang so every view renders it the same way."
        )
    return " ".join(parts)
