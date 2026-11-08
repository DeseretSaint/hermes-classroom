#!/usr/bin/env bash
# The admission gate. Run before every merge into master.
set -euo pipefail
cd "$(dirname "$0")/.."
# Export helper shared with scripts/validate-plugin.sh.
# shellcheck source=scripts/lib/gate-export.sh
. scripts/lib/gate-export.sh
trap gate_export_cleanup EXIT

echo "== 1/5 unit tests + contract audit =="
"${COURSEBOOK_PYTHON:-python3}" -m unittest discover -s tests -t . -v

echo
echo "== 2/5 desktop module parses as ESM =="
node --check desktop/plugin.js
echo "desktop/plugin.js: syntax OK"

echo
echo "== 3/5 catalog admission =="
# Validate an export of the tracked tree, never the checkout root: the validator
# walks every directory it is given, and the root contains the gitignored
# .worktrees/ farm (other tasks' fixtures and review notes). A worktree export
# includes uncommitted edits to tracked files, so a local violation still fails
# this step without requiring a commit.
if ! gate_export_tree "$PWD" worktree; then
  echo "catalog admission: could not export the tracked tree (see above)" >&2
  exit 2
fi
UNTRACKED="$(git ls-files --others --exclude-standard | wc -l | tr -d ' ')"
if [ "$UNTRACKED" != "0" ]; then
  echo "catalog admission: note - $UNTRACKED untracked file(s) are not in the export"
fi
(
  cd "$GATE_EXPORT_DIR"
  hermes plugins validate "$GATE_EXPORT_DIR"
)

echo
echo "== 4/5 runtime contracts (doctor, on the export) =="
# Doctor stages a copy of the directory it is given. Pointed at the checkout, that copy walks the
# gitignored .worktrees/ farm and dies on Chromium Singleton* sockets (`[Errno 6]`), reporting a
# validation ERROR for the host's test rigs rather than for this package. The export (step 3) has
# no worktrees and no ignored files, so Doctor checks exactly the bytes being gated.
hermes plugins doctor "$GATE_EXPORT_DIR"

echo
echo "== 5/5 mounted backend trace (isolated HERMES_HOME) =="
"${COURSEBOOK_PYTHON:-python3}" scripts/probe-backend.py

echo
echo "Validation passed."
