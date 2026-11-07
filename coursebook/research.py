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

Provenance is not support. A fetched source starts at ``unverified`` and only a *separate*
validation pass may move it to ``supported`` / ``partial`` / ``contradictory`` through
:func:`apply_support_verdicts`. A model asserting its own citation support is not evidence.

The search/extract seam is injected. The production adapter is :class:`HermesToolSearch`, which
uses the host's own ``web_search`` / ``web_extract`` tools through ``ctx.dispatch_tool`` so the
plugin inherits the user's configured backend, egress rules and SSRF checks instead of calling a
vendor API with a raw key.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Protocol
from urllib.parse import urlparse

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
    "ResearchBudgetExceeded",
    "SourceRecord",
    "ResearchRun",
    "SearchSeam",
    "HermesToolSearch",
    "NullSearch",
    "budget_for",
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
_MAX_EXCERPT = 600
_MAX_SOURCE_TYPE = 40
_MAX_QUERY = 220
_MAX_REASON = 300


class ResearchUnavailable(RuntimeError):
    """No usable search/extract seam is wired in this process.

    Callers must not degrade silently: a plan may still be proposed from model knowledge, but
    every claim is then labelled ``unverified`` and the research block says ``unavailable``.
    """


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

    def __init__(self, host: Any) -> None:
        if not callable(getattr(host, "dispatch_tool", None)):
            raise ResearchUnavailable("host context exposes no dispatch_tool; research seam unavailable")
        self._host = host

    @classmethod
    def from_ctx(cls, ctx: Any) -> "HermesToolSearch":
        return cls(ctx)

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        raw = self._host.dispatch_tool("web_search", {"query": query, "limit": int(limit)})
        payload = _loads_tool_json(raw)
        if payload.get("success") is False:
            raise ResearchUnavailable(_bound(str(payload.get("error") or "web_search failed"), _MAX_REASON))
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
                    "description": _bound(str(row.get("description") or ""), _MAX_EXCERPT),
                }
            )
        return results[:limit]

    def fetch(self, url: str, max_chars: int) -> dict[str, Any]:
        raw = self._host.dispatch_tool("web_extract", {"urls": [url], "char_limit": int(max_chars)})
        payload = _loads_tool_json(raw)
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            raise ResearchUnavailable(_bound(str(payload.get("error") or "web_extract returned nothing"), _MAX_REASON))
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

_HOST_SEAM: Any = None


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
) -> list[str]:
    """Derive a small, deterministic query set. Never random, never unbounded.

    Depth now means what the contract says it means:

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
    queries = [base]
    if depth != "survey":
        if recipe == "one_off":
            queries.append(f"{base} official instructions safety")
        elif recipe == "committed":
            queries.append(f"{base} syllabus learning objectives")
        elif recipe == "companion":
            queries.append(f"{base} course outline exam")
        elif recipe == "parent":
            queries.append(f"{base} lesson plan for children")
        else:
            queries.append(f"{base} beginner guide")
    if depth == "deep":
        queries.append(f"{base} reference documentation")
        queries.append(f"{base} official guidance")
        if locale:
            queries.append(f"{base} {_language_name(locale)} reference")
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


# ── The bounded pass ────────────────────────────────────────────────────────


def run_research(
    goal: str,
    *,
    recipe: str = "casual",
    dials: dict[str, Any] | None = None,
    locale: str | None = None,
    scope: str | None = None,
    search: SearchSeam | None = None,
    budget: ResearchBudget | None = None,
    now: datetime | None = None,
    mint_id: Any = None,
) -> ResearchRun:
    """Run one bounded research pass and return the ledger rows it produced.

    The depth dial and course scope choose an executable budget cell via :func:`budget_for`.
    An explicit ``budget`` still wins (tests and the research worker pass one).

    Failure policy, in order of honesty:

    * no seam at all -> ``status="unavailable"`` with zero sources (the plan may still be
      proposed from model knowledge, every claim marked ``unverified``);
    * a seam that errors on every query -> ``status="unavailable"`` with the recorded errors;
    * a seam that yields some sources -> ``status="ok"`` or ``"degraded"`` when fetches failed.

    No branch invents a URL, a title or a fetch date.
    """
    dials = dict(dials or {})
    budget = budget or budget_for(dials.get("depth"), scope)
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

    queries = derive_queries(goal, recipe=recipe, dials=dials, locale=locale, max_queries=budget.max_queries)

    records: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for query_index, query in enumerate(queries):
        entry: dict[str, Any] = {"query": query, "result_count": 0, "error": None}
        try:
            results = search.search(query, budget.max_results_per_query)
        except ResearchCancelled:
            raise
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
        try:
            page = search.fetch(candidate["url"], budget.max_page_chars)
        except ResearchCancelled:
            raise
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


def apply_support_verdicts(
    sources: Iterable[SourceRecord],
    verdicts: Iterable[dict[str, Any]],
) -> list[SourceRecord]:
    """Move source support from ``unverified`` using *validator* claim verdicts only.

    A source with no verdict stays ``unverified``; a ``contradictory`` verdict wins over
    ``supported`` because conflicting evidence is the fact worth surfacing. Provenance never
    upgrades support on its own.
    """
    by_id = {source.source_id: source for source in sources}
    rank = {"unverified": 0, "partial": 1, "supported": 2, "contradictory": 3}
    for verdict in verdicts or []:
        source_id = verdict.get("source_id")
        status = verdict.get("support")
        if not source_id or source_id not in by_id or status not in SUPPORT_STATUSES:
            continue
        source = by_id[source_id]
        if rank[status] > rank.get(source.support_status, 0):
            source.support_status = status
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
    collapsed = " ".join(text.split())
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
