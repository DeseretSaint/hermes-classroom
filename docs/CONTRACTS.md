# Coursebook contracts — authoritative files and owners

Status: **frozen at v1**. Governed by `PREBUILD_SPEC.md` (architecture) and `UX_SPEC.md` (interface).
Owner of every contract: **Atlas**. Implementers are the specialists named below.

A contract file is the single authority for its vocabulary, payload shapes and error codes.
No module may redeclare an enum or error code that lives in `contracts/`. Python reads them
through `coursebook/contracts.py`; the Desktop half reads them from the backend
(`GET /api/plugins/coursebook/schema`) instead of embedding a copy.

## The contract set

| Contract id | File | Ver | Implementer | Consumers |
|---|---|---|---|---|
| `cb.vocabulary` | `contracts/vocabulary.v1.json` | 1 | Atlas | every other contract (shared enums, hashes, ids) |
| `cb.errors` | `contracts/errors.v1.json` | 1 | Atlas | RPC envelope, job errors, HTTP mapping |
| `cb.rpc` | `contracts/rpc.v1.json` | 1 | Cinder (kernel methods), Sable (transport) | Desktop half, Coursebook tools, `pre_llm_call` |
| `cb.db` | `contracts/db.v1.json` | 1 | Cinder | migrations, every command, evidence views |
| `cb.jobs` | `contracts/jobs.v1.json` | 1 | Cinder | job service, Activity view |
| `cb.pack` | `contracts/pack-manifest.v1.json` | 1 | Lattice | import/export, bundled demo packs |

Each document carries `$id` (versioned URI), `x-contract-id`, `x-contract-version`, `x-owner`.
`tests/test_contracts.py` asserts that the id, the version in the URI and the declared version
agree for every file.

## Wire rule

`cb.rpc` is transport-neutral. The root schema validates a **request envelope**:

```json
{ "contract": "cb.rpc", "contract_version": 1,
  "method": "attempt.submit", "operation_id": "op-...", "idempotency_key": "...",
  "expected_revision": 12, "payload": { } }
```

Success and failure are separate envelopes (`$defs/envelope_response_ok`,
`$defs/envelope_response_error`). Every method has `request` and `response` payload schemas in
`$defs.methods`; `coursebook.api.dispatch` validates the envelope, then the payload, then runs the
handler, then validates the handler's result against the response schema. A handler that returns
something outside the contract becomes `INTERNAL_ERROR` — it is never rendered.

`POST /api/plugins/coursebook/rpc` always answers **HTTP 200** with a contract envelope. A refused
command is `ok:false` with an error code; a transport failure is the only reason a client sees an
HTTP error. That keeps the Desktop half to one branch (`response.ok`) instead of two.

### State and identity rules baked into the contract

* Every mutation carries `expected_revision` and is refused with `STALE_REVISION` +
  `current_revision` rather than silently winning.
* `attempt.submit` additionally **requires** `idempotency_key` and `expected_revision`. Repeating a
  key with the same payload hash returns the persisted original result; the same key with a
  different payload is `IDEMPOTENCY_CONFLICT`.
* Evidence classes are fixed: `cold`, `hinted`, `answer_shown`, `self_reported`, `parent_reported`,
  `override`. Only `cold` can count as independent evidence; `override` grants access, never mastery.
* `bindings.status` of anything other than `active` refuses a submit with `BINDING_NOT_ACTIVE`.
* Ids are minted by Coursebook (`identifier` pattern). Titles, paths and chat session ids are never
  primary keys — that is the R1 finding in `AUDIT.md`.

## Changing a contract

1. Open an Atlas decision in the task thread. A semantic change is **not** a patch.
2. Add a new file (`rpc.v2.json`) and bump `$id`/`x-contract-version`. Never edit a shipped `v1`
   in a way that changes meaning; clients cache by version.
3. Update `CONTRACT_FILES` in `coursebook/contracts.py` and run `python3 -m unittest discover -s tests -t .`.
4. Record the decision, the reason and the migration path below.

| Version | Date | Decision |
|---|---|---|
| v1 | 2026-11-06 | Initial freeze. 24 RPC methods, 17 tables, 16 error codes, 9 job states, 1 pack manifest. |

## Deliberate omissions (do not "helpfully" add these)

* No `mastered` boolean and no global progress percentage. Evidence states are distinct on purpose.
* No free-form `instructions` field in a pack or a check. Untrusted prose is content, never policy.
* No `provider`, `model` or credential field in a pack, and no `settings` passthrough.
* No `safe`/`verified` badge enum. Trust dimensions stay separate (`pack_trust_label`).
* No numeric attainment estimate field. Schedule arithmetic and attainment uncertainty are separate
  (R9); an estimate, if ever shown, is a `model_estimate` with limits, not a contract field.
* No transcript or notebook text in the pack schema, and none is obtainable by export options.

## Open questions for Atlas (blocking a *feature*, not this skeleton)

1. **Aux grader task lane.** `ctx.llm` exists (`agent.plugin_llm.PluginLlm`), but which auxiliary
   task name Coursebook claims, and whether that needs `llm.task_override` consent, must be settled
   by Sentinel's probe #4 before `attempt.submit` gets a grader body.
2. **Workspace topology.** Is an isolated course workspace creatable outside any git root on the
   supported local topology, and does the Desktop half share it? Probe #3 decides; until then
   `TOPOLOGY_UNSUPPORTED` is the honest answer for remote backends.
3. **`pack.import` staging transport.** `staged_id` assumes a backend upload route. If the gateway
   offers no upload door, import uses an explicit local file grant and `staged_id` refers to a
   backend-registered staging record. Lattice must not invent a `file://` path.
