#!/usr/bin/env bash
# Reproducible local install of the unified Coursebook package into ONE Hermes home.
#
# What "install" means for this package (plugin.yaml manifest_version 2):
#   1. the agent half is linked into <home>/plugins/coursebook  (a linked package is watched and
#      re-synced, so a checkout edit hot-reloads the Desktop half instead of needing a rescan);
#   2. the Desktop half is materialized at <home>/desktop-plugins/coursebook with the marker the
#      Desktop pairs back to the agent row (the app does the same lift on its own rescan; doing it
#      here makes a headless install deterministic), and its SHA-256 is compared with the package;
#   3. the plugin is ENABLED in that home's config.yaml — nothing is enabled implicitly;
#   4. the install is verified on an EXPORT of the checkout: `hermes plugins validate` and
#      `hermes plugins doctor` both pass, and the installed Desktop copy still matches.
#
# The default home is a dedicated, disposable test home. It is NOT the root profile and NOT any
# bot profile: installing into the root profile is an operator decision, not a script default.
#
#   scripts/install-local.sh                          # test home, install + enable + verify
#   scripts/install-local.sh --home ~/.hermes/profiles/cbqa
#   scripts/install-local.sh --source /path/to/checkout --no-enable
#   scripts/install-local.sh --home <home> --refresh-desktop   # only refresh a stale Desktop copy
#
# --refresh-desktop is the one-command repair `scripts/check-install.sh` prints. It copies nothing
# while a Hermes/Desktop process is using the home, and it refuses the machine-level ~/.hermes:
# installing there is an operator decision. Use --force only to copy the file under a live worker
# (the worker keeps the old code until it restarts).
#
# Exit codes: 0 installed and verified; 1 refused (not a checkout, real dir in the way, a gate
# failed, the copy is stale); 2 bad usage; 3 a refresh was refused (live worker, machine home).
set -euo pipefail

SOURCE_DEFAULT="$(cd "$(dirname "$0")/.." && pwd)"
# Deliberately NOT `${HERMES_HOME:-...}`: an agent worker runs with HERMES_HOME pointing at its own
# profile, and inheriting that would install into a real bot profile instead of the test home.
HOME_DIR="${COURSEBOOK_TEST_HOME:-$HOME/.hermes/coursebook-test/home}"
SOURCE="$SOURCE_DEFAULT"
DO_ENABLE=1
REFRESH_ONLY=0
HERMES_BIN="${HERMES_BIN:-$(command -v hermes || echo "$HOME/.local/bin/hermes")}"
PYTHON_BIN="${COURSEBOOK_PYTHON:-python3}"
CHECK=( "$PYTHON_BIN" "$SOURCE_DEFAULT/coursebook/install_check.py" )

while [[ $# -gt 0 ]]; do
  case "$1" in
    --home) HOME_DIR="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --no-enable) DO_ENABLE=0; shift ;;
    --refresh-desktop) REFRESH_ONLY=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,31p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
FORCE="${FORCE:-0}"

SOURCE="$(cd "$SOURCE" && pwd)"
[[ -f "$SOURCE/plugin.yaml" ]] || { echo "not a Coursebook checkout: $SOURCE has no plugin.yaml" >&2; exit 1; }
[[ -f "$SOURCE/desktop/plugin.js" ]] || { echo "checkout has no desktop/plugin.js; the Desktop half would be missing" >&2; exit 1; }

COMMIT="$(git -C "$SOURCE" rev-parse --short HEAD 2>/dev/null || echo 'not-a-git-checkout')"
PLUGIN_TARGET="$HOME_DIR/plugins/coursebook"
DESKTOP_TARGET="$HOME_DIR/desktop-plugins/coursebook"
CHECK=( "$PYTHON_BIN" "$SOURCE/coursebook/install_check.py" --source "$SOURCE" )
FORCE_ARG=()
[[ "$FORCE" == "1" ]] && FORCE_ARG=( --force )

if [[ "$REFRESH_ONLY" == "1" ]]; then
  echo "source : $SOURCE ($COMMIT)"
  echo "home   : $HOME_DIR"
  echo
  # Refuses a live worker and the machine-level home unless --force (exit 3).
  "${CHECK[@]}" --home "$HOME_DIR" --refresh-desktop "${FORCE_ARG[@]}"
  exit $?
