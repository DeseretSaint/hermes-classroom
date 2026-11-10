"""Bounded, ledgered research for Coursebook course generation.

Research is a *bounded* job (``PREBUILD_SPEC.md`` §9, ``AUDIT.md`` H2/R7), not an open crawl:

* the query set is derived deterministically from the goal, recipe, dials and locale and is
  capped before any provider call;
* every query that ran is recorded, including the ones that returned nothing;
* every page keeps a real URL, title, publisher, fetch date, nullable publication date, source
  type and a content hash — nothing is invented, and a failed fetch is recorded as a failure
  rather than filled in;
* fetched text is kept as a bounded excerpt only. It is untrusted content: it never becomes
  policy, rubric or prompt-injection surface (``PREBUILD_SPEC.md`` §9).

Provenance is not support. A fetched source starts at ``unverified`` and only an *independent*
validation pass (a different model identity) may move it to ``supported`` / ``partial`` /
``contradictory`` through :func:`apply_support_verdicts`, and only when the verdict quotes a span
that appears verbatim in the fetched excerpt. A model asserting its own citation support is not
evidence, and a same-model "validator" cannot move the ledger at all.

The search/extract seam is injected. The production adapter is :class:`HermesToolSearch`, which
uses the host's own ``web_search`` / ``web_extract`` tools through ``ctx.dispatch_tool`` so the
plugin inherits the user's configured backend, egress rules and SSRF checks instead of calling a
vendor API with a raw key.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Protocol
from urllib.parse import urlparse

from . import curriculum, policy
from .deadline import (
    CallCapacityExhausted,
    DeadlineExceeded,
    run_bounded,
)

__all__ = [
    "SUPPORT_STATUSES",
    "CONTRACT_SUPPORT_STATUS",
    "DEPTH_VALUES",
    "DEPTH_ALIASES",
    "SCOPES",
    "DEFAULT_DEPTH",
    "DEFAULT_SCOPE",
    "SOURCE_TYPE_RANK",
    "ResearchBudget",
    "ResearchUnavailable",
    "ResearchTimeout",
    "ResearchBudgetExceeded",
    "SourceRecord",
    "ResearchRun",
    "SearchSeam",
    "HermesToolSearch",
    "ensure_host_tools",
    "NullSearch",
    "budget_for",
    "effective_depth",
    "SCOPE_MIN_DEPTH",
    "normalize_depth",
    "normalize_scope",
    "derive_queries",
    "run_research",
    "apply_support_verdicts",
    "support_status_for_contract",
    "canonical_json",
    "sha256_of_text",
]

#: The depth values the contract actually sends (``course.create`` dials.depth in cb.rpc v9/v10).
#: Research had historically branched on ``overview``/``thorough``, which no product payload can
#: produce, so the dial was a no-op. These three names are now the only canonical values.
DEPTH_VALUES: tuple[str, ...] = ("survey", "working", "deep")

#: Older in-process names. They normalize **loudly** to a contract value instead of acting as a
#: fourth behaviour: ``overview`` is ``survey``, ``thorough`` is ``deep``.
DEPTH_ALIASES: dict[str, str] = {"overview": "survey", "thorough": "deep"}

#: Course scope from cb.rpc v10 (``single`` one objective, ``short`` 3–6, ``full`` multi-unit).
SCOPES: tuple[str, ...] = ("single", "short", "full")

#: Defaults when a brief does not declare the value. The product's default create flow is a
#: short course at working depth; this is documented rather than a silent dial-like fallback.
DEFAULT_DEPTH = "working"
DEFAULT_SCOPE = "short"

#: One row per (scope, depth): ``(max_queries, max_results_per_query, max_pages, max_sources)``.
#: Every value is a ceiling checked before the call it bounds; the derived query set may be
#: smaller. A full course never receives the old six-page demo pass: at ``working`` it gets at
#: least 9 queries / 14 pages, and at ``deep`` 12 / 18 — bounded, never an open crawl.
_BUDGET_MATRIX: dict[str, dict[str, tuple[int, int, int, int]]] = {
    "single": {
        "survey": (2, 4, 2, 2),
        "working": (4, 5, 4, 4),
        "deep": (6, 6, 6, 6),
    },
    "short": {
        "survey": (3, 4, 4, 4),
        "working": (6, 5, 8, 8),
        "deep": (9, 6, 12, 10),
    },
    "full": {
        "survey": (6, 5, 8, 8),
        "working": (9, 5, 14, 12),
        "deep": (12, 6, 18, 16),
    },
}

#: Selection preference when candidates outnumber the page budget. Lower is fetched first.
#: This ranks *who publishes the URL* (a fact); it is not a support verdict. Every fetched row
#: still starts ``unverified`` and only an independent validator may move it.
SOURCE_TYPE_RANK: dict[str, int] = {
    "government": 0,
    "academic": 1,
    "reference": 2,
    "documentation": 3,
    "organization": 4,
    "web_page": 5,
}

#: Generation-layer support statuses (this card's vocabulary for the source ledger).
SUPPORT_STATUSES: tuple[str, ...] = ("supported", "partial", "contradictory", "unverified")

#: Translation into the frozen ``cb.vocabulary#/$defs/source_support_status`` enum. The ledger
#: keeps the finer generation status alongside it; the contract value is what the kernel stores.
CONTRACT_SUPPORT_STATUS: dict[str, str] = {
    "supported": "model_assessed",
    "partial": "model_assessed",
    "contradictory": "conflicting",
    "unverified": "unassessed",
}

#: Hard caps on the shape of a snippet/excerpt we keep. Content is never stored in full.
_MAX_TITLE = 300
_MAX_PUBLISHER = 120
#: A pipeline excerpt is the text a plan/lesson validator judges a claim against, so it must carry
#: real prose, not the first few hundred characters of site chrome. 600 characters was measured to
#: end inside a navigation menu (``Search ## Suggested Searches - [Artemis]…``) and left every
#: objective unsupportable. The worker still bounds the request by ``REQUEST_BYTES_BOUNDS``; this
#: value is the per-source window, chosen so eight sources fit a 24 kB ``short`` request.
_MAX_EXCERPT = 1600
#: Search-result descriptions are not judged evidence; keep them small and stable.
_MAX_DESCRIPTION = 600
_MAX_SOURCE_TYPE = 40
_MAX_QUERY = 220
_MAX_REASON = 300

#: Declared deadlines for the host research tools (H-66). The host may ignore any timeout the
#: plugin merely forwards, so the adapter enforces its own wall clock. These are outer bounds
#: for one call, not target latencies; an operator can raise them per tool.
RESEARCH_TOOL_TIMEOUT_SECONDS: dict[str, float] = {"web_search": 45.0, "web_extract": 60.0}
RESEARCH_TIMEOUT_ENV: dict[str, str] = {
    "web_search": "COURSEBOOK_WEB_SEARCH_TIMEOUT_SECONDS",
    "web_extract": "COURSEBOOK_WEB_EXTRACT_TIMEOUT_SECONDS",
}


def research_tool_timeout_s(tool: str) -> float:
    """The declared deadline for one host research tool, overridable by environment."""
    default = RESEARCH_TOOL_TIMEOUT_SECONDS.get(str(tool), 60.0)
    raw = os.environ.get(RESEARCH_TIMEOUT_ENV.get(str(tool), ""), "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class ResearchUnavailable(RuntimeError):
    """No usable search/extract seam is wired in this process.

    Callers must not degrade silently: a plan may still be proposed from model knowledge, but
    every claim is then labelled ``unverified`` and the research block says ``unavailable``.
    """


class ResearchTimeout(ResearchUnavailable):
    """A host search/extract call missed its declared deadline (H-66).

    A subclass of :class:`ResearchUnavailable` so an ordinary research pass degrades honestly
    (the page/query is recorded as failed), while the job service can still report it as a
    *host* failure rather than a policy refusal.
    """

    def __init__(self, message: str, *, tool: str, deadline_s: float) -> None:
        self.tool = str(tool)
        self.deadline_s = float(deadline_s)
        super().__init__(message)


class ResearchBudgetExceeded(RuntimeError):
    """The pipeline tried to exceed a declared query/page/source ceiling."""


class ResearchCancelled(RuntimeError):
    """A cancellation reached a provider-call boundary mid-run.

    Search/extract failures are recorded and skipped; **cancellation is not a failure** and must
    propagate, otherwise a cancelled job would keep spending and look like a completed one.
    Provider adapters must raise this (or a subclass) to stop the run.
    """


@dataclass(frozen=True)
class ResearchBudget:
    """Executable ceilings. Every field is checked before the call it bounds.

    The default is the ``short``/``working`` cell of :data:`_BUDGET_MATRIX`. Product jobs do not
    rely on it: :func:`budget_for` derives the cell from the declared depth and scope.
    """

    max_queries: int = 6
    max_results_per_query: int = 5
    max_pages: int = 8
    max_sources: int = 8
    max_page_chars: int = 6000
    max_excerpt_chars: int = _MAX_EXCERPT

    def __post_init__(self) -> None:
        if not 1 <= self.max_queries <= 12:
            raise ValueError("max_queries must be between 1 and 12")
        if not 1 <= self.max_pages <= 24:
            raise ValueError("max_pages must be between 1 and 24")
        if not 1 <= self.max_sources <= 24:
            raise ValueError("max_sources must be between 1 and 24")
        if not 1 <= self.max_results_per_query <= 20:
            raise ValueError("max_results_per_query must be between 1 and 20")
        if not 500 <= self.max_page_chars <= 40000:
            raise ValueError("max_page_chars must be between 500 and 40000")


def normalize_depth(value: Any) -> str:
    """Map a depth input onto a contract value, or fail loudly.

    ``None``/blank means "the brief did not say", which is the documented ``working`` default.
    A legacy alias normalizes to its contract value. Anything else is an error: a fourth value
    must never quietly behave like one of the three (that is the defect this closes).
    """
    if value is None:
        return DEFAULT_DEPTH
    text = str(value).strip().lower()
    if not text:
        return DEFAULT_DEPTH
    text = DEPTH_ALIASES.get(text, text)
    if text not in DEPTH_VALUES:
        raise ValueError(
            f"unknown research depth {value!r}; expected one of {', '.join(DEPTH_VALUES)}"
        )
    return text


def normalize_scope(value: Any) -> str:
    """Map a scope input onto ``single``/``short``/``full``; blank means ``short``."""
    if value is None:
        return DEFAULT_SCOPE
    text = str(value).strip().lower()
    if not text:
        return DEFAULT_SCOPE
    if text not in SCOPES:
        raise ValueError(f"unknown course scope {value!r}; expected one of {', '.join(SCOPES)}")
    return text


#: The minimum research depth a course size buys. A full course is not authored from a
#: goal-only survey; a short course must at least see the recipe qualifier and curriculum
#: sequence. These are floors, not a replacement for the learner's declared depth: a higher
#: depth still wins, and an explicit ``budget`` remains the hard ceiling.
#:
#: The create flow used to send ``survey`` for every course, which made the SQL budget cell
#: (e.g. full/survey: 6 queries, 8 pages) look sufficient while ``derive_queries`` returned only
#: the goal. The floor is recorded beside, not written into, the closed four-dial object.
SCOPE_MIN_DEPTH: dict[str, str] = {
    "single": "working",
    "short": "working",
    "full": "deep",
}
_DEPTH_ORDER: dict[str, int] = {"survey": 0, "working": 1, "deep": 2}


def effective_depth(depth: Any = None, scope: Any = None) -> str:
    """The depth a course size actually gets, raising a too-low declaration to its floor.

    This is deliberately separate from :func:`budget_for`. The budget matrix remains a set of
    ceilings and its three cells stay distinguishable for callers that inspect it; this function
    answers the different question *"what pass will this course size run?"*.
    """
    declared = normalize_depth(depth)
    scope_value = normalize_scope(scope)
    floor = SCOPE_MIN_DEPTH[scope_value]
    return declared if _DEPTH_ORDER[declared] >= _DEPTH_ORDER[floor] else floor


def budget_for(depth: Any = None, scope: Any = None) -> ResearchBudget:
    """The documented ``(scope, depth)`` budget cell, with per-field validation."""
    depth_value = normalize_depth(depth)
    scope_value = normalize_scope(scope)
    queries, results, pages, sources = _BUDGET_MATRIX[scope_value][depth_value]
    return ResearchBudget(
        max_queries=queries,
        max_results_per_query=results,
        max_pages=pages,
        max_sources=sources,
    )


@dataclass
class SourceRecord:
    """One ledger entry as returned by research.

    ``source_id`` is minted here; ``content_hash`` is ``sha256:<hex>`` over the bounded fetched
    text. ``claim_links`` are added later by the plan/lesson pipeline, not by research.
    """

    source_id: str
    url: str
    title: str
    publisher: str
    source_type: str
    fetched_at: str
    published_at: str | None
    content_hash: str
    support_status: str = "unverified"
    claim_links: list[str] = field(default_factory=list)
    excerpt: str = ""
    query: str = ""
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchRun:
    """Outcome of a bounded research pass. ``status`` is never silently ``ok``.

    ``failures`` is the per-URL half of the ledger: a fetch that failed is recorded with its URL,
    the query that found it and the error, so a partial pass is auditable instead of reduced to
    one reason string. No failure entry is ever promoted into a source.
    """

    status: str  # "ok" | "degraded" | "unavailable"
    queries: list[dict[str, Any]]
    sources: list[SourceRecord]
    reason: str | None = None
    failures: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "queries": [dict(q) for q in self.queries],
            "sources": [s.to_dict() for s in self.sources],
            "reason": self.reason,
            "failures": [dict(item) for item in self.failures],
        }


class SearchSeam(Protocol):
    """The injected search/extract interface. Both calls are bounded by the caller."""

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:  # pragma: no cover - protocol
        ...

    def fetch(self, url: str, max_chars: int) -> dict[str, Any]:  # pragma: no cover - protocol
        ...


class NullSearch:
    """Explicitly unavailable seam. Research fails honestly instead of guessing URLs."""

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        raise ResearchUnavailable("no search backend is wired into this process")

    def fetch(self, url: str, max_chars: int) -> dict[str, Any]:
        raise ResearchUnavailable("no extract backend is wired into this process")


class HermesToolSearch:
    """Production adapter over the host's own ``web_search`` / ``web_extract`` tools.

    ``host`` is the plugin ``ctx`` (an object with ``dispatch_tool``). Using the host tools means
    Coursebook inherits the active search provider, the user's egress configuration, and the
    extract-side SSRF/secret checks. It also means this adapter only works where ``ctx`` exists —
    i.e. the agent process, not the dashboard backend loaded by path (see ``docs/GENERATION.md``).
    """

    def __init__(self, host: Any, *, timeout_s: float | dict[str, float] | None = None) -> None:
        if not callable(getattr(host, "dispatch_tool", None)):
            raise ResearchUnavailable("host context exposes no dispatch_tool; research seam unavailable")
        self._host = host
        #: Explicit deadline(s) for tests; production resolves per tool from policy.
        self._timeouts = timeout_s

    @classmethod
    def from_ctx(cls, ctx: Any, **kwargs: Any) -> "HermesToolSearch":
        return cls(ctx, **kwargs)

    def _deadline(self, tool: str) -> float:
        if isinstance(self._timeouts, dict):
            value = self._timeouts.get(tool)
            if value is not None:
                return float(value)
        elif self._timeouts is not None:
            return float(self._timeouts)
        return research_tool_timeout_s(tool)

    def _dispatch(self, tool: str, arguments: dict[str, Any]) -> Any:
        """Call one host tool under a real deadline (H-66).

        The host is free to ignore a forwarded timeout, and a blocked tool call cannot be
        interrupted from Python, so the adapter enforces its own wall clock through the bounded
        pool. Overrun is a typed :class:`ResearchTimeout`; a fully stuck pool is
        :class:`ResearchUnavailable` — never an unbounded wait.

        ``dispatch_tool`` answering ``Unknown tool`` means the host registry in this process never
        registered the tool (a serve/dashboard process loads plugins but not the agent's tool
        setup). :func:`ensure_host_tools` registers the host's own handlers, then the call is
        retried once; nothing is invented if that fails (H-63 D-H63-1).
        """
        raw = self._call_bounded(tool, arguments)
        payload = _loads_tool_json(raw)
        if str(payload.get("error") or "").startswith(_UNKNOWN_TOOL) and ensure_host_tools():
            raw = self._call_bounded(tool, arguments)
        return raw

    def _call_bounded(self, tool: str, arguments: dict[str, Any]) -> Any:
        try:
            return run_bounded(
                lambda: self._host.dispatch_tool(tool, arguments),
                timeout_s=self._deadline(tool),
                label=tool,
            )
        except DeadlineExceeded as exc:
            raise ResearchTimeout(
                f"{tool} exceeded its {exc.deadline_s:g}s deadline; research cannot wait",
                tool=tool,
                deadline_s=exc.deadline_s,
            ) from exc
        except CallCapacityExhausted as exc:
            raise ResearchUnavailable(str(exc)) from exc

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        raw = self._dispatch("web_search", {"query": query, "limit": int(limit)})
        payload = _loads_tool_json(raw)
        error = _tool_error(payload)
        if error:
            raise ResearchUnavailable(_bound(error, _MAX_REASON))
        rows = ((payload.get("data") or {}).get("web")) or []
        results: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "").strip()
            if not _is_http_url(url):
                continue
            results.append(
                {
                    "url": url,
                    "title": _bound(str(row.get("title") or url), _MAX_TITLE),
                    "description": _bound(str(row.get("description") or ""), _MAX_DESCRIPTION),
                }
            )
        return results[:limit]

    def fetch(self, url: str, max_chars: int) -> dict[str, Any]:
        raw = self._dispatch("web_extract", {"urls": [url], "char_limit": int(max_chars)})
        payload = _loads_tool_json(raw)
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            raise ResearchUnavailable(
                _bound(_tool_error(payload) or "web_extract returned nothing", _MAX_REASON)
            )
        entry = results[0]
        if not isinstance(entry, dict) or entry.get("error"):
            raise ResearchUnavailable(
                _bound(str((entry or {}).get("error") or "web_extract failed for this URL"), _MAX_REASON)
            )
        content = entry.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ResearchUnavailable("extracted page had no text")
        return {
            "url": str(entry.get("url") or url),
            "title": _bound(str(entry.get("title") or ""), _MAX_TITLE) or None,
            "publisher": _bound(str(entry.get("publisher") or ""), _MAX_PUBLISHER) or None,
            "published_at": _normalize_timestamp(entry.get("published_at")),
            "content": content,
        }


# ── Host seam binding (agent half) ──────────────────────────────────────────
#
# ``register(ctx)`` in the plugin entry point binds the host object once. The job executor then
# asks for :func:`host_search`; an unbound (or unusable) host yields ``None``, which
# ``run_research`` records honestly as ``status="unavailable"`` rather than inventing a source.

#: The registry's unknown-tool body. ``tools.registry.dispatch`` answers a missing handler with
#: ``{"error": "Unknown tool: <name>"}`` — not the ``{"success": false, ...}`` shape the web tools
#: themselves return. Reading only ``success`` made that body look like a successful empty search
#: and hid the missing seam (H-63 D-H63-1).
_UNKNOWN_TOOL = "Unknown tool"

_HOST_SEAM: Any = None

#: Result of :func:`ensure_host_tools`, cached: one import attempt per process.
_HOST_TOOLS: bool | None = None


def _tool_error(payload: dict[str, Any]) -> str | None:
    """The error a host tool result carries, in either host shape.

    ``web_search_tool`` returns ``{"success": false, "error": ...}``; a registry-level dispatch
    failure (unknown tool, a handler raising) returns the bare ``tool_error`` body
    ``{"error": ...}``. Both are failures, never an empty result set.
    """
    if payload.get("success") is False:
        return str(payload.get("error") or "host tool reported failure")
    if payload.get("error") and not payload.get("data") and not payload.get("results"):
        return str(payload.get("error"))
    return None


def ensure_host_tools() -> bool:
    """Register the host's own web tools in this process when the seam cannot see them.

    A ``hermes serve`` / dashboard process loads plugins but never runs the agent's tool setup, so
    ``ctx.dispatch_tool("web_search", ...)`` answers ``Unknown tool`` there and every plan authored
    by that process carries zero sources (H-63 D-H63-1). Importing the host's own tool module
    registers the same handlers the agent would dispatch — provider selection, egress rules and
    SSRF checks stay the host's own; the plugin still never reads a provider key.

    Returns whether the import succeeded. False is honest: the unknown-tool failure is then
    recorded in the research ledger instead of being mistaken for an empty search.
    """
    global _HOST_TOOLS
    if _HOST_TOOLS is not None:
        return _HOST_TOOLS
    try:
        import tools.web_tools  # noqa: F401 - registers web_search/web_extract handlers
    except Exception:  # noqa: BLE001 - a bare test host has no agent tool package
        _HOST_TOOLS = False
        return False
    _HOST_TOOLS = True
    return True


def bind_host_seam(host: Any) -> None:
    """Bind the plugin ``ctx`` so research can use the host's own search/extract tools."""
    global _HOST_SEAM
    _HOST_SEAM = host


