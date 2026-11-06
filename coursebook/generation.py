"""Governed course generation with an independent validation pass.

Coursebook's promise is that a goal becomes a *validated* course, not a confident paragraph. This
module is the whole authoring pipeline and it is built around one rule: **the model that writes an
artifact never certifies it** (``PREBUILD_SPEC.md`` §8–§9, ``AUDIT.md`` R7/R10).

Three passes, three different bounded calls and three different schemas:

``plan``        goal + bounded research + recipe/dials -> strict JSON plan (4–8 objectives,
                ordered sections, check plan, time estimate with an honest ``basis``).
``validate``    a *separate* system prompt and schema re-reads the plan (or lesson) with the
                source ledger and returns per-criterion verdicts and explicit rejections.
``lesson``      for an approved plan only: one durable page per section with teaching segments,
                a worked example, one check, and a reference answer/rubric stored separately.

Rules this module will not bend:

* provider calls never run inside a DB transaction; writes are short ``BEGIN IMMEDIATE`` blocks
  after the result exists (``PREBUILD_SPEC.md`` §6);
* nothing is marked approved here — approval is the learner's/parent's command
  (``plan.approve``), and a plan produced here stays ``draft``;
* reference answers and rubrics never enter a learner-facing payload;
* a validator can reject; a rejected item regenerates **once** with the validator's reasons, and a
  second failure marks the lesson ``needs_review`` with no learner-facing check enabled;
* unsupported or absent research downgrades claims to ``unverified`` and says so — it never
  fabricates a citation;
* retries are idempotent per request fingerprint / ``plan_hash`` / section / version.

The LLM seam is the host-owned plugin route (``ctx.llm``), not a raw provider key. See
``docs/GENERATION.md`` for why the job runner — not the dashboard backend — is the caller.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Sequence

from jsonschema import Draft202012Validator

from . import research as research_mod
from .research import (
    ResearchBudget,
    ResearchRun,
    SearchSeam,
    SourceRecord,
    apply_support_verdicts,
    canonical_json,
    run_research,
    sha256_of_text,
    support_status_for_contract,
)

__all__ = [
    "GenerationRejected",
    "PlanNotApproved",
    "ProviderTimeout",
    "ProviderFailure",
    "CostCeilingExceeded",
    "LessonNotAvailable",
    "LLMRequest",
    "LLMResponse",
    "CostBudget",
    "PluginLLMAdapter",
    "bind_host_llm",
    "host_llm",
    "PLAN_SCHEMA",
    "LESSON_SCHEMA",
    "VALIDATION_SCHEMA",
    "PLAN_PROMPT_VERSION",
    "LESSON_PROMPT_VERSION",
    "VALIDATION_PROMPT_VERSION",
    "VALIDATION_CRITERIA",
    "run_plan_job",
    "run_lesson_job",
    "learner_page",
    "ensure_schema",
    "plan_document",
]

#: Bumped when the shape of a plan/lesson/validation artifact changes. Part of every idempotency
#: fingerprint, so an old result is never silently reused under new rules.
PIPELINE_VERSION = "cb.gen.v1"

PLAN_PROMPT_VERSION = "plan-prompt.v1"
LESSON_PROMPT_VERSION = "lesson-prompt.v1"
VALIDATION_PROMPT_VERSION = "validation-prompt.v1"

#: The ten checks the independent pass owes the pipeline. A validation that omits any of them is
#: malformed output, not a pass.
VALIDATION_CRITERIA: tuple[str, ...] = (
    "objective_alignment",
    "source_support",
    "factual_correctness",
    "answer_uniqueness",
    "alternative_coverage",
    "rubric_consistency",
    "internal_contradiction",
    "answer_leakage",
    "hazard_age_appropriateness",
    "evidence_target_fit",
)

RECIPES = ("one_off", "casual", "committed", "companion", "parent")
EVIDENCE_TARGETS = ("recall", "comprehension", "production", "discrimination", "procedure", "transfer")
SUPPORT_VALUES = ("sourced", "unverified")

MAX_PLAN_BYTES = 48 * 1024
MAX_LESSON_BYTES = 64 * 1024
MAX_VALIDATION_BYTES = 24 * 1024


# ── Errors ──────────────────────────────────────────────────────────────────


class GenerationError(RuntimeError):
    """Base class for honest pipeline failures. Nothing is persisted on these paths."""


class GenerationRejected(GenerationError):
    """Provider output was malformed, empty, oversized, or violated a hard rule."""


class PlanNotApproved(GenerationError):
    """Lesson authoring was requested for a plan the learner/parent has not approved."""


class ProviderTimeout(GenerationError):
    """The provider call did not finish inside its declared deadline."""


class ProviderFailure(GenerationError):
    """The provider call raised. Retry is the job service's decision, not this module's."""


class CostCeilingExceeded(GenerationError):
    """A declared spend ceiling would be exceeded. Future calls are refused; spend is recorded."""


class LessonNotAvailable(GenerationError):
    """A lesson exists but is not servable to a learner (e.g. ``needs_review``)."""


class _RuleViolation(GenerationError):
    """The generator broke a deterministic rule (recipe, scaffolding, answer leakage)."""

    def __init__(self, reasons: Sequence[str]) -> None:
        self.reasons = [str(r) for r in reasons]
        super().__init__("; ".join(self.reasons) or "generation rule violated")


# ── LLM seam ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LLMRequest:
    """One bounded structured call. The pipeline never sends anything else."""

    purpose: str
    prompt_version: str
    system_prompt: str
    instructions: str
    input_text: str
    schema: dict[str, Any]
    schema_name: str
    max_tokens: int
    timeout_s: float
    temperature: float = 0.0


@dataclass
class LLMResponse:
    """Provider result, already split into parsed/text/usage.

    ``parsed`` may be ``None`` when the host could not parse JSON; the pipeline then decides. Usage
    fields that the host did not supply stay ``None`` — they are recorded as unknown, never as 0.
    """

    text: str = ""
    parsed: dict[str, Any] | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


LLM = Callable[[LLMRequest], LLMResponse]


@dataclass
class CostBudget:
    """Honest ceilings for one job. Unknown cost is tracked, not guessed."""

    max_calls: int = 8
    max_cost_usd: float | None = 0.75


@dataclass
class _Usage:
    budget: CostBudget
    calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    known_cost: float = 0.0
    unknown_cost: bool = False

    def before_call(self, request: LLMRequest) -> None:
        if len(self.calls) >= self.budget.max_calls:
            raise CostCeilingExceeded(
                f"job already made {len(self.calls)} provider calls (ceiling {self.budget.max_calls})"
            )
        if self.budget.max_cost_usd is not None and self.known_cost >= self.budget.max_cost_usd:
            raise CostCeilingExceeded(
                f"known spend {self.known_cost:.4f} USD already reaches the "
                f"{self.budget.max_cost_usd:.4f} USD ceiling"
            )

    def record(self, request: LLMRequest, response: LLMResponse, duration_ms: int) -> None:
        cost = response.cost_usd
        self.unknown_cost = self.unknown_cost or cost is None
        self.known_cost += float(cost or 0.0)
        self.input_tokens += int(response.input_tokens or 0)
        self.output_tokens += int(response.output_tokens or 0)
        self.calls.append(
            {
                "purpose": request.purpose,
                "prompt_version": request.prompt_version,
                "provider": response.provider,
                "model": response.model,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": cost,
                "duration_ms": duration_ms,
            }
        )
        if self.budget.max_cost_usd is not None and self.known_cost > self.budget.max_cost_usd:
            raise CostCeilingExceeded(
                f"known spend {self.known_cost:.4f} USD exceeded the "
                f"{self.budget.max_cost_usd:.4f} USD ceiling"
            )

    def summary(self) -> dict[str, Any]:
        return {
            "calls": len(self.calls),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": None if self.unknown_cost and self.known_cost == 0 else self.known_cost,
            "unknown_cost": self.unknown_cost,
        }


class PluginLLMAdapter:
    """Production adapter over the host's ``ctx.llm`` (``PluginLlm``).

    This is the only sanctioned route: host-owned credentials, per-plugin trust gate, no key in
    the plugin. It is a plain callable, so tests inject a fake with the same signature.
    """

    def __init__(self, plugin_llm: Any) -> None:
        if not callable(getattr(plugin_llm, "complete_structured", None)):
            raise TypeError("ctx.llm does not expose complete_structured; refusing to bypass trust")
        self._llm = plugin_llm

    @classmethod
    def from_ctx(cls, ctx: Any) -> "PluginLLMAdapter":
        llm = getattr(ctx, "llm", None)
        if llm is None:
            raise TypeError("host context has no ctx.llm; Coursebook will not call a raw provider")
        return cls(llm)

    def __call__(self, request: LLMRequest) -> LLMResponse:
        result = self._llm.complete_structured(
            instructions=request.instructions,
            input=[{"type": "text", "text": request.input_text}],
            json_schema=request.schema,
            schema_name=request.schema_name,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            timeout=request.timeout_s,
            purpose=request.purpose,
        )
        usage = getattr(result, "usage", None)
        return LLMResponse(
            text=str(getattr(result, "text", "") or ""),
            parsed=getattr(result, "parsed", None),
            provider=getattr(result, "provider", None),
            model=getattr(result, "model", None),
            input_tokens=_attr_int(usage, "input_tokens"),
            output_tokens=_attr_int(usage, "output_tokens"),
            cost_usd=_attr_float(usage, "cost_usd"),
        )


#: Bound by the agent half's ``register(ctx)`` — the job runner calls into this process.
_HOST_LLM: Any = None


def bind_host_llm(plugin_llm: Any) -> None:
    """Bind the host-owned LLM for job-runner use. Called from the agent half only."""
    global _HOST_LLM
    _HOST_LLM = plugin_llm


def host_llm() -> LLM:
    """Return the bound adapter, or fail loudly. Never falls back to a raw provider."""
    if _HOST_LLM is None:
        raise GenerationRejected(
            "no host LLM bound: call coursebook.generation.bind_host_llm(ctx.llm) from register(ctx)"
        )
    return PluginLLMAdapter(_HOST_LLM)


def _call_llm(llm: LLM, request: LLMRequest, usage: _Usage) -> LLMResponse:
    usage.before_call(request)
    started = time.monotonic()
    try:
        response = llm(request)
    except (TimeoutError,) as exc:
        raise ProviderTimeout(f"{request.purpose} timed out: {exc}") from exc
    except GenerationError:
        raise
    except Exception as exc:  # noqa: BLE001 - provider bug becomes a typed failure
        raise ProviderFailure(f"{request.purpose} failed: {type(exc).__name__}: {exc}") from exc
    duration_ms = int((time.monotonic() - started) * 1000)
    if duration_ms > int(request.timeout_s * 1000):
        raise ProviderTimeout(f"{request.purpose} took {duration_ms}ms, over its {request.timeout_s}s deadline")
    if not isinstance(response, LLMResponse):
        raise GenerationRejected(f"{request.purpose} returned {type(response).__name__}, not LLMResponse")
    usage.record(request, response, duration_ms)
    return response


# ── Strict schemas ──────────────────────────────────────────────────────────

_short = {"type": "string", "minLength": 1, "maxLength": 200}
_text = {"type": "string", "minLength": 5, "maxLength": 1200}
_identifier = {"type": "string", "minLength": 4, "maxLength": 64}

OBJECTIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ordinal", "title", "evidence_target", "evidence_criteria", "support"],
    "properties": {
        "ordinal": {"type": "integer", "minimum": 1, "maximum": 8},
        "title": {"type": "string", "minLength": 3, "maxLength": 200},
        "evidence_target": {"type": "string", "enum": list(EVIDENCE_TARGETS)},
        "evidence_criteria": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {"type": "string", "minLength": 5, "maxLength": 300},
        },
        "support": {"type": "string", "enum": list(SUPPORT_VALUES)},
        "source_ids": {"type": "array", "maxItems": 8, "items": _identifier},
    },
}

SECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ordinal", "title", "lesson_intent", "objective_refs", "context_needs"],
    "properties": {
        "ordinal": {"type": "integer", "minimum": 1, "maximum": 8},
        "title": {"type": "string", "minLength": 3, "maxLength": 200},
        "lesson_intent": {"type": "string", "minLength": 10, "maxLength": 400},
        "objective_refs": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {"type": "integer", "minimum": 1, "maximum": 8},
        },
        "context_needs": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 120}},
        "source_ids": {"type": "array", "maxItems": 6, "items": _identifier},
    },
}

CHECK_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["objective_ref", "kind", "evidence_target", "count", "independent_evidence"],
    "properties": {
        "objective_ref": {"type": "integer", "minimum": 1, "maximum": 8},
        "kind": {"type": "string", "enum": ["quiz", "verification", "observation"]},
        "evidence_target": {"type": "string", "enum": list(EVIDENCE_TARGETS)},
        "count": {"type": "integer", "minimum": 1, "maximum": 4},
        "independent_evidence": {"type": "boolean"},
        "notes": {"type": "string", "maxLength": 300},
    },
}

TIME_ESTIMATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "sessions_per_week",
        "minutes_per_session",
        "weeks",
        "basis",
        "confidence",
        "rationale",
    ],
    "properties": {
        "sessions_per_week": {"type": "integer", "minimum": 1, "maximum": 14},
        "minutes_per_session": {"type": "integer", "minimum": 5, "maximum": 240},
        "weeks": {"type": "integer", "minimum": 1, "maximum": 104},
        "basis": {"type": "string", "enum": ["fsi", "derived", "model", "none"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "rationale": {"type": "string", "minLength": 10, "maxLength": 600},
        "benchmark": {"type": ["string", "null"], "maxLength": 400},
        "attainment_hours": {
            "type": ["array", "null"],
            "minItems": 2,
            "maxItems": 2,
            "items": {"type": "number", "minimum": 0, "maximum": 10000},
        },
    },
}

PARENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["age_band", "reading_level", "supervision_notes", "hazards", "setting_materials"],
    "properties": {
        "age_band": {"type": "string", "enum": ["3-5", "6-8", "9-11", "12-14", "15-18"]},
        "reading_level": {"type": "string", "minLength": 2, "maxLength": 40},
        "supervision_notes": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {"type": "string", "minLength": 5, "maxLength": 300},
        },
        "hazards": {"type": "array", "maxItems": 10, "items": {"type": "string", "minLength": 5, "maxLength": 300}},
        "setting_materials": {
            "type": "array",
            "maxItems": 10,
            "items": {"type": "string", "minLength": 2, "maxLength": 200},
        },
        "parent_facing_summary": {"type": "string", "maxLength": 600},
    },
}

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "title",
        "learner_outcome",
        "delivery",
        "time_estimate",
        "objectives",
        "sections",
        "check_plan",
        "context_needs",
        "source_ids",
        "exclusions",
        "spaced_review",
    ],
    "properties": {
        "title": {"type": "string", "minLength": 3, "maxLength": 200},
        "learner_outcome": {"type": "string", "minLength": 10, "maxLength": 600},
        "delivery": {"type": "string", "enum": ["self_study", "parent_led", "instructor_led"]},
        "time_estimate": TIME_ESTIMATE_SCHEMA,
        "objectives": {"type": "array", "minItems": 4, "maxItems": 8, "items": OBJECTIVE_SCHEMA},
        "sections": {"type": "array", "minItems": 2, "maxItems": 8, "items": SECTION_SCHEMA},
        "check_plan": {"type": "array", "minItems": 1, "maxItems": 16, "items": CHECK_PLAN_SCHEMA},
        "context_needs": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {"type": "string", "minLength": 2, "maxLength": 120},
        },
        "source_ids": {"type": "array", "maxItems": 12, "items": _identifier},
        "exclusions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {"type": "string", "minLength": 3, "maxLength": 300},
        },
        "spaced_review": {"type": "boolean"},
        "evidence_note": {"type": ["string", "null"], "maxLength": 400},
        "parent": PARENT_SCHEMA,
    },
}

LESSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "section_title",
        "segments",
        "worked_example",
        "learner_explanation",
        "check",
        "sources",
        "media",
    ],
    "properties": {
        "section_title": {"type": "string", "minLength": 3, "maxLength": 200},
        "segments": {
            "type": "array",
            "minItems": 2,
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "heading", "body"],
                "properties": {
                    "kind": {"type": "string", "enum": ["model", "explain", "guided", "retrieval"]},
                    "heading": {"type": "string", "minLength": 1, "maxLength": 120},
                    "body": {"type": "string", "minLength": 10, "maxLength": 2000},
                },
            },
        },
        "worked_example": {
            "type": "object",
            "additionalProperties": False,
            "required": ["prompt", "steps", "answer"],
            "properties": {
                "prompt": {"type": "string", "minLength": 3, "maxLength": 500},
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 8,
                    "items": {"type": "string", "minLength": 3, "maxLength": 500},
                },
                "answer": {"type": "string", "minLength": 1, "maxLength": 500},
            },
        },
        "learner_explanation": {"type": "string", "minLength": 10, "maxLength": 1500},
        "check": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "kind",
                "stimulus",
                "learner_instructions",
                "evidence_target",
                "accepted_answers",
                "rubric",
                "reference_answer",
                "assistance_policy",
                "scaffolds",
            ],
            "properties": {
                "kind": {"type": "string", "enum": ["quiz", "verification", "observation"]},
                "stimulus": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["prompt", "format"],
                    "properties": {
                        "prompt": {"type": "string", "minLength": 3, "maxLength": 800},
                        "format": {"type": "string", "enum": ["text", "selection", "verification"]},
                        "choices": {
                            "type": "array",
                            "maxItems": 8,
                            "items": {"type": "string", "minLength": 1, "maxLength": 200},
                        },
                    },
                },
                "learner_instructions": {"type": "string", "minLength": 3, "maxLength": 400},
                "evidence_target": {"type": "string", "enum": list(EVIDENCE_TARGETS)},
                "accepted_answers": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 10,
                    "items": {"type": "string", "minLength": 1, "maxLength": 300},
                },
                "accepted_alternatives": {
                    "type": "array",
                    "maxItems": 10,
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 6,
                        "items": {"type": "string", "minLength": 1, "maxLength": 300},
                    },
                },
                "rubric": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 6,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["criterion", "weight", "description"],
                        "properties": {
                            "criterion": {"type": "string", "minLength": 2, "maxLength": 120},
                            "weight": {"type": "number", "minimum": 0, "maximum": 1},
                            "description": {"type": "string", "minLength": 3, "maxLength": 300},
                        },
                    },
                },
                "reference_answer": {"type": "string", "minLength": 1, "maxLength": 600},
                "assistance_policy": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["hint", "answer_marks_evidence_class"],
                    "properties": {
                        "hint": {"type": "string", "enum": ["available", "after_attempt", "none"]},
                        "answer_marks_evidence_class": {
                            "type": "string",
                            "enum": ["answer_shown", "hinted", "none"],
                        },
                    },
                },
                "scaffolds": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["romaji", "furigana", "english_meaning"],
                    "properties": {
                        "romaji": {"type": "boolean"},
                        "furigana": {"type": "boolean"},
                        "english_meaning": {"type": "boolean"},
                    },
                },
            },
        },
        "sources": {"type": "array", "maxItems": 8, "items": _identifier},
        "media": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "purpose", "spec", "text_equivalent"],
                "properties": {
                    "kind": {"type": "string", "enum": ["visual", "audio"]},
                    "purpose": {"type": "string", "minLength": 3, "maxLength": 200},
                    "spec": {"type": "string", "minLength": 3, "maxLength": 800},
                    "text_equivalent": {"type": "string", "minLength": 5, "maxLength": 1200},
                },
            },
        },
        "parent_notes": {"type": ["string", "null"], "maxLength": 1500},
        "supervision_notes": {
            "type": "array",
            "maxItems": 10,
            "items": {"type": "string", "minLength": 5, "maxLength": 300},
        },
    },
}

VALIDATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "criteria", "rejections"],
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "reject"]},
        "criteria": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "verdict", "reason"],
                "properties": {
                    "id": {"type": "string", "enum": list(VALIDATION_CRITERIA)},
                    "verdict": {"type": "string", "enum": ["pass", "fail", "unknown"]},
                    "reason": {"type": "string", "minLength": 3, "maxLength": 400},
                },
            },
        },
        "rejections": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["item", "criterion", "reason"],
                "properties": {
                    "item": {"type": "string", "minLength": 1, "maxLength": 80},
                    "criterion": {"type": "string", "enum": list(VALIDATION_CRITERIA)},
                    "reason": {"type": "string", "minLength": 5, "maxLength": 400},
                    "fix_hint": {"type": "string", "maxLength": 400},
                },
            },
        },
        "claim_verdicts": {
            "type": "array",
            "maxItems": 30,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["item", "support", "reason"],
                "properties": {
                    "item": {"type": "string", "minLength": 1, "maxLength": 80},
                    "source_id": {"type": ["string", "null"], "maxLength": 64},
                    "support": {"type": "string", "enum": list(research_mod.SUPPORT_STATUSES)},
                    "reason": {"type": "string", "minLength": 3, "maxLength": 400},
                },
            },
        },
    },
}


def validate_artifact(schema: dict[str, Any], instance: Any, *, what: str) -> None:
    """Validate provider output against a strict schema. Raises ``GenerationRejected``."""
    if not isinstance(instance, dict):
        raise GenerationRejected(f"{what} is not a JSON object")
    if not instance:
        raise GenerationRejected(f"{what} is empty")
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise GenerationRejected(f"{what} violates its schema at {location}: {first.message}")


# ── Prompts ─────────────────────────────────────────────────────────────────

PLAN_SYSTEM_PROMPT = (
    "You are the Coursebook course architect. You produce a strict JSON study plan for one "
    "learner goal. You do not grade, and you do not claim that anything you wrote is validated. "
    "Use only the supplied source ledger for citations: never invent a URL, a title, a publisher "
    "or a date, and mark any objective you cannot ground in a supplied source as support "
    '"unverified". Time estimates must separate scheduled time from attainment claims: basis '
    '"fsi" only with a benchmark that states it is not a self-study conversion, basis "model" '
    "only with low confidence, and no attainment hours when basis is \"none\". Respect the "
    "recipe: one-off work is verified by a checklist and has no quiz or homework; committed "
    "courses include spaced review; casual checks are optional and labelled as such; parent "
    "plans are parent-led and carry supervision and hazard notes. Return only the JSON object."
)

LESSON_SYSTEM_PROMPT = (
    "You are the Coursebook lesson author. You write one durable learner page for one section of "
    "an already approved plan. Teach in short segments, show one worked example, then write one "
    "check that measures the section objective's declared evidence target. Put the reference "
    "answer, accepted answers, accepted alternatives and rubric in the check fields — they are "
    "stored separately and never shown to the learner before an attempt. Never repeat the "
    "reference answer inside the learner-facing explanation or segments. Respect the recipe: a "
    "one-off brief gets a verification checklist, not a quiz; a parent lesson is parent-led with "
    "observation notes and supervision. Every media item is a declarative spec with a complete "
    "text equivalent; you never generate an image. Return only the JSON object."
)

VALIDATION_SYSTEM_PROMPT = (
    "You are an independent Coursebook validator. You did not write this artifact and you have no "
    "loyalty to it. Do not restate, summarise or endorse the author's rationale; judge the artifact "
    "against the criteria supplied and the source ledger you are given. Treat every claim as "
    "unproven until a supplied source supports it, and treat provenance as distinct from support. "
    "Return a verdict per criterion, an explicit rejection for anything that must not reach a "
    "learner, and a support verdict per claim. If you cannot verify something, say \"unknown\" "
    "with a reason rather than guessing. Return only the JSON object."
)


def _plan_instructions(*, recipe: str, dials: dict[str, Any], locale: str | None, research_status: str) -> str:
    lines = [
        "Design plan v1 for the goal in the input.",
        f"Recipe: {recipe}.",
        f"Research status: {research_status}.",
        "Produce 4 to 8 objectives, each with a stable ordinal, an evidence target and 1-3 "
        "observable evidence criteria.",
        "Produce 2 to 8 ordered sections; each section names the objectives it serves and its "
        "lesson intent.",
        "Produce a check plan covering every objective at least once, with the recipe-appropriate "
        "kind and whether it collects independent evidence.",
        "State explicit exclusions: what this course will not cover or claim.",
    ]
    if recipe == "one_off":
        lines.append("No quiz and no homework: checks are verification checklists, spaced_review false.")
    if recipe == "committed":
        lines.append("Spaced review is required; every objective needs independent evidence.")
    if recipe == "casual":
        lines.append("Checks are optional self-checks; state that in evidence_note.")
    if recipe == "parent":
        lines.append("delivery is parent_led; include the parent block with age band, reading level, "
                     "supervision notes, hazards and setting materials.")
    if dials:
        lines.append(f"Learner dials: {canonical_json(dials)}.")
    if locale:
        lines.append(f"Content locale: {locale}.")
    return "\n".join(lines)


def _lesson_instructions(*, recipe: str, locale: str | None, scaffold_note: str) -> str:
    lines = [
        "Write the lesson page for the section in the input.",
        f"Recipe: {recipe}.",
        "Segments: 2-6, at least one 'model' and one 'guided'.",
        "Include exactly one check.",
        "Media items are declarative specs only, each with a complete text equivalent.",
    ]
    if locale:
        lines.append(f"Content locale: {locale}.")
    if scaffold_note:
        lines.append(scaffold_note)
    if recipe == "one_off":
        lines.append("The check is a verification checklist (kind 'verification', format 'verification').")
    if recipe == "parent":
        lines.append("The check is a parent observation (kind 'observation'); include parent_notes and "
                     "supervision_notes.")
    return "\n".join(lines)


def _validation_instructions(*, subject: str, criteria: Sequence[str]) -> str:
    return (
        f"Independently validate this {subject}. Check every one of these criteria and return one "
        f"entry per criterion: {', '.join(criteria)}. Reject any item that must not reach a "
        "learner, with the item reference and a concrete reason. For each claim in the artifact, "
        "return a support verdict against the supplied source ledger; use source_id only when the "
        "ledger actually contains that source."
    )


# ── Deterministic rule enforcement (generation-side, not validation) ────────


def _scaffold_policy(recipe: str, dials: dict[str, Any], locale: str | None) -> dict[str, bool]:
    """Task-mandated scaffolds. This is accessibility, never a learning-style diagnosis."""
    policy = {"romaji": False, "furigana": False, "english_meaning": False}
    if not locale:
        return policy
    primary = str(locale).split("-")[0].lower()
    level = str(dials.get("level") or "").upper()
    if primary == "ja" and level in ("L0", "L1", "BEGINNER"):
        policy.update({"romaji": True, "furigana": True, "english_meaning": True})
    if primary == "ja" and dials.get("romaji") is True:
        policy["romaji"] = True
    return policy


def _scaffold_note(policy: dict[str, bool], locale: str | None) -> str:
    if not locale or not any(policy.values()):
        return ""
    required = [name.replace("_", " ") for name, needed in policy.items() if needed]
    return (
        "Scaffolds are required for this learner: "
        + ", ".join(required)
        + ". Set check.scaffolds accordingly and never treat romaji-only output as script-reading evidence."
    )


def enforce_plan_rules(
    plan: dict[str, Any],
    *,
    recipe: str,
    dials: dict[str, Any],
    locale: str | None,
    ledger: Sequence[SourceRecord],
) -> None:
    """Deterministic plan rules. Runs *before* the validator and never replaces it."""
    reasons: list[str] = []
    if recipe not in RECIPES:
        raise GenerationRejected(f"unknown recipe {recipe!r}")

    objectives = plan.get("objectives") or []
    sections = plan.get("sections") or []
    ordinals = [int(obj.get("ordinal", 0)) for obj in objectives]
    if sorted(ordinals) != list(range(1, len(ordinals) + 1)):
        reasons.append("objective ordinals must be contiguous starting at 1")
    for section in sections:
        for ref in section.get("objective_refs") or []:
            if int(ref) not in ordinals:
                reasons.append(f"section {section.get('ordinal')} references missing objective {ref}")

    # Time honesty (AUDIT R9).
    estimate = plan.get("time_estimate") or {}
    basis = estimate.get("basis")
    if basis == "none" and estimate.get("attainment_hours"):
        reasons.append("basis 'none' must not carry attainment hours")
    if basis == "model" and estimate.get("confidence") != "low":
        reasons.append("basis 'model' requires low confidence")
    if basis == "fsi" and not estimate.get("benchmark"):
        reasons.append("basis 'fsi' requires a benchmark with explicit non-transferability")
    if estimate.get("attainment_hours") and estimate.get("confidence") == "high":
        reasons.append("attainment hours cannot carry high confidence")

    # Provenance: never cite a source the ledger does not contain (AUDIT R7).
    ledger_ids = {source.source_id for source in ledger}
    cited = list(plan.get("source_ids") or [])
    for section in sections:
        cited.extend(section.get("source_ids") or [])
    unknown = [sid for sid in cited if sid not in ledger_ids]
    if unknown:
        raise GenerationRejected(f"plan cites sources that were never fetched: {sorted(set(unknown))}")

    # Unsupported claims must say so.
    for obj in objectives:
        if obj.get("support") == "sourced":
            obj_sources = [sid for sid in (obj.get("source_ids") or []) if sid in ledger_ids]
            if not obj_sources:
                reasons.append(f"objective {obj.get('ordinal')} claims 'sourced' support without a ledger source")

    # Recipe rules.
    check_plan = plan.get("check_plan") or []
    checked = {int(item.get("objective_ref", 0)) for item in check_plan}
    missing = [ordinal for ordinal in ordinals if ordinal not in checked]
    if missing:
        reasons.append(f"check plan does not cover objectives {missing}")

    if recipe == "one_off":
        if any(item.get("kind") == "quiz" for item in check_plan):
            reasons.append("one-off briefs must not schedule a quiz")
        if not any(item.get("kind") == "verification" for item in check_plan):
            reasons.append("one-off briefs need an explicit verification checklist")
        if plan.get("spaced_review"):
            reasons.append("one-off briefs do not require spaced review or homework")
        if plan.get("delivery") == "parent_led":
            reasons.append("a one-off brief is not a parent-led lesson")
    elif recipe == "committed":
        if not plan.get("spaced_review"):
            reasons.append("committed courses must schedule spaced review")
        if not any(item.get("kind") == "quiz" for item in check_plan):
            reasons.append("committed courses need graded checks")
    elif recipe == "casual":
        if not plan.get("evidence_note"):
            reasons.append("casual courses must label what the evidence does and does not show")
    elif recipe == "parent":
        parent = plan.get("parent")
        if plan.get("delivery") != "parent_led":
            reasons.append("parent plans are parent-led, never a child chat")
        if not isinstance(parent, dict):
            reasons.append("parent plans require a parent block")
        else:
            if not parent.get("supervision_notes"):
                reasons.append("parent plans require supervision notes")
            if not parent.get("hazards"):
                reasons.append("parent plans must name hazards or explicitly state none apply")
        if any(item.get("kind") == "quiz" for item in check_plan):
            reasons.append("parent-mode checks are observations, not graded quizzes")

    # Mandated scaffolds for the locale/level (VAULT_LEARNING §2, task-mandated modality).
    policy = _scaffold_policy(recipe, dials, locale)
    if policy["romaji"]:
        needs = {str(item).lower() for item in plan.get("context_needs") or []}
        if not any("romaji" in item for item in needs):
            reasons.append("this learner's context needs must include romaji")

    if reasons:
        raise _RuleViolation(reasons)


def enforce_lesson_rules(
    lesson: dict[str, Any],
    *,
    section: dict[str, Any],
    objective: dict[str, Any] | None,
    recipe: str,
    locale: str | None,
    dials: dict[str, Any],
) -> None:
    reasons: list[str] = []
    check = lesson.get("check") or {}
    if objective is not None and check.get("evidence_target") != objective.get("evidence_target"):
        reasons.append(
            f"check targets {check.get('evidence_target')!r} but the objective requires "
            f"{objective.get('evidence_target')!r}"
        )
    if recipe == "one_off":
        if check.get("kind") != "verification" or (check.get("stimulus") or {}).get("format") != "verification":
            reasons.append("one-off lessons use a verification checklist, not a quiz")
    elif recipe == "parent":
        if check.get("kind") != "observation":
            reasons.append("parent lessons use a parent observation check")
        if not lesson.get("parent_notes") or not lesson.get("supervision_notes"):
            reasons.append("parent lessons require parent notes and supervision notes")
    else:
        if check.get("kind") != "quiz":
            reasons.append("this recipe needs a graded check")

    policy = _scaffold_policy(recipe, dials, locale)
    scaffolds = check.get("scaffolds") or {}
    for name, needed in policy.items():
        if needed and not scaffolds.get(name):
            reasons.append(f"check.scaffolds.{name} must be true for this learner's locale/level")

    for media in lesson.get("media") or []:
        if not str(media.get("text_equivalent") or "").strip():
            reasons.append("every media spec requires a complete text equivalent")

    if reasons:
        raise _RuleViolation(reasons)


def _normalize_answer(text: str) -> str:
    return " ".join(str(text).casefold().split())


def _narrative_text(page: dict[str, Any]) -> str:
    """The parts of a learner page where an answer must never be spelled out.

    Stimulus prompts and selection choices are excluded on purpose: in a selection check the
    correct choice necessarily appears in the page. The invariant is that the *key* is not
    announced — not that a correct string cannot exist among the options.
    """
    parts: list[str] = []
    for segment in page.get("segments") or []:
        parts.append(str(segment.get("heading") or ""))
        parts.append(str(segment.get("body") or ""))
    example = page.get("worked_example") or {}
    parts.extend([str(example.get("prompt") or ""), str(example.get("answer") or "")])
    parts.extend(str(step) for step in example.get("steps") or [])
    parts.append(str(page.get("learner_explanation") or ""))
    parts.append(str(page.get("parent_notes") or ""))
    for item in page.get("media") or []:
        parts.append(str(item.get("purpose") or ""))
        parts.append(str(item.get("text_equivalent") or ""))
    return _normalize_answer("\n".join(parts))


def assert_no_answer_leak(page: dict[str, Any], lesson: dict[str, Any]) -> None:
    """A reference answer must not be announced anywhere in the learner-facing narrative."""
    narrative = _narrative_text(page)
    check = lesson.get("check") or {}
    secrets = [str(check.get("reference_answer") or "")] + [str(item) for item in check.get("accepted_answers") or []]
    leaked = [secret for secret in secrets if secret and _normalize_answer(secret) in narrative]
    if leaked:
        raise _RuleViolation(["learner-facing narrative contains the check reference answer or a keyed answer"])
    rubric_terms = [str(item.get("description") or "") for item in check.get("rubric") or []]
    leaked_rubric = [term for term in rubric_terms if term and _normalize_answer(term) in narrative]
    if leaked_rubric:
        raise _RuleViolation(["learner-facing narrative contains rubric text"])


# ── Response parsing and validation verdicts ────────────────────────────────


def _parse_structured(response: LLMResponse, schema: dict[str, Any], *, what: str, max_bytes: int) -> dict[str, Any]:
    text = response.text or ""
    if len(text.encode("utf-8")) > max_bytes:
        raise GenerationRejected(f"{what} is {len(text.encode('utf-8'))} bytes, over the {max_bytes}-byte bound")
    parsed: Any = response.parsed
    if parsed is None:
        stripped = text.strip()
        if not stripped:
            raise GenerationRejected(f"{what} was empty")
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise GenerationRejected(f"{what} is not valid JSON: {exc.msg} at line {exc.lineno}") from exc
    validate_artifact(schema, parsed, what=what)
    return parsed


def assert_separate_pass(generation: LLMRequest, validation: LLMRequest) -> None:
    """Structural guarantee that validation is a second, different call.

    Same prompt or same schema means the "validator" is the generator wearing a hat; the pipeline
    refuses rather than recording a fake pass.
    """
    if generation.system_prompt == validation.system_prompt:
        raise GenerationRejected("validation reused the generation system prompt")
    if canonical_json(generation.schema) == canonical_json(validation.schema):
        raise GenerationRejected("validation reused the generation response schema")
    if generation.prompt_version == validation.prompt_version:
        raise GenerationRejected("validation reused the generation prompt version")


def validation_verdict(report: dict[str, Any], *, research_status: str) -> dict[str, Any]:
    """Turn a validator report into a verdict the pipeline can act on.

    A validator cannot pass an artifact while any criterion failed, and it must answer every
    criterion. ``unknown`` is honest only where the evidence genuinely is missing (no usable
    research); elsewhere it is treated as a failure to validate.
    """
    allowed_unknown = {"source_support", "factual_correctness"} if research_status != "ok" else set()
    seen: dict[str, str] = {}
    for entry in report.get("criteria") or []:
        seen[str(entry.get("id"))] = str(entry.get("verdict"))
    missing = [criterion for criterion in VALIDATION_CRITERIA if criterion not in seen]
    if missing:
        raise GenerationRejected(f"validator omitted criteria: {', '.join(missing)}")
    failed = [criterion for criterion, value in seen.items() if value == "fail"]
    unknown = [criterion for criterion, value in seen.items() if value == "unknown" and criterion not in allowed_unknown]
    rejections = list(report.get("rejections") or [])
    declared = str(report.get("verdict"))
    passed = declared == "pass" and not failed and not unknown and not rejections
    return {
        "verdict": "pass" if passed else "reject",
        "declared": declared,
        "failed": sorted(failed),
        "unknown": sorted(unknown),
        "rejections": rejections,
        "criteria": [dict(entry) for entry in report.get("criteria") or []],
        "claim_verdicts": [dict(entry) for entry in report.get("claim_verdicts") or []],
    }


def _feedback(rejections: Sequence[dict[str, Any]]) -> str:
    if not rejections:
        return "The independent validator rejected the previous attempt without itemised reasons; " \
               "fix the objective/source alignment and try again."
    lines = ["The independent validator rejected the previous attempt for these reasons:"]
    for entry in rejections[:8]:
        lines.append(
            f"- item {entry.get('item')} ({entry.get('criterion')}): {entry.get('reason')}"
        )
        if entry.get("fix_hint"):
            lines.append(f"  fix: {entry['fix_hint']}")
    return "\n".join(lines)


def _bounded_input(payload: dict[str, Any], limit: int = 24000) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1)
    return text if len(text) <= limit else text[:limit]


def _source_brief(sources: Iterable[SourceRecord]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": source.source_id,
            "url": source.url,
            "title": source.title,
            "publisher": source.publisher,
            "published_at": source.published_at,
            "fetched_at": source.fetched_at,
            "source_type": source.source_type,
            "support_status": source.support_status,
            "excerpt": source.excerpt,
        }
        for source in sources
    ]


# ── Provider request builders ───────────────────────────────────────────────


def build_plan_request(
    *,
    goal: str,
    recipe: str,
    dials: dict[str, Any],
    locale: str | None,
    research_run: ResearchRun,
    feedback: str | None = None,
    timeout_s: float = 60.0,
) -> LLMRequest:
    payload = {
        "goal": goal,
        "recipe": recipe,
        "dials": dials,
        "locale": locale,
        "research": {
            "status": research_run.status,
            "reason": research_run.reason,
            "queries": [entry.get("query") for entry in research_run.queries],
        },
        "sources": _source_brief(research_run.sources),
        "rules": {
            "objective_count": [4, 8],
            "section_count": [2, 8],
            "source_ids": "use only ids present in sources",
            "support": "unverified when no supplied source grounds the objective",
        },
    }
    if feedback:
        payload["revision_instructions"] = feedback
    return LLMRequest(
        purpose="coursebook.plan.generate",
        prompt_version=PLAN_PROMPT_VERSION,
        system_prompt=PLAN_SYSTEM_PROMPT,
        instructions=_plan_instructions(recipe=recipe, dials=dials, locale=locale, research_status=research_run.status),
        input_text=_bounded_input(payload),
        schema=PLAN_SCHEMA,
        schema_name="coursebook_plan_v1",
        max_tokens=4000,
        timeout_s=timeout_s,
    )


def build_plan_validation_request(
    *,
    plan: dict[str, Any],
    goal: str,
    recipe: str,
    dials: dict[str, Any],
    locale: str | None,
    research_run: ResearchRun,
    timeout_s: float = 60.0,
) -> LLMRequest:
    payload = {
        "artifact_kind": "plan",
        "goal": goal,
        "recipe": recipe,
        "dials": dials,
        "locale": locale,
        "research_status": research_run.status,
        "sources": _source_brief(research_run.sources),
        "plan": plan,
        "learner_facing": False,
    }
    return LLMRequest(
        purpose="coursebook.plan.validate",
        prompt_version=VALIDATION_PROMPT_VERSION,
        system_prompt=VALIDATION_SYSTEM_PROMPT,
        instructions=_validation_instructions(subject="plan", criteria=VALIDATION_CRITERIA),
        input_text=_bounded_input(payload),
        schema=VALIDATION_SCHEMA,
        schema_name="coursebook_validation_v1",
        max_tokens=2000,
        timeout_s=timeout_s,
    )


def build_lesson_request(
    *,
    plan: dict[str, Any],
    section: dict[str, Any],
    objective: dict[str, Any] | None,
    recipe: str,
    dials: dict[str, Any],
    locale: str | None,
    sources: Sequence[SourceRecord],
    feedback: str | None = None,
    timeout_s: float = 60.0,
) -> LLMRequest:
    policy = _scaffold_policy(recipe, dials, locale)
    payload = {
        "plan_title": plan.get("title"),
        "learner_outcome": plan.get("learner_outcome"),
        "delivery": plan.get("delivery"),
        "section": section,
        "objective": objective,
        "recipe": recipe,
        "dials": dials,
        "locale": locale,
        "sources": [brief for brief in _source_brief(sources) if brief["source_id"] in set(section.get("source_ids") or [])]
        or _source_brief(sources)[:4],
        "rules": {
            "segments": [2, 6],
            "checks": 1,
            "reference_answer": "stored separately; never inside segments, explanation or worked example",
            "media": "declarative spec with complete text equivalent; never generate an image",
        },
    }
    if feedback:
        payload["revision_instructions"] = feedback
    return LLMRequest(
        purpose="coursebook.lesson.generate",
        prompt_version=LESSON_PROMPT_VERSION,
        system_prompt=LESSON_SYSTEM_PROMPT,
        instructions=_lesson_instructions(recipe=recipe, locale=locale, scaffold_note=_scaffold_note(policy, locale)),
        input_text=_bounded_input(payload),
        schema=LESSON_SCHEMA,
        schema_name="coursebook_lesson_v1",
        max_tokens=4000,
        timeout_s=timeout_s,
    )


def build_lesson_validation_request(
    *,
    lesson: dict[str, Any],
    page: dict[str, Any],
    section: dict[str, Any],
    objective: dict[str, Any] | None,
    recipe: str,
    dials: dict[str, Any],
    locale: str | None,
    sources: Sequence[SourceRecord],
    timeout_s: float = 60.0,
) -> LLMRequest:
    payload = {
        "artifact_kind": "lesson",
        "section": section,
        "objective": objective,
        "recipe": recipe,
        "dials": dials,
        "locale": locale,
        "sources": _source_brief(sources),
        "lesson": lesson,
        "learner_facing_page": page,
        "learner_facing": True,
    }
    return LLMRequest(
        purpose="coursebook.lesson.validate",
        prompt_version=VALIDATION_PROMPT_VERSION,
        system_prompt=VALIDATION_SYSTEM_PROMPT,
        instructions=_validation_instructions(subject="lesson and its learner page", criteria=VALIDATION_CRITERIA),
        input_text=_bounded_input(payload),
        schema=VALIDATION_SCHEMA,
        schema_name="coursebook_validation_v1",
        max_tokens=2000,
        timeout_s=timeout_s,
    )


# ── SQLite schema owned by this module ──────────────────────────────────────
#
# The contract tables below are `CREATE TABLE IF NOT EXISTS` copies of `cb.db` v1, so this module
# works before Cinder's migrations land and is a no-op afterwards. The `gen_*` tables are the
# authoring records that `cb.db` v1 does not name; they are additive and owned here.

_GENERATION_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS courses (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        recipe TEXT NOT NULL,
        goal TEXT NOT NULL,
        locale TEXT,
        dials_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL,
        pack_id TEXT,
        revision INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plans (
        id TEXT PRIMARY KEY,
        course_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        state TEXT NOT NULL,
        plan_hash TEXT,
        schedule_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        approved_at TEXT,
        UNIQUE(course_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS objectives (
        id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL,
        ordinal INTEGER NOT NULL,
        title TEXT NOT NULL,
        evidence_target TEXT NOT NULL,
        evidence_criteria_json TEXT NOT NULL DEFAULT '[]',
        state TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        UNIQUE(plan_id, ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY,
        course_id TEXT NOT NULL,
        url TEXT,
        title TEXT NOT NULL,
        source_type TEXT NOT NULL,
        published_at TEXT,
        fetched_at TEXT NOT NULL,
        support_status TEXT NOT NULL,
        claim_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS checks (
        id TEXT PRIMARY KEY,
        objective_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        evidence_target TEXT NOT NULL,
        stimulus_json TEXT NOT NULL,
        rubric_json TEXT NOT NULL,
        reference_json TEXT NOT NULL,
        locale TEXT,
        audit_state TEXT NOT NULL,
        state TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(objective_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usage_events (
        id TEXT PRIMARY KEY,
        operation_id TEXT,
        enrollment_id TEXT,
        provider TEXT,
        model TEXT,
        tokens_json TEXT NOT NULL DEFAULT '{}',
        duration_ms INTEGER,
        artifact_count INTEGER NOT NULL DEFAULT 0,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gen_plan_documents (
        id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL,
        course_id TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        plan_hash TEXT NOT NULL,
        document_json TEXT NOT NULL,
        research_json TEXT NOT NULL,
        generation_state TEXT NOT NULL,
        validation_id TEXT,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(course_id, request_fingerprint)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gen_plan_sections (
        id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL,
        ordinal INTEGER NOT NULL,
        plan_hash TEXT NOT NULL,
        title TEXT NOT NULL,
        lesson_intent TEXT NOT NULL,
        objective_refs_json TEXT NOT NULL DEFAULT '[]',
        context_needs_json TEXT NOT NULL DEFAULT '[]',
        source_ids_json TEXT NOT NULL DEFAULT '[]',
        UNIQUE(plan_id, plan_hash, ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gen_lessons (
        id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL,
        section_id TEXT NOT NULL,
        plan_hash TEXT NOT NULL,
        version INTEGER NOT NULL,
        state TEXT NOT NULL,
        page_json TEXT NOT NULL,
        media_json TEXT NOT NULL DEFAULT '[]',
        parent_notes_json TEXT,
        rejection_reasons_json TEXT NOT NULL DEFAULT '[]',
        validation_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(section_id, plan_hash, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gen_lesson_checks (
        lesson_id TEXT NOT NULL,
        check_id TEXT NOT NULL,
        objective_ref INTEGER NOT NULL,
        PRIMARY KEY (lesson_id, check_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gen_validation_records (
        id TEXT PRIMARY KEY,
        subject_kind TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        subject_hash TEXT NOT NULL,
        generator_prompt_version TEXT NOT NULL,
        validator_prompt_version TEXT NOT NULL,
        validator_model TEXT,
        verdict TEXT NOT NULL,
        criteria_json TEXT NOT NULL,
        rejections_json TEXT NOT NULL,
        generator_prompt_sha256 TEXT NOT NULL,
        validator_prompt_sha256 TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(subject_kind, subject_id, subject_hash, validator_prompt_version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gen_research_runs (
        id TEXT PRIMARY KEY,
        course_id TEXT NOT NULL,
        job_id TEXT,
        status TEXT NOT NULL,
        queries_json TEXT NOT NULL DEFAULT '[]',
        sources_json TEXT NOT NULL DEFAULT '[]',
        reason TEXT,
        created_at TEXT NOT NULL
    )
    """,
)


