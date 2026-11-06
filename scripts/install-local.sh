#!/usr/bin/env bash
# Reproducible local install of the unified Coursebook package into ONE Hermes home.
#
# What "install" means for this package (plugin.yaml manifest_version 2):
#   1. the agent half is linked into <home>/plugins/coursebook  (a linked package is watched and
#      re-synced, so a checkout edit hot-reloads the Desktop half instead of needing a rescan);
#   2. the Desktop half is materialized at <home>/desktop-plugins/coursebook with the marker the
#      Desktop pairs back to the agent row (the app does the same lift on its own rescan; doing it
#      here makes a headless install deterministic);
#   3. the plugin is ENABLED in that home's config.yaml — nothing is enabled implicitly;
#   4. the install is verified: `hermes plugins validate` and `hermes plugins doctor` both pass.
#
# The default home is a dedicated, disposable test home. It is NOT the root profile and NOT any
# bot profile: installing into the root profile is an operator decision, not a script default.
#
#   scripts/install-local.sh                          # test home, install + enable + verify
#   scripts/install-local.sh --home ~/.hermes/profiles/cbqa
#   scripts/install-local.sh --source /path/to/checkout --no-enable
#
# Exit codes: 0 installed and verified; 1 refused (not a checkout, real dir in the way, a gate
# failed); 2 bad usage.
set -euo pipefail

SOURCE_DEFAULT="$(cd "$(dirname "$0")/.." && pwd)"
# Deliberately NOT `${HERMES_HOME:-...}`: an agent worker runs with HERMES_HOME pointing at its own
# profile, and inheriting that would install into a real bot profile instead of the test home.
HOME_DIR="${COURSEBOOK_TEST_HOME:-$HOME/.hermes/coursebook-test/home}"
SOURCE="$SOURCE_DEFAULT"
DO_ENABLE=1
HERMES_BIN="${HERMES_BIN:-$(command -v hermes || echo "$HOME/.local/bin/hermes")}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --home) HOME_DIR="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --no-enable) DO_ENABLE=0; shift ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

SOURCE="$(cd "$SOURCE" && pwd)"
[[ -f "$SOURCE/plugin.yaml" ]] || { echo "not a Coursebook checkout: $SOURCE has no plugin.yaml" >&2; exit 1; }
[[ -f "$SOURCE/desktop/plugin.js" ]] || { echo "checkout has no desktop/plugin.js; the Desktop half would be missing" >&2; exit 1; }

COMMIT="$(git -C "$SOURCE" rev-parse --short HEAD 2>/dev/null || echo 'not-a-git-checkout')"
PLUGIN_TARGET="$HOME_DIR/plugins/coursebook"
DESKTOP_TARGET="$HOME_DIR/desktop-plugins/coursebook"

echo "source : $SOURCE ($COMMIT)"
echo "home   : $HOME_DIR"
echo

echo "== 1/5 agent half: link the package =="
mkdir -p "$HOME_DIR/plugins"
if [[ -e "$PLUGIN_TARGET" && ! -L "$PLUGIN_TARGET" ]]; then
  echo "refusing to replace a real directory: $PLUGIN_TARGET" >&2
  exit 1
fi
ln -sfn "$SOURCE" "$PLUGIN_TARGET"
readlink -f "$PLUGIN_TARGET"

echo
echo "== 2/5 desktop half: materialize the app root copy =="
mkdir -p "$DESKTOP_TARGET"
cp "$SOURCE/desktop/plugin.js" "$DESKTOP_TARGET/plugin.js"
python3 - "$DESKTOP_TARGET" "$SOURCE" <<'PY'
import json, os, pathlib, sys
target = pathlib.Path(sys.argv[1])
source = pathlib.Path(sys.argv[2]) / "desktop" / "plugin.js"
marker = target / ".hermes-package.json"
marker.write_text(json.dumps({
    "package": "coursebook",
    "source": str(source),
    "sourceMtimeMs": source.stat().st_mtime * 1000,
    "linked": True,
}, indent=2) + "\n", encoding="utf-8")
print(f"marker: {marker}")
PY

echo
echo "== 3/5 single-home flag for an isolated backend =="
# The Desktop half reports sharedRemote and appends ?profile=<launch profile>. On an isolated
# backend that scope escapes to the DEFAULT home (~/.hermes), which is the operator's live profile.
# This flag makes Coursebook pin its own storage to this install's home instead (coursebook/db.py).
# Multi-profile gateways never set it.
ENV_FILE="$HOME_DIR/coursebook-single-home.env"
printf 'export %s=1\n' HERMES_COURSEBOOK_SINGLE_HOME > "$ENV_FILE"
echo "wrote $ENV_FILE"
echo "start the backend with it:  set -a; . $ENV_FILE; HERMES_HOME=$HOME_DIR hermes serve --isolated --port 44219"

echo
echo "== 4/5 enable the agent half in this home =="
if [[ "$DO_ENABLE" == "1" ]]; then
  HERMES_HOME="$HOME_DIR" "$HERMES_BIN" plugins enable coursebook
else
  echo "skipped (--no-enable); enable with: HERMES_HOME=$HOME_DIR hermes plugins enable coursebook"
fi

echo
echo "== 5/6 discover it in this home =="
HERMES_HOME="$HOME_DIR" "$HERMES_BIN" plugins list --plain --no-bundled | grep -q coursebook \
  || { echo "coursebook is not listed in this home" >&2; exit 1; }
echo "discovered: coursebook"

echo
echo "== 6/6 admission gates =="
HERMES_HOME="$HOME_DIR" "$HERMES_BIN" plugins validate "$SOURCE" | tail -1
HERMES_HOME="$HOME_DIR" "$HERMES_BIN" plugins doctor "$SOURCE" | tail -3

echo
echo "Installed."
echo "  backend : restart the gateway that serves $HOME_DIR, then the /api/plugins/coursebook/ routes mount"
echo "  desktop : open Desktop with HERMES_HOME=$HOME_DIR, then Capabilities -> Plugins -> Coursebook"
echo "  teardown: scripts/uninstall-local.sh --home $HOME_DIR"
