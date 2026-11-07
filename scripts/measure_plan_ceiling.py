#!/usr/bin/env python3
"""One measured probe of the provider structured-output ceiling for a `full` blueprint.

This is the §6 measurement the blueprint card must carry: the request is the real
``coursebook.plan.v2`` request for the largest declared scope (12 units, up to 40 objectives),
sent once through the host-owned ``ctx.llm`` seam. Nothing here reaches for a provider key or a
raw HTTP client.

    python3 scripts/measure_plan_ceiling.py --dry     # build and size the request, spend nothing
    python3 scripts/measure_plan_ceiling.py --live    # the single probe (real provider spend)

The result is printed as JSON and, with ``--out``, written to a file. ``--dry`` is safe to run
any number of times; ``--live`` is the one call the task budget allows.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coursebook import generation as gen  # noqa: E402
from coursebook.research import ResearchRun  # noqa: E402

FULL_BRIEF = {
    "goal": (
        "Braise, roast and rest meat so a home cook can serve a tender result without a "
        "thermometer guess: temperature, time, carry-over and safety at each step."
    ),
    "recipe": "committed",
    "dials": {"pace": "steady", "depth": "working", "assessment": "graded", "autonomy": "guided"},
    "locale": "en-US",
    "scope": "full",
}


def build_request() -> gen.LLMRequest:
    return gen.build_plan_request(
        goal=FULL_BRIEF["goal"],
        recipe=FULL_BRIEF["recipe"],
        dials=dict(FULL_BRIEF["dials"]),
        locale=FULL_BRIEF["locale"],
        research_run=ResearchRun(status="unavailable", queries=[], sources=[], reason="probe"),
        scope=FULL_BRIEF["scope"],
        level="adult",
        subject_domain="cooking",
    )


def size_report(request: gen.LLMRequest) -> dict:
    schema_text = json.dumps(request.schema, separators=(",", ":"), sort_keys=True)
    return {
        "purpose": request.purpose,
        "prompt_version": request.prompt_version,
        "max_tokens": request.max_tokens,
        "input_bytes": len(request.input_text.encode("utf-8")),
        "instructions_chars": len(request.instructions),
        "system_prompt_chars": len(request.system_prompt),
        "schema_bytes": len(schema_text.encode("utf-8")),
        "schema_name": request.schema_name,
    }


def capacity_report(probe: dict[str, Any]) -> dict[str, Any]:
    """Turn one measured completion into the cap statement §6 asks for.

    Method: the probe's document and its provider-reported ``output_tokens`` give a measured
    tokens-per-objective density for the real provider and prompt. That density is applied to
    the declared ``full`` maximum (40 objectives) and compared with the request's ``max_tokens``
    and ``MAX_PLAN_BYTES``. A density overestimates the *marginal* cost of the last objective
    (units, title and metadata are in the numerator), so the resulting capacity is conservative.
    """
    request = probe.get("request") or {}
    call = probe.get("provider_call") or {}
    document = probe.get("document") or {}
    objectives = int(document.get("objectives") or 0)
    output_tokens = int(call.get("output_tokens") or 0)
    text_bytes = int(call.get("text_bytes") or 0)
    max_tokens = int(request.get("max_tokens") or 0)
    if not objectives or not output_tokens:
        return {"measurable": False, "reason": "the probe returned no parsed document or no usage"}
    tokens_per_objective = output_tokens / objectives
    bytes_per_token = text_bytes / output_tokens
    projected_tokens = tokens_per_objective * 40
    projected_bytes = projected_tokens * bytes_per_token
    return {
        "measurable": True,
        "measured_objectives": objectives,
        "measured_output_tokens": output_tokens,
        "measured_text_bytes": text_bytes,
        "tokens_per_objective": round(tokens_per_objective, 2),
        "bytes_per_token": round(bytes_per_token, 3),
        "projected_tokens_at_40": round(projected_tokens),
        "projected_bytes_at_40": round(projected_bytes),
        "max_tokens": max_tokens,
        "max_plan_bytes": gen.MAX_PLAN_BYTES,
        "fits_max_tokens": projected_tokens <= max_tokens,
        "fits_max_plan_bytes": projected_bytes <= gen.MAX_PLAN_BYTES,
        "capacity_objectives": int(max_tokens // tokens_per_objective),
        "full_cap_decision": 40 if projected_tokens <= max_tokens else int(max_tokens // tokens_per_objective),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="make the one real provider call")
    parser.add_argument("--dry", action="store_true", help="size the request only")
    parser.add_argument(
        "--report", type=Path, default=None,
        help="recompute the capacity statement from a saved --live probe JSON (no spend)",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.report is not None:
        probe = json.loads(args.report.read_text(encoding="utf-8"))
        print(json.dumps({"capacity": capacity_report(probe)}, indent=2))
        return 0
    if args.live == args.dry:
        parser.error("choose exactly one of --dry or --live (or --report PATH)")

    request = build_request()
    report: dict[str, Any] = {"request": size_report(request)}
    if args.dry:
        print(json.dumps(report, indent=2))
        return 0

    # The production seam: host-owned credentials, plugin trust gate, no key in the plugin.
    import agent.plugin_llm  # noqa: PLC0415

    llm = gen.PluginLLMAdapter(agent.plugin_llm.PluginLlm(plugin_id="coursebook"))
    report["provider_call"] = {"attempted": True}
    try:
        response = llm(request)
    except Exception as exc:  # noqa: BLE001 - the probe reports the failure, it does not hide it
        report["provider_call"] = {
            "attempted": True,
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(report, indent=2))
        return 2

    text = response.text or ""
    parsed = response.parsed
    report["provider_call"].update(
        {
            "provider": response.provider,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost_usd": response.cost_usd,
            "text_bytes": len(text.encode("utf-8")),
            "text_chars": len(text),
            "ends_with_close_brace": text.rstrip().endswith("}"),
            "parsed_json": parsed is not None,
        }
    )
    if parsed is not None:
        document = parsed
        report["document"] = {
            "plan_schema": document.get("plan_schema"),
            "scope": document.get("scope"),
            "units": len(document.get("units") or []),
            "objectives": len(document.get("objectives") or []),
            "check_plan": len(document.get("check_plan") or []),
            "canonical_bytes": len(
                json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
            ),
        }
        try:
            gen.validate_artifact(gen.PLAN_SCHEMA_V2, document, what="plan")
            report["document"]["schema_valid"] = True
        except Exception as exc:  # noqa: BLE001
            report["document"]["schema_valid"] = False
            report["document"]["schema_error"] = str(exc)
        try:
            gen.enforce_plan_rules(
                document,
                recipe=FULL_BRIEF["recipe"],
                dials=dict(FULL_BRIEF["dials"]),
                locale=FULL_BRIEF["locale"],
                ledger=[],
                scope=FULL_BRIEF["scope"],
            )
            report["document"]["rules_pass"] = True
        except Exception as exc:  # noqa: BLE001
            report["document"]["rules_pass"] = False
            report["document"]["rules_error"] = str(exc)[:2000]
    else:
        # Not JSON at all: record why, without inventing a document.
        report["provider_call"]["text_head"] = text[:400]
        report["provider_call"]["text_tail"] = text[-400:]

    output = json.dumps(report, indent=2)
    print(output)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
