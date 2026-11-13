# CP-051 — why a private Desktop rig reported `runtime_exited`, and the recipe that replaces it

Status: mechanism **proven**; the private rig script is shipped; the end-to-end Coursebook frame
from this rig is **not yet captured** (see "What is still open" at the bottom). Nothing here was
inferred from a source read alone — every claim carries the command or log line that produced it.

## 1. The mechanism, with the exact lines

A private window launched with only `HERMES_HOME=<isolated home>` and the default **local**
connection never reaches a backend of its own. The chain is:

1. Desktop's main process calls `hermes <home> gateway ensure` for the local connection
   (`apps/desktop/electron/local-gateway.ts`, `runGatewayEnsure`).
2. `hermes_cli/gateway_runtime.py: ensure_gateway_runtime` finds the home `absent` and spawns one
   daemon: `hermes_cli/gateway_runtime_start.py: spawn_unmanaged_gateway`. For any home whose parent
   is not `profiles/`, that function pins the selector:

   ```python
   selector = [] if home.parent.name == "profiles" else ["--profile", "default"]
   ```

3. `hermes_cli/main.py: _apply_profile_override` re-parses that flag and re-resolves `HERMES_HOME`
   to the **real default root**, discarding the isolated home:

   ```python
   if profile_name is None and hermes_env and Path(hermes_env).parent.name == "profiles":
       return          # trusted as-is — a named profile
   ...
   hermes_home = resolve_profile_env(profile_name)   # 'default' -> ~/.hermes
   ```

4. Now the child *is* the default profile's gateway. `gateway/host_attach.py: decide` sees the live
   host multiplexer already serving `default` and attaches instead of starting:

   ```
   ✓ The host gateway already serves profile 'default' — nothing to start.
     PID 388977 (launched by profile 'default'; serves: default, atlas, cbqa, cinder, harbor,
     lattice, quill, sable, sentinel, vellum, easel)
   ```

   and exits **0**.
5. `ensure_gateway_runtime` (`gateway_runtime.py:448`) treats a child that exited before a ready
   endpoint as the failure it is:

   ```python
   return GatewayDiscovery("inaccessible", reason_code="runtime_exited",
                           detail=startup_failure_report(...))
   ```

6. Desktop surfaces it as the line both blocked cards recorded:

   ```
   Error occurred in handler for 'hermes:connection:for': Error: Gateway inaccessible
   (runtime_exited). the gateway exited with status 0 before it could serve:.
   Use hermes gateway status for recovery.
   ```

Reproduced directly, without any Electron, as the same call Desktop makes:

```
$ HERMES_HOME=~/.hermes/coursebook-test/home hermes gateway ensure --timeout 30
{"detail":"the gateway exited with status 0 before it could serve:\n  ✓ The host gateway already
serves profile 'default' — nothing to start. ...","reason_code":"runtime_exited",
 "state":"inaccessible"}`         # exit 7
```

**The cause is the launch topology, not the plugin, not a host change.** The spawn pins
`--profile default` for a home that is not `<root>/profiles/<name>`, so the isolated home is
discarded before the gateway starts.

## 2. The "headless backend" line is a red herring

`/api/plugins` on a `hermes serve` backend answers
`{"error":"Headless backend (hermes serve): web UI disabled — use `hermes dashboard` …"}`.
That is the **frontend catch-all** (`hermes_cli/web_server_dashboard.py: mount_spa`, the
`HERMES_SERVE_HEADLESS` branch): every non-API path 404s with that message. `/api/plugins` is not an
API route on any backend, so this response says nothing about whether a plugin is installed or
whether the Desktop can load it. Do not debug the plugin route from that line.

## 3. The two working peer topologies (both measured)

Both keep the host multiplexer untouched — no signal is ever sent to PID 388977.

**(a) standalone named profile.** A profile directory under the default root with
`gateway.standalone: true` starts its own gateway beside the multiplexer:

```
~/.hermes/profiles/cp051rig/config.yaml  ->  gateway: { standalone: true }
$ HERMES_HOME=~/.hermes/profiles/cp051rig hermes gateway ensure --timeout 45
{"state":"ready","endpoint":{"api_origin":"http://127.0.0.1:43553",
 "profile_id":"/home/deseretsaint/.hermes/profiles/cp051rig", ...}}
```

The gateway records its own reason: `"multiplex_standalone_reason": "this profile is standalone
(gateway.standalone: true); it serves only itself"`. A ticket mint over its control socket answers
correctly (`gateway/control_socket.py: _session_ticket`, reply carries `ticket`, `instance_id`,
`profile_id`).

**(b) private root (strictest isolation).** A separate Hermes root —
`~/.hermes/coursebook-test-cp051/root/{config.yaml, profiles/rig}` — is also accepted as a named
profile (`hermes_constants._is_hermes_profiles_root`) and gets its own standalone gateway on its own
port. This root is invisible to the operator's profile list.