def ensure_schema(connection: sqlite3.Connection) -> None:
    """Create the tables this module writes, idempotently. Safe to call per job."""
    with _transaction(connection):
        for statement in _GENERATION_DDL:
            connection.execute(statement)


# ── Persistence helpers ─────────────────────────────────────────────────────


_SAVEPOINT_COUNTER = 0


@contextmanager
def _transaction(connection: sqlite3.Connection) -> Any:
    """Short write transaction. Never wraps a provider call.

    Opens ``BEGIN IMMEDIATE`` when the connection is between transactions, and nests as a
    ``SAVEPOINT`` when a caller (the job executor) already holds one — so the pipeline can run
    inside the job service's unit of work without committing work it does not own.
    """
    global _SAVEPOINT_COUNTER
    if getattr(connection, "in_transaction", False):
        _SAVEPOINT_COUNTER += 1
        name = f"cb_gen_{_SAVEPOINT_COUNTER}"
        connection.execute(f"SAVEPOINT {name}")
        try:
            yield
        except BaseException:
            connection.execute(f"ROLLBACK TO {name}")
            connection.execute(f"RELEASE {name}")
            raise
        else:
            connection.execute(f"RELEASE {name}")
        return

    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


def _row_dict(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    if isinstance(row, dict):
        return dict(row)
    return None


def _new_id() -> str:
    return secrets.token_hex(8)


def _now_iso(now: datetime | None) -> str:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load_json(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def _request_fingerprint(goal: str, recipe: str, dials: dict[str, Any], locale: str | None) -> str:
    return sha256_of_text(
        canonical_json(
            {
                "pipeline": PIPELINE_VERSION,
                "goal": goal,
                "recipe": recipe,
                "dials": dials,
                "locale": locale,
                "plan_prompt": PLAN_PROMPT_VERSION,
                "validation_prompt": VALIDATION_PROMPT_VERSION,
            }
        )
    )


def plan_hash(plan: dict[str, Any]) -> str:
    return sha256_of_text(canonical_json(plan))


def _load_plan_document(connection: sqlite3.Connection, plan_id: str) -> dict[str, Any] | None:
    row = _row_dict(
        connection.execute("SELECT * FROM gen_plan_documents WHERE plan_id = ?", (plan_id,)).fetchone()
    )
    if row is None:
        return None
    row["document"] = _load_json(row.pop("document_json"), {})
    row["research"] = _load_json(row.pop("research_json"), {})
    row["result"] = _load_json(row.pop("result_json"), {})
    return row


def plan_document(connection: sqlite3.Connection, plan_id: str) -> dict[str, Any]:
    """Return ``{"plan", "research", "sections", "objectives"}`` for an authored plan."""
    ensure_schema(connection)
    row = _load_plan_document(connection, plan_id)
    if row is None:
        raise GenerationRejected(f"plan {plan_id!r} has no authored document")
    document = row["document"]
    objectives = [
        dict(item)
        for item in connection.execute(
            "SELECT id, ordinal, title, evidence_target, evidence_criteria_json FROM objectives "
            "WHERE plan_id = ? ORDER BY ordinal",
            (plan_id,),
        ).fetchall()
    ]
    sections = [
        dict(item)
        for item in connection.execute(
            "SELECT * FROM gen_plan_sections WHERE plan_id = ? ORDER BY ordinal", (plan_id,)
        ).fetchall()
    ]
    return {
        "plan_id": plan_id,
        "plan": document.get("plan") or {},
        "research": document.get("research") or {},
        "objectives": objectives,
        "sections": sections,
        "plan_hash": row.get("plan_hash"),
        "generation_state": row.get("generation_state"),
        "validation_id": row.get("validation_id"),
    }


def _record_usage(connection: sqlite3.Connection, job_id: str | None, usage: _Usage, now: datetime | None) -> None:
    if not usage.calls:
        return
    recorded_at = _now_iso(now)
    with _transaction(connection):
        for call in usage.calls:
            connection.execute(
                "INSERT INTO usage_events (id, operation_id, enrollment_id, provider, model, tokens_json, "
                "duration_ms, artifact_count, recorded_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    _new_id(),
                    job_id,
                    None,
                    call.get("provider"),
                    call.get("model"),
                    _json(
                        {
                            "input_tokens": call.get("input_tokens"),
                            "output_tokens": call.get("output_tokens"),
                            "cost_usd": call.get("cost_usd"),
                            "purpose": call.get("purpose"),
                            "prompt_version": call.get("prompt_version"),
                            "unknown_cost": call.get("cost_usd") is None,
                        }
                    ),
                    call.get("duration_ms"),
                    0,
                    recorded_at,
                ),
            )


def _persist_research(
    connection: sqlite3.Connection,
    *,
    course_id: str,
    job_id: str | None,
    run: ResearchRun,
    plan: dict[str, Any] | None = None,
    now: datetime | None,
) -> str:
    run_id = _new_id()
    created_at = _now_iso(now)
    claim_links = _claim_links(run, plan)
    with _transaction(connection):
        connection.execute(
            "INSERT INTO gen_research_runs (id, course_id, job_id, status, queries_json, sources_json, reason, "
            "created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                run_id,
                course_id,
                job_id,
                run.status,
                _json(run.queries),
                _json([source.to_dict() for source in run.sources]),
                run.reason,
                created_at,
            ),
        )
        for source in run.sources:
            existing = connection.execute(
                "SELECT id FROM sources WHERE course_id = ? AND url = ?", (course_id, source.url)
            ).fetchone()
            if existing is not None:
                continue
            connection.execute(
                "INSERT INTO sources (id, course_id, url, title, source_type, published_at, fetched_at, "
                "support_status, claim_count, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    source.source_id,
                    course_id,
                    source.url,
                    source.title,
                    source.source_type,
                    source.published_at,
                    source.fetched_at,
                    support_status_for_contract(source.support_status),
                    claim_links.get(source.source_id, 0),
                    created_at,
                ),
            )
    return run_id


