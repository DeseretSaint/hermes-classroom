# An isolated `hermes serve` cannot read `PERPLEXITY_API_KEY`: the failing lookup path

| | |
|---|---|
| Subject | Web-search credential resolution inside an isolated backend |
| Blocked card | `t_3e8b07ba` (research-dependent acceptance) |
| Repo state | origin/master `b7ed6cf0`; worktree `bfe66db5` (branch `wt/t_f818a065`) |
| Host under test | `hermes-agent` checkout `1513f54f69` (`v0.23.1+1.g1513f54`), unmodified by this probe |
| Measured | 2026-11-13, host `DeseretDesktop` |
| Verdict | Host defect, not configuration. A plugin body born at `register()` reads credentials in a context that no profile scope covers, and once `hermes serve` flips to multi-profile hosting the read raises instead of consulting the home's own `.env`. |

No credential value appears in this document, in the reproduction, or in any command it quotes. The
probe home used a sentinel (`probe-sentinel-not-a-key`), which is why the evidence can be shown
verbatim: a "resolved" reading proves the file was consulted; a raise proves it was not.

## 1. The failing lookup path, with file:line

Reading `PERPLEXITY_API_KEY` from a search performed by a plugin body inside the isolated backend
walks this chain, and stops at the last entry:

| # | Frame | What it does |
|---|---|---|
| 1 | `plugins/web/perplexity/provider.py:95` (`_perplexity_request`) | `api_key = get_provider_env("PERPLEXITY_API_KEY")` |
| 2 | `agent/web_search_provider.py:37` (`get_provider_env`) | `val = get_env_value(name)` |
| 3 | `hermes_cli/config.py:2822` (`get_env_value`) | `val = _scoped_environ_get(key)` |
| 4 | `hermes_cli/config.py:2808` (`_scoped_environ_get`) | `return _get_secret(key)` |
| 5 | `agent/secret_scope.py:252` (`get_secret`) | raises `UnscopedSecretError` |

`get_env_value` is a two-step reader: line 2822 takes the environment value through the
scope-aware `get_secret`, and line 2823 (`return load_env().get(key) if val is None else val`)
is where `~/.hermes/.env` (here, `<HERMES_HOME>/.env`) would be consulted. The raise at
`secret_scope.py:252` fires inside step 1 of that pair, so line 2823 is never reached. The
home's `.env` is not read even when it exists and holds the key.

The gate itself is six lines of `get_secret` (`agent/secret_scope.py:242-252`):

```
242    bound = _SECRET_SCOPE.get()
243    if bound is not None:
248    if is_multiplex_active():
249        launch_scope = _LAUNCH_BODY_SCOPE.get()
250        if launch_scope is not None:
251            return launch_scope().get(name, default)
252        raise UnscopedSecretError(
```

(Line 244-247, the bound-scope branch, is elided above; line 261 is the fall-through quoted in
section 2.)

So the read fails on exactly one condition: multiplexing is active and neither a profile scope
nor a launch-body scope is bound in this context.

### Why that context exists

`hermes serve` activates multi-profile hosting as its last boot step
(`hermes_cli/web_server.py:1511`, which calls `activate_multi_profile_hosting_eagerly` at
`tui_gateway/launch_profile_policy.py:71`). It does so whenever the machine can serve more than one
profile home, including a throwaway rig home. Activation is one-way and process-wide.

Coursebook's plan tick is born earlier, in plugin discovery: `register(ctx)` starts a long-lived
worker under `contextvars.copy_context()`. That copied context predates activation and carries no
secret scope. The existing seam for this ordering, `launch_body()`
(`tui_gateway/launch_profile_policy.py:171`), is entered for adapter bodies and routed turns, but
not for plugin discovery on this checkout, which is why the copied context has neither a bound
scope nor a launch-body scope at line 249.

This is the same finding already recorded in `docs/CP-051-PRIVATE-RIG.md` sections 7.1 and 7.2 and
in `audit/adversarial/h63-live-generation/H63F-evidence.json` (D-H63-3). What this note adds is a
deterministic reproduction that does not depend on a real key, and the exact frames above.

## 2. The working lookup path

The identical call in a single-profile process (plain CLI, multiplexing inactive) takes the
same first four frames and then diverges at `agent/secret_scope.py:248`: `is_multiplex_active()`
is false, so execution falls to line 261, `return _environ_or(name, default)`
(`agent/secret_scope.py:225`, whose `os.environ` read is line 226). That returns `None` when the key
is not in the process environment, `get_env_value` then reaches `hermes_cli/config.py:2823`, and
`load_env()` (`hermes_cli/config.py:2414`) resolves `<HERMES_HOME>/.env` via
`get_env_path()` (`hermes_cli/config.py:473`).

