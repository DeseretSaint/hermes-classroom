#!/usr/bin/env python3
"""H-191: rebuild the plan-validation request a stored live job built, without calling a provider.

The H-187 runs kept their isolated homes. ``gen_plan_documents`` holds the exact plan candidate and
research ledger the validator was handed, and ``jobs.brief_json`` holds the brief. This module
replays ``coursebook.generation.build_plan_validation_requests`` with those stored inputs so the
*exact* request the job built can be measured (bytes, prompt version, schema name, ``max_tokens``,
``_request_bound``) instead of guessed.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace


def load_json(text: str | None) -> dict:
    try:
        value = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def import_coursebook(source: str, agent_root: str):
    for path in (agent_root, source):
        if path and path not in sys.path:
            sys.path.insert(0, path)
    from coursebook import generation  # noqa: PLC0415
    from coursebook.research import ResearchRun, SourceRecord  # noqa: PLC0415

    return SimpleNamespace(
        generation=generation, ResearchRun=ResearchRun, SourceRecord=SourceRecord
    )


def read_stored(db_path: str) -> dict:
    """Read one stored plan job: the newest plan document row and the newest plan brief."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    doc = connection.execute(
        "SELECT * FROM gen_plan_documents ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    job = connection.execute(
        "SELECT * FROM jobs WHERE kind = 'plan' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    rows = {
        "plan_id": (doc["plan_id"] if doc else None),
        "generation_state": (doc["generation_state"] if doc else None),
        "created_at": (doc["created_at"] if doc else None),
        "validation_id": (doc["validation_id"] if doc else None),
        "document": load_json(doc["document_json"] if doc else None),
        "research": load_json(doc["research_json"] if doc else None),
        "brief": load_json(job["brief_json"] if job else None),
    }
    connection.close()
    return rows


def research_run_from_stored(rows: dict, modules) -> object:
    research = rows["research"]
    sources = [
        modules.SourceRecord(
            source_id=str(entry.get("source_id") or ""),
            url=str(entry.get("url") or ""),
            title=str(entry.get("title") or ""),
            publisher=str(entry.get("publisher") or ""),
            source_type=str(entry.get("source_type") or ""),
            fetched_at=str(entry.get("fetched_at") or ""),
            published_at=entry.get("published_at"),
            content_hash=str(entry.get("content_hash") or ""),
            support_status=str(entry.get("support_status") or "unverified"),
            claim_links=list(entry.get("claim_links") or []),
            excerpt=str(entry.get("excerpt") or ""),
            query=str(entry.get("query") or ""),
            truncated=bool(entry.get("truncated")),
        )
        for entry in research.get("sources") or []
    ]
    return modules.ResearchRun(
        status=str(research.get("status") or "unavailable"),
        queries=list(research.get("queries") or []),
        sources=sources,
        reason=research.get("reason"),
        failures=list(research.get("failures") or []),
    )


def rebuild(db_path: str, source: str, agent_root: str) -> dict:
    """Return ``{"request": LLMRequest, "scope": str, "bound": int, "stored": {...}}``."""
    modules = import_coursebook(source, agent_root)
    rows = read_stored(db_path)
    stored = rows["document"]
    plan = stored.get("plan") if isinstance(stored.get("plan"), dict) else stored
    if not isinstance(plan, dict):
        raise SystemExit(f"no plan object in the newest plan document of {db_path}")
    brief = rows["brief"]
    scope = stored.get("scope") or brief.get("scope")
    requests = modules.generation.build_plan_validation_requests(
        plan=plan,
        goal=brief.get("goal") or "",
        recipe=brief.get("recipe") or stored.get("recipe") or "",
        dials=stored.get("dials") or brief.get("dials") or {},
        locale=stored.get("locale"),
        research_run=research_run_from_stored(rows, modules),
        level=stored.get("level"),
        subject_domain=stored.get("subject_domain"),
        scope=scope,
        parent_brief=stored.get("parent_brief"),
    )
    return {
        "request": requests[0],
        "requests": requests,
        "scope": scope,
        "bound": modules.generation._request_bound(scope),
        "stored": rows,
        "modules": modules,
    }
