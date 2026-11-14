#!/usr/bin/env python3
"""Probe the host's real text_to_speech seam before spending a capture attempt.

Reads the same things ``HermesPluginContext.dispatch_tool`` and the TTS tool resolve:
the raw tts selection, the managed-gateway route, and whether the registry has a
callable ``text_to_speech`` entry. Prints no secret values.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERMES_AGENT = Path("/home/deseretsaint/.hermes/hermes-agent")
sys.path.insert(0, str(HERMES_AGENT))

report: dict[str, object] = {"hermes_home": os.environ.get("HERMES_HOME"), "hermes_agent": str(HERMES_AGENT)}

from hermes_constants import get_hermes_home  # noqa: E402
report["resolved_home"] = str(get_hermes_home())

from tools.tool_backend_helpers import (  # noqa: E402
    managed_nous_tools_enabled,
    read_selection,
    resolve_openai_audio_api_key,
)
report["tts_selection"] = read_selection("tts")
report["managed_nous_tools_enabled"] = managed_nous_tools_enabled()
report["openai_audio_env_key_present"] = bool(resolve_openai_audio_api_key())

from tools.managed_tool_gateway import peek_nous_access_token, resolve_managed_tool_gateway  # noqa: E402
report["nous_token_present"] = bool(peek_nous_access_token())
gw = resolve_managed_tool_gateway("openai-audio")
report["managed_gateway"] = None if gw is None else {
    "vendor": gw.vendor,
    "gateway_origin": gw.gateway_origin,
    "managed_mode": gw.managed_mode,
    "token_present": bool(gw.nous_user_token),
}

import tools.tts_tool  # noqa: E402  (registers the tool)
from tools.registry import registry  # noqa: E402
entry = registry.get_entry("text_to_speech")
report["registry_entry"] = None if entry is None else {"toolset": entry.toolset, "is_async": entry.is_async}
check = getattr(entry, "check_fn", None) if entry is not None else None
try:
    report["check_fn"] = None if check is None else bool(check())
except Exception as exc:  # noqa: BLE001
    report["check_fn"] = f"{type(exc).__name__}: {exc}"

try:
    from tools.tts_tool_openai import _resolve_openai_audio_client_config
    key, base, managed = _resolve_openai_audio_client_config()
    report["openai_audio_route"] = {"base_url": base, "managed": managed, "key_present": bool(key)}
except Exception as exc:  # noqa: BLE001
    report["openai_audio_route"] = f"{type(exc).__name__}: {exc}"

print(json.dumps(report, indent=2, ensure_ascii=False))
