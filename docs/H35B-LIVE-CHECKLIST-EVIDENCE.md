# H-35b — live checklist DOM capture on a fresh rig

Evidence-only follow-up to H-35 (`t_65e7d83a`, merged at `f990cad`). No product code, no kernel,
no contract, no merge, no provider spend.

## Rig

| | |
|---|---|
| State dir | `~/.hermes/h35b-live-1794046842` (`home/` + `userdata/`), created fresh for this capture |
| Window | dev Electron from `~/.hermes/hermes-agent/node_modules/electron`, `HERMES_DESKTOP_USER_DATA_DIR=<state>/userdata` |
| CDP | `127.0.0.1:9351` (new port; the old `~/.hermes/coursebook-test` rig was not reused or repointed) |
| Backend | `hermes serve --isolated --port 44277`, `HERMES_HOME=<state>/home` |
| Wire observation | logging reverse proxy `127.0.0.1:44288 -> 44277` (the Desktop REST bridge is a locked native method, so CDP Network cannot see plugin RPC bodies) |
| Checkout | `~/Projects/hermes-classroom` @ `f990cad` (`git status` clean for `desktop/plugin.js`) |
| plugin.js sha256 | `ab63470906c792299ec1db5a25b178a72a6577c7571aac9aec49c8bd64f64540` — identical for the checkout file and the materialized `<state>/home/desktop-plugins/coursebook/plugin.js` |

The fresh renderer loaded the current module: the checklist nodes (`data-cb-check-items-mode="selection"`,
`data-cb-check-tick`) render, so the stale-module condition that blocked the parent card did not recur.

## Seeded course (offline pipeline, no provider call)

Authored through the shipped pipeline with `tests.test_generation.FakeLLM` / `FakeSearch`, recipe
`one_off`, exactly as `scripts/m1u-guided-probe.py` does (seeder kept in the worker scratch dir, not
the repo). Seed result: `<state>/seed-one-off.json`.

| | |
|---|---|
| Course | `e790c71d21f86198` — "Order coffee in Japanese", recipe `one_off` |
| Enrollment | `enr_1cdb789007174e10aec0c2426ec9659e` |
| Plan | `9e70b80c87ed4f32`, validation `pass`; 4 lessons `validated` |
| Check (partial capture) | `126084cfc416908d`, objective `aa85d4fcfa71beff` |
| Check (full pass) | `abfa0d29805df8d1`, objective `eacf60f1a53e550b` |

Each check has `stimulus.format="verification"` with exactly three declared items
(`item_1` "Pad model matched to the manual", `item_2` "Worn pad removed with the listed tool",
`item_3` "Caliper undamaged") and `reference.kind="rubric_only"`.

## What the live renderer showed

Served checklist (from the DOM, both captures):

```json
{"count":3,"ids":["item_1","item_2","item_3"],
 "labels":["Pad model matched to the manual","Worn pad removed with the listed tool","Caliper undamaged"]}
```

- `data-cb-answer-kind="selection"` on the answer form.
- Submit control disabled before any tick (`{"disabled":true}`).
- After ticking two items: `ticks ["true","true","false"]`, submit enabled.
- Verdict panel (`data-cb-verdict="partial"`, `data-cb-evidence-class="self_reported"`):
  - `item_1` met=true — Confirmed
  - `item_2` met=true — Confirmed
  - `item_3` met=false — Not confirmed
  - frozen copy: "You confirmed 2 of 3 steps. Tick the remaining steps and submit again; this stays
    your own report, not an independent check."
  - evidence notice: "Self-reported — you told us. It cannot count as independent evidence."
- Screenshot (checklist, ticked rows and verdict rows):
  `docs/h35b-shots/checklist-partial.png`

Full confirmation on the second check: all three items ticked, submit clicked, and the page then
shows "Self-reported pass" with the same evidence notice. The attempt row is
`att_f359ff07a62a439cab1ab30a75e51531` `verdict=pass`, `evidence_class=self_reported`, `answer_json=
{"kind":"selection","selection":["item_1","item_2","item_3"]}` (first check:
`att_cc2cc3bd6fe242899416380fe22e1bbe` partial → `att_c7f92ce07aee4310a9b546550705a7cb` pass).

## Exact `attempt.submit` body off the wire

`docs/h35b-shots/attempt-submit-wire.jsonl` — captured by the logging proxy, not reconstructed:

```json
{"contract":"cb.rpc","contract_version":11,"method":"attempt.submit",
 "operation_id":"cb-attempt-submit-3902ea81-d75",
 "payload":{"enrollment_id":"enr_1cdb789007174e10aec0c2426ec9659e",
            "check_id":"abfa0d29805df8d1","check_version":1,
            "attempt_nonce":"cb-attempt-ee1a5b18-cd8",
            "answer":{"kind":"selection","selection":["item_1","item_2","item_3"]}},
 "idempotency_key":"cb-attempt-abfa0d29805df8d1-cb-attempt-ee1a5b18-cd8",
 "expected_revision":3}
```

The `answer` object is exactly `{"kind":"selection","selection":[ids]}`.

## Honest limits of this capture

- The chat binding that enables the confirmation form was created through the shipped
  `POST /api/plugins/coursebook/sessions/bind` seam against a run created by `lesson.begin`; the
  `stored_session_id` is a stand-in because a real first chat turn would call a provider, and this
  card forbids provider spend. The checklist surface, payload, and verdict are the product's; the
  chat turn behind the binding was not exercised here.
- The "Self-reported pass" state replaces the open check form, so no `data-cb-verdict` panel exists
  after a pass. The pass is evidenced by the attempts table, the rendered "Self-reported pass" line,
  the evidence notice, and the wire body; the verdict rows are evidenced from the partial attempt
  in the screenshot.
