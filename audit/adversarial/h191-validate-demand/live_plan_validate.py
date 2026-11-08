#!/usr/bin/env python3
"""H-191 follow-up: the live acceptance measurement for ``coursebook.plan.validate``.

Runs the *production* validation path — ``build_plan_validation_requests`` (rebuilt from the
stored H-187 single-scope home), ``_run_validation_passes`` over the real host seam
(``PluginLLMAdapter`` -> ``agent.plugin_llm.PluginLlm``, validator route ``nous`` /
``z-ai/glm-5.3-flash``), ``_parse_structured``, ``merge_validation_reports`` and
``validation_verdict`` — and records per-call and aggregate wall time, completion tokens and the
schema/merge outcome. No FakeLLM, no transcript edit.

One ``--repeat`` per sample; the baseline it is compared against is the H-191 single-call matrix
(243.0 s / 12 356, 283.6 s / 16 060, 286.1 s / 15 499 completion tokens).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import reconstruct  # noqa: E402


def now() -> str:
    return time.strftime("%H:%M:%S", time.localtime())


def author_model_from_db(db_path: str) -> str | None:
    """The model the stored run used to author the plan, read from its own usage rows."""
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT model FROM usage_events WHERE purpose = 'coursebook.plan.generate' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        connection.close()
        return str(row["model"]) if row and row["model"] else None
    except Exception:  # noqa: BLE001 - the acceptance does not depend on this lookup
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--agent-root", default=os.path.expanduser("~/.hermes/hermes-agent"))
    parser.add_argument("--validator-provider", default="nous")
    parser.add_argument("--validator-model", default="z-ai/glm-5.3-flash")
    parser.add_argument("--out", required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--deadline", type=float, default=180.0)
    parser.add_argument("--author-model", default=None)
    parser.add_argument(
        "--pass-layout",
        default="pairs",
        choices=("pairs", "single", "halves"),
        help="Override VALIDATION_CRITERIA_PASSES before rebuilding (a measurement lever).",
    )
    args = parser.parse_args()

    # Measurement lever: the shipped layout is ``pairs``. ``single`` puts all ten criteria and
    # every claim label in one call (the shape this card compares against); ``halves`` splits them
    # into two concurrent calls of five.
    if args.source not in sys.path:
        sys.path.insert(0, args.source)
    from coursebook import generation as _layout_generation

    _criteria = tuple(_layout_generation.VALIDATION_CRITERIA)
    layout = {
        "pairs": None,
        "single": (_criteria,),
        "halves": (_criteria[:5], _criteria[5:]),
    }[args.pass_layout]
    if layout is not None:
        _layout_generation.VALIDATION_CRITERIA_PASSES = layout

    rebuilt = reconstruct.rebuild(args.db, args.source, args.agent_root)
    modules = rebuilt["modules"]
    generation = modules.generation
    requests = rebuilt["requests"]
    author_model = args.author_model or author_model_from_db(args.db)

    from agent.plugin_llm import PluginLlm

    host = PluginLlm(plugin_id="coursebook")
    generation.bind_host_llm(host)
    generation.bind_validator_llm(host, provider=args.validator_provider, model=args.validator_model)
    adapter = generation.PluginLLMAdapter(host, provider=args.validator_provider, model=args.validator_model)

    def request_identity(request) -> dict:
        wire = (
            len(request.input_text.encode("utf-8"))
            + len(request.instructions.encode("utf-8"))
            + len(request.system_prompt.encode("utf-8"))
            + len(json.dumps(request.schema, sort_keys=True).encode("utf-8"))
        )
        return {
            "purpose": request.purpose,
            "prompt_version": request.prompt_version,
            "schema_name": request.schema_name,
            "max_tokens": request.max_tokens,
            "declared_deadline_s": request.timeout_s,
            "input_text_bytes": len(request.input_text.encode("utf-8")),
            "instructions_bytes": len(request.instructions.encode("utf-8")),
            "schema_bytes": len(json.dumps(request.schema, sort_keys=True).encode("utf-8")),
            "wire_messages_bytes": wire,
            "criteria": list(generation.validation_pass_criteria(request)),
            "claims": list(
                (
                    request.schema["properties"]
                    .get("claim_verdicts", {})
                    .get("items", {})
                    .get("properties", {})
                    .get("item", {})
                    .get("enum")
                )
                or []
            ),
        }

    packet = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_db": args.db,
        "source_worktree": args.source,
        "validator_route": {"provider": args.validator_provider, "model": args.validator_model},
        "author_model_from_db": author_model,
        "pass_count": len(requests),
        "baseline_single_call": {
            "source": "audit/adversarial/h191-validate-stall/STATUS.md",
            "elapsed_s": [242.955, 283.606, 286.065, 282.507],
            "completion_tokens": [12356, 16060, 15499, 16188],
            "declared_deadline_s": 180.0,
        },
        "requests": [request_identity(request) for request in requests],
        "samples": [],
    }
    out = Path(args.out)

    def flush() -> None:
        out.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    flush()
    for attempt in range(1, args.repeat + 1):
        usage = generation._Usage(generation.CostBudget(max_calls=32, max_cost_usd=None))
        sample: dict = {"attempt": attempt, "started": now()}
        started = time.monotonic()
        try:
            responses = generation._run_validation_passes(adapter, requests, usage)
            sample["aggregate_elapsed_s"] = round(time.monotonic() - started, 3)
            sample["outcome"] = "returned"
            sample["calls"] = [
                {
                    "purpose": call["purpose"],
                    "duration_ms": call["duration_ms"],
                    "input_tokens": call["input_tokens"],
                    "output_tokens": call["output_tokens"],
                    "provider": call["provider"],
                    "model": call["model"],
                }
                for call in usage.calls
            ]
            sample["aggregate_completion_tokens"] = sum(int(call["output_tokens"] or 0) for call in usage.calls)
            reports = []
            for request, response in zip(requests, responses):
                reports.append(
                    (
                        generation.validation_pass_criteria(request),
                        generation._parse_structured(
                            response,
                            generation.VALIDATION_SCHEMA,
                            what="plan validation",
                            max_bytes=generation.MAX_VALIDATION_BYTES,
                        ),
                    )
                )
            sample["passes"] = [
                {
                    "criteria": list(owned),
                    "entries": [entry.get("id") for entry in report.get("criteria") or []],
                    "verdict": report.get("verdict"),
                    "rejections": len(report.get("rejections") or []),
                    "claim_verdicts": len(report.get("claim_verdicts") or []),
                    "schema_valid_against_pass_schema": _pass_schema_valid(generation, request, report),
                }
                for (owned, report), request in zip(reports, requests)
            ]
            merged = generation.merge_validation_reports(reports)
            sample["merged"] = {
                "verdict": merged["verdict"],
                "criteria": [entry["id"] for entry in merged["criteria"]],
                "criterion_count": len(merged["criteria"]),
                "rejections": len(merged["rejections"]),
                "claim_verdicts": len(merged["claim_verdicts"]),
            }
            validator_identity = {
                "model": usage.calls[0]["model"],
                "provider": usage.calls[0]["provider"],
            }
            independence = generation.validation_independence(
                {"model": author_model, "provider": None} if author_model else None,
                validator_identity,
            )
            verdict = generation.validation_verdict(
                merged,
                research_status=rebuilt["stored"]["research"].get("status") or "unavailable",
                ledger=reconstruct.research_run_from_stored(rebuilt["stored"], modules).sources,
                independence=independence,
            )
            sample["verdict"] = {
                key: verdict[key]
                for key in (
                    "verdict",
                    "declared",
                    "outcome",
                    "independence",
                    "independent",
                    "failed",
                    "unknown",
                    "facts_unverified",
                )
            }
            sample["validator_identity"] = validator_identity
            sample["within_declared_deadline"] = bool(
                sample["aggregate_elapsed_s"] <= float(generation.PROVIDER_TIMEOUT_SECONDS["coursebook.plan.validate"])
            )
            sample["verdict_outcome_is_not_upgraded"] = verdict["outcome"] != "independently_validated" or bool(
                verdict["independent"]
            )
        except BaseException as exc:  # noqa: BLE001 - the sampled outcome is the finding
            sample["aggregate_elapsed_s"] = round(time.monotonic() - started, 3)
            sample["outcome"] = "raised"
            sample["error"] = f"{type(exc).__name__}: {exc}"
            sample["traceback_tail"] = traceback.format_exc().strip().splitlines()[-6:]
            sample["calls"] = list(usage.calls)
        sample["ended"] = now()
        packet["samples"].append(sample)
        flush()

    flush()
    print(json.dumps({k: packet[k] for k in ("pass_count", "requests", "author_model_from_db")}, indent=2))
    for sample in packet["samples"]:
        print(
            json.dumps(
                {
                    k: sample.get(k)
                    for k in (
                        "attempt",
                        "outcome",
                        "aggregate_elapsed_s",
                        "aggregate_completion_tokens",
                        "within_declared_deadline",
                        "merged",
                        "verdict",
                        "error",
                    )
                },
                sort_keys=True,
            )
        )
    return 0


def _pass_schema_valid(generation, request, report) -> bool | None:
    try:
        generation.validate_artifact(request.schema, report, what="pass")
    except Exception:  # noqa: BLE001
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
