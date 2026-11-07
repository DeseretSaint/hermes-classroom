#!/usr/bin/env python3
"""Summarise the H-63R live runs into audit/adversarial/h63-live-generation/evidence.json."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"

RUNS = ["topic1-derailleur", "topic2-relative-minor", "topic3-cancel", "topic4-http"]


def inner_plan(run: dict) -> dict:
    stored = (run.get("plan") or {}).get("document") or {}
    if not isinstance(stored, dict):
        return {}
    plan = stored.get("plan") if isinstance(stored.get("plan"), dict) else stored
    return plan if isinstance(plan, dict) else {}


def plan_fields(run: dict) -> dict:
    plan = inner_plan(run)
    out = {}
    for key, cap in (("learner_outcome", 600), ("evidence_note", 400)):
        value = plan.get(key)
        if isinstance(value, str):
            out[key] = {"length": len(value), "schema_max": cap,
                        "at_cap": len(value) == cap, "tail": value[-28:]}
    parent = plan.get("parent") or {}
    reading = parent.get("reading_level") if isinstance(parent, dict) else None
    if isinstance(reading, str):
        out["parent.reading_level"] = {"length": len(reading), "schema_max": 40,
                                       "bytes": len(reading.encode()), "repr": reading}
    return out


def main() -> int:
    runs = []
    for name in RUNS:
        path = EVIDENCE / f"{name}.json"
        run = json.loads(path.read_text(encoding="utf-8"))
        final = run.get("final_job") or {}
        research = run.get("research") or {}
        gr = run.get("generation_result") or {}
        validation = run.get("validation") or gr.get("validation") or {}
        runs.append({
            "tag": run.get("tag"),
            "job_id": run.get("job_id"),
            "terminal_state": run.get("terminal_state"),
            "elapsed_to_terminal_s": run.get("elapsed_to_terminal_s"),
            "bound_s": 600,
            "research_status": research.get("status"),
            "research_reason": research.get("reason"),
            "research_queries": len(research.get("queries") or []),
            "research_sources": len(research.get("sources") or []),
            "research_failures": len(research.get("failures") or []),
            "validation_verdict": run.get("validation_verdict") or gr.get("validation_verdict"),
            "validation_independence": validation.get("independence"),
            "validator": validation.get("validator"),
            "generator": validation.get("generator"),
            "generation_status": run.get("generation_status") or gr.get("status"),
            "rejection_reasons": run.get("rejection_reasons") or gr.get("rejection_reasons"),
            "plan_schema": inner_plan(run).get("plan_schema"),
            "units": len(inner_plan(run).get("units") or []),
            "objectives": len(inner_plan(run).get("objectives") or []),
            "checks": len(inner_plan(run).get("check_plan") or []),
            "truncation": plan_fields(run),
            "job_lease_at_end": final.get("lease"),
            "progress_message": (final.get("progress") or {}).get("message"),
            "pump": run.get("pump"),
            "usage_calls": len(run.get("usage_events") or []),
            "timeline": run.get("timeline"),
        })
    packet = {
        "card": "H-63R / t_af57b886",
        "auditor": "sentinel (cbqa)",
        "date": "2026-11-07",
        "source_commit": json.loads((EVIDENCE / "topic1-derailleur.json").read_text())["source_commit"],
        "isolated_home": json.loads((EVIDENCE / "topic1-derailleur.json").read_text())["isolated_home"],
        "provider": {"author": "nous / deepseek/deepseek-v4.1-flash-1017",
                     "validator": "nous / deepseek/deepseek-v4.1-flash"},
        "provider_calls_are_live": True,
        "search_backend": "host web_search/web_extract tools through coursebook.research.HermesToolSearch",
        "verdicts": {
            "live_loop_terminates_in_process_with_seams": "PASS",
            "live_research_grounded": "PASS",
            "cross_model_validation": "PASS",
            "cancel_reaches_terminal": "PASS (completed_late; running provider call not interrupted)",
            "approvable_live_plan": "FAIL",
            "serve_process_runs_tick_without_research_seam": "FAIL (defect D-H63-1)",
        },
        "runs": runs,
        "defects": [
            {
                "id": "D-H63-1",
                "severity": "P1",
                "title": "serve/dashboard process executes the job tick without the host research seam",
                "evidence": "job_1a348fd966c541bea02a270f4a591fb6 was created over HTTP, then claimed and "
                            "executed by the isolated `hermes serve` process on port 44229 while the "
                            "agent-side pump returned finished=[]; that run recorded research.status="
                            "'unavailable' (no source fetched) and rejected the plan for a deterministic rule.",
                "why_it_matters": "This is the same class as the card's stalled RPC job: the process the Desktop "
                                  "talks to can run generation with no agent tools, so every RPC-created job "
                                  "gets zero research support even though a properly bound agent tick does "
                                  "ground research.",
            },
            {
                "id": "D-H63-2",
                "severity": "P2",
                "title": "plan prose fields are hard-truncated at JSON-schema maxLength, producing mid-word and "
                         "mid-codepoint artifacts",
                "evidence": "topic1 learner_outcome length=600 (cap 600) ends '...do not establish,so'; "
                            "topic2 evidence_note length=400 (cap 400) ends '...excluded as a'; "
                            "topic2 parent.reading_level length=40 (cap 40) contains 'chart-l\\u6279'. "
                            "The independent validator rejected all three as incomplete/corrupted.",
                "why_it_matters": "The generator asks for prose at the schema cap and the provider truncates at "
                                  "the limit; the validator then correctly refuses the plan, so a live arbitrary "
                                  "topic can never be approved when the model writes near the cap.",
            },
            {
                "id": "D-H63-3",
                "severity": "P3",
                "title": "cancel during a running provider call is only honoured after the call returns",
                "evidence": "topic3: jobs.cancel -> cancel_requested at 8.2s; job reached completed_late at "
                            "244.3s after authoring the whole plan. No stage boundary existed to stop at.",
                "why_it_matters": "Documented contract behaviour (completed_late), but a user who cancels still "
                                  "pays for and receives a full generation; the UI copy must not promise an "
                                  "immediate stop.",
            },
        ],
        "follow_up": "H-63F: bind the research/validator seams for the serve tick or keep the tick in the agent "
                     "process only; and make plan prose length-aware (no hard maxLength truncation) before an "
                     "arbitrary-topic live plan can be approved.",
    }
    (HERE / "evidence.json").write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    print("wrote", HERE / "evidence.json")
    for run in runs:
        print(run["tag"], run["terminal_state"], run["elapsed_to_terminal_s"], run["research_status"],
              run["validation_verdict"], run["validation_independence"], "reasons:", len(run["rejection_reasons"] or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