def _claim_links(run: ResearchRun, plan: dict[str, Any] | None) -> dict[str, int]:
    """Count how many plan items actually cite each source.

    Research found the page; the plan decides what it is used for. A source nobody cites keeps a
    claim count of zero, which is the honest answer.
    """
    counts: dict[str, int] = {source.source_id: 0 for source in run.sources}
    if not plan:
        return counts
    for obj in plan.get("objectives") or []:
        for sid in obj.get("source_ids") or []:
            if sid in counts:
                counts[sid] += 1
    for section in plan.get("sections") or []:
        for sid in section.get("source_ids") or []:
            if sid in counts:
                counts[sid] += 1
    return counts


def _record_validation(
    connection: sqlite3.Connection,
    *,
    subject_kind: str,
    subject_id: str,
    subject_hash: str,
    generation_request: LLMRequest,
    validation_request: LLMRequest,
    response: LLMResponse,
    verdict: dict[str, Any],
    now: datetime | None,
) -> str:
    validation_id = _new_id()
    with _transaction(connection):
        connection.execute(
            "INSERT OR IGNORE INTO gen_validation_records (id, subject_kind, subject_id, subject_hash, "
            "generator_prompt_version, validator_prompt_version, validator_model, verdict, criteria_json, "
            "rejections_json, generator_prompt_sha256, validator_prompt_sha256, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                validation_id,
                subject_kind,
                subject_id,
                subject_hash,
                generation_request.prompt_version,
                validation_request.prompt_version,
                response.model,
                verdict["verdict"],
                _json(verdict["criteria"]),
                _json(
                    {
                        "rejections": verdict["rejections"],
                        "failed": verdict["failed"],
                        "unknown": verdict["unknown"],
                        "declared": verdict["declared"],
                    }
                ),
                sha256_of_text(generation_request.system_prompt),
                sha256_of_text(validation_request.system_prompt),
                _now_iso(now),
            ),
        )
        row = connection.execute(
            "SELECT id FROM gen_validation_records WHERE subject_kind = ? AND subject_id = ? AND subject_hash = ? "
            "AND validator_prompt_version = ?",
            (subject_kind, subject_id, subject_hash, validation_request.prompt_version),
        ).fetchone()
    return str(row[0]) if row is not None else validation_id


