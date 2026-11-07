# Pronunciation STT seam — verdict, call chain, and the smallest missing host seam

Card: **M3-S1** (`t_43ec5abc`). Branch `wt/m3-pronunciation-seam`, based on master `4a33f2d`.
Host under test: Hermes Agent checkout `2bd378ed1b8d` (2026-11-05), Python 3.14.9.
Probe: `probes/p8_stt_seam.py` → evidence `probes/raw/p8/stt_seam.json` (run 2026-11-07T03:12Z).

This card is a seam spike. It adds no product code, no scoring UI, no attempt mutation and no
`model_assessed` evidence. The probe used a synthetic 0.5 s 16 kHz mono **silence** WAV
(sha256 `358c6dcef444…`, see the evidence file) and a fake provider; it contacted no provider, read no
credential, and uploaded nothing.

---

## Verdict

**BLOCKED — no documented plugin seam reaches the host's configured speech-to-text.**

**Decision 2026-11-06:** the product line will use the **plugin-owned local fallback** for the
first slice. The host seam remains the preferred upstreaming target, but no pronunciation
feature will wait on a core change. `M3-B1` now builds an optional `faster-whisper` adapter
inside Coursebook: local-only, no provider key, no `stt.provider` hijack, model cached under the
plugin data directory, and an explicit practice-only state when the dependency or model is
unavailable. The adapter is never labelled as the host's STT.

A plugin can *be* an STT backend; it cannot *use* the host's STT. The three plausible seams were
each tested and each fails:

| # | Candidate seam | Result | Decisive evidence |
|---|---|---|---|
| 1 | Register a `TranscriptionProvider` that delegates to the host's configured STT | **NO** — it is a backend, dispatched only when the user sets the host-wide `stt.provider` to the plugin's name; it receives no config, no key and no host client | `probes/raw/p8/stt_seam.json` → `builtin_wins_over_plugin`, `plugin_provider_dispatch` |
| 2 | Reach `POST /api/audio/transcribe` from the plugin (desktop or Python half) | **NO** — `ctx.rest`/`ctx.socket` are namespaced to `/api/plugins/<id>` by construction; `host.request` is JSON-RPC with no audio method; `ctx.dispatch_tool` has no transcription tool | `no_transcription_tool`, `no_transcription_rpc`, `ctx_rest_is_namespaced`, `ctx_has_no_stt_request` |
| 3 | Import `tools.transcription_tools` from `plugin_api.py` | **NO** — works only as forbidden private coupling; flagged by the admission lint, off the public allowlist, and the dashboard router moves to the plugin-host process under `plugins.isolation: host` | `private_import_is_flagged` |

The plan's open decision 3 (`docs/VISUAL_MEDIA_PLAN.md` §13) — “use the host's configured STT
provider; do not add a plugin credential path” — is therefore **not implementable today**. The
plan needs one host-side prerequisite (below) before anyone writes a pronunciation score.

---

## 1. Trace: what `register_transcription_provider` actually gives a plugin

Registration path:

- `agent/transcription_provider.py:19` — `TranscriptionProvider(CatalogProviderBase)` with one
  required method, `transcribe(file_path, *, model=None, language=None, **extra)`; envelope
  `{success, transcript, provider, error}`.
- `agent/transcription_registry.py:37-45` — the registry, with a hard-coded built-in set
  (`local, local_command, groq, openai, mistral, xai, elevenlabs, deepinfra`) at `:23`.
- `hermes_cli/plugins_registrars.py:80-84` — `ctx.register_transcription_provider` is generated
  from that registry row; a built-in name is refused at registration
  (`agent/provider_registry.py:83-89`, warning at `transcription_registry.py:28-33`).

Dispatch path (one call, exactly):

```
tools/transcription_tools.py:566  transcribe_audio(file_path, model=None, source=None)
  :433  _transcribe_prepared_audio(...)
  :443    stt_config = _load_stt_config()            # the HOST's config.yaml `stt:`
  :446    provider = _get_provider(stt_config)       # :249 — the HOST's stt.provider
  :517    _dispatch_stt_provider(...)
  :522      _route_stt_provider(...)
  :525        provider in BUILTIN_STT_PROVIDERS  ->  globals()[f"_transcribe_{provider}"]
  :534        command provider (stt.providers.<name>: type: command) wins next  (:535-538)
  :540      _dispatch_to_plugin_provider(...)   (tools/transcription_command.py:156)
             -> agent.transcription_registry.get_provider(key)
             -> plugin.transcribe(file_path, model=, language=, prompt=)
```

