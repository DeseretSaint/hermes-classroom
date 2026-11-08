#!/usr/bin/env python3
"""H-191 follow-up: measure whether either repair fits the 180 s deadline.

Two questions, one process:

  (b) If the host *did* forward ``max_tokens`` on the nous chat-completions route, would a
      2 000-token cap still return a schema-valid 10-criterion verdict? Patched in memory only
      (``agent.auxiliary_client._forwards_max_tokens`` -> True); no host file is edited.
  (a) How does the call behave when the same request is split into smaller output demands
      (10 -> 5 / 3 / 1 criteria, with and without the claim-verdict paragraph)?

Every call goes through the production seam: ``coursebook.generation._call_llm`` over
``PluginLLMAdapter`` -> ``agent.plugin_llm.PluginLlm`` (``ctx.llm``), the validator route bound by
``bind_validator_llm``. No FakeLLM, no transcript edit. Results are flushed after every step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import reconstruct  # noqa: E402

CLAIM_PARAGRAPH_START = "For each claim in the artifact"


def now() -> str:
    return time.strftime("%H:%M:%S", time.localtime())


def subset_instructions(generation, criteria, *, claims: bool) -> str:
    """The production instruction text, restricted to a subset of criteria.

    ``claims=True`` keeps the production claim-verdict paragraph; ``False`` drops it so one call
    in a split can own the claim verdicts and the others do not re-judge them.
    """
    text = generation._validation_instructions(subject="plan", criteria=tuple(criteria))
    if claims:
        return text
    head, _, tail = text.partition(CLAIM_PARAGRAPH_START)
    addendum = ""
    if " Also judge curriculum sequence" in tail:
        addendum = " Also judge curriculum sequence" + tail.split(" Also judge curriculum sequence", 1)[1]
        if "objective_alignment" not in criteria:
            addendum = ""
    return head.rstrip() + addendum


def run_call(label, adapter, request, generation, sink, *, extra=None):
    usage = generation._Usage(generation.CostBudget())
    record = {
        "step": label,
        "purpose": request.purpose,
        "instructions_bytes": len(request.instructions.encode("utf-8")),
        "input_text_bytes": len(request.input_text.encode("utf-8")),
        "instructions_sha256": hashlib.sha256(request.instructions.encode("utf-8")).hexdigest()[:16],
        "max_tokens": request.max_tokens,
        "deadline_s": request.timeout_s,
        "started": now(),
    }
    if extra:
        record.update(extra)
    started = time.monotonic()
    try:
        response = generation._call_llm(adapter, request, usage)
    except BaseException as exc:  # noqa: BLE001 - the sampled outcome is the finding
        record["outcome"] = "raised"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["traceback_tail"] = traceback.format_exc().strip().splitlines()[-4:]
    else:
        record["outcome"] = "returned"
        record["reported"] = {
            "provider": response.provider,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "text_chars": len(response.text or ""),
        }
        record["parsed"] = isinstance(response.parsed, dict)
        record["text_tail"] = (response.text or "")[-400:]
        record["criterion_entries"] = (
            len((response.parsed or {}).get("criteria") or []) if isinstance(response.parsed, dict) else None
        )
        record["criterion_ids"] = (
            [entry.get("id") for entry in (response.parsed or {}).get("criteria") or []]
            if isinstance(response.parsed, dict)
            else None
        )
        record["claim_verdict_entries"] = (
            len((response.parsed or {}).get("claim_verdicts") or [])
            if isinstance(response.parsed, dict)
            else None
        )
        if isinstance(response.parsed, dict):
            try:
                generation.validate_artifact(response.parsed, generation.VALIDATION_SCHEMA, what="probe")
            except Exception as exc:  # noqa: BLE001
                record["schema_valid"] = False
                record["schema_error"] = f"{type(exc).__name__}: {exc}"
            else:
                record["schema_valid"] = True
    record["elapsed_s"] = round(time.monotonic() - started, 3)
    record["usage"] = usage.summary()
    record["ended"] = now()
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--agent-root", default=os.path.expanduser("~/.hermes/hermes-agent"))
    parser.add_argument("--validator-provider", default="nous")
    parser.add_argument("--validator-model", default="z-ai/glm-5.3-flash")
    parser.add_argument("--out", required=True)
    parser.add_argument("--steps", default="split-1,split-3,split-5,split-5-claims,cap-b")
    parser.add_argument("--deadline", type=float, default=300.0)
    parser.add_argument(
        "--trust-open",
        action="store_true",
        help=(
            "Open the host's per-plugin trust gate in memory so a cross-model validator "
            "override is allowed. Only the *cap* probe needs this; no host file is edited."
        ),
    )
    args = parser.parse_args()

    rebuilt = reconstruct.rebuild(args.db, args.source, args.agent_root)
    modules = rebuilt["modules"]
    generation = modules.generation
    exact = rebuilt["request"]
    wanted = [name.strip() for name in args.steps.split(",") if name.strip()]

    from agent.plugin_llm import PluginLlm

    if args.trust_open:
        import agent.plugin_llm as _plugin_llm

        # In-memory only: the probe measures the *cap*, not the trust gate. The host file is
        # untouched and the call still goes through PluginLlm.acomplete_structured.
        _plugin_llm._resolve_trust_policy = lambda plugin_id: _plugin_llm._TrustPolicy(
            plugin_id=plugin_id,
            allow_provider_override=True,
            allow_model_override=True,
            allow_any_provider=True,
            allow_any_model=True,
        )

    host = PluginLlm(plugin_id="coursebook")
    generation.bind_host_llm(host)
    generation.bind_validator_llm(host, provider=args.validator_provider, model=args.validator_model)
    adapter = generation.PluginLLMAdapter(host, provider=args.validator_provider, model=args.validator_model)

    criteria = list(generation.VALIDATION_CRITERIA)
    results: list[dict] = []
    sink: list = []

    def flush():
        packet = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source_db": args.db,
            "source_worktree": args.source,
            "validator_route": {"provider": args.validator_provider, "model": args.validator_model},
            "request_identity": {
                "purpose": exact.purpose,
                "prompt_version": exact.prompt_version,
                "schema_name": exact.schema_name,
                "max_tokens": exact.max_tokens,
                "scope": rebuilt["scope"],
                "declared_deadline_s": exact.timeout_s,
                "input_text_bytes": len(exact.input_text.encode("utf-8")),
                "wire_messages_bytes": len(exact.input_text.encode("utf-8"))
                + len(exact.instructions.encode("utf-8"))
                + len(exact.system_prompt.encode("utf-8"))
                + len(json.dumps(exact.schema, sort_keys=True).encode("utf-8")),
                "criteria_count": len(criteria),
                "criteria": criteria,
            },
            "steps": results,
        }
        Path(args.out).write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def bounded_schema(subset):
        """The production schema with the criteria array narrowed to *subset*.

        The instruction text alone does not bound the answer: measured on 2026-11-08, asking for
        one criterion still produced ten entries and 14 409 completion tokens. The schema is what
        makes an out-of-subset answer impossible.
        """
        schema = json.loads(json.dumps(exact.schema))
        criteria_schema = schema["properties"]["criteria"]
        criteria_schema["minItems"] = len(subset)
        criteria_schema["maxItems"] = len(subset)
        criteria_schema["items"] = json.loads(json.dumps(criteria_schema["items"]))
        criteria_schema["items"]["properties"]["id"]["enum"] = list(subset)
        criteria_schema["items"]["properties"]["reason"]["maxLength"] = 200
        rejections = schema["properties"]["rejections"]
        rejections["items"] = json.loads(json.dumps(rejections["items"]))
        rejections["items"]["properties"]["criterion"]["enum"] = list(subset)
        return schema

    def bounded_instructions(subset, *, claims):
        names = ", ".join(subset)
        text = (
            f"You are judging exactly {len(subset)} criterion/criteria of this plan: {names}. "
            "Judge only those. Do not evaluate, mention or return any other criterion, and do not "
            "restate the plan. For each criterion return a verdict and at most one sentence of "
            "reason (200 characters) that names the concrete artifact feature it rests on."
        )
        if claims:
            text += (
                " For each claim in the plan, also return a support verdict against the supplied "
                "source ledger; use source_id only when the ledger contains that source, and quote "
                "in 'excerpt' the exact words from that source that carry the claim."
            )
        text += " Return only the JSON object."
        return text

    def split_request(label, subset, *, claims, purpose):
        return generation.LLMRequest(
            purpose=purpose,
            prompt_version=exact.prompt_version,
            system_prompt=exact.system_prompt,
            instructions=subset_instructions(generation, subset, claims=claims),
            input_text=exact.input_text,
            schema=exact.schema,
            schema_name=exact.schema_name,
            max_tokens=exact.max_tokens,
            timeout_s=float(args.deadline),
        )

    cap_patched = False
    for step in wanted:
        if step.startswith("split-"):
            n = int(step.split("-")[1])
            claims = "claims" in step
            subset = criteria[:n]
            request = split_request(
                step, subset, claims=claims, purpose=f"probe.split.{n}{'.claims' if claims else ''}"
            )
            results.append(
                run_call(
                    f"split {n} criteria{' + claim verdicts' if claims else ''} (exact input)",
                    adapter,
                    request,
                    generation,
                    sink,
                    extra={"criteria_in_demand": subset, "claims_demanded": claims},
                )
            )
        elif step.startswith("bound-"):
            n = int(step.split("-")[1])
            claims = step.endswith("-claims")
            subset = criteria[:n]
            request = generation.LLMRequest(
                purpose=f"probe.bound.{n}{'.claims' if claims else ''}",
                prompt_version=exact.prompt_version,
                system_prompt=exact.system_prompt,
                instructions=bounded_instructions(subset, claims=claims),
                input_text=exact.input_text,
                schema=bounded_schema(subset),
                schema_name=exact.schema_name,
                max_tokens=exact.max_tokens,
                timeout_s=float(args.deadline),
            )
            results.append(
                run_call(
                    f"bound {n} criteria (schema-narrowed){' + claim verdicts' if claims else ''}",
                    adapter,
                    request,
                    generation,
                    sink,
                    extra={"criteria_in_demand": subset, "claims_demanded": claims, "schema_narrowed": True},
                )
            )
        elif step in ("criteria-only", "claims-only"):
            schema = json.loads(json.dumps(exact.schema))
            if step == "criteria-only":
                schema["properties"].pop("claim_verdicts", None)
                schema["properties"]["criteria"]["items"]["properties"]["reason"]["maxLength"] = 200
                instructions = subset_instructions(generation, criteria, claims=False) + (
                    " Give each criterion a one-sentence reason of at most 200 characters that names "
                    "the concrete feature it rests on; do not restate the artifact or explain your "
                    "method."
                )
            else:
                schema["properties"]["criteria"]["minItems"] = 0
                schema["properties"]["criteria"]["maxItems"] = 0
                instructions = (
                    "Judge only claim support for this plan. For each claim in the plan return one "
                    "claim_verdicts entry against the supplied source ledger: item, source_id, "
                    "support, reason, and 'excerpt' quoting the exact words from that source that "
                    "carry the claim. Use 'unverified' when no supplied source carries it; never "
                    "invent a source. Return criteria as an empty array and rejections as an empty "
                    "array. Return only the JSON object."
                )
            request = generation.LLMRequest(
                purpose=f"probe.{step}",
                prompt_version=exact.prompt_version,
                system_prompt=exact.system_prompt,
                instructions=instructions,
                input_text=exact.input_text,
                schema=schema,
                schema_name=exact.schema_name,
                max_tokens=exact.max_tokens,
                timeout_s=float(args.deadline),
            )
            results.append(run_call(f"{step} (exact input)", adapter, request, generation, sink))
        elif step == "cap-b":
            import agent.auxiliary_client as aux

            if not cap_patched:
                aux._forwards_max_tokens = lambda *a, **k: True  # type: ignore[assignment]
                cap_patched = True
            request = generation.LLMRequest(
                **{**exact.__dict__, "purpose": "probe.cap-forwarded", "timeout_s": float(args.deadline)}
            )
            results.append(
                run_call(
                    "exact 10-criterion request, max_tokens forwarded (2000)",
                    adapter,
                    request,
                    generation,
                    sink,
                    extra={"max_tokens_forwarded": True, "forwards_patched": True},
                )
            )
        else:
            raise SystemExit(f"unknown step {step!r}")
        flush()

    flush()
    packet = json.loads(Path(args.out).read_text())
    print(json.dumps({k: v for k, v in packet.items() if k != "steps"}))
    for entry in results:
        print(
            json.dumps(
                {
                    k: entry.get(k)
                    for k in (
                        "step",
                        "outcome",
                        "elapsed_s",
                        "criterion_entries",
                        "claim_verdict_entries",
                        "schema_valid",
                        "schema_error",
                        "reported",
                    )
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