def _course_id(connection: sqlite3.Connection, brief: dict[str, Any], *, goal: str, recipe: str, locale: str | None, now: datetime | None) -> str:
    provided = brief.get("course_id")
    if provided:
        row = connection.execute("SELECT id FROM courses WHERE id = ?", (str(provided),)).fetchone()
        if row is None:
            raise GenerationRejected(f"job brief names course {provided!r}, which does not exist")
        return str(provided)
    course_id = _new_id()
    timestamp = _now_iso(now)
    with _transaction(connection):
        connection.execute(
            "INSERT INTO courses (id, title, recipe, goal, locale, dials_json, status, pack_id, revision, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                course_id,
                str(brief.get("title") or goal)[:200],
                recipe,
                goal,
                locale,
                _json(brief.get("dials") or {}),
                "draft",
                None,
                0,
                timestamp,
                timestamp,
            ),
        )
    return course_id


# ── Plan job ────────────────────────────────────────────────────────────────


def run_plan_job(
    connection: sqlite3.Connection,
    job: dict[str, Any],
    llm: LLM,
    search: SearchSeam | None = None,
    *,
    now: datetime | None = None,
    budget: CostBudget | None = None,
    research_budget: ResearchBudget | None = None,
) -> dict[str, Any]:
    """Research -> plan -> independent validation. Persists a **draft** plan only.

    Raises typed failures for malformed/oversized output, provider timeout and spend ceilings;
    nothing is written on those paths except the usage that was actually spent.
    """
    job = dict(job or {})
    brief = dict(job.get("brief") or {})
    goal = str(brief.get("goal") or brief.get("brief") or "").strip()
    if not goal:
        raise GenerationRejected("job brief has no goal")
    recipe = str(brief.get("recipe") or "casual")
    if recipe not in RECIPES:
        raise GenerationRejected(f"unknown recipe {recipe!r}")
    dials = dict(brief.get("dials") or {})
    locale = brief.get("locale")
    job_id = str(job.get("job_id") or "") or None
    usage = _Usage(budget or CostBudget())

    ensure_schema(connection)
    fingerprint = _request_fingerprint(goal, recipe, dials, locale)

    existing = _row_dict(
        connection.execute(
            "SELECT result_json FROM gen_plan_documents WHERE request_fingerprint = ?",
            (fingerprint,),
        ).fetchone()
    )
    if existing is not None:
        result = _load_json(existing["result_json"], {})
        result["reused"] = True
        return result

    course_id = _course_id(connection, brief, goal=goal, recipe=recipe, locale=locale, now=now)

    existing = _row_dict(
        connection.execute(
            "SELECT result_json FROM gen_plan_documents WHERE course_id = ? AND request_fingerprint = ?",
            (course_id, fingerprint),
        ).fetchone()
    )
    if existing is not None:
        result = _load_json(existing["result_json"], {})
        result["reused"] = True
        return result

    try:
        research_run = run_research(
            goal,
            recipe=recipe,
            dials=dials,
            locale=locale,
            search=search,
            budget=research_budget or ResearchBudget(),
            now=now,
        )

        plan: dict[str, Any] | None = None
        validation_request: LLMRequest | None = None
        validation_response: LLMResponse | None = None
        plan_request: LLMRequest | None = None
        verdict: dict[str, Any] | None = None
        feedback: str | None = None
        rejection_reasons: list[str] = []
        validation_id: str | None = None

        for attempt in (1, 2):
            plan_request = build_plan_request(
                goal=goal,
                recipe=recipe,
                dials=dials,
                locale=locale,
                research_run=research_run,
                feedback=feedback,
            )
            response = _call_llm(llm, plan_request, usage)
            candidate = _parse_structured(response, PLAN_SCHEMA, what="plan", max_bytes=MAX_PLAN_BYTES)

            try:
                enforce_plan_rules(
                    candidate, recipe=recipe, dials=dials, locale=locale, ledger=research_run.sources
                )
            except _RuleViolation as exc:
                rejection_reasons = exc.reasons
                if attempt == 2:
                    plan = candidate
                    break
                feedback = "The plan broke required rules:\n- " + "\n- ".join(exc.reasons)
                continue

            validation_request = build_plan_validation_request(
                plan=candidate,
                goal=goal,
                recipe=recipe,
                dials=dials,
                locale=locale,
                research_run=research_run,
            )
            assert_separate_pass(plan_request, validation_request)
            validation_response = _call_llm(llm, validation_request, usage)
            report = _parse_structured(
                validation_response, VALIDATION_SCHEMA, what="plan validation", max_bytes=MAX_VALIDATION_BYTES
            )
            verdict = validation_verdict(report, research_status=research_run.status)
            if verdict["verdict"] == "pass":
                plan = candidate
                break
            rejection_reasons = [
                f"{entry.get('item')}: {entry.get('reason')}" for entry in verdict["rejections"]
            ] or [f"criteria failed: {', '.join(verdict['failed'])}"]
            if attempt == 2:
                plan = candidate
                break
            feedback = _feedback(verdict["rejections"])

        assert plan is not None and plan_request is not None
        if verdict is None:
            # The generator could not satisfy a deterministic rule in two attempts. That is a
            # rejection, not a pass: no validation record is invented for a pass that never happened.
            verdict = {
                "verdict": "reject",
                "declared": "reject",
                "failed": [],
                "unknown": [],
                "rejections": [
                    {"item": "plan", "criterion": "objective_alignment", "reason": reason}
                    for reason in rejection_reasons
                ] or [{"item": "plan", "criterion": "objective_alignment", "reason": "generator broke required rules"}],
                "criteria": [],
                "claim_verdicts": [],
            }

        applied = apply_support_verdicts(research_run.sources, verdict.get("claim_verdicts") or [])
        research_run.sources = applied

        digest = plan_hash(plan)
        plan_id = _new_id()
        timestamp = _now_iso(now)
        generation_state = "draft" if verdict["verdict"] == "pass" else "needs_review"
        sections = [dict(section) for section in plan.get("sections") or []]
        objectives = [dict(obj) for obj in plan.get("objectives") or []]

        result = {
            "job_id": job_id,
            "job_kind": "plan",
            "course_id": course_id,
            "plan_id": plan_id,
            "plan_hash": digest,
            "plan_version": 1,
            "status": generation_state,
            "validation_id": None,
            "validation_verdict": verdict["verdict"],
            "objectives": len(objectives),
            "sections": len(sections),
            "sources": len(research_run.sources),
            "research": {
                "status": research_run.status,
                "reason": research_run.reason,
                "queries": [entry.get("query") for entry in research_run.queries],
            },
            "warnings": _plan_warnings(recipe, research_run, verdict),
            "usage": usage.summary(),
        }

        # One write transaction for the whole bundle: a plan must never exist without its document,
        # its ledger and its validation record. Provider calls already finished above.
        with _transaction(connection):
            version_row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM plans WHERE course_id = ?", (course_id,)
            ).fetchone()
            version = int((version_row["v"] if isinstance(version_row, sqlite3.Row) else version_row[0]) or 0) + 1
            connection.execute(
                "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json, created_at, approved_at) "
                "VALUES (?,?,?,?,?,?,?,NULL)",
                (
                    plan_id,
                    course_id,
                    version,
                    "draft",
                    digest,
                    _json(
                        {
                            "time_estimate": plan.get("time_estimate"),
                            "context_needs": plan.get("context_needs"),
                            "check_plan": plan.get("check_plan"),
                            "exclusions": plan.get("exclusions"),
                            "spaced_review": plan.get("spaced_review"),
                            "delivery": plan.get("delivery"),
                            "recipe": recipe,
                        }
                    ),
                    timestamp,
                ),
            )
            for objective in objectives:
                connection.execute(
                    "INSERT INTO objectives (id, plan_id, ordinal, title, evidence_target, "
                    "evidence_criteria_json, state, version, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        _new_id(),
                        plan_id,
                        int(objective["ordinal"]),
                        str(objective["title"]),
                        str(objective["evidence_target"]),
                        _json(objective.get("evidence_criteria") or []),
                        "not_started",
                        1,
                        timestamp,
                    ),
                )
            for section in sections:
                connection.execute(
                    "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent, "
                    "objective_refs_json, context_needs_json, source_ids_json) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        _new_id(),
                        plan_id,
                        int(section["ordinal"]),
                        digest,
                        str(section["title"]),
                        str(section["lesson_intent"]),
                        _json(section.get("objective_refs") or []),
                        _json(section.get("context_needs") or []),
                        _json(section.get("source_ids") or []),
                    ),
                )

            run_id = _persist_research(
                connection,
                course_id=course_id,
                job_id=job_id,
                run=research_run,
                plan=plan,
                now=now,
            )
            validation_id: str | None = None
            if validation_request is not None and validation_response is not None:
                validation_id = _record_validation(
                    connection,
                    subject_kind="plan",
                    subject_id=plan_id,
                    subject_hash=digest,
                    generation_request=plan_request,
                    validation_request=validation_request,
                    response=validation_response,
                    verdict=verdict,
                    now=now,
                )
            result["validation_id"] = validation_id
            result["plan_version"] = version
            result["research_id"] = run_id
            if generation_state == "needs_review":
                result["rejection_reasons"] = rejection_reasons

            connection.execute(
                "INSERT OR REPLACE INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint, plan_hash, "
                "document_json, research_json, generation_state, validation_id, result_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    _new_id(),
                    plan_id,
                    course_id,
                    fingerprint,
                    digest,
                    _json(
                        {
                            "plan": plan,
                            "recipe": recipe,
                            "dials": dials,
                            "locale": locale,
                            "pipeline_version": PIPELINE_VERSION,
                        }
                    ),
                    _json(research_run.to_dict()),
                    generation_state,
                    validation_id,
                    _json(result),
                    timestamp,
                ),
            )

        _record_usage(connection, job_id, usage, now)
        return result
    except BaseException:
        _record_usage(connection, job_id, usage, now)
        raise


