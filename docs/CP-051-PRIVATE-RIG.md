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