fi

echo "source : $SOURCE ($COMMIT)"
echo "home   : $HOME_DIR"
echo

echo "== 1/7 agent half: link the package =="
mkdir -p "$HOME_DIR/plugins"
if [[ -e "$PLUGIN_TARGET" && ! -L "$PLUGIN_TARGET" ]]; then
  echo "refusing to replace a real directory: $PLUGIN_TARGET" >&2
  exit 1
fi
ln -sfn "$SOURCE" "$PLUGIN_TARGET"
readlink -f "$PLUGIN_TARGET"

echo
echo "== 2/7 desktop half: materialize the app root copy, SHA-matched =="
mkdir -p "$HOME_DIR/desktop-plugins"
# One implementation of the copy and the marker: `source` in .hermes-package.json is the Desktop
# DIRECTORY, which is how Hermes and Electron resolve it. Staging plus rename means a failure
# leaves the old copy or none, never a partial one.
"${CHECK[@]}" --home "$HOME_DIR" --refresh-desktop --quiet
echo "materialized: $DESKTOP_TARGET"

echo
echo "== 3/7 single-home flag for an isolated backend =="
# The Desktop half reports sharedRemote and appends ?profile=<launch profile>. On an isolated
# backend that scope escapes to the DEFAULT home (~/.hermes), which is the operator's live profile.
# This flag makes Coursebook pin its own storage to this install's home instead (coursebook/db.py).
# Multi-profile gateways never set it.
ENV_FILE="$HOME_DIR/coursebook-single-home.env"
printf 'export %s=1\n' HERMES_COURSEBOOK_SINGLE_HOME > "$ENV_FILE"
echo "wrote $ENV_FILE"
echo "start the backend with it:  set -a; . $ENV_FILE; HERMES_HOME=$HOME_DIR hermes serve --isolated --port 44219"

echo
echo "== 4/7 enable the agent half in this home =="
if [[ "$DO_ENABLE" == "1" ]]; then
  HERMES_HOME="$HOME_DIR" "$HERMES_BIN" plugins enable coursebook
else
  echo "skipped (--no-enable); enable with: HERMES_HOME=$HOME_DIR hermes plugins enable coursebook"
fi

echo
echo "== 5/7 discover it in this home =="
HERMES_HOME="$HOME_DIR" "$HERMES_BIN" plugins list --plain --no-bundled | grep -q coursebook \
  || { echo "coursebook is not listed in this home" >&2; exit 1; }
echo "discovered: coursebook"

echo
echo "== 6/7 admission gates on an export of the checkout =="
# Both gates are run on a `git archive` export, not the checkout. `hermes plugins validate` and
# `doctor` walk every directory they are given, and the checkout root contains the gitignored
# `.worktrees/` farm: other tasks' fixtures (a false `dangerous` for validate) and Chromium
# Singleton* sockets, which make Doctor's staging copy fail with `[Errno 6]`. The export has
# neither. A worktree export keeps uncommitted edits to tracked files in scope.
# shellcheck source=scripts/lib/gate-export.sh
. "$SOURCE/scripts/lib/gate-export.sh"
trap gate_export_cleanup EXIT INT TERM
gate_export_tree "$SOURCE" worktree || { echo "could not export the checkout" >&2; exit 1; }
HERMES_HOME="$HOME_DIR" "$HERMES_BIN" plugins validate "$GATE_EXPORT_DIR" | tail -1
HERMES_HOME="$HOME_DIR" "$HERMES_BIN" plugins doctor "$GATE_EXPORT_DIR" | tail -3
gate_export_cleanup
trap - EXIT INT TERM

echo
echo "== 7/7 installed Desktop copy matches the package =="
"${CHECK[@]}" --home "$HOME_DIR" --quiet
echo "installed copy matches desktop/plugin.js (sha256)"

echo
echo "Installed."
echo "  backend : restart the gateway that serves $HOME_DIR, then the /api/plugins/coursebook/ routes mount"
echo "  desktop : open Desktop with HERMES_HOME=$HOME_DIR, then Capabilities -> Plugins -> Coursebook"
echo "  verify  : bash scripts/check-install.sh --home $HOME_DIR"
echo "  teardown: scripts/uninstall-local.sh --home $HOME_DIR"
