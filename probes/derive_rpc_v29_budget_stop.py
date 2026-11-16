"""Compose the ``cb.errors`` v5 reference fold into the shipped ``rpc.v29.json``.

Run from the repository root::

    python3 probes/derive_rpc_v29_budget_stop.py

t_891d90e7: a declared spend ceiling is a typed **state** stop, not a content refusal.
``cb.errors`` v5 adds exactly one code, ``BUDGET_EXHAUSTED`` (``state``, ``retryable: false``,
HTTP 409). The shared error envelope is the object both wire contracts ``$ref``, so leaving the
reference at v4 would make the plugin's own budget-stop response fail its own schema on the one
path the code exists for.

v29 already ships (other cards issued it), so this is a **composing** sibling, not a new version:
it folds two named amendments into that document and moves no wire echo (v29 is already the wire).

* the envelope ``$ref`` moves ``errors/v4`` → ``errors/v5`` — one line, no payload;
* ``health.get``'s ``db`` block gains required ``state`` (``ready|unmigrated|failed``) and
  ``target_schema_version``, plus an optional bounded ``error`` ``{type<=80, message<=300,
  target_schema_version}`` present only when the migration attempt raised, and the response gains
  a required bounded ``reconciliation`` block ``{state ok|failed, error|null, message|null}``
  carrying the plugin-load recovery report (H-131).

``ready: false`` was one fact for two different truths: a profile that was never migrated and a
store whose migration raised. The pane told the second user their course tables did not exist.

No other method, payload, error code, job kind, answer kind, verdict, evidence class or vocabulary
value moves; ``contracts/rpc.v28.json`` stays byte-identical history. Running it twice rewrites
identical bytes.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "contracts" / "rpc.v29.json"

FOLD_NOTE = (
    "Folded in place by t_891d90e7 and H-131: (1) the shared error envelope resolves cb.errors v5 "
    "(one added code, BUDGET_EXHAUSTED — a declared spend ceiling is a state stop, not a content "
    "refusal), a reference-only move; (2) `health.get`'s `db` block gains required `state` "
    "(ready|unmigrated|failed) and `target_schema_version`, plus an optional bounded `error` "
    "{type<=80, message<=300, target_schema_version} present only when the migration attempt "
    "raised, and the response gains a required bounded `reconciliation` block {state ok|failed, "
    "error|null, message|null} carrying the plugin-load recovery report. `ready: false` is no "
    "longer one fact: a never-migrated profile and a store whose migration failed are different "
    "answers, and the pane must stop telling a user their course tables do not exist when the "
    "truth is that preparing them failed. No other method, payload, error code, job kind, answer "
    "kind, verdict, evidence class or vocabulary value moves."
)


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
    """Fold the errors/v5 reference and the named health amendment into the rpc v29 in hand."""
    return _composition().fold_rpc(document)


def main() -> int:
    module = _composition()
    raw = TARGET.read_text(encoding="utf-8")
    source = module.json.loads(raw)
    if module.serialise(source) != raw:
        raise SystemExit("rpc.v29.json does not round-trip under the shared serialiser")
    target = module.serialise(derive(source))
    TARGET.write_text(target, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(target)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