def host_search() -> "HermesToolSearch | None":
    """The host-backed seam, or ``None`` when this process has no usable host tools."""
    if _HOST_SEAM is None:
        return None
    try:
        return HermesToolSearch.from_ctx(_HOST_SEAM)
    except ResearchUnavailable:
        return None


# ── Query derivation ────────────────────────────────────────────────────────


def derive_queries(
    goal: str,
    *,
    recipe: str = "casual",
    dials: dict[str, Any] | None = None,
    locale: str | None = None,
    max_queries: int = 4,
    subject_domain: str | None = None,
    level: str | None = None,
) -> list[str]:
    """Derive a small, deterministic query set. Never random, never unbounded.

    The first query is always the goal itself; later variants add the one qualifier that the
    declared subject domain, recipe or locale actually needs.

    ``subject_domain`` is what the course is *about*; ``locale`` is the language of delivery.
    They are not interchangeable (P0-4): before v10 a Spanish brake-pad brief handed a locale
    and no domain, so research treated it as a language course. When a domain is declared the
    domain qualifier is used, and the locale-derived language query is only added for a
    language course.

    Depth means what the contract says it means:

    * ``survey`` — the goal itself only;
    * ``working`` — the goal plus the one recipe qualifier the brief actually needs;
    * ``deep`` — those plus reference/documentation, official-guidance, common-mistake and
      practice queries, and a locale-aware query when a locale is declared.

    ``overview``/``thorough`` are documented aliases for ``survey``/``deep``; any other value
    raises. The caller's ``max_queries`` (the budget cell) is the hard ceiling.
    """
    dials = dict(dials or {})
    base = _bound(" ".join(str(goal).split()), _MAX_QUERY)
    if not base:
        raise ValueError("cannot derive research queries from an empty goal")
    depth = normalize_depth(dials.get("depth"))
    domain = (
        policy.normalise_subject_domain(subject_domain, locale)
        if subject_domain and str(subject_domain).strip()
        else None
    )
    queries = [base]
    if depth != "survey":
        qualifier = _domain_qualifier(domain, level)
        if qualifier is not None:
            queries.append(f"{base} {qualifier}")
        elif recipe == "one_off":
            queries.append(f"{base} official instructions safety")
        elif recipe == "committed":
            queries.append(f"{base} syllabus learning objectives")
        elif recipe == "companion":
            queries.append(f"{base} course outline exam")
        elif recipe == "parent":
            queries.append(f"{base} lesson plan for children")
        else:
            queries.append(f"{base} beginner guide")
        # A course is not a list of topics. Ask how the subject is sequenced and what has
        # to come first, before the generic reference/glossary questions can consume the
        # bounded budget. Survey depth stays deliberately one query, and a one-off brief
        # keeps its bounded speed rather than paying for a full curriculum pass.
        if recipe != "one_off":
            queries.extend(
                curriculum.curriculum_queries(
                    base, domain=domain, level=level, locale=locale
                )
            )
    if depth == "deep":
        # A declared non-language domain is never researched as a language question, even
        # when the delivery locale is set. The language query is kept early so a bounded
        # budget cell can never truncate it away.
        if locale and (domain is None or domain == "language"):
            queries.append(f"{base} {_language_name(locale)} reference")
        queries.append(f"{base} reference documentation")
        queries.append(f"{base} official guidance")
        queries.append(f"{base} common mistakes")
        queries.append(f"{base} examples and practice")
        queries.append(f"{base} step by step")
        queries.append(f"{base} glossary")
    unique: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = query.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(_bound(query, _MAX_QUERY))
        if len(unique) >= max(1, min(int(max_queries), 12)):
            break
    return unique


