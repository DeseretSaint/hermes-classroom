#!/usr/bin/env python3
"""What does the *real* Hermes runtime expose after its bootstrap?"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "/home/deseretsaint/.hermes/hermes-agent")

try:
    import hermes_bootstrap  # noqa: F401  (must precede runtime imports)
    boot = "ok"
except Exception as exc:  # noqa: BLE001
    boot = f"{type(exc).__name__}: {exc}"

out = {"bootstrap": boot, "python": sys.version.split()[0]}
for mod in ("ruamel.yaml", "jsonschema"):
    try:
        m = __import__(mod, fromlist=["*"])
        out[mod] = getattr(m, "__version__", "present")
    except Exception as exc:  # noqa: BLE001
        out[mod] = f"ABSENT ({type(exc).__name__})"

from agent.plugin_llm import _parse_structured_text

schema = {"type": "object", "required": ["verdict"],
          "properties": {"verdict": {"enum": ["pass"]}}}
try:
    parsed, ctype = _parse_structured_text(
        text=json.dumps({"verdict": "fail"}), json_mode=False, json_schema=schema)
    out["schema_violation"] = {"parsed": parsed, "content_type": ctype}
except Exception as exc:  # noqa: BLE001
    out["schema_violation"] = {"error_type": type(exc).__name__, "error": str(exc)[:160]}

print(json.dumps(out, indent=2))
