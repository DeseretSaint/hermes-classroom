"""Compose the ``cb.errors`` v5 reference fold into the shipped ``jobs.v6.json``.

Run from the repository root::

    python3 probes/derive_jobs_v6_error_ref.py

t_891d90e7: ``cb.errors`` v5 adds exactly one code, ``BUDGET_EXHAUSTED`` (``state``,
``retryable: false``, HTTP 409), so a declared spend ceiling stops as a state fact instead of a
content verdict. A failed job carries the error envelope, and that envelope is a ``$ref`` into
``cb.errors`` — a v4 reference would reject the very failure the code exists for.

v6 already ships (upgrade 36 issued it), so this is a **composing** sibling: it moves the one
``$ref`` in the document in hand onto ``errors/v5`` and nothing else. No job kind, state,
transition, field, ``activity`` key or progress percentage moves, and every v5 payload validates
unchanged. ``contracts/jobs.v5.json`` stays byte-identical history. Running it twice rewrites
identical bytes.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "contracts" / "jobs.v6.json"


def _composition():
    """The single authority for the fold: ``probes/derive_budget_stop_contracts.py``."""
    path = ROOT / "probes" / "derive_budget_stop_contracts.py"
    spec = importlib.util.spec_from_file_location("derive_budget_stop_contracts", path)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load probes/derive_budget_stop_contracts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive(document: dict, composed: bool = False) -> dict:
    """Fold the errors/v5 reference into the jobs v6 in hand; nothing else moves."""
    return _composition().fold_jobs(document)


def main() -> int:
    module = _composition()
    raw = TARGET.read_text(encoding="utf-8")
    source = module.json.loads(raw)
    if module.serialise(source) != raw:
        raise SystemExit("jobs.v6.json does not round-trip under the shared serialiser")
    target = module.serialise(derive(source))
    TARGET.write_text(target, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