def _plan_warnings(recipe: str, research_run: ResearchRun, verdict: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if research_run.status != "ok":
        warnings.append(
            "research "
            + research_run.status
            + ": claims are labelled unverified and no citation is presented as fetched support"
        )
    if recipe == "casual":
        warnings.append("casual course: checks are optional self-checks, not independent evidence")
    if recipe == "one_off":
        warnings.append("one-off brief: completion is instruction_complete plus a self-reported checklist")
    if verdict["verdict"] != "pass":
        warnings.append("independent validation did not pass: the plan is not approvable as-is")
    if verdict.get("unknown"):
        warnings.append("validator could not verify: " + ", ".join(verdict["unknown"]))
    return warnings


# ── Lesson job ──────────────────────────────────────────────────────────────


def _objective_for(connection: sqlite3.Connection, plan_id: str, ordinal: int) -> dict[str, Any] | None:
    row = _row_dict(
        connection.execute(
            "SELECT * FROM objectives WHERE plan_id = ? AND ordinal = ?", (plan_id, ordinal)
        ).fetchone()
    )
    if row is None:
        return None
    row["evidence_criteria"] = _load_json(row.pop("evidence_criteria_json"), [])
    return row


def _section_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "section_id": row["id"],
        "ordinal": row["ordinal"],
        "title": row["title"],
        "lesson_intent": row["lesson_intent"],
        "objective_refs": _load_json(row.get("objective_refs_json"), []),
        "context_needs": _load_json(row.get("context_needs_json"), []),
        "source_ids": _load_json(row.get("source_ids_json"), []),
    }


