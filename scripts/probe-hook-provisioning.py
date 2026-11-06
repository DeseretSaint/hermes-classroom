"""Before/after probe: does an unbound chat turn provision Coursebook storage?

Run with a throwaway HERMES_HOME:

    TMP=$(mktemp -d) && HERMES_HOME=$TMP python3 scripts/probe-hook-provisioning.py

Prints one JSON object. Exit code 1 when the invariants are violated.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

home = Path(os.environ["HERMES_HOME"])
plugin_data = home / "plugin-data"
db_file = plugin_data / "coursebook" / "data.db"

report: dict[str, Any] = {"home": str(home)}


def snap(label: str) -> dict:
    return {
        "label": label,
        "plugin_data_exists": plugin_data.exists(),
        "db_exists": db_file.exists(),
    }


report["steps"] = [snap("before import")]

from coursebook import api, db, hooks  # noqa: E402

report["steps"].append(snap("after `import coursebook.hooks`"))
report["applied_schema_version"] = db.applied_schema_version()
_store_exists = getattr(db, "store_exists", None)  # absent on the pre-fix build, by design
report["store_exists"] = _store_exists() if _store_exists is not None else None
report["steps"].append(snap("after applied_schema_version() / store_exists()"))

report["pre_llm_call"] = hooks.pre_llm_call(
    session_id="stored-unbound-fresh-install",
    user_message="hello there",
    is_first_turn=True,
)
report["post_llm_call"] = hooks.post_llm_call(
    session_id="stored-unbound-fresh-install", user_message="hello", assistant_response="hi"
)
report["post_tool_call"] = hooks.post_tool_call(
    tool_name="terminal", task_id="task-1", duration_ms=9, session_id="stored-unbound-fresh-install"
)
report["steps"].append(snap("after the three hooks"))

health = api.dispatch(
    {
        "contract": api.RPC_CONTRACT,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "method": "health.get",
        "operation_id": "op-probe-health",
        "payload": {},
    }
)
report["health_get"] = health
report["steps"].append(snap("after health.get"))

failures = []
created_before_health = [step for step in report["steps"][:-1] if step["plugin_data_exists"] or step["db_exists"]]
if created_before_health:
    failures.append(f"storage was created before health.get: {created_before_health}")
if report["pre_llm_call"] is not None:
    failures.append(f"an unbound chat turn was not ungoverned: {report['pre_llm_call']!r}")
if report["applied_schema_version"] is not None:
    failures.append("applied_schema_version() reported a schema in a fresh home")
if not db_file.is_file():
    failures.append("health.get did not provision the store")
elif not health.get("ok") or not health["result"]["db"]["ready"]:
    failures.append(f"health.get did not report ready after provisioning: {health}")
elif health["result"]["db"]["schema_version"] != db.target_schema_version():
    failures.append(f"health.get reported {health['result']['db']['schema_version']}, target {db.target_schema_version()}")

report["failures"] = failures
print(json.dumps(report, indent=2, default=str))
raise SystemExit(1 if failures else 0)