What the plugin provider is handed (probe `plugin_provider_dispatch`, captured call):
`{file_path, model="probe-model", language="ja", prompt=None, extra_keys=[]}`. It is **not** handed
`stt_config`, the resolved provider, an API key, an HTTP client, or any host object.

Consequences, all observed:

1. **Built-ins always win.** With `stt.provider: local` (the legacy default) the built-in handler
   runs and the plugin provider is never consulted — `builtin_wins_over_plugin`: builtin calls 1,
   plugin calls 0.
2. **Opting in is a host-wide config change.** A plugin provider runs only when the user sets
   `stt.provider: <plugin-name>`. That same setting drives Desktop dictation, voice notes, inbound
   gateway audio and the live voice loop — the plugin would hijack all of them.
3. **Registration is a backend contract, not a client.** To return a transcript the provider must
   run speech recognition itself: read a provider key, call a vendor SDK, or ship a local model.
   The registry has no “delegate to the configured provider” mode.
4. **A built-in name cannot be shadowed.** Registering `name = "openai"` is dropped with a warning —
   `builtin_name_rejected`.

So the answer to question 1 is: **no, not in the sense that matters.** A plugin can register a
`TranscriptionProvider`, and that provider can be *selected* by the operator, but it can never
borrow the host's STT; it replaces it.

---

## 2. Trace: can the plugin backend reach `/api/audio/transcribe`?

The endpoint is real and does exactly what pronunciation would want:

- `hermes_cli/web_routers/audio.py:89-149` — `POST /api/audio/transcribe`, body is a base64 data
  URL (`audio/*` or `video/webm`), writes a temp file, calls
  `tools.voice_mode.transcribe_recording` (`:126-129`), returns `{ok, transcript, provider}`;
  empty transcript is a successful empty result, other failures are HTTP 400.
- Mounted on the host web app at `hermes_cli/web_server.py:825`.
- Desktop client: `apps/desktop/src/api/system.ts:183-205` (`transcribeAudio`) through
  `window.hermesDesktop.api` — Electron main `apps/desktop/electron/main.ts:16081`, preload
  `apps/desktop/electron/preload.ts:358`.

Every documented plugin door, and why it does not reach that route:

| Door | Scope by construction | Evidence |
|---|---|---|
| `ctx.rest(path)` | `path: /api/plugins/${pluginId}${suffix}`; `..` rejected; source comment: “a plugin can't address another plugin's API or a core route through it” | `apps/desktop/src/api/plugins.ts:53-86` |
| `ctx.socket(path)` | same namespace, URL minted per plugin | `plugins.ts:104-130` |
| `host.request(method)` | gateway JSON-RPC; 150 declared methods scanned, **zero** match `transcri|audio|stt` | `tui_gateway/methods_*.py` scan; `apps/desktop/src/sdk/index.ts:1503-1511` |
| `ctx.dispatch_tool(name,args)` | thin wrapper over `tools.registry.registry.dispatch` (`hermes_cli/plugins.py:676-684`); the model tool surface is 22 tools, `text_to_speech` is the only audio tool, and `dispatch("transcribe_audio")` returns `{"error": "Unknown tool: transcribe_audio"}` | `no_transcription_tool` |
| Python `ctx` | 57 public members; the only audio member is `register_transcription_provider` (a backend registration). No request method. | `ctx_has_no_stt_request` |

Question 2 is therefore **disproved**: there is no documented seam from either plugin half to
`/api/audio/transcribe`, and no host tool or RPC that does file→transcript.

### Undocumented routes that exist, and why they are not seams

Reported for honesty and for the host team — **neither is adopted**:

1. **Private core import in `plugin_api.py`.** `from tools.transcription_tools import
   transcribe_audio` works today because the dashboard router is imported into the web-server
   process, and under `plugins.isolation: host` the same router is served from the plugin-host
   process (`hermes_cli/web_server_dashboard.py:1017-1044`), which also has `hermes_cli` on its
   path. It is nonetheless:
   - flagged at admission (`private_import_is_flagged`: `plugin_api.py:1
     tools.transcription_tools.transcribe_audio`), because `tools.*` is not on the public allowlist
     (`hermes_cli/plugin_validate_private_imports.py:27-68`) — catalog rule 9;
   - a second Hermes tool stack with its own config/provider state inside the plugin host;
   - a direct violation of this card's hard limit (“use the documented plugin seams only”) and of
     `plugin.yaml`'s standing promise that Coursebook stores no secrets and reads no provider key.
