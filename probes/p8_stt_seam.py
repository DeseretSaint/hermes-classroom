#!/usr/bin/env python3
"""P8 — pronunciation STT seam probe (M3-S1).

Bounded, offline probe. It answers one question: **can the Coursebook plugin obtain a
transcript from the host's configured speech-to-text without reading a provider key,
without uploading real audio and without importing a private core module?**

The probe never contacts a provider. It uses:
  * a synthetic 0.5 s 16 kHz mono silence WAV written to a temp dir,
  * a fake ``TranscriptionProvider`` registered through the real registry,
  * test doubles for two module attributes the host's own tests also patch
    (``tools.transcription_tools._transcribe_local`` and
    ``hermes_cli.plugins._ensure_plugins_discovered``).

Every result is written to ``probes/raw/p8/stt_seam.json`` and printed as a ``RESULT`` line.
Run: ``python3 probes/p8_stt_seam.py`` (needs the host checkout; set HERMES_HOST_CHECKOUT to
override ``~/.hermes/hermes-agent``).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

HOST = Path(os.environ.get("HERMES_HOST_CHECKOUT") or (Path.home() / ".hermes" / "hermes-agent"))
OUT_DIR = Path(__file__).resolve().parent / "raw" / "p8"
OUT_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HOST))

results: dict[str, Any] = {"host_checkout": str(HOST), "probes": {}}


def record(name: str, passed: bool, **payload) -> None:
    results["probes"][name] = {"pass": passed, **payload}
    print(f"RESULT {name} {'PASS' if passed else 'FAIL'} {json.dumps(payload, sort_keys=True)[:900]}")


def synthetic_wav() -> Path:
    """0.5 s of 16 kHz mono s16le silence — no speech, no person, no upload."""
    path = Path(tempfile.mkdtemp(prefix="cb-p8-stt-")) / "probe.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<" + "h" * 8000, *([0] * 8000)))
    return path


def main() -> int:
    wav = synthetic_wav()
    results["synthetic_wav"] = {
        "path_name": wav.name, "bytes": wav.stat().st_size,
        "sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
        "format": "16000 Hz mono s16le, 0.5 s silence",
    }

    from agent.transcription_provider import TranscriptionProvider
    import agent.transcription_registry as treg

    class FakeProvider(TranscriptionProvider):
        @property
        def name(self) -> str:
            return "coursebook_probe_stt"

        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def transcribe(self, file_path, *, model=None, language=None, **extra):
            self.calls.append({
                "file_path_suffix": Path(file_path).name,
                "model": model, "language": language,
                "extra_keys": sorted(extra),
                "prompt": extra.get("prompt"),
            })
            return {"success": True, "transcript": "probe transcript", "provider": self.name}

    class BuiltinNamed(TranscriptionProvider):
        @property
        def name(self) -> str:
            return "openai"

        def transcribe(self, file_path, *, model=None, language=None, **extra):
            raise AssertionError("a built-in-named provider must never be dispatched")

    fake = FakeProvider()
    treg.register_provider(fake)
    record("provider_registers", treg.get_provider("coursebook_probe_stt") is fake,
           registered_name="coursebook_probe_stt")

    treg.register_provider(BuiltinNamed())
    record("builtin_name_rejected", treg.get_provider("openai") is None,
           reason="built-in STT names always win; registration is dropped with a warning")

    import tools.transcription_tools as tt
    from unittest.mock import patch

    def _no_plugin_discovery(*_a, **_k) -> None:
        """Probe double: do not load the operator's real plugins into this process."""

    # --- Probe A: a built-in provider never consults the plugin registry -------------------
    builtin_calls: list[dict[str, object]] = []

    def _record_builtin(path, model, language=None, prompt=None):
        builtin_calls.append({"model": model, "language": language})
        return {"success": True, "transcript": "builtin", "provider": "local"}

    # The host's own tests patch `_transcribe_local` for the same reason (the module looks the
    # handler up at call time): record the built-in branch instead of loading Whisper.
    with patch.object(tt, "_transcribe_local", _record_builtin):
        out_builtin = tt._dispatch_stt_provider(str(wav), "local", {"provider": "local"}, None, "probe")
    record("builtin_wins_over_plugin", bool(builtin_calls) and fake.calls == [],
           builtin_handler_calls=len(builtin_calls), plugin_provider_calls=len(fake.calls),
           envelope=out_builtin, note="stt.provider=local (the default) never reaches a plugin")

    # --- Probe B: what a plugin provider is handed when the user opts into it -------------
    import hermes_cli.plugins as hc_plugins

    with patch.object(hc_plugins, "_ensure_plugins_discovered", _no_plugin_discovery):
        out_plugin = tt._dispatch_stt_provider(
            str(wav), "coursebook_probe_stt",
            {"provider": "coursebook_probe_stt", "language": "ja"},
            model="probe-model", source="probe",
        )

    record("plugin_provider_dispatch", len(fake.calls) == 1 and out_plugin.get("success") is True,
           call=fake.calls[0] if fake.calls else None, envelope=out_plugin,
           note="the provider receives the file path and hints ONLY — no stt_config, no credential, "
                "no host STT handle. To return a transcript it must run an STT backend itself.")

    # --- Probe C: the end-to-end entry point, same fake, host config doubled --------------
    with patch.object(tt, "_load_stt_config", lambda: {"enabled": True, "provider": "coursebook_probe_stt"}), \
            patch.object(hc_plugins, "_ensure_plugins_discovered", _no_plugin_discovery):
        e2e = tt.transcribe_audio(str(wav), source="probe")
    record("transcribe_audio_end_to_end", e2e.get("success") is True and e2e.get("transcript") == "probe transcript",
           envelope=e2e, note="the seam works only because a fake backend was registered; "
                              "nothing in this path supplies real speech recognition")

    # --- Probe D: the host tool surface the plugin may dispatch -------------------------
    import model_tools
    defs = model_tools.get_tool_definitions(quiet_mode=True) or []
    names = sorted({d.get("function", {}).get("name") for d in defs if d.get("function")})
    stt_tools = [n for n in names if any(k in n.lower() for k in ("transcri", "audio", "voice", "speech"))]
    from tools.registry import registry
    dispatch_err = registry.dispatch("transcribe_audio", {}, scope=None)
    record("no_transcription_tool", "transcribe_audio" not in names and "transcribe_audio" not in stt_tools,
           tool_count=len(names), audio_like_tools=stt_tools, dispatch_result=str(dispatch_err)[:300],
           note="ctx.dispatch_tool is a thin wrapper over registry.dispatch (hermes_cli/plugins.py:676)")

    # --- Probe E: the documented ctx surface --------------------------------------------
    from hermes_cli.plugins import PluginContext
    members = sorted(m for m in dir(PluginContext) if not m.startswith("_"))
    audio_members = [m for m in members if any(k in m.lower() for k in ("audio", "transcri", "stt", "speech", "voice"))]
    # `register_transcription_provider` installs a BACKEND the host may dispatch to; it does not
    # perform a transcription. Only a member that would *run* one counts as a request seam.
    request_members = [m for m in audio_members if not m.startswith("register_")]
    record("ctx_has_no_stt_request", request_members == [],
           member_count=len(members), audio_members=audio_members, request_members=request_members,
           note="ctx.register_transcription_provider only installs a backend (Probe B shows what "
                "that backend is handed); no ctx member performs a transcription and ctx.rest/"
                "ctx.socket are desktop-SDK facades to /api/plugins/<id>, not Python ctx members")

    # --- Probe F: private-import lint on the only in-process route to host STT -----------
    from hermes_cli.plugin_validate_private_imports import private_import_findings
    with tempfile.TemporaryDirectory(prefix="cb-p8-lint-") as tmp:
        handful = Path(tmp)
        (handful / "plugin_api.py").write_text(
            "from tools.transcription_tools import transcribe_audio\n"
            "def transcribe(path):\n    return transcribe_audio(path)\n", encoding="utf-8")
        private_hits = private_import_findings(handful)
        (handful / "plugin_api.py").write_text(
            "from agent.transcription_provider import TranscriptionProvider\n", encoding="utf-8")
        public_hits = private_import_findings(handful)
    record("private_import_is_flagged",
           bool(private_hits) and not public_hits,
           flagged=private_hits[:3], control_clean=(public_hits == []),
           note="tools.transcription_tools is not on the plugin public-surface allowlist "
                "(hermes_cli/plugin_validate_private_imports.py); agent.transcription_provider is")

    # --- Probe G: gateway JSON-RPC method surface (host.request) -------------------------
    method_names: set[str] = set()
    pattern = re.compile(r"@(?:method|_scoped_rpc)\(\s*[\"']([^\"']+)[\"']")
    for py in (HOST / "tui_gateway").glob("methods_*.py"):
        method_names.update(pattern.findall(py.read_text(encoding="utf-8", errors="ignore")))
    stt_rpc = sorted(n for n in method_names if any(k in n.lower() for k in ("transcri", "audio", "stt")))
    record("no_transcription_rpc", stt_rpc == [],
           rpc_method_count=len(method_names), stt_rpc=stt_rpc,
           note="host.request is the gateway JSON-RPC door; it exposes no audio-file -> transcript method")

    # --- Probe H: the desktop REST door is namespaced by construction -------------------
    plugins_ts = (HOST / "apps/desktop/src/api/plugins.ts").read_text(encoding="utf-8")
    forced = "path: `/api/plugins/${pluginId}${suffix}`" in plugins_ts
    record("ctx_rest_is_namespaced", forced,
           constructs="/api/plugins/<id><suffix>", rejects_traversal=("illegal path traversal" in plugins_ts),
           documented_limit="'a plugin can't address another plugin's API or a core route through it' "
                            "(apps/desktop/src/api/plugins.ts:64-70)",
           note="no /api/audio/transcribe reachable through ctx.rest; the route is mounted on the "
                "host web app (hermes_cli/web_server.py:825) and its only client auth is the desktop "
                "main process bridge")

    definite = all(results["probes"][k]["pass"] for k in (
        "no_transcription_tool", "no_transcription_rpc",
        "ctx_has_no_stt_request", "ctx_rest_is_namespaced",
    ))
    results["verdict"] = "no_documented_seam" if definite else "documented_seam_found"
    results["backend_seam_note"] = (
        "plugins CAN register a TranscriptionProvider, but it is a backend: it is dispatched only "
        "when stt.provider names it (built-ins always win) and it must implement speech recognition "
        "itself. It cannot borrow the host's configured STT."
    )
    (OUT_DIR / "stt_seam.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"RESULT verdict {'DEFINITE' if definite else 'NEGATIVE'} {results['verdict']}")
    print(f"evidence {OUT_DIR / 'stt_seam.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
