#!/usr/bin/env python3
"""Regenerate the two contract-derived constants in ``desktop/src/76-v3-scope.js``.

``CB_TOKENS_V3_JSON`` must be the contract's canonical bytes for the five build-critical sections,
and ``CB3_V3_ROLES`` must be the contract's own role list. Both are generated rather than typed so
a contract edit cannot leave the shipped module describing an older palette:

    python3 scripts/build_v3_scope.py           # rewrite the two constants
    python3 scripts/build_v3_scope.py --check   # exit 1 when they have drifted

``tests/test_desktop_tokens_v3.py`` recomputes the same bytes, so a hand edit fails there too; this
script exists so the fix is one command instead of a copy-paste.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contracts" / "cb.tokens.v3.json"
SEGMENT = ROOT / "desktop" / "src" / "76-v3-scope.js"
SECTIONS = ("modes", "elevation", "radii", "type", "motion", "materials")

LITERAL_RE = re.compile(r"const CB_TOKENS_V3_JSON =\n  [^\n]*\n")
ROLES_RE = re.compile(r"const CB3_V3_ROLES = Object\.freeze\([^\n]*\)\n")


def rendered() -> tuple[str, str]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    projection = {key: contract[key] for key in SECTIONS}
    literal = json.dumps(projection, ensure_ascii=False, separators=(",", ":"))
    literal_line = "const CB_TOKENS_V3_JSON =\n  '%s'\n" % literal.replace("\\", "\\\\").replace("'", "\\'")
    roles_line = "const CB3_V3_ROLES = Object.freeze(%s)\n" % json.dumps(contract["roles"])
    return literal_line, roles_line


def apply(source: str) -> str:
    literal_line, roles_line = rendered()
    if LITERAL_RE.search(source) is None or ROLES_RE.search(source) is None:
        raise SystemExit("build_v3_scope: the generated constants are not in 76-v3-scope.js")
    source = LITERAL_RE.sub(lambda _: literal_line, source, count=1)
    return ROLES_RE.sub(lambda _: roles_line, source, count=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify only; exit 1 on drift")
    args = parser.parse_args(argv)
    current = SEGMENT.read_text(encoding="utf-8")
    expected = apply(current)
    if args.check:
        if current != expected:
            print("build_v3_scope: 76-v3-scope.js is not the contract's bytes; run "
                  "`python3 scripts/build_v3_scope.py`", file=sys.stderr)
            return 1
        print("build_v3_scope: constants match contracts/cb.tokens.v3.json")
        return 0
    if current != expected:
        SEGMENT.write_text(expected, encoding="utf-8")
        print("build_v3_scope: rewrote the contract constants in desktop/src/76-v3-scope.js")
    else:
        print("build_v3_scope: constants already match the contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
