#!/usr/bin/env bash
# Link this checkout into a Hermes plugins root for live development.
#
# Why a symlink: an installed package's desktop half is only re-copied on Rescan/update/restart.
# A *linked* package is watched, so every save of desktop/plugin.js re-syncs the copy and
# hot-reloads the plugin (website/docs/developer-guide/desktop-plugin-sdk.md, "Developing a
# unified package").
#
# This script does NOT enable the plugin. Both halves default to off on purpose:
#   - backend: add "coursebook" to plugins.enabled in config.yaml (`hermes plugins enable coursebook`)
#   - desktop: Capabilities → Plugins → Coursebook → on
set -euo pipefail
cd "$(dirname "$0")/.."

SOURCE="$(pwd)"
HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
TARGET="$HOME_DIR/plugins/coursebook"

if [[ ! -f "$SOURCE/plugin.yaml" ]]; then
  echo "run this from the coursebook checkout (plugin.yaml not found)" >&2
  exit 1
fi

mkdir -p "$HOME_DIR/plugins"

if [[ -e "$TARGET" && ! -L "$TARGET" ]]; then
  echo "$TARGET already exists and is not a symlink; refusing to replace it." >&2
  exit 1
fi

ln -sfn "$SOURCE" "$TARGET"
echo "linked $TARGET -> $SOURCE"
echo
echo "next:"
echo "  hermes plugins enable coursebook   # backend half (imports plugin_api.py)"
echo "  restart the gateway, then enable the Desktop half in Capabilities → Plugins"
echo "  bash scripts/check-install.sh --home $HOME_DIR   # both halves on one sha?"
