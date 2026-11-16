"""The world quality critic: a separate stage after every *generated* plate.

The generator asks for a textless place; the critic is what decides whether it got one. It is not
the generator, it is not the user, and it is not the UI (``docs/launch/GAME-MODE-VISUAL-KIT.md`` §6,
``docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md`` §10C.5).

Two independent passes, both of which must answer before a plate can be admitted:

* **OCR** — any readable letter, number, word, logo, watermark or UI chrome is a hard fail. The
  rule is the kit's own calibrated one (``kit.json`` ``ocr_policy``): a token of three or more
  alphanumeric characters at 60 % confidence or better. The host pass shells out to ``tesseract``
  when it is installed; a host without it has no OCR pass, which is *not* a pass.
* **Vision** — subject-swap, grammar mismatch, a generic fantasy skin, a depicted procedure or
  measurement presented as authority, and a plate with no quiet field for the headline are hard
  fails. The vision verdict is supplied by a host seam; the backend has no local vision model, so
  a host that cannot answer has no vision pass.

A seam that cannot answer makes the **generated path unavailable** rather than admitted: an
uncertified plate is never stored as ``textless`` on the strength of its prompt. The world job then
uses the curated kit role, which was approved once by the owner and is not re-critiqued per course.

Both seams are injectable (``bind``) so the tests prove the refusal rules against deterministic
answers; neither seam is ever called inside a database transaction.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

#: The closed vocabulary of hard fails. A seam that names anything else is refused as unavailable,
#: never accepted: a typo in a review answer must not become a pass.
SUBJECT_SWAP = "subject_swap"
GRAMMAR_MISMATCH = "grammar_mismatch"
GENERIC_FANTASY_SKIN = "generic_fantasy_skin"
AUTHORITY_PROCEDURE = "authority_procedure_or_measurement"
NO_QUIET_FIELD = "no_quiet_field"
OCR_READABLE_TEXT = "ocr_readable_text"
SCORE_BELOW_MINIMUM = "score_below_minimum"

#: Reasons a seam may return for a *generated* plate that must be refused.
HARD_FAIL_REASONS: frozenset[str] = frozenset(
    {
        SUBJECT_SWAP,
        GRAMMAR_MISMATCH,
        GENERIC_FANTASY_SKIN,
        AUTHORITY_PROCEDURE,
        NO_QUIET_FIELD,
        OCR_READABLE_TEXT,
        SCORE_BELOW_MINIMUM,
    }
)

#: ``critic_unavailable:<pass>`` — the generated path is unavailable for this plate.
UNAVAILABLE_PREFIX = "critic_unavailable"

#: The rubric floor every scored dimension must reach (``VISUAL-QUALITY-PROGRAM`` §4 Gate 4,
#: ``GAME-MODE-AND-TUTOR-RAIL-PLAN`` §10C.3). A score that is supplied and below this refuses the
#: plate; a seam that supplies no scores is not credited with one.
MIN_SCORE = 4.0

#: The kit's calibrated OCR rule (``kit.json`` ``ocr_policy.fail_rule``).
OCR_MIN_CHARACTERS = 3
OCR_MIN_CONFIDENCE = 60.0

#: A host OCR pass is bounded I/O, run outside every transaction.
OCR_TIMEOUT_S = 20.0


@dataclass(frozen=True)
class OcrToken:
    text: str
    confidence: float


@dataclass(frozen=True)
class CriticVerdict:
    """One plate's verdict. ``passed`` is true only when both passes answered and neither failed."""

    passed: bool
    reasons: tuple[str, ...] = ()
    scores: Mapping[str, float] = field(default_factory=dict)
    unavailable: tuple[str, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.unavailable:
            return "unavailable"
        return "passed" if self.passed else "failed"

    def as_provenance(self) -> dict[str, Any]:
        """What the artifact records. It never says "verified"; it states the verdict and its basis."""
        return {
            "passed": bool(self.passed),
            "approved": bool(self.passed),
            "status": self.status,
            "reasons": list(self.reasons),
            "unavailable": list(self.unavailable),
            "scores": {str(key): float(value) for key, value in self.scores.items()},
            "min_score": MIN_SCORE,
            "evidence": dict(self.evidence),
            "reviewed_by": "world_critic",
        }


# ── seams ───────────────────────────────────────────────────────────────────

#: Raised/bound to mean "this host has no such pass". ``None`` means "ask the host".
class Unavailable:
    """A seam explicitly bound as absent. Distinct from ``None`` (the host default)."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<critic pass unavailable>"


UNAVAILABLE = Unavailable()

_OCR: Any = None
_VISION: Any = None


def bind_ocr(seam: Any) -> None:
    global _OCR
    _OCR = seam


def bind_vision(seam: Any) -> None:
    global _VISION
    _VISION = seam


def bind(*, ocr: Any = None, vision: Any = None) -> None:
    """Bind both passes. ``None`` restores the host default; :data:`UNAVAILABLE` removes it."""
    bind_ocr(ocr)
    bind_vision(vision)


def reset() -> None:
    bind_ocr(None)
    bind_vision(None)


# ── OCR pass ────────────────────────────────────────────────────────────────


def ocr_tokens(data: bytes, mime: str = "image/png") -> tuple[OcrToken, ...] | None:
    """Every token the OCR pass could read, or ``None`` when this host has no OCR pass."""
    seam = _OCR if _OCR is not None else _host_ocr
    if seam is UNAVAILABLE or not callable(seam):
        return None
    result: Any = seam(data, mime)
    if result is None:
        return None
    tokens: list[OcrToken] = []
    for item in result:
        token = _as_token(item)
        if token is not None:
            tokens.append(token)
    return tuple(tokens)


def _as_token(item: Any) -> OcrToken | None:
    if isinstance(item, OcrToken):
        return item
    if isinstance(item, Mapping):
        text = str(item.get("text") or "")
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            return None
        return OcrToken(text=text, confidence=confidence)
    if isinstance(item, (tuple, list)) and len(item) == 2:
        try:
            return OcrToken(text=str(item[0]), confidence=float(item[1]))
        except (TypeError, ValueError):
            return None
    return None


def readable_text(tokens: Sequence[OcrToken]) -> tuple[OcrToken, ...]:
    """The tokens that break the textless rule, in reading order."""
    return tuple(
        token
        for token in tokens
        if token.confidence >= OCR_MIN_CONFIDENCE
        and sum(1 for char in token.text if char.isalnum()) >= OCR_MIN_CHARACTERS
    )


def _host_ocr(data: bytes, mime: str) -> Sequence[OcrToken] | None:
    """The calibrated tesseract pass, or ``None`` when this host cannot run it."""
    binary = shutil.which("tesseract")
    if not binary:
        return None
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, bounded timeout
            [binary, "stdin", "stdout", "tsv"],
            input=data,
            capture_output=True,
            timeout=OCR_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    text = completed.stdout.decode("utf-8", "replace")
    tokens: list[OcrToken] = []
    for line in text.splitlines()[1:]:
        cells = line.split("\t")
        if len(cells) < 12:
            continue
        word = cells[11].strip()
        if not word:
            continue
        try:
            confidence = float(cells[10])
        except ValueError:
            continue
        tokens.append(OcrToken(text=word, confidence=confidence))
    return tuple(tokens)


# ── vision pass ─────────────────────────────────────────────────────────────


def vision_verdict(
    data: bytes, *, context: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    """The host vision review, or ``None`` when this host has no vision pass."""
    seam = _VISION if _VISION is not None else UNAVAILABLE
    if seam is UNAVAILABLE or not callable(seam):
        return None
    result = seam(data, context)
    if result is None:
        return None
    if not isinstance(result, Mapping):
        return {"hard_fails": ["<invalid>"]}
    return result


def available() -> bool:
    """Whether this host can run **both** passes. A host with one pass has no critic."""
    ocr_ok = _OCR is not UNAVAILABLE and (_OCR is not None or shutil.which("tesseract") is not None)
    vision_ok = _VISION is not UNAVAILABLE and _VISION is not None
    return bool(ocr_ok and vision_ok)


# ── the one entry point ─────────────────────────────────────────────────────


def critique(
    data: bytes,
    *,
    prompt: Any,
    brief: Any,
    grammar: str,
    role: str,
    mime: str = "image/png",
) -> CriticVerdict:
    """Run both passes on one generated plate and return the verdict.

    Pure with respect to the database: no row is written here. The caller records the verdict on
    the artifact it is about to store, so a refused plate cannot reach ``world_assets``.
    """
    evidence: dict[str, Any] = {}
    unavailable: list[str] = []
    reasons: list[str] = []
    scores: dict[str, float] = {}

    tokens = ocr_tokens(data, mime)
    if tokens is None:
        unavailable.append(f"{UNAVAILABLE_PREFIX}:ocr")
    else:
        flagged = readable_text(tokens)
        evidence["ocr"] = {
            "tokens": [
                {"text": token.text, "confidence": round(token.confidence, 2)} for token in tokens
            ],
            "readable": [
                {"text": token.text, "confidence": round(token.confidence, 2)} for token in flagged
            ],
            "rule": {
                "min_characters": OCR_MIN_CHARACTERS,
                "min_confidence": OCR_MIN_CONFIDENCE,
            },
        }
        if flagged:
            reasons.append(OCR_READABLE_TEXT)

    review = vision_verdict(data, context=_vision_context(prompt, brief, grammar, role))
    if review is None:
        unavailable.append(f"{UNAVAILABLE_PREFIX}:vision")
    else:
        named = review.get("hard_fails") or ()
        if isinstance(named, str) or not isinstance(named, Sequence):
            unavailable.append(f"{UNAVAILABLE_PREFIX}:vision_invalid")
        else:
            unknown = [str(item) for item in named if str(item) not in HARD_FAIL_REASONS]
            if unknown:
                # A review answer the critic cannot interpret is not a pass.
                unavailable.append(f"{UNAVAILABLE_PREFIX}:vision_invalid")
                evidence["vision_invalid"] = unknown
            else:
                reasons.extend(sorted({str(item) for item in named}))
        raw_scores = review.get("scores") or {}
        if isinstance(raw_scores, Mapping):
            for key, value in raw_scores.items():
                try:
                    scores[str(key)] = float(value)
                except (TypeError, ValueError):
                    continue
        evidence["vision"] = {
            "hard_fails": sorted({str(item) for item in (review.get("hard_fails") or ())}),
            "reviewed_by": str(review.get("reviewed_by") or "host_vision"),
            "notes": str(review.get("notes") or ""),
        }
        below = sorted(key for key, value in scores.items() if value < MIN_SCORE)
        if below:
            reasons.append(SCORE_BELOW_MINIMUM)
            evidence["below_minimum"] = below

    return CriticVerdict(
        passed=not unavailable and not reasons,
        reasons=tuple(sorted(set(reasons))),
        scores=scores,
        unavailable=tuple(unavailable),
        evidence=evidence,
    )


def _vision_context(prompt: Any, brief: Any, grammar: str, role: str) -> dict[str, Any]:
    """What the reviewer is allowed to see: the request, never a check, key or attempt."""
    return {
        "grammar": str(grammar),
        "role": str(role),
        "prompt": str(getattr(prompt, "prompt", "")),
        "negative_prompt": str(getattr(prompt, "negative_prompt", "")),
        "motifs": list(getattr(brief, "motifs", ()) or ()),
        "subject_domain": str(getattr(brief, "subject_domain", "")),
        "end_capability": str(getattr(brief, "end_capability", "")),
        "safety_class": str(getattr(brief, "safety_class", "")),
        "illustration_role": _illustration_role(grammar),
        "hard_checks": [
            "subject_swap",
            "grammar_mismatch",
            "generic_fantasy_skin",
            "authority_procedure_or_measurement",
            "no_quiet_field",
        ],
    }


def _illustration_role(grammar: str) -> str:
    from .world import grammar_record

    try:
        return grammar_record(grammar).illustration_role
    except Exception:  # noqa: BLE001 - an unknown grammar is not this module's refusal
        return "orientation only"


__all__ = [
    "AUTHORITY_PROCEDURE",
    "CriticVerdict",
    "GENERIC_FANTASY_SKIN",
    "GRAMMAR_MISMATCH",
    "HARD_FAIL_REASONS",
    "MIN_SCORE",
    "NO_QUIET_FIELD",
    "OCR_MIN_CHARACTERS",
    "OCR_MIN_CONFIDENCE",
    "OCR_READABLE_TEXT",
    "OcrToken",
    "SCORE_BELOW_MINIMUM",
    "SUBJECT_SWAP",
    "UNAVAILABLE",
    "UNAVAILABLE_PREFIX",
    "available",
    "bind",
    "bind_ocr",
    "bind_vision",
    "critique",
    "ocr_tokens",
    "readable_text",
    "reset",
    "vision_verdict",
]
