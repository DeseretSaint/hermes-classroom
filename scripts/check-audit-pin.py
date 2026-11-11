#!/usr/bin/env python3
"""Fail when the painted visual audit belongs to a different desktop/plugin.js than the tree's.

Every `python3 scripts/build_plugin.py` rewrites `desktop/plugin.js`, which changes its sha256.
The audit in `audit/visual/m4-visual/audit.json` records the sha it painted. When the two differ,
`tests.test_m4_visual_audit` fails with an opaque assertion; this script says what to run instead.

Exit codes: 0 the audit matches, 1 it does not, 2 the audit or the module is missing.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "desktop" / "plugin.js"
AUDIT = ROOT / "audit" / "visual" / "m4-visual" / "audit.json"


def main() -> int:
    if not MODULE.exists() or not AUDIT.exists():
        print(f"missing {MODULE if not MODULE.exists() else AUDIT}", file=sys.stderr)
        return 2
    digest = hashlib.sha256(MODULE.read_bytes()).hexdigest()
    audit_text = AUDIT.read_text(encoding="utf-8")
    if digest in audit_text:
        print(f"audit matches desktop/plugin.js ({digest[:12]})")
        return 0
    painted = ""
    try:
        painted = json.loads(audit_text).get("source_scan", {}).get("module_sha256", "")
    except json.JSONDecodeError:
        pass
    print(
        "the painted audit was generated against a different module\n"
        f"  tree:   {digest}\n"
        f"  audit:  {painted or 'no module sha recorded'}\n"
        "regenerate it, then re-run the pinning test:\n"
        "  python3 scripts/m4v-audit.py\n"
        "  python3 -m unittest tests.test_m4_visual_audit",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
