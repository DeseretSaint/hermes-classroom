# The measured `full` plan ceiling (H-21c)

`docs/COURSE-BLUEPRINT.md` §6 requires the implementing card to measure the real provider
structured-output ceiling, record input and output tokens, and lower the `full` objective cap if
40 objectives do not fit. This is that measurement. No blueprint was trimmed.

## Method

One real structured call, through the production seam (`ctx.llm` → `PluginLLMAdapter`), with the
real `coursebook.plan.v2` request for a `full` brief:

```
python3 scripts/measure_plan_ceiling.py --live --out <probe.json>
python3 scripts/measure_plan_ceiling.py --report <probe.json>    # no spend, recomputes the math
```

`--dry` sizes the request and spends nothing. `--report` is pure arithmetic over the saved probe.
The request is built by `generation.build_plan_request` (prompt `plan-prompt.v4`, schema
`coursebook.plan.v2`, `max_tokens` 12000, `MAX_PLAN_BYTES` 49152), so it is the same request the
plan job sends.

The capacity statement divides the probe's provider-reported `output_tokens` by the number of
objectives in the returned document, then applies that density to 40 objectives. That density
includes units, title and metadata in the numerator, so it overstates the marginal cost of the
last objective; the capacity it yields is conservative.

## The probe

Provider `nous`, model `deepseek/deepseek-v4.1-flash-1017` (the host's active model at
measurement time).

| request | value |
|---|---|
| purpose | `coursebook.plan.generate` |
| prompt | `plan-prompt.v4` |
| schema | `coursebook_plan_v2` (4183 bytes) |
| input bytes | 2047 |
| `max_tokens` | 12000 |

| provider result | value |
|---|---|
| input tokens | 2920 |
| output tokens | 5859 |
| text bytes | 16448 |
| complete JSON | yes (`ends_with_close_brace`, parsed) |
| schema valid | yes |
| deterministic rules | pass |
| units / objectives / checks | 6 / 24 / 24 |
| cost account reported | none (`cost_usd: null`) |

The provider returned a complete, schema-valid, rules-passing `full` blueprint. It chose 24
objectives inside the declared 12–40 band; it did not hit `max_tokens` and did not truncate.

## Result and cap decision

```
tokens_per_objective   = 5859 / 24 = 244.12
projected tokens at 40 = 244.12 * 40 = 9765      (81.4% of max_tokens 12000)
bytes_per_token        = 16448 / 5859 = 2.807
projected bytes at 40  = 27413                   (55.8% of MAX_PLAN_BYTES 49152)
capacity at 12000      = floor(12000 / 244.12) = 49 objectives
```

40 objectives fit: 9,765 projected output tokens against a 12,000 cap, and 27,413 projected bytes
against a 49,152 byte artifact cap. The `full` cap therefore stays at **40 objectives**
(`SCOPE_EXPECTATIONS["full"]["blueprint_objectives"]` and `PLAN_SCHEMA_V2` `maxItems: 40`), and no
contract value is lowered.

## Spend

One provider call only: 2,920 input tokens, 5,859 output tokens, model
`deepseek/deepseek-v4.1-flash-1017`, provider `nous`. The host reported no cost figure for this
call, so none is recorded (a fabricated cost is worse than an absent one). The saved probe JSON
is the durable record of this call; re-running `--report` spends nothing.

## Limit of the measurement

One completion measures the provider's output density for this prompt, not every possible plan.
The projection is a linear extrapolation and the density is conservative. A future plan that
fails its own scope must refuse with a typed reason naming the scope, the measured bytes and the
cap — it must never truncate a blueprint to fit.