Measured, same home, same file, same key name:

```
$ HERMES_HOME=<probe home> python3 probe_control.py
{ "env_file_exists": true,
  "env_path": ".../scope-probe-home/.env",
  "multiplex_active": false,
  "result": "resolved",
  "value_is_sentinel": true }
```

When the file is absent, that path degrades cleanly: the provider reports a missing key rather
than an internal scoping bug (`plugins/web/perplexity/provider.py:103`):

```
$ HERMES_HOME=~/.hermes/coursebook-test-cp015g-r3/home python3 probe_control.py
{ "env_file_exists": false,
  "multiplex_active": false,
  "result": "empty",
  "provider_call": "RAISED ValueError",
  "provider_message_first_line": "PERPLEXITY_API_KEY is not set. Get a key at https://www.perplexity.ai/account/api" }
```

The differing step is `agent/secret_scope.py:248`, reached from `hermes_cli/config.py:2822`,
before `hermes_cli/config.py:2823` can read the home's `.env`.

## 3. Reproduction

The probe is a small plugin whose `register(ctx)` starts a worker under
`contextvars.copy_context()`, the same birth a Coursebook job tick has, and samples
`get_provider_env("PERPLEXITY_API_KEY")` plus the production frame
`_perplexity_request("search", ...)`. It is installed into a disposable home, never into a profile
or another card's rig, and it ships with nothing.

1. Disposable home `$H` with `config.yaml` enabling the probe and a sentinel `.env`
   (`PERPLEXITY_API_KEY=probe-sentinel-not-a-key`, mode 600).
2. `$H/plugins/scope-probe/{plugin.yaml,__init__.py}`, the probe (source in Appendix A).
3. Start the real isolated backend:

```
$ HERMES_HOME=$H hermes serve --isolated --port 44619 --skip-build
```

4. The worker's own record, written by the serve process itself:

```json
{
  "samples": [
    {
      "env_file_exists": true,
      "env_path": ".../scope-probe-home/.env",
      "hermes_home": ".../scope-probe-home",
      "message_first_line": "Hermes could not read this profile's PERPLEXITY_API_KEY (an internal profile-scoping bug on the multiplexed gateway, not your configuration). Run `hermes gateway restart`; if it keeps happening, report it with `hermes debug share`.",
      "multiplex_active": true,
      "pid": 516258,
      "provider_call": "RAISED UnscopedSecretError",
      "provider_message_first_line": "Hermes could not read this profile's PERPLEXITY_API_KEY (an internal profile-scoping bug on the multiplexed gateway, not your configuration). Run `hermes gateway restart`; if it keeps happening, report it with `hermes debug share`.",
      "provider_traceback_tail": [
        "__init__.py:67 in _record",
        "provider.py:95 in _perplexity_request",
        "web_search_provider.py:37 in get_provider_env",
        "config.py:2822 in get_env_value",
        "config.py:2808 in _scoped_environ_get",
        "secret_scope.py:252 in get_secret"
      ],
      "result": "RAISED UnscopedSecretError",
      "scope_bound": false,
      "sample": 0
    }
  ]
}
```

The traceback is the section 1 table, produced by the host itself, in order. Note
`"env_file_exists": true` and `"scope_bound": false` in the same record: the file was there and
the read never looked.

### Control matrix (all measured, same host, same minute)

| Process | `<home>/.env` | `multiplex_active` | `scope_bound` | Result |
|---|---|---|---|---|
| plain CLI, probe home | present (sentinel) | false | false | `resolved`, `value_is_sentinel: true` |
| plain CLI, rig home `cp015g-r3` | absent | false | false | `empty` then `ValueError: PERPLEXITY_API_KEY is not set` (`provider.py:103`) |
| `hermes serve --isolated`, probe home | present (sentinel) | true | false | `UnscopedSecretError` (`secret_scope.py:252`) |

Only the third row raises, and it raises because it is the isolated backend, not because the
credential is missing.

## 4. A second, independent gap in the card's rig home

`~/.hermes/coursebook-test-cp015g-r3/home` has no `.env` and no credential of any kind: no
`auth.json`, no secret-source plugin loaded, and `PERPLEXITY_API_KEY` is absent from every `.env`
on the host (11 files scanned) and from every live process environment. Two consequences:

1. Today the failure the card sees is the scoping raise of section 1.
2. After the host fix lands, that same home would produce the clean "not set" error of section 2,
   still no research, because the rig home has nothing to read.