def _build_learner_page(lesson: dict[str, Any], section: dict[str, Any], sources: Sequence[SourceRecord]) -> dict[str, Any]:
    """Project the authored lesson onto the learner-facing page.

    Built from an allowlist, not by deleting keys: a field the author invents can never leak
    because it is never copied.
    """
    check = lesson["check"]
    source_index = {source.source_id: source for source in sources}
    return {
        "section_title": lesson["section_title"],
        "lesson_intent": section.get("lesson_intent"),
        "segments": [
            {"kind": segment["kind"], "heading": segment["heading"], "body": segment["body"]}
            for segment in lesson["segments"]
        ],
        "worked_example": {
            "prompt": lesson["worked_example"]["prompt"],
            "steps": list(lesson["worked_example"]["steps"]),
            "answer": lesson["worked_example"]["answer"],
        },
        "learner_explanation": lesson["learner_explanation"],
        "check": {
            "kind": check["kind"],
            "stimulus": {
                "prompt": check["stimulus"]["prompt"],
                "format": check["stimulus"]["format"],
                "choices": list(check["stimulus"].get("choices") or []),
            },
            "learner_instructions": check["learner_instructions"],
            "evidence_target": check["evidence_target"],
            "scaffolds": dict(check["scaffolds"]),
            "assistance_policy": dict(check["assistance_policy"]),
        },
        "sources": [
            {
                "source_id": sid,
                "title": source_index[sid].title,
                "publisher": source_index[sid].publisher,
                "url": source_index[sid].url,
                "published_at": source_index[sid].published_at,
                "fetched_at": source_index[sid].fetched_at,
                "support_status": source_index[sid].support_status,
            }
            for sid in lesson.get("sources") or []
            if sid in source_index
        ],
        "media": [
            {
                "kind": item["kind"],
                "purpose": item["purpose"],
                "text_equivalent": item["text_equivalent"],
            }
            for item in lesson.get("media") or []
        ],
        "parent_notes": lesson.get("parent_notes"),
        "supervision_notes": list(lesson.get("supervision_notes") or []),
    }


