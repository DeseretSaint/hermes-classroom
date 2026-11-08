#!/usr/bin/env python3
"""Build the H-187 evidence packet from the three per-scope captures.

Reads ``evidence/{single,short,full}.json`` (raw worker output), writes
``evidence/summary.json`` + ``evidence/manifest.json`` and prints the per-scope table.

Redaction is applied here, not in the capture: absolute paths under the isolated homes become
``<ISOLATED_HOME>/…`` and token counts become ``redacted``. Provider, model, call counts, source
counts and cost are kept, because those are the facts the card asks to record.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SCOPES = ("single", "short", "full")

_PATH_RE = re.compile(r"/home/[A-Za-z0-9._-]+/\.hermes/h187-live-gen/[a-z]+/home[^\s\"']*")
_TOKENS = ("input_tokens", "output_tokens", "total_tokens", "cache_read_tokens", "cache_write_tokens")


def redact(value):
    if isinstance(value, str):
        return _PATH_RE.sub("<ISOLATED_HOME>", value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in _TOKENS and isinstance(item, int):
                out[key] = "redacted"
            else:
                out[key] = redact(item)
        return out
    return value


def scope_row(tag: str, data: dict) -> dict:
    plan = (data.get("phases") or {}).get("plan") or {}
    facts = plan.get("facts") or {}
    generation = facts.get("generation") or {}
    research = facts.get("research") or {}
    approve = (data.get("phases") or {}).get("approve") or {}
    lessons = (data.get("phases") or {}).get("lessons") or {}
    page = ((data.get("phases") or {}).get("page") or {}).get("served") or {}
    validation = generation.get("validation") or {}
    record = generation.get("validation_record") or {}
    units = facts.get("units") or []
    objectives = facts.get("objectives") or []
    time_estimate = generation.get("time_estimate") or {}
    return {
        "scope": data.get("scope"),
        "recipe": data.get("recipe"),
        "tag": tag,
        "goal": data.get("goal"),
        "job_terminal_state": plan.get("terminal_state"),
        "plan_elapsed_s": plan.get("elapsed_s"),
        "plan_state": facts.get("plan_state"),
        "generation_state": generation.get("generation_state"),
        "plan_schema": generation.get("plan_schema"),
        "plan_hash": facts.get("plan_hash"),
        "objective_count": len(objectives),
        "unit_count": len(units),
        "units": [
            {"ordinal": unit.get("ordinal"), "title": unit.get("title"),
             "target_lessons": unit.get("target_lessons"),
             "prerequisite_refs": unit.get("prerequisite_refs")}
            for unit in units
        ],
        "time_estimate_weeks": time_estimate.get("weeks"),
        "check_plan_count": len(generation.get("check_plan") or []),
        "validation_verdict": generation.get("validation_verdict"),
        "validation_outcome": validation.get("outcome") or record.get("outcome"),
        "independence": validation.get("independence") or record.get("independence"),
        "generator": {"provider": record.get("generator_provider"), "model": record.get("generator_model")},
        "validator": {"provider": record.get("validator_provider"), "model": record.get("validator_model")},
        "facts_unverified": validation.get("facts_unverified"),
        "validation_warning": record.get("warning"),
        "rejection_reasons": generation.get("rejection_reasons") or [],
        "research_status": research.get("status"),
        "research_reason": research.get("reason"),
        "research_query_count": research.get("query_count"),
        "research_source_count": research.get("source_count"),
        "research_failure_count": research.get("failure_count"),
        "research_queries": research.get("queries"),
        "research_sources": research.get("sources"),
        "approve_ok": approve.get("ok"),
        "approve_result": approve.get("result"),
        "approve_error": approve.get("error"),
        "plan_state_after_approve": approve.get("plan_state_after"),
        "lessons_jobs": [
            {"job_id": run.get("job_id"), "terminal_state": run.get("terminal_state"),
             "elapsed_s": run.get("elapsed_s"),
             "checkpoint": ((run.get("final_job") or {}).get("checkpoint") or {})}
            for run in lessons.get("jobs") or []
        ],
        "lesson_count": len(((lessons.get("facts") or {}).get("rows") or [])),
        "lesson_states": (lessons.get("facts") or {}).get("states") or [],
        "lesson_rows": (lessons.get("facts") or {}).get("rows") or [],
        "served_lesson": page,
        "usage": data.get("usage"),
        "validator_config": data.get("validator_config"),
        "wire_contract_version": data.get("wire_contract_version"),
        "error": data.get("error"),
    }


def main() -> int:
    packet = {"packet": "h187-live-generation-2026-11-08", "scopes": {}}
    for tag in SCOPES:
        path = EVIDENCE / f"{tag}.json"
        if not path.is_file():
            packet["scopes"][tag] = {"tag": tag, "missing": True}
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        packet["scopes"][tag] = redact(scope_row(tag, raw))

    summary_path = EVIDENCE / "summary.json"
    summary_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {}
    for path in sorted(EVIDENCE.glob("*.json")):
        manifest[path.name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
    (EVIDENCE / "manifest.json").write_text(
        json.dumps({"files": manifest}, indent=2, sort_keys=True), encoding="utf-8"
    )

    columns = ("scope", "research_status", "queries", "sources", "objectives", "units",
               "validation_outcome", "independence", "approve_ok", "lessons", "lesson_states", "page")
    print("| " + " | ".join(columns) + " |")
    print("|" + "---|" * len(columns))
    for tag in SCOPES:
        row = packet["scopes"][tag]
        if row.get("missing"):
            print("| " + " | ".join([tag] + ["MISSING"] * (len(columns) - 1)) + " |")
            continue
        page = row.get("served_lesson") or {}
        print("| " + " | ".join(str(value) for value in (
            tag,
            row.get("research_status"),
            row.get("research_query_count"),
            row.get("research_source_count"),
            row.get("objective_count"),
            row.get("unit_count"),
            row.get("validation_outcome"),
            row.get("independence"),
            row.get("approve_ok"),
            row.get("lesson_count"),
            ",".join(row.get("lesson_states") or []) or "-",
            (page.get("objective_title") or "none") if page else "none",
        )) + " |")
    print()
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
