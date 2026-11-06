#!/usr/bin/env python3
"""Runtime capability + structured-output validation seam checks.

Run with the interpreter the Hermes gateway uses. Read-only; no network.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "/home/deseretsaint/.hermes/hermes-agent")
import hermes_bootstrap  # noqa: F401,E402  — mirrors the real entry point's import path


def main() -> None:
    out = {"python": sys.version.split()[0], "executable": sys.executable}
    try:
        import jsonschema  # type: ignore

        out["jsonschema"] = getattr(jsonschema, "__version__", "unknown")
    except Exception as exc:  # noqa: BLE001
        out["jsonschema"] = f"ABSENT ({type(exc).__name__})"

    from agent.plugin_llm import _parse_structured_text

    schema = {"type": "object", "required": ["verdict"],
              "properties": {"verdict": {"enum": ["pass"]}}}
    invalid = {"verdict": "fail"}

    try:
        parsed, ctype = _parse_structured_text(text=json.dumps(invalid), json_mode=False, json_schema=schema)
        out["with_jsonschema"] = {"parsed": parsed, "content_type": ctype}
    except Exception as exc:  # noqa: BLE001
        out["with_jsonschema"] = {"error_type": type(exc).__name__, "error": str(exc)[:200]}

    parsed, ctype = _parse_structured_text(text="NOT JSON AT ALL", json_mode=True, json_schema=None)
    out["non_json_text"] = {"parsed": parsed, "content_type": ctype}

    # Simulate the optional host package being absent (the spec's stated hazard).
    real = sys.modules.get("jsonschema")
    sys.modules["jsonschema"] = None  # type: ignore[assignment]
    try:
        parsed, ctype = _parse_structured_text(text=json.dumps(invalid), json_mode=False, json_schema=schema)
        out["without_jsonschema"] = {"parsed": parsed, "content_type": ctype}
    except Exception as exc:  # noqa: BLE001
        out["without_jsonschema"] = {"error_type": type(exc).__name__, "error": str(exc)[:200]}
    finally:
        if real is not None:
            sys.modules["jsonschema"] = real
        else:
            sys.modules.pop("jsonschema", None)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