#: One qualifier per canonical subject domain. These are research questions about the subject,
#: not about the language the lesson will be delivered in. An unknown domain falls back to the
#: recipe qualifier rather than inventing a category.
_DOMAIN_QUALIFIERS: dict[str, str] = {
    "technical_procedure": "official procedure steps safety limits",
    "mathematics": "definitions worked examples",
    "grammar": "grammar rules examples",
    "history": "primary sources dates",
    "language": "learner vocabulary phrases",
}


def _domain_qualifier(domain: str | None, level: str | None) -> str | None:
    """The subject qualifier for a declared domain, or ``None`` when the recipe owns it."""
    if domain is None:
        return None
    qualifier = _DOMAIN_QUALIFIERS.get(domain)
    if qualifier is None:
        return None
    if domain == "language" and level and str(level).strip():
        return f"{str(level).strip()} level {qualifier}"
    return qualifier


# ── The bounded pass ────────────────────────────────────────────────────────


def run_research(
    goal: str,
    *,
    recipe: str = "casual",
    dials: dict[str, Any] | None = None,
    locale: str | None = None,
    subject_domain: str | None = None,
    level: str | None = None,
    scope: str | None = None,
    search: SearchSeam | None = None,
    budget: ResearchBudget | None = None,
    now: datetime | None = None,
    mint_id: Any = None,
    cancel_probe: Any = None,
) -> ResearchRun:
    """Run one bounded research pass and return the ledger rows it produced.

    The depth dial and course scope choose an executable budget cell via :func:`budget_for`.
    An explicit ``budget`` still wins (tests and the research worker pass one).

    Failure policy, in order of honesty:

    * no seam at all -> ``status="unavailable"`` with zero sources (the plan may still be
      proposed from model knowledge, every claim marked ``unverified``);
    * a seam that errors on every query -> ``status="unavailable"`` with the recorded errors;
    * a seam that yields some sources -> ``status="ok"`` or ``"degraded"`` when fetches failed.

    No branch invents a URL, a title or a fetch date. ``subject_domain`` and ``level`` are the
    declared cb.rpc v10 inputs; they shape the query set, never the provenance rules.
    """
    dials = dict(dials or {})
    # A course size buys a floor. Keep the caller's closed dials object untouched (the plan
    # document records exactly what the learner sent); only the effective pass uses the raised
    # depth. An explicit budget still wins as the ceiling.
    effective_dials = dict(dials)
    effective_dials["depth"] = effective_depth(dials.get("depth"), scope)
    budget = budget or budget_for(effective_dials.get("depth"), scope)
    now = now or datetime.now(timezone.utc)
    mint_id = mint_id or _mint_id
    fetched_at = _iso(now)

    if search is None or isinstance(search, NullSearch):
        return ResearchRun(
            status="unavailable",
            queries=[],
            sources=[],
            reason="no search/extract seam is wired; plan claims will be marked unverified",
        )

    try:
        queries = derive_queries(
            goal,
            recipe=recipe,
            dials=effective_dials,
            locale=locale,
            max_queries=budget.max_queries,
            subject_domain=subject_domain,
            level=level,
        )
    except ValueError as exc:
        return ResearchRun(status="unavailable", queries=[], sources=[], reason=_bound(str(exc), _MAX_REASON))

    records: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for query_index, query in enumerate(queries):
        if callable(cancel_probe) and cancel_probe():
            raise ResearchCancelled("job cancelled before the next search call")
        entry: dict[str, Any] = {"query": query, "result_count": 0, "error": None}
        try:
            results = search.search(query, budget.max_results_per_query)
        except ResearchCancelled:
            raise
        except ResearchTimeout as exc:
            # A host tool that missed its deadline is very likely stuck; spending the rest of
            # the query budget waiting on it would turn one bounded call into many.
            entry["error"] = _bound(str(exc), _MAX_REASON)
            records.append(entry)
            break
        except ResearchUnavailable as exc:
            entry["error"] = _bound(str(exc), _MAX_REASON)
            records.append(entry)
            continue
        except Exception as exc:  # noqa: BLE001 - a provider bug is a recorded failure
            entry["error"] = _bound(f"{type(exc).__name__}: {exc}", _MAX_REASON)
            records.append(entry)
            continue
        entry["result_count"] = len(results or [])
        records.append(entry)
        # Collect *all* candidates, not just the first page's worth: selection below ranks them
        # by what kind of publisher the URL names, so an official page found by the last query
        # can still be fetched. The search calls themselves stay bounded by the budget.
        for position, row in enumerate(results or []):
            url = str((row or {}).get("url") or "").strip()
            if not _is_http_url(url) or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(
                {
                    "url": url,
                    "title": (row or {}).get("title") or "",
                    "query": query,
                    "query_index": query_index,
                    "position": position,
                }
            )

    # Selection preference: government/academic/reference/documentation pages before generic web
    # pages, stable within a rank by query order. This is a fact about the URL, not a claim that
    # the page is correct — support status stays ``unverified`` for every row.
    candidates.sort(
        key=lambda item: (
            SOURCE_TYPE_RANK.get(_classify_source(item["url"]), len(SOURCE_TYPE_RANK)),
            item["query_index"],
            item["position"],
        )
    )

    sources: list[SourceRecord] = []
    failures: list[dict[str, str]] = []
    for candidate in candidates[: budget.max_pages]:
        if len(sources) >= budget.max_sources:
            break
        if callable(cancel_probe) and cancel_probe():
            raise ResearchCancelled("job cancelled before the next extract call")
        try:
            page = search.fetch(candidate["url"], budget.max_page_chars)
        except ResearchCancelled:
            raise
        except ResearchTimeout as exc:
            failures.append(
                {"url": candidate["url"], "query": str(candidate.get("query") or ""), "error": _bound(str(exc), _MAX_REASON)}
            )
            break
        except ResearchUnavailable as exc:
            failures.append(
                {"url": candidate["url"], "query": str(candidate.get("query") or ""), "error": _bound(str(exc), _MAX_REASON)}
            )
            continue
        except Exception as exc:  # noqa: BLE001
            failures.append(
                {
                    "url": candidate["url"],
                    "query": str(candidate.get("query") or ""),
                    "error": _bound(f"{type(exc).__name__}: {exc}", _MAX_REASON),
                }
            )
            continue
        content = str(page.get("content") or "")
        if not content.strip():
            failures.append(
                {"url": candidate["url"], "query": str(candidate.get("query") or ""), "error": "empty extract"}
            )
            continue
        truncated = len(content) > budget.max_page_chars
        bounded = content[: budget.max_page_chars]
        url = str(page.get("url") or candidate["url"])
        publisher = page.get("publisher") or _publisher_of(url)
        sources.append(
            SourceRecord(
                source_id=mint_id(),
                url=url,
                title=_bound(str(page.get("title") or candidate.get("title") or url), _MAX_TITLE),
                publisher=_bound(str(publisher), _MAX_PUBLISHER),
                source_type=_classify_source(url),
                fetched_at=fetched_at,
                published_at=_normalize_timestamp(page.get("published_at")),
                content_hash=sha256_of_text(bounded),
                support_status="unverified",
                excerpt=_excerpt(bounded, budget.max_excerpt_chars),
                query=str(candidate.get("query") or ""),
                truncated=truncated,
            )
        )

    if not sources:
        reason = "no source could be fetched"
        if failures:
            reason += f"; {len(failures)} fetch failure(s), first: {failures[0]['url']}: {failures[0]['error']}"
        else:
            search_errors = [entry["error"] for entry in records if entry.get("error")]
            if search_errors:
                reason += f"; search failed: {search_errors[0]}"
        return ResearchRun(
            status="unavailable",
            queries=records,
            sources=[],
            reason=_bound(reason, _MAX_REASON),
            failures=failures,
        )
    reason = None
    if failures:
        reason = _bound(
            f"{len(failures)} fetch failure(s); first: {failures[0]['url']}: {failures[0]['error']}",
            _MAX_REASON,
        )
    return ResearchRun(
        status="degraded" if failures else "ok",
        queries=records,
        sources=sources,
        reason=reason,
        failures=failures,
    )


