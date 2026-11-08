#!/usr/bin/env bash
# Release gate for Coursebook: validate an export of the commit, not the checkout.
#
# Why this exists (CB-018): `hermes plugins validate .` walks the whole directory it
# is given. The repository root contains `.worktrees/` (one worktree per kanban task,
# gitignored), so pointing the validator at `.` makes it scan other commits' adversarial
# fixtures and report `dangerous` on files that are not part of this package. On the
# same commit, a clean `git archive HEAD` export reports `security scan — safe`. A gate
# that fails for files it should never read can also pass while a real violation is
# buried in the noise, so the release gate exports the commit first.
#
# Usage:
#   bash scripts/validate-plugin.sh                 # gate HEAD (the release gate)
#   bash scripts/validate-plugin.sh --ref <commit>  # gate another commit or tag
#   bash scripts/validate-plugin.sh --worktree      # gate uncommitted edits to tracked files
#
# Exit codes:
#   0  every check passed
#   1  at least one check failed
#   2  usage or setup error (not a checkout, dirty tree in HEAD mode, export failed)
#
# What runs, inside the export:
#   1. hermes plugins validate <export>          (admission + security scan)
#   2. node --check desktop/plugin.js            (Desktop half parses as ESM)
#   3. python3 -m unittest tests.test_desktop_contracts
#   4. hermes plugins doctor <export>            (runtime discovery, import, registration)
#
# Environment overrides: HERMES_BIN, NODE_BIN, COURSEBOOK_PYTHON.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Export helper shared with scripts/validate.sh (step 3 of the pre-merge gate).
# shellcheck source=scripts/lib/gate-export.sh
. "$REPO/scripts/lib/gate-export.sh"
HERMES_BIN="${HERMES_BIN:-hermes}"
NODE_BIN="${NODE_BIN:-node}"
PYTHON_BIN="${COURSEBOOK_PYTHON:-python3}"

MODE="head"
REF="HEAD"

usage() {
  cat <<'EOF'
usage: bash scripts/validate-plugin.sh [--ref <commit>] [--worktree]

  (no option)      gate HEAD: exports the commit with `git archive` and validates it
  --ref <commit>   gate another commit or tag
  --worktree       gate uncommitted edits to tracked files (pre-commit check)

Exit codes: 0 pass, 1 a check failed, 2 usage or setup error.
EOF
}

die() {
  printf 'validate-plugin: %s\n' "$1" >&2
  exit 2
}

cleanup() {
  gate_export_cleanup
}

trap cleanup EXIT INT TERM

while [ "$#" -gt 0 ]; do
  case "$1" in
    --ref)
      [ "$#" -ge 2 ] || die "--ref needs a commit or tag"
      REF="$2"
      MODE="head"
      shift 2
      ;;
    --worktree)
      MODE="worktree"
      REF="HEAD"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1 (try --help)"
      ;;
  esac
done

cd "$REPO" || die "cannot enter $REPO"

# --- preconditions -----------------------------------------------------------

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "$REPO is not a git checkout"
[ -f plugin.yaml ] || die "no plugin.yaml in $REPO; run this from the Coursebook checkout"
[ -f desktop/plugin.js ] || die "no desktop/plugin.js in $REPO"
[ -f tests/test_desktop_contracts.py ] || die "no tests/test_desktop_contracts.py in $REPO"
command -v "$HERMES_BIN" >/dev/null 2>&1 || die "hermes not found (set HERMES_BIN)"
command -v "$NODE_BIN" >/dev/null 2>&1 || die "node not found (set NODE_BIN)"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "python3 not found (set COURSEBOOK_PYTHON)"

COMMIT="$(git rev-parse --verify "$REF^{commit}")" || die "cannot resolve $REF to a commit"

if [ "$MODE" = "head" ]; then
  # A release gate pins a commit. If tracked files differ from it, the export would
  # not be what you are looking at, which is how a green gate gets attached to code
  # that is not shipped. Untracked files are not in the export either way, so they
  # are reported but do not fail the gate.
  DIRTY="$(git status --porcelain --untracked-files=no)"
  if [ -n "$DIRTY" ]; then
    printf '%s\n' "$DIRTY" >&2
    die "tracked files differ from $REF; commit them, or run --worktree to gate local edits"
  fi
  UNTRACKED="$(git ls-files --others --exclude-standard | wc -l | tr -d ' ')"
else
  UNTRACKED="0"
fi

# --- export ------------------------------------------------------------------

gate_export_tree "$REPO" "$MODE" "$REF"
EXPORT_STATUS=$?
case "$EXPORT_STATUS" in
  0) ;;
  1) die "export of $REF failed" ;;
  *) die "could not export $REF; see the message above" ;;
esac

SCRATCH="$GATE_EXPORT_DIR"
FILE_COUNT="$GATE_EXPORT_FILES"

printf 'validate-plugin: gate %s (%s, %s files)\n' "$COMMIT" "$MODE" "$FILE_COUNT"
printf 'validate-plugin: export %s (removed on exit)\n' "$SCRATCH"
if [ "$MODE" = "head" ] && [ "$UNTRACKED" != "0" ]; then
  printf 'validate-plugin: note - %s untracked file(s) are not in the export (git status --short)\n' "$UNTRACKED"
fi
printf '\n'

# --- checks ------------------------------------------------------------------

FAILED=0
TOTAL=4

report() { # report <name> <status>
  if [ "$2" -eq 0 ]; then
    printf '\n== %s: PASS ==\n\n' "$1"
  else
    printf '\n== %s: FAIL (exit %s) ==\n\n' "$1" "$2"
    FAILED=$((FAILED + 1))
  fi
}

printf '== 1/%s plugin admission (hermes plugins validate) ==\n' "$TOTAL"
(
  cd "$SCRATCH" && "$HERMES_BIN" plugins validate "$SCRATCH"
)
STATUS=$?
report "1/$TOTAL plugin admission" "$STATUS"

printf '== 2/%s desktop module parses as ESM (node --check) ==\n' "$TOTAL"
(
  cd "$SCRATCH" && "$NODE_BIN" --check desktop/plugin.js
)
STATUS=$?
[ "$STATUS" -eq 0 ] && printf 'desktop/plugin.js: syntax OK\n'
report "2/$TOTAL desktop module" "$STATUS"

printf '== 3/%s desktop contract tests (unittest) ==\n' "$TOTAL"
(
  cd "$SCRATCH" && "$PYTHON_BIN" -m unittest tests.test_desktop_contracts
)
STATUS=$?
report "3/$TOTAL desktop contract tests" "$STATUS"

printf '== 4/%s runtime contracts (hermes plugins doctor, on the export) ==\n' "$TOTAL"
# Doctor stages a copy of the directory it is given. Never point it at the checkout: the copy
# walks the gitignored .worktrees/ farm and fails on Chromium Singleton* sockets, which is a
# host-state error, not a defect of the gated commit.
(
  cd "$SCRATCH" && "$HERMES_BIN" plugins doctor "$SCRATCH"
)
STATUS=$?
report "4/$TOTAL runtime contracts" "$STATUS"

# --- verdict -----------------------------------------------------------------

if [ "$FAILED" -ne 0 ]; then
  printf 'Release gate failed: %s of %s checks failed on %s.\n' "$FAILED" "$TOTAL" "$COMMIT" >&2
  exit 1
fi

printf 'Release gate passed: %s/%s checks on %s (%s files).\n' "$TOTAL" "$TOTAL" "$COMMIT" "$FILE_COUNT"
exit 0
