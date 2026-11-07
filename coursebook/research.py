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

from . import policy

__all__ = [
    "SUPPORT_STATUSES",
    "CONTRACT_SUPPORT_STATUS",
    "ResearchBudget",
    "ResearchUnavailable",
    "ResearchBudgetExceeded",
    "SourceRecord",
    "ResearchRun",
    "SearchSeam",
    "HermesToolSearch",
    "NullSearch",
    "derive_queries",
    "run_research",
    "apply_support_verdicts",
    "support_status_for_contract",
    "canonical_json",
    "sha256_of_text",
]

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
    """Executable ceilings. Every field is checked before the call it bounds."""

    max_queries: int = 4
    max_results_per_query: int = 5
    max_pages: int = 6
    max_sources: int = 6
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
    """Outcome of a bounded research pass. ``status`` is never silently ``ok``."""

    status: str  # "ok" | "degraded" | "unavailable"
    queries: list[dict[str, Any]]
    sources: list[SourceRecord]
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "queries": [dict(q) for q in self.queries],
            "sources": [s.to_dict() for s in self.sources],
            "reason": self.reason,
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
    subject_domain: str | None = None,
    level: str | None = None,
) -> list[str]:
    """Derive a small, deterministic query set. Never random, never unbounded.

    The first query is always the goal itself; later variants add the one qualifier that the
    declared subject domain, recipe or locale actually needs. ``dials["depth"] == "overview"``
    keeps only the base query, which is the cheapest honest option.

    ``subject_domain`` is what the course is *about*; ``locale`` is the language of delivery.
    They are not interchangeable (P0-4): before v10 a Spanish brake-pad brief handed a locale
    and no domain, so research treated it as a language course. When a domain is declared the
    domain qualifier is used, and the locale-derived language query is only added for a
    language course.
    """
    dials = dict(dials or {})
    base = _bound(" ".join(str(goal).split()), _MAX_QUERY)
    if not base:
        raise ValueError("cannot derive research queries from an empty goal")
    depth = str(dials.get("depth") or "standard").lower()
    domain = (
        policy.normalise_subject_domain(subject_domain, locale)
        if subject_domain and str(subject_domain).strip()
        else None
    )
    queries = [base]
    if depth != "overview":
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
        if depth == "thorough":
            queries.append(f"{base} reference documentation")
            # A declared non-language domain is never researched as a language question, even
            # when the delivery locale is set.
            if locale and (domain is None or domain == "language"):
                queries.append(f"{base} {_language_name(locale)}")
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
    search: SearchSeam | None = None,
    budget: ResearchBudget | None = None,
    now: datetime | None = None,
    mint_id: Any = None,
) -> ResearchRun:
    """Run one bounded research pass and return the ledger rows it produced.

    Failure policy, in order of honesty:

    * no seam at all -> ``status="unavailable"`` with zero sources (the plan may still be
      proposed from model knowledge, every claim marked ``unverified``);
    * a seam that errors on every query -> ``status="unavailable"`` with the recorded errors;
    * a seam that yields some sources -> ``status="ok"`` or ``"degraded"`` when fetches failed.

    No branch invents a URL, a title or a fetch date. ``subject_domain`` and ``level`` are the
    declared cb.rpc v10 inputs; they shape the query set, never the provenance rules.
    """
    budget = budget or ResearchBudget()
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
            dials=dials,
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
    for query in queries:
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
        for row in results or []:
            url = str((row or {}).get("url") or "").strip()
            if not _is_http_url(url) or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append({"url": url, "title": (row or {}).get("title") or "", "query": query})
            if len(candidates) >= budget.max_pages:
                break
        if len(candidates) >= budget.max_pages:
            break

    sources: list[SourceRecord] = []
    failures: list[str] = []
    for candidate in candidates[: budget.max_pages]:
        if len(sources) >= budget.max_sources:
            break
        try:
            page = search.fetch(candidate["url"], budget.max_page_chars)
        except ResearchCancelled:
            raise
        except ResearchUnavailable as exc:
            failures.append(f"{candidate['url']}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{candidate['url']}: {type(exc).__name__}")
            continue
        content = str(page.get("content") or "")
        if not content.strip():
            failures.append(f"{candidate['url']}: empty extract")
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
        reason = "no source could be fetched" + (f": {failures[0]}" if failures else "")
        return ResearchRun(
            status="unavailable",
            queries=records,
            sources=[],
            reason=_bound(reason, _MAX_REASON),
        )
    return ResearchRun(
        status="degraded" if failures else "ok",
        queries=records,
        sources=sources,
        reason=_bound(failures[0], _MAX_REASON) if failures else None,
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
    host = urlparse(url).netloc.lower()
    if host.endswith(".gov") or ".gov." in host or host.endswith(".mil"):
        return "government"
    if host.endswith(".edu") or ".edu." in host or ".ac." in host:
        return "academic"
    if "wikipedia.org" in host or "britannica.com" in host:
        return "encyclopedia"
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