Both are documented in `scripts/rig-private-desktop.sh`, which uses the **remote** lane (below),
because that is the one that never calls `gateway ensure` at all.

### 3.1 The remote connection's token shape is load-bearing

`connections.json` stores the token as `{"encoding":"plain","value":"<token>"}` — a bare string is
accepted into the file but the window then paints `Backend offline` even though the backend answers
`/api/plugins/coursebook/runtime` with 200 for the same credential. The working file also keeps a
`{"id":"local","kind":"local"}` entry beside the remote one. With the object shape the window's
status bar shows the rig endpoint (`127.0.0.1:44551`) instead of `Backend offline`.

## 4. What is still open — the honest gap

With the gateway/question settled, the remaining wall is plugin **registration inside the window**.
Measured states on module `desktop/plugin.js` sha256 `4087908c1881df93bf0f7e71bbac65c2511aee3f115271f6b3f846091c9d03b7`
(installed copy sha-matched by `scripts/install-local.sh`):

| topology | window | backend | Coursebook route |
|---|---|---|---|
| isolated home + local connection | paints, `Backend needs setup` | never started (`runtime_exited`, §1) | absent |
| standalone profile `cp051rig` + local connection (`--profile cp051rig`) | paints, sessions load | ready (`43553`) | **absent**; `hermes:api` still logs `Invalid gateway ticket response` |
| private root + local connection | paints, sessions load | ready (`59983`…`)` | absent; `hermes:api` logs `403 profile_scope_mismatch` |
| isolated home + **remote** connection to `hermes serve --isolated` | paints; status bar names `127.0.0.1:44551` once the connection token uses the object shape (§3.1); earlier bare-string attempt painted `Backend offline` | ready (`44551`) | **absent** — no sidebar entry, no `[data-cb-route]` |

So: a private Desktop can reach a private backend, but on this host/checkout the Coursebook
Desktop half does not register in the window. That is a separate defect from the one in §1 and must
not be papered over with another card's frame (VISUAL-GATE rule 5 still applies).

Two things worth checking first on the next run, both cheap:

1. `Invalid gateway ticket response` on the `--profile` lane means Desktop's cached endpoint
   `instance_id` disagrees with the live owner (`control_socket.py: _session_ticket` raises
   `stale runtime instance` on mismatch). Minting by hand with the live id succeeds, so the fault is
   in Desktop's ensure→mint handoff on a freshly created profile, not in the gateway.
2. The plugin catalog is fetched over the gateway WS/RPC, never over `/api/plugins` (§2). Read what
   the window actually asked for before touching `desktop/plugin.js` again.

Neither is a plugin-code fault, and neither is fixed by restarting the default-profile gateway.

## 5. Operator action that opens the lane (single, exact)

If the next card cannot get a route after (1) and (2): the one operator step that closes the CB-017
gate is the CB-017 relaunch — restart the default-profile gateway **and** relaunch the operator's
Desktop from the same install:

```
hermes -p default gateway restart
```

That is an operator-owned action. A board worker must not run it: the default gateway is the parent
of the live agent/board session, so restarting it kills the run that asks for it. Until it is run,
every live capture either hits the stale owner or must borrow a frame, and borrowing is forbidden.

## 6. Using the rig

```
scripts/rig-private-desktop.sh                # install checkout plugin, backend 44551, CDP 9411
scripts/rig-private-desktop.sh --restart      # after a plugin.js change
scripts/rig-private-desktop.sh --status       # ports + installed/checkout shas
scripts/rig-private-desktop.sh --stop         # this rig only
node visual/find-cdp.mjs                      # which port actually paints [data-cb-route]
```

`--stop` kills only the PIDs recorded in `$STATE`. It never uses `pkill`, never
`hermes gateway stop`, and never touches `~/.config/Hermes` or another card's
`~/.hermes/coursebook-test-*` state.

## 7. Research credentials in an isolated rig (t_3e8b07ba) — blocked on host code

An isolated backend makes research look broken, and it is **not** a missing key:

```
plugins.web.perplexity.provider: Perplexity search error: Hermes could not read this profile's
PERPLEXITY_API_KEY (an internal profile-scoping bug on the multiplexed gateway, ...)
```

With research unavailable, `plan.validate` honestly returns `research_status: "unavailable"`, every
objective has no `source_ids`, and the validator refuses the draft on `source_support` — so no plan
can be approved in a rig, and the green course path cannot be measured there.

### 7.1 The mechanism (measured on host `1513f54f69`)

`hermes serve` activates multi-profile hosting fail-closed as its last boot step whenever the machine
has more than one servable profile home
(`tui_gateway/launch_profile_policy.py::activate_multi_profile_hosting_eagerly`). This host logs
`Multi-profile hosting activated at startup (12 servable profile homes)` even when `HERMES_HOME` is
a throwaway rig home, because the enumeration includes the machine's real profiles.

From then on a credential read is scope-checked **before** it may consult a `.env`:
`plugins/web/perplexity/provider.py::_perplexity_request` calls
`agent/web_search_provider.py::get_provider_env`, which calls
`hermes_cli/config.py::get_env_value`, whose **first** step is
`agent/secret_scope.py::get_secret`. With no profile scope bound and multiplexing on, that raises
`UnscopedSecretError`; the home's own `.env` is never reached, and `get_provider_env` re-raises
afterwards. Coursebook's plan tick starts at plugin *discovery* (`register()`), in a context with no
scope bound, so that is the context every research call inherits.

There is no config that turns this off: `gateway.multiplex_profiles: false` is retired and
deliberately ignored by the activation step.

### 7.2 Two workarounds were measured, and both stop short

**(a) A per-home `.env` alone does nothing.** With `<rig home>/.env` holding
`PERPLEXITY_API_KEY=...` (mode 600) and serve semantics, `get_provider_env` raised
`UnscopedSecretError` — the value was never read. In a process where multiplexing is *not* active the
same read returns that `.env`'s value (probe: `value_read: True`), so the file and the path
(`get_env_path()` → the rig home) are correct; only the scope binding is missing.

**(b) `plugins.isolation: host` fixes the plugin-side read but moves dispatch into the parent.**
With `plugins.isolation: host` (a supported host setting) the plugin loads in this home's own
plugin-host process (`hermes_cli/plugin_host.py::PluginHost._build_base_context` binds
`build_profile_secret_scope(self._home)`), and the plan tick runs there: logs show
`Plugin host started for <home>`, `coursebook job tick started on its own thread`,
`Mounted plugin API routes via the plugin host`. Two live plan jobs then failed, in order:

| run | what changed | `gen_research_runs` outcome |
|---|---|---|
| 1 | `plugins.isolation: host` | `unavailable` — `search failed: Unknown tool: web_search` |
| 2 | + one `tools.show` RPC (registers the agent tool list in the parent) | `unavailable` — `Error searching web: Hermes could not read this profile's PERPLEXITY_API_KEY`; **9** provider attempts, 0 successful searches (the same 9 lines appear in `logs/agent.log` and `logs/errors.log`) |

The first failure is `ctx.dispatch_tool("web_search", ...)` being executed by the parent `hermes
serve`, whose tool registry carries no `web_search` until something imports `model_tools`
(`hermes_cli/web_server*.py` never does). Once warmed, dispatch reaches the provider — and the
provider's own credential read happens **in the parent**, which is not running under the profile
scope either, so the card's original error returns verbatim. Host isolation therefore cannot deliver
research; it only relocates the failure.

### 7.3 What the repo can and cannot do

Repo-local work cannot make a rig research-capable. The read that fails is host code, named in §7.1;
binding a profile secret scope is host policy (`agent/secret_scope.py`), and the plugin `ctx` has no
supported method that runs plugin work under one. Do **not** work around it by importing
`agent.secret_scope` from plugin code: that is the plugin granting itself credentials, exactly what
the fail-closed flip exists to prevent.

What the repo does own is the *check* that will prove the fix, and the record of what was measured:

```
scripts/rig-research-acceptance.py --db <rig home>/plugin-data/coursebook/data.db --out <record>
```

It drives one `course.create` → one plan job over `cb.rpc`, then reads the backend's own rows. Exit 0
requires all three of: `gen_research_runs.status == "ok"`, a non-empty `sources` ledger for the
course, and at least one plan objective whose `provenance.source_ids` is non-empty. It never prints
`ok` on an `unavailable` run (covered by `tests/test_rig_research_acceptance.py`). The check also does
the `tools.show` warm-up described above, because it is required whenever a rig runs with
`plugins.isolation: host`.

### 7.4 The operator action that unblocks it

Land the launch-body secret-scope fix in the Hermes host checkout, so a plugin body at discovery
resolves credentials from the launch profile's own `.env`/env instead of raising:

```
git -C ~/.hermes/hermes-agent merge --ff-only wt/t_3e8b07ba-ready && hermes gateway restart
```

That branch is the two reviewed commits (`73b26e2323` H-68 launch-body scope, `2fb0469993` gating
`_plugin_launch_body_scope()` on `self.home_path == get_process_hermes_home()` — harbor's remedy)
rebased onto the checkout's own HEAD `1513f54f69`, so it fast-forwards with no rebase and no conflict;
its tree over `agent/ hermes_cli/ tests/` is identical to the original pair. After the restart,
re-run `scripts/rig-research-acceptance.py` on a fresh rig home; it must report
`research_status: "ok"` with a non-empty ledger and cited objectives.