2. **`window.hermesDesktop.api` from plugin JS.** The Electron bridge is exposed to the whole
   renderer (`preload.ts:358`) and its handler does not check the caller (`main.ts:16081`), so a
   plugin module could POST `/api/audio/transcribe` directly, bypassing `ctx.rest`. It is
   undocumented, Electron-only, has no Python equivalent, and depends on a bridge the SDK
   explicitly does not grant plugins. This is a host hardening observation (plugin JS is not
   sandboxed from the renderer bridge), not a product seam.

---

## 3. The smallest generic addition that makes pronunciation possible

One method, one capability, one wire entry — no key exposure, no new egress path, no weakening of
isolation:

```python
# hermes_cli/plugins.py — PluginContext
def transcribe_audio(self, file_path: str, *, language: str | None = None,
                     prompt: str | None = None) -> dict:
    """Transcribe a plugin-owned file with the host's configured STT. Returns the standard
    envelope {success, transcript, provider, error}. Never exposes provider config or keys."""
```

Implementation contract:

1. Calls `tools.transcription_tools.transcribe_audio(file_path, source="plugin:<id>")` — the
   host's configured provider decides the backend, model and endpoint. The plugin passes only a
   language/prompt hint.
2. **Capability-gated**: new `audio.transcribe` capability in `plugin.yaml`, granted through the
   existing consent flow; absent/declined → `{"success": False, "error": "audio.transcribe not
   granted"}`, the plugin degrades to practice-only.
3. **Path allowlist**: only files under the plugin's own data directory or a user-granted folder;
   reject everything else before dispatch (same rule the desktop `ctx.files` door already uses).
4. **Bounds**: the existing upload cap plus an explicit max duration; refuse oversize with a
   stated error.
5. **Wire**: plain-data method in the plugin-host protocol (like `ctx.state`/`ctx.llm` calls), so
   it works under both `in_process` and `host` isolation; add it to the isolation audit table so
   “pool-safe” and “loads in the host” cannot drift
   (`hermes_cli/plugin_isolation.py:54-74` is the table).
6. **Audit**: log `(plugin, provider, bytes, sha256[:12], duration)` and never the transcript.

Call chain the Coursebook plugin would then have:

```
desktop plugin.js  -> ctx.rest('/pronunciation/attempt', {audio_data_url, locale})   # own namespace
plugin_api.py      -> ctx.transcribe_audio(take_path, language=locale)              # host seam
                   -> tools.transcription_tools.transcribe_audio(...)               # host configured STT
                   -> {success, transcript, provider}
coursebook         -> scoring adapter (word-level comparison) -> attempt(evidence_class=model_assessed)
```

No plugin-held key at any step. The egress destination is whatever the operator already configured.

**Fallback if the host seam is not upstreamed before the product line needs it**: Coursebook runs
its **own local** STT (`faster-whisper`) as a `python_dependency`, model cached under the plugin
data dir, opt-in, local-only, and **not** registered as the host provider (no `stt.provider`
hijack). It reads no provider key and never uploads audio, which suits parent/child use; the cost
is a ~100–200 MB dependency, a slower first run, and a second STT stack on the machine. It must be
labelled as Coursebook's own recogniser, never as “the host's STT”.

---

## 4. Privacy and egress

- **Today's configured provider decides.** With `stt.provider: openai` (the current plan text) the
  audio leaves the machine to OpenAI; with `local` it stays on device via faster-whisper. The
  plugin must disclose the provider name before the first upload and show it in the attempt record
  provenance.
- **A pronunciation take is voice data**, and in Parent mode it can be a child's voice. Requirements
  for the implementation card: explicit record action only; no background capture; take deleted
  after scoring unless the learner saves it; never in a pack, export, notebook or telemetry;
  transcript stored only as the evidence field the score needs (no raw audio in the DB); logs carry
  a path hash, not a transcript.
- **Recommended default for the first slice: local-only.** If `stt.provider` is a cloud provider,
  the pronunciation surface says “practice only, not graded — the configured speech provider is
  cloud” and does not upload, until a parent/learner opts in for that lesson.
- The host seam adds no egress. It makes the existing, already-configured destination reachable
  from a plugin — nothing more.

---

## 5. Failure behaviour (fail closed)

