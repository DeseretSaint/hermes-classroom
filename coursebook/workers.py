"""Stage builders that run inside the durable job service.

Two families ship here:

``research``
    governed, budgeted, cancellable web research. The budget is executable
    (:class:`coursebook.research.ResearchBudget`); every search/fetch is counted and a cancel
    request is honored before the next call. Deep research never runs in the pre-turn grading
    hook — this module is only reachable from a job.

``media``
    cached artifact generation with an honest text fallback. A cached artifact (same spec hash +
    source hash) is reused before any provider is called, so a retry or a reconnect never pays
    twice; a provider failure leaves the complete text lesson.

The stages do all provider work outside transactions and return :class:`StageResult` so the job
service can checkpoint and record real usage.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from . import artifacts as media
from . import db, generation, job_service, research, sources
from .job_service import JobCancelled, Lease, Stage, StageResult, UsageRecord


# ── governed research ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResearchRequest:
    goal: str
    course_id: str | None = None
    recipe: str = "casual"
    dials: dict[str, Any] = field(default_factory=dict)
    locale: str | None = None
    #: Declared cb.rpc v10 inputs. They shape the query set the same way the plan job's do; they
    #: are never folded into ``dials``, which stays the closed four-dial object.
    subject_domain: str | None = None
    level: str | None = None
    budget: research.ResearchBudget | None = None

    @property
    def effective_budget(self) -> research.ResearchBudget:
        """The explicit budget, else the cell the declared depth selects.

        A research job used to default to one fixed budget regardless of `dials.depth`, which is
        the same no-op this card removes from the plan path.
        """
        return self.budget or research.budget_for(self.dials.get("depth"))

    def as_brief(self) -> dict[str, Any]:
        budget = self.effective_budget
        return {
            "goal": self.goal,
            "course_id": self.course_id,
            "recipe": self.recipe,
            "dials": dict(self.dials),
            "locale": self.locale,
            "subject_domain": self.subject_domain,
            "level": self.level,
            "budget": {
                "max_queries": budget.max_queries,
                "max_results_per_query": budget.max_results_per_query,
                "max_pages": budget.max_pages,
                "max_sources": budget.max_sources,
                "max_page_chars": budget.max_page_chars,
            },
        }


class CountingSeam:
    """Wraps a :class:`research.SearchSeam`: checks cancellation, counts real calls.

    ``calls`` is the usage ledger — every entry is a call that actually happened, with the real
    duration. Token counts stay absent because a search call exposes none.
    """

    def __init__(self, seam: research.SearchSeam, lease: Lease | None) -> None:
        self._seam = seam
        self._lease = lease
        self.usage: list[UsageRecord] = []

    def _guard(self) -> None:
        if self._lease is not None and job_service.is_cancel_requested(self._lease.job_id):
            raise JobCancelled("cancellation reached a provider-call boundary", usage=self.usage)

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        self._guard()
        started = time.monotonic()
        results = self._seam.search(query, limit)
        self.usage.append(
            UsageRecord(
                provider="web_search",
                model=None,
                tokens={},
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
        return results

    def fetch(self, url: str, max_chars: int) -> dict[str, Any]:
        self._guard()
        started = time.monotonic()
        page = self._seam.fetch(url, max_chars)
        self.usage.append(
            UsageRecord(
                provider="web_extract",
                model=None,
                tokens={},
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
        return page


def _persist_run(lease: Lease, request: ResearchRequest, run: research.ResearchRun) -> dict[str, Any]:
    """Write the run snapshot + ledger in one transaction. Adoption is part of the same stage."""
    if not request.course_id:
        return {
            "checkpoint": {"ledger": "skipped", "reason": "no course_id on the brief"},
            "message": "research complete; no course to attach the ledger to",
        }
    with db.transaction() as connection:
        generation.ensure_schema(connection)
        research_run_id = generation._persist_research(
            connection,
            course_id=request.course_id,
            job_id=lease.job_id,
            run=run,
            now=None,
        )
        ledger = sources.ledger(connection, request.course_id)
    return {
        "checkpoint": {"research_run_id": research_run_id, "ledger_size": len(ledger)},
        "message": f"ledger recorded {len(ledger)} sources",
    }


def research_stages(
    request: ResearchRequest,
    seam_factory: Callable[[Lease], research.SearchSeam],
    *,
    now: Any = None,
) -> list[Stage]:
    """Build the two stages of a research job. Provider work happens in stage two only."""
    box: dict[str, Any] = {}

    def prepare(lease: Lease) -> StageResult:
        queries = research.derive_queries(
            request.goal,
            recipe=request.recipe,
            dials=request.dials,
            locale=request.locale,
            max_queries=request.effective_budget.max_queries,
            subject_domain=request.subject_domain,
            level=request.level,
        )
        box["queries"] = queries
        return StageResult(
            checkpoint={"queries": queries},
            message=f"{len(queries)} bounded queries prepared",
        )

    def gather(lease: Lease) -> StageResult:
        seam = CountingSeam(seam_factory(lease), lease)
        started = time.monotonic()
        run = research.run_research(
            request.goal,
            search=seam,
            recipe=request.recipe,
            dials=request.dials,
            locale=request.locale,
            subject_domain=request.subject_domain,
            level=request.level,
            budget=request.effective_budget,
        )
        box["run"] = run
        persist_result = _persist_run(lease, request, run)
        return StageResult(
            usage=seam.usage,
            artifacts=persist_result.get("artifacts", []),
            checkpoint={
                "research_status": run.status,
                "queries": [dict(item) for item in run.queries],
                "source_count": len(run.sources),
                "duration_ms": int((time.monotonic() - started) * 1000),
                **persist_result.get("checkpoint", {}),
            },
            message=persist_result.get("message") or f"research {run.status}: {len(run.sources)} sources",
        )

    return [
        Stage("derive_queries", prepare),
        Stage("research", gather),
    ]


def run_research_job(
    request: ResearchRequest,
    seam_factory: Callable[[Lease], research.SearchSeam],
    *,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """Create and execute a research job end-to-end. Returns the final job view."""
    created = job_service.create("research", request.as_brief(), operation_id=operation_id)
    job_id = created["job_id"]
    with db.read() as connection:
        row = connection.execute("SELECT state FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is not None and str(row["state"]) != "queued":
        return job_service._view(job_id)
    return job_service.execute(job_id, research_stages(request, seam_factory))


# ── media artifacts ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MediaRequest:
    spec: media.MediaSpec
    producer: Callable[[], bytes]
    mime: str
    course_id: str | None = None
    source_texts: tuple[str, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)

    def cache_key(self) -> tuple[str, str, str]:
        spec_fp = media.spec_hash(self.spec.as_cache_spec())
        source_fp = media.source_hash(self.source_texts)
        return (self.spec.kind, spec_fp, source_fp)


def media_stages(request: MediaRequest, *, store: media.ArtifactStore | None = None) -> list[Stage]:
    """Validate → reuse-or-generate → record. A cached artifact costs nothing."""
    store = store or media.ArtifactStore()
    box: dict[str, Any] = {}

    def validate(lease: Lease) -> StageResult:
        media.assert_media_ok(request.spec)
        kind, spec_fp, source_fp = request.cache_key()
        with db.read() as connection:
            cached = store.lookup(
                connection, kind=kind, spec_fingerprint=spec_fp, source_fingerprint=source_fp
            )
        box["cached"] = cached
        box["spec_fp"] = spec_fp
        box["source_fp"] = source_fp
        return StageResult(
            checkpoint={
                "spec_hash": spec_fp,
                "source_hash": source_fp,
                "cache_hit": cached is not None,
            },
            message="cache hit" if cached is not None else "generation required",
            artifacts=[cached["artifact_id"]] if cached else (),
        )

    def produce(lease: Lease) -> StageResult:
        if box.get("cached") is not None:
            return StageResult(
                artifacts=[],
                checkpoint={"reused": True},
                message="reused the cached artifact; no provider call",
            )
        assert not db.active_transactions(), "media generation must not run inside a transaction"
        started = time.monotonic()
        outcome = media.produce_with_fallback(
            store,
            request.spec,
            request.producer,
            course_id=request.course_id,
            mime=request.mime,
            provenance={**request.provenance, "source_hash": box.get("source_fp")},
        )
        box["outcome"] = outcome
        artifact = outcome.artifact
        checkpoint = {
            "degraded": outcome.degraded,
            "reason": outcome.reason,
            "text_equivalent": outcome.text_equivalent,
            "label": outcome.label,
            "triage": outcome.triage,
        }
        if artifact is None:
            return StageResult(checkpoint=checkpoint, message=outcome.reason or "text fallback")
        return StageResult(
            artifacts=[artifact["artifact_id"]],
            usage=[
                UsageRecord(
                    provider=request.provenance.get("provider"),
                    model=request.provenance.get("model"),
                    tokens={},
                    duration_ms=int((time.monotonic() - started) * 1000),
                    artifact_count=1,
                )
            ],
            checkpoint=checkpoint,
            message="artifact recorded",
        )

    def expose(lease: Lease) -> StageResult:
        outcome = box.get("outcome")
        if outcome is None or outcome.artifact is None:
            return StageResult(checkpoint={"renderer": []}, message="text-only lesson is complete")
        artifact = outcome.artifact
        manifest = media.renderer_manifest([artifact])
        with db.read() as connection:
            row = connection.execute(
                "SELECT path FROM artifacts WHERE id = ?", (artifact["artifact_id"],)
            ).fetchone()
        return StageResult(
            checkpoint={
                "renderer": manifest,
                "media_marker": media.media_marker(artifact, path=row["path"] if row else None),
            },
            message="renderer manifest ready",
        )

    return [
        Stage("validate_spec", validate),
        Stage("generate", produce),
        Stage("expose", expose),
    ]


def run_media_job(
    request: MediaRequest,
    *,
    store: media.ArtifactStore | None = None,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """Create and run a media job. Returns the final job view."""
    brief = {
        "kind": request.spec.kind,
        "role": request.spec.role,
        "course_id": request.course_id,
        "voice": request.spec.voice,
        "language": request.spec.language,
    }
    created = job_service.create("media", brief, operation_id=operation_id)
    job_id = created["job_id"]
    with db.read() as connection:
        row = connection.execute("SELECT state FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is not None and str(row["state"]) != "queued":
        return job_service._view(job_id)
    return job_service.execute(job_id, media_stages(request, store=store))