def _check_payloads(lesson: dict[str, Any], *, locale: str | None) -> dict[str, Any]:
    check = lesson["check"]
    stimulus = {
        "prompt": check["stimulus"]["prompt"],
        "format": check["stimulus"]["format"],
        "choices": list(check["stimulus"].get("choices") or []),
        "learner_instructions": check["learner_instructions"],
        "scaffolds": dict(check["scaffolds"]),
        "assistance_policy": dict(check["assistance_policy"]),
    }
    reference = {
        "reference_answer": check["reference_answer"],
        "accepted_answers": list(check["accepted_answers"]),
        "accepted_alternatives": [list(group) for group in check.get("accepted_alternatives") or []],
    }
    rubric = {"criteria": [dict(item) for item in check["rubric"]]}
    return {"stimulus": stimulus, "reference": reference, "rubric": rubric, "locale": locale}


def run_lesson_job(
    connection: sqlite3.Connection,
    job: dict[str, Any],
    llm: LLM,
    *,
    plan_id: str | None = None,
    now: datetime | None = None,
    budget: CostBudget | None = None,
) -> dict[str, Any]:
    """Author one validated lesson per section of an **approved** plan.

    Idempotent per ``(section, plan_hash, version)``: re-running the job reuses existing lessons
    and never duplicates rows or spend.
    """
    ensure_schema(connection)
    job = dict(job or {})
    brief = dict(job.get("brief") or {})
    plan_id = plan_id or brief.get("plan_id")
    if not plan_id:
        raise GenerationRejected("lesson job needs a plan_id")
    job_id = str(job.get("job_id") or "") or None
    usage = _Usage(budget or CostBudget())

    document = _load_plan_document(connection, str(plan_id))
    if document is None:
        raise GenerationRejected(f"plan {plan_id!r} has no authored document")
    plan_row = _row_dict(connection.execute("SELECT * FROM plans WHERE id = ?", (str(plan_id),)).fetchone())
    if plan_row is None:
        raise GenerationRejected(f"plan {plan_id!r} does not exist")
    if plan_row["state"] != "approved":
        raise PlanNotApproved(f"plan {plan_id!r} is {plan_row['state']!r}; lessons require an approved plan")

    plan = document["document"].get("plan") or {}
    recipe = str(document["document"].get("recipe") or "casual")
    dials = dict(document["document"].get("dials") or {})
    locale = document["document"].get("locale")
    digest = str(document["plan_hash"])
    research_doc = document["research"]
    sources = [
        SourceRecord(**{**source, "claim_links": list(source.get("claim_links") or [])})
        for source in research_doc.get("sources") or []
    ]
    research_status = str(research_doc.get("status") or "unavailable")

    section_rows = [
        _section_dict(dict(row))
        for row in connection.execute(
            "SELECT * FROM gen_plan_sections WHERE plan_id = ? ORDER BY ordinal", (str(plan_id),)
        ).fetchall()
    ]
    if not section_rows:
        raise GenerationRejected(f"plan {plan_id!r} has no sections to author")

    lesson_summaries: list[dict[str, Any]] = []
    try:
        for section in section_rows:
            existing = _row_dict(
                connection.execute(
                    "SELECT * FROM gen_lessons WHERE section_id = ? AND plan_hash = ? AND version = 1",
                    (section["section_id"], digest),
                ).fetchone()
            )
            if existing is not None:
                lesson_summaries.append(
                    {
                        "section_id": section["section_id"],
                        "lesson_id": existing["id"],
                        "state": existing["state"],
                        "check_enabled": existing["state"] == "validated",
                        "reused": True,
                    }
                )
                continue
            lesson_summaries.append(
                _author_section(
                    connection,
                    plan=plan,
                    section=section,
                    plan_id=str(plan_id),
                    digest=digest,
                    recipe=recipe,
                    dials=dials,
                    locale=locale,
                    sources=sources,
                    research_status=research_status,
                    llm=llm,
                    usage=usage,
                    job_id=job_id,
                    now=now,
                )
            )
    except BaseException:
        _record_usage(connection, job_id, usage, now)
        raise

    _record_usage(connection, job_id, usage, now)
    return {
        "job_id": job_id,
        "job_kind": "lesson",
        "plan_id": str(plan_id),
        "plan_hash": digest,
        "lessons": lesson_summaries,
        "needs_review": [item["section_id"] for item in lesson_summaries if item["state"] == "needs_review"],
        "usage": usage.summary(),
    }