| Condition | Result | Evidence / rule |
|---|---|---|
| no STT configured / `stt.enabled: false` | `verdict: unavailable`, UI “practice only, not graded”, **no attempt row with `model_assessed`**, no score | `tools/transcription_tools.py:444`, `:546-563` |
| provider error / outage | same unavailable state; error text shown; retry allowed; no partial evidence | envelope `success=False` |
| empty transcript (silence) | “didn't catch that — try again”, no evidence | `web_routers/audio.py:133-138` maps empty transcript to `ok` |
| take too large / too long / unsupported mime | refused before dispatch with a stated error | `audio.py:103-113`; seam adds duration bound |
| `audio.transcribe` capability not granted | unavailable state, plugin keeps working | capability contract |
| seam absent (today) | **blocked** — the UI may offer practice playback only; no recording control that implies a score | this document |

A provider failure must never produce a fabricated transcript, a placeholder score, or an attempt
with `evidence_class=model_assessed`. That is the whole point of this card.

---

## 6. Recommended bounded implementation card

**M3-S2 — Host STT request seam + coursebook practice-only attempt (split delivery).**

Part A (host, upstream, generic; reviewer: host maintainers):
- `PluginContext.transcribe_audio` + `audio.transcribe` capability + path allowlist + bounds + host
  wire entry + isolation-audit row, per §3. One method, one capability, no provider changes.

Part B (Coursebook, ships only after Part A lands):
- `POST /api/plugins/coursebook/pronunciation/attempt` taking a bounded data URL (own `ctx.rest`
  namespace, reuse the media route's MIME/size rules);
- scoring adapter: transcript vs target, word-level comparison, `verdict`, nullable phoneme
  confidence — no single opaque similarity number;
- attempt row `evidence_class=model_assessed` **only** when a real transcript came back; dispute
  handle; take deleted by default;
- UI: record → transcribing → word-diff → verdict, plus the explicit unavailable state.

Out of scope for that card: pitch-accent scoring, free-speech scoring, cloud opt-in flow, any
provider key, any pack audio.

**Do not start Part B before Part A lands.** Without it, any pronunciation UI is either a fake score
or a private-import violation.

---

## 7. Probe evidence

Reproduce: `python3 probes/p8_stt_seam.py` (needs the host checkout; `HERMES_HOST_CHECKOUT`
overrides `~/.hermes/hermes-agent`). Output: `probes/raw/p8/stt_seam.json`. Exit 0 = probe suite
completed with a definite verdict; every `pass` is the host behaving as recorded.

| Probe | Result | What it proves |
|---|---|---|
| `provider_registers` | PASS | a plugin `TranscriptionProvider` can be registered |
| `builtin_name_rejected` | PASS | built-in names cannot be shadowed |
| `builtin_wins_over_plugin` | PASS | `stt.provider: local` never reaches a plugin provider |
| `plugin_provider_dispatch` | PASS | the provider receives file path + hints only; no config, no key, no host client |
| `transcribe_audio_end_to_end` | PASS | `transcribe_audio` dispatches to the plugin backend *when named*; with the real fake it returns only what the fake wrote |
| `no_transcription_tool` | PASS | 22 model tools, `text_to_speech` only; `dispatch("transcribe_audio")` → `Unknown tool` |
| `ctx_has_no_stt_request` | PASS | 57 ctx members, no transcription request method |
| `private_import_is_flagged` | PASS | `tools.transcription_tools` import is flagged; `agent.transcription_provider` is clean |
| `no_transcription_rpc` | PASS | 150 gateway RPC methods, none transcribe audio |
| `ctx_rest_is_namespaced` | PASS | `ctx.rest` is `/api/plugins/<id>` by construction and rejects traversal |

Test doubles used (and declared in the script): `tools.transcription_tools._load_stt_config`
(forces the provider name), `tools.transcription_tools._transcribe_local` (records the built-in
branch instead of loading Whisper), and `hermes_cli.plugins._ensure_plugins_discovered` (prevents
loading the operator's real plugins in the probe process). No provider was contacted, no
credential read, no real recording used.

---

## 8. What this changes in the plan

- `docs/VISUAL_MEDIA_PLAN.md` §5.1 (“Future pronunciation scoring needs a host STT seam. Until a
  public seam exists…”) is now precise: the seam does **not** exist, and `register_transcription_provider`
  is not it.
- §7 step 4 (“the backend sends the take through the host STT adapter”) is blocked on Part A.
- §13 open decision 3 stays the right product decision but gains a prerequisite: the host seam must
  be added first; the plugin-local fallback (§3) is the only no-host-change path and must be
  labelled as Coursebook's own recogniser.
- Until then, the pronunciation surface is practice playback only: reference audio, transcript,
  romaji/furigana scaffolds, and no score.