def _normalize_quote(text: Any) -> str:
    """Whitespace-normalised text used for exact quote matching. No fuzzy tolerance."""
    return " ".join(str(text or "").split())


#: A validator must quote at least this many characters for a verdict to count as a link. It is
#: a floor against a one-word "quote", not a claim that a short quote proves anything.
MIN_CLAIM_EXCERPT_CHARS = 12

#: Statuses that may move a source off ``unverified``. Every one of them needs an explicit link.
UPGRADE_STATUSES = frozenset({"partial", "supported", "contradictory"})


def claim_verdict_link_problem(
    verdict: dict[str, Any],
    source: SourceRecord | None,
) -> str | None:
    """Why a validator verdict cannot upgrade support, or ``None`` when the link is explicit.

    The rule is deterministic: a non-``unverified`` verdict needs (a) a ``source_id`` present in
    the ledger and (b) a verbatim quote from that source's fetched excerpt — ``evidence_quote``
    (the field the validation schema asks for) or its older alias ``excerpt`` — that occurs in
    the stored text after whitespace collapsing. A source id alone is provenance, never support.
    The validator cannot link a claim to text the ledger did not fetch.
    """
    status = verdict.get("support")
    if status not in UPGRADE_STATUSES:
        return "status does not upgrade support"
    if source is None:
        return "source id is absent from the ledger"
    quote = verdict.get("evidence_quote")
    if quote is None:
        quote = verdict.get("excerpt")
    if not isinstance(quote, str):
        return "no verbatim evidence quote was provided"
    needle = _normalize_quote(quote)
    if len(needle) < MIN_CLAIM_EXCERPT_CHARS:
        return f"quoted evidence is shorter than {MIN_CLAIM_EXCERPT_CHARS} characters"
    if needle not in _normalize_quote(source.excerpt):
        return "quoted evidence does not occur in the fetched source text"
    return None