Fixing the host bug is therefore necessary but not sufficient for `cp015g-r3`. The rig needs a
credential, and that is a secret-handling decision, not a code change. See section 6.

## 5. The one recommended fix

Land the reviewed launch-body scope for plugin discovery in the host checkout. The fix exists,
is reviewed, and is not on the running checkout: branch `wt/t_3e8b07ba-ready` adds
`_plugin_launch_body_scope` (`hermes_cli/plugins_loader.py:194` on that branch) and enters it around
discovery (`hermes_cli/plugins.py:405`), so a `register()`-time worker gets the launch profile's own
frozen mapping when the process flips to fail-closed. `HEAD` (`1513f54f69`) contains neither symbol.
The branch is two commits ahead (`73b26e2323` H-68 launch-body scope, `2fb0469993` gating on the
manager's own home) and fast-forwards:

```
git -C ~/.hermes/hermes-agent merge --ff-only wt/t_3e8b07ba-ready && hermes gateway restart
```

That is an operator command: the gateway being restarted parents the live board session. Verify
afterwards with `scripts/rig-research-acceptance.py` (exit 0 requires `gen_research_runs.status ==
"ok"`, a non-empty `sources` ledger, and a cited objective).

`gateway.multiplex_profiles: false` is not the fix: the activation step at
`hermes_cli/web_server.py:1511` deliberately ignores it. Neither is `plugins.isolation: host`, which
moves dispatch into the parent process, equally unscoped (measured in
`docs/CP-051-PRIVATE-RIG.md` section 7.2b).

## 6. Owner action this document does not perform

Provisioning a credential into a rig home means copying a live secret onto disk in a directory that
test scripts, screenshots and `hermes debug share` bundles can reach, outside the operator's
600-mode `.env` and outside its rotation. It also converts "no key" failures into billed provider
calls on every isolated boot of that home. Not run here, and not recommended as a routine
practice. The decision belongs to the owner (@DeseretSaint for spend and secret placement, @Atlas
for host policy):

- Preferred: land the fix, then point `web.search_backend` at a keyless backend for rigs where only
  search is needed, accepting that `web_extract` still needs its own provider.
- If a key must exist in a rig: give that home its own dedicated, low-quota key (never the
  operator's), `chmod 600` the `.env`, and delete the home when the card closes.

## 7. What this document does not claim

- It does not claim the pack, the course, or any content is safe. This is a credential-resolution
  defect, and no hash or review badge is offered as evidence of anything else.
- It does not claim `cp015g-r3` will be research-capable after the fix (section 4).
- It does not claim the error's "internal profile-scoping bug" phrasing is wrong: on this checkout
  it is accurate, and the message is emitted by the host, not by Coursebook.

## Appendix A: the probe (diagnostic only, never shipped)

`$H/config.yaml`:

```yaml
plugins:
  enabled:
    - scope-probe
  disabled: []
```

`$H/.env` (sentinel, mode 600): `PERPLEXITY_API_KEY=probe-sentinel-not-a-key`

`$H/plugins/scope-probe/plugin.yaml`:

```yaml
name: scope-probe
version: 1.0.0
description: "Diagnostic probe: resolves a provider credential from a plugin register-time worker (Lattice t_f818a065). Never ships."
```

`$H/plugins/scope-probe/__init__.py`, the essential part:

```python
import contextvars, json, os, threading, time

def _record():
    from agent.secret_scope import current_secret_scope, is_multiplex_active
    from agent.web_search_provider import get_provider_env
    rec = {"multiplex_active": is_multiplex_active(),
           "scope_bound": current_secret_scope() is not None}
    try:
        rec["value_is_sentinel"] = get_provider_env("PERPLEXITY_API_KEY") == "probe-sentinel-not-a-key"
        rec["result"] = "resolved"
    except Exception as exc:
        rec["result"] = "RAISED " + type(exc).__name__
        rec["message_first_line"] = str(exc).splitlines()[0]
    return rec

def _worker():
    time.sleep(5)  # plugin born before serve's last-boot-step activation
    with open(os.path.join(os.environ["HERMES_HOME"], "scope-probe.json"), "w") as fh:
        json.dump(_record(), fh, indent=2)

def register(ctx):
    copied = contextvars.copy_context()   # the birth Coursebook's job tick has
    threading.Thread(target=lambda: copied.run(_worker), daemon=True).start()
```

Run it as a plain process for the working path (no thread, no activation), and under
`hermes serve --isolated` for the failing path.
