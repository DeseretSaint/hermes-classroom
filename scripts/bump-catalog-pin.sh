#!/usr/bin/env bash
# Move the Coursebook catalog entry to a commit and prove the catalog still validates.
#
# The catalog pins an exact sha and never tracks a branch, so every release needs this. Doing it by
# hand is how a submission ends up describing one tree and installing another.
#
#   scripts/bump-catalog-pin.sh                 # pin to the local origin/master
#   scripts/bump-catalog-pin.sh <sha|ref>       # pin to anything git can resolve
#
# Env: COURSEBOOK_REPO (default: this checkout), HERMES_FORK (default: ~/Projects/hermes-fork).
set -euo pipefail

REPO="${COURSEBOOK_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
FORK="${HERMES_FORK:-$HOME/Projects/hermes-fork}"
CATALOG="$FORK/plugin-catalog/coursebook.yaml"
REF="${1:-origin/master}"

[[ -f "$CATALOG" ]] || { echo "no catalog entry at $CATALOG" >&2; exit 2; }

SHA="$(git -C "$REPO" rev-parse --verify "$REF^{commit}")"
OLD="$(awk '/^sha:/{print $2; exit}' "$CATALOG")"
[[ "$SHA" == "$OLD" ]] && { echo "catalog already pins ${SHA:0:12}"; exit 0; }

git -C "$REPO" cat-file -e "$SHA^{commit}" 2>/dev/null || {
  echo "the pinned commit is not in this clone; a reader cannot resolve it" >&2
  exit 3
}

python3 - "$CATALOG" "$SHA" <<'PY'
import pathlib, sys
path, sha = pathlib.Path(sys.argv[1]), sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
out, done = [], False
for line in lines:
    if line.startswith("sha:") and not done:
        out.append(f"sha: {sha}\n")
        done = True
    else:
        out.append(line)
if not done:
    out.append(f"sha: {sha}\n")
path.write_text("".join(out), encoding="utf-8")
PY

echo "pin ${OLD:0:12} -> ${SHA:0:12} in $CATALOG"

if [[ -f "$FORK/scripts/validate_plugin_catalog.py" ]]; then
  (cd "$FORK" && python3 scripts/validate_plugin_catalog.py)
fi

if git -C "$REPO" show "$SHA:desktop/plugin.js" >/dev/null 2>&1; then
  echo "next:"
  echo "  git -C $FORK add plugin-catalog/coursebook.yaml"
  echo "  git -C $FORK commit -m 'catalog: pin coursebook to ${SHA:0:12}'"
  echo "  git -C $FORK push"
else
  echo "warning: $SHA has no desktop/plugin.js; check the ref before publishing" >&2
fi