def apply_support_verdicts(
    sources: Iterable[SourceRecord],
    verdicts: Iterable[dict[str, Any]],
    *,
    independent: bool = False,
) -> list[SourceRecord]:
    """Move source support from ``unverified`` using *linked* validator claim verdicts only.

    Two conditions are required, and neither is a model's opinion of itself:

    * ``independent`` — the validator's model identity differs from the author's. A same-model
      "validator" is a second prompt, not a second opinion, so it may not move the ledger at all.
    * a **deterministic claim link** — the verdict carries an ``evidence_quote`` that, after
      whitespace/case normalisation, appears verbatim in the fetched ``excerpt``. A fabricated
      quote does not match, so the source stays ``unverified``.

    A source with no verdict stays ``unverified``; a ``contradictory`` verdict wins over
    ``supported`` because conflicting evidence is the fact worth surfacing. Provenance never
    upgrades support on its own: every non-``unverified`` verdict must name a ledger source and
    quote an ``evidence_quote`` of at least 12 characters that occurs verbatim in that source's
    stored excerpt (see :func:`claim_verdict_link_problem`), and a same-model pass never upgrades
    it either. An accepted verdict appends its claim reference to ``source.claim_links``.
    """
    by_id = {source.source_id: source for source in sources}
    if not independent:
        # Explicitly refused, never silently skipped: the ledger is the artifact a learner reads.
        return list(by_id.values())
    rank = {"unverified": 0, "partial": 1, "supported": 2, "contradictory": 3}
    for verdict in verdicts or []:
        source_id = verdict.get("source_id")
        status = verdict.get("support")
        if not source_id or source_id not in by_id or status not in SUPPORT_STATUSES:
            continue
        source = by_id[source_id]
        if claim_verdict_link_problem(verdict, source) is not None:
            continue
        if rank[status] > rank.get(source.support_status, 0):
            source.support_status = status
        item = verdict.get("item")
        if isinstance(item, str) and item.strip() and item.strip() not in source.claim_links:
            source.claim_links.append(item.strip())
    return list(by_id.values())