def _author_section(
    connection: sqlite3.Connection,
    *,
    plan: dict[str, Any],
    section: dict[str, Any],
    plan_id: str,
    digest: str,
    recipe: str,
    dials: dict[str, Any],
    locale: str | None,
    sources: Sequence[SourceRecord],
    research_status: str,
    llm: LLM,
    usage: _Usage,
    job_id: str | None,
    now: datetime | None,
) -> dict[str, Any]:
    objective_ordinal = int((section.get("objective_refs") or [1])[0])
    objective = _objective_for(connection, plan_id, objective_ordinal)
    lesson: dict[str, Any] | None = None
    request: LLMRequest | None = None
    validation_request: LLMRequest | None = None
    validation_response: LLMResponse | None = None
    verdict: dict[str, Any] | None = None
    feedback: str | None = None
    rejection_reasons: list[str] = []

    for attempt in (1, 2):
        request = build_lesson_request(
            plan=plan,
            section=section,
            objective=objective,
            recipe=recipe,
            dials=dials,
            locale=locale,
            sources=sources,
            feedback=feedback,
        )
        response = _call_llm(llm, request, usage)
        candidate = _parse_structured(response, LESSON_SCHEMA, what="lesson", max_bytes=MAX_LESSON_BYTES)
        page = _build_learner_page(candidate, section, sources)

        try:
            enforce_lesson_rules(
                candidate, section=section, objective=objective, recipe=recipe, locale=locale, dials=dials
            )
            assert_no_answer_leak(page, candidate)
        except _RuleViolation as exc:
            rejection_reasons = exc.reasons
            if attempt == 2:
                lesson = candidate
                break
            feedback = "The lesson broke required rules:\n- " + "\n- ".join(exc.reasons)
            continue

        validation_request = build_lesson_validation_request(
            lesson=candidate,
            page=page,
            section=section,
            objective=objective,
            recipe=recipe,
            dials=dials,
            locale=locale,
            sources=sources,
        )
        assert_separate_pass(request, validation_request)
        validation_response = _call_llm(llm, validation_request, usage)
        report = _parse_structured(
            validation_response, VALIDATION_SCHEMA, what="lesson validation", max_bytes=MAX_VALIDATION_BYTES
        )
        verdict = validation_verdict(report, research_status=research_status)
        if verdict["verdict"] == "pass":
            lesson = candidate
            break
        rejection_reasons = [
            f"{entry.get('item')}: {entry.get('reason')}" for entry in verdict["rejections"]
        ] or [f"criteria failed: {', '.join(verdict['failed'])}"]
        if attempt == 2:
            lesson = candidate
            break
        feedback = _feedback(verdict["rejections"])

    assert lesson is not None and request is not None
    if verdict is None:
        # Deterministic rules failed twice, so no independent validation ever ran. That is not a
        # pass: the lesson is parked for review with the rule reasons attached.
        verdict = {
            "verdict": "reject",
            "declared": "reject",
            "failed": [],
            "unknown": [],
            "rejections": [{"item": "lesson", "criterion": "objective_alignment", "reason": reason} for reason in rejection_reasons],
            "criteria": [],
            "claim_verdicts": [],
        }

    page = _build_learner_page(lesson, section, sources)
    state = "validated" if verdict["verdict"] == "pass" else "needs_review"
    check_payloads = _check_payloads(lesson, locale=locale)
    lesson_id = _new_id()
    check_id = _new_id()
    timestamp = _now_iso(now)
    objective_id = str(objective["id"]) if objective else plan_id

    validation_id: str | None = None
    # One transaction: the lesson row, its check, the check link and the validation record land
    # together, so a validated lesson can never exist without the pass that allowed it.
    with _transaction(connection):
        connection.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json, media_json, "
            "parent_notes_json, rejection_reasons_json, validation_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                lesson_id,
                plan_id,
                section["section_id"],
                digest,
                1,
                state,
                _json(page),
                _json(lesson.get("media") or []),
                _json({"parent_notes": lesson.get("parent_notes"), "supervision_notes": lesson.get("supervision_notes")}),
                _json(rejection_reasons),
                None,
                timestamp,
                timestamp,
            ),
        )
        version_row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS v FROM checks WHERE objective_id = ?", (objective_id,)
        ).fetchone()
        check_version = int((version_row["v"] if isinstance(version_row, sqlite3.Row) else version_row[0]) or 0) + 1
        connection.execute(
            "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json, rubric_json, "
            "reference_json, locale, audit_state, state, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                check_id,
                objective_id,
                check_version,
                str(lesson["check"]["evidence_target"]),
                _json(check_payloads["stimulus"]),
                _json(check_payloads["rubric"]),
                _json(check_payloads["reference"]),
                locale,
                "passed" if state == "validated" else "failed",
                "open" if state == "validated" else "closed",
                timestamp,
            ),
        )
        connection.execute(
            "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref) VALUES (?,?,?)",
            (lesson_id, check_id, objective_ordinal),
        )

        if validation_request is not None and validation_response is not None:
            validation_id = _record_validation(
                connection,
                subject_kind="lesson",
                subject_id=lesson_id,
                subject_hash=sha256_of_text(canonical_json(page)),
                generation_request=request,
                validation_request=validation_request,
                response=validation_response,
                verdict=verdict,
                now=now,
            )
            connection.execute("UPDATE gen_lessons SET validation_id = ? WHERE id = ?", (validation_id, lesson_id))

    summary: dict[str, Any] = {
        "section_id": section["section_id"],
        "lesson_id": lesson_id,
        "check_id": check_id,
        "state": state,
        "check_enabled": state == "validated",
        "audit_state": "passed" if state == "validated" else "failed",
        "validation_id": validation_id,
        "validation_verdict": verdict["verdict"],
        "validation_model": validation_response.model if validation_response is not None else None,
        "reused": False,
    }
    if state == "needs_review":
        summary["rejection_reasons"] = rejection_reasons
    return summary


# ── Learner-facing read ─────────────────────────────────────────────────────

_FORBIDDEN_PAGE_KEYS = {"reference_answer", "accepted_answers", "accepted_alternatives", "rubric", "reference"}


def learner_page(connection: sqlite3.Connection, lesson_id: str) -> dict[str, Any]:
    """Return the learner-facing page. Raises when the lesson is not servable.

    Defence in depth: the projection already excludes answers, and this re-checks the stored JSON
    and the linked checks before returning anything.
    """
    ensure_schema(connection)
    row = _row_dict(connection.execute("SELECT * FROM gen_lessons WHERE id = ?", (lesson_id,)).fetchone())
    if row is None:
        raise LessonNotAvailable(f"lesson {lesson_id!r} does not exist")
    if row["state"] != "validated":
        raise LessonNotAvailable(
            f"lesson {lesson_id!r} is {row['state']!r}: no learner-facing check is enabled"
        )
    page = _load_json(row["page_json"], {})
    if _leaks(page):
        raise LessonNotAvailable("stored lesson page contains answer material; refusing to serve it")
    check_rows = connection.execute(
        "SELECT reference_json, rubric_json FROM checks c JOIN gen_lesson_checks l ON l.check_id = c.id "
        "WHERE l.lesson_id = ?",
        (lesson_id,),
    ).fetchall()
    page_text = _narrative_text(page)
    for check_row in check_rows:
        reference = _load_json(dict(check_row).get("reference_json"), {})
        for answer in [reference.get("reference_answer")] + list(reference.get("accepted_answers") or []):
            if answer and _normalize_answer(str(answer)) in page_text:
                raise LessonNotAvailable("stored lesson page announces a check answer; refusing to serve it")
    return page


def _leaks(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in _FORBIDDEN_PAGE_KEYS or _leaks(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_leaks(child) for child in value)
    return False


# ── small numeric helpers ───────────────────────────────────────────────────


def _attr_int(obj: Any, name: str) -> int | None:
    value = getattr(obj, name, None)
    return int(value) if isinstance(value, (int, float)) else None


def _attr_float(obj: Any, name: str) -> float | None:
    value = getattr(obj, name, None)
    return float(value) if isinstance(value, (int, float)) else None
