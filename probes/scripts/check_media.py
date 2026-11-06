#!/usr/bin/env python3
"""MEDIA: delivery seam checks against the live Hermes runtime.

Run with PYTHONPATH=<hermes-agent> and the gateway interpreter.
No network, no external send.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/deseretsaint/.hermes/hermes-agent")
import hermes_bootstrap  # noqa: F401,E402  — the gateway's real import path


def main() -> None:
    result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    png = result["MEDIA"].split("MEDIA:", 1)[1]
    text_alt = result["text_fallback"]

    from gateway.platforms.base import BasePlatformAdapter
    from gateway.run import _collect_auto_append_media_tags, _AUTO_APPEND_MEDIA_TOOL_NAMES

    files, _ = BasePlatformAdapter.extract_media(f"Here is the diagram.\n{result['MEDIA']}")
    masked_files, _ = BasePlatformAdapter.extract_media(json.dumps(result))

    messages = [
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "coursebook_emit_visual", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": json.dumps(result)},
    ]
    auto, voice = _collect_auto_append_media_tags(messages, history_offset=0)

    print(json.dumps({
        "artifact_exists": Path(png).exists(),
        "artifact_bytes": Path(png).stat().st_size if Path(png).exists() else 0,
        "text_fallback_exists": Path(text_alt).exists(),
        "text_fallback_head": Path(text_alt).read_text(encoding="utf-8")[:120] if Path(text_alt).exists() else "",
        "extract_media_plain_text": [p for p, _ in files],
        "extract_media_from_json_tool_result": [p for p, _ in masked_files],
        "auto_append_allowlist": sorted(_AUTO_APPEND_MEDIA_TOOL_NAMES),
        "auto_append_for_plugin_tool": auto,
        "plugin_tool_is_allowlisted": "coursebook_emit_visual" in _AUTO_APPEND_MEDIA_TOOL_NAMES,
        "voice_directive": voice,
    }, indent=2))


if __name__ == "__main__":
    main()