def support_status_for_contract(status: str) -> str:
    """Map a generation support status onto the frozen ``cb.vocabulary`` enum."""
    if status not in CONTRACT_SUPPORT_STATUS:
        raise ValueError(f"unknown support status {status!r}")
    return CONTRACT_SUPPORT_STATUS[status]


# ── small helpers ───────────────────────────────────────────────────────────


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_of_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mint_id() -> str:
    import secrets

    return secrets.token_hex(8)


def _iso(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bound(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _excerpt(text: str, limit: int) -> str:
    """A content-first slice of the fetched page, whitespace-collapsed and bounded.

    Extraction returns the whole page; the first characters are frequently a site header or a
    navigation menu (NASA's starts ``Search ## Suggested Searches - [Artemis](…)``). An excerpt
    that stops inside that menu cannot carry a claim, so the leading chrome lines are skipped
    before the window is taken. The skip is deliberately narrow — blank lines, an explicit
    search/nav banner, and link-list lines — so real prose is never discarded.
    """
    lines = text.splitlines()
    start = 0
    while start < len(lines):
        stripped = lines[start].strip()
        if not stripped:
            start += 1
            continue
        low = stripped.casefold()
        is_chrome = (
            low.startswith("search")
            or "suggested searches" in low
            or "an official website of the united states government" in low
            or low.startswith("ask ")  # "Ask DOI Anything - How Can We Help?"
            or stripped.startswith(("- [", "* [", "* * *"))
            or (stripped.startswith("[") and "](" in stripped)
        )
        if is_chrome:
            start += 1
            continue
        break
    body = "\n".join(lines[start:])
    collapsed = " ".join(body.split())
    return collapsed[:limit]


def _loads_tool_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ResearchUnavailable("host tool returned a non-JSON result")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResearchUnavailable(f"host tool returned malformed JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ResearchUnavailable("host tool returned a non-object result")
    return payload


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _publisher_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _classify_source(url: str) -> str:
    """Classify *who publishes this URL* from the host/path alone.

    The type is a fallible URL fact recorded in the ledger, not a judgement of authority or
    correctness. It drives which candidates are fetched first when the page budget binds.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host.endswith(".gov") or ".gov." in host or host.endswith(".mil") or host.endswith(".int"):
        return "government"
    if host.endswith(".edu") or ".edu." in host or ".ac." in host:
        return "academic"
    if any(
        name in host
        for name in ("wikipedia.org", "britannica.com", "dictionary.com", "merriam-webster.com")
    ):
        return "reference"
    if (
        host.startswith(("docs.", "developer.", "support."))
        or host in ("w3.org", "www.w3.org", "rfc-editor.org", "www.rfc-editor.org", "ietf.org", "www.ietf.org")
        or path.startswith(("/docs/", "/documentation/", "/reference/"))
    ):
        return "documentation"
    if host.endswith(".org") or ".org." in host:
        return "organization"
    return "web_page"


def _language_name(locale: str) -> str:
    primary = str(locale).split("-")[0].lower()
    return {
        "ja": "Japanese",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "ko": "Korean",
        "zh": "Chinese",
        "ar": "Arabic",
    }.get(primary, primary)


_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$")


def _normalize_timestamp(value: Any) -> str | None:
    """Keep a real publication date, or ``None``. Never guess one."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or not _TIMESTAMP_RE.match(text):
        return None
    text = text.replace(" ", "T")
    if text.endswith("Z"):
        return text
    if re.search(r"[+-]\d{2}:?\d{2}$", text):
        return text if ":" in text[-6:] else text[:-5] + text[-5:-2] + ":" + text[-2:]
    return text + "Z" if "T" in text else text + "T00:00:00Z"
