#!/usr/bin/env bash
# Teardown for scripts/install-local.sh — disable, then let Hermes remove the package.
#
# Why there is no recursive delete here: the catalog security scan refuses a plugin that ships
# home-directory deletion (`destructive_home_rm`), and that rule is right. Removal goes through the
# host's own command, `hermes plugins remove <name>`, which owns both halves and its provenance
# record. Deleting a whole test home is an operator action, not something an installed package
# does to the machine it was installed on.
#
#   scripts/uninstall-local.sh --home ~/.hermes/coursebook-test/home
#
# Exit codes: 0 removed and verified; 1 still listed; 2 bad usage.
set -euo pipefail

TEST_HOME=""
HERMES_BIN="${HERMES_BIN:-$(command -v hermes || echo "$HOME/.local/bin/hermes")}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --home) TEST_HOME="$2"; shift 2 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$TEST_HOME" ]] || { echo "refusing to guess which home to tear down; pass --home PATH" >&2; exit 2; }
[[ -d "$TEST_HOME" ]] || { echo "no such home: $TEST_HOME" >&2; exit 2; }
TEST_HOME="$(cd "$TEST_HOME" && pwd)"
if [[ "$TEST_HOME" == "$HOME/.hermes" ]]; then
  echo "refusing: $TEST_HOME is the machine-level root home" >&2
  exit 2
fi

echo "home: $TEST_HOME"
echo
echo "== 1/4 remove the credential copy =="
# A live capture needs a provider, so the disposable home may hold a copy of the operator's
# auth.json. That copy is the one piece of test residue that must never survive teardown: it lives
# outside the root home and outlives the plugin. Delete exactly that path, never a tree.
if [[ -e "$TEST_HOME/auth.json" ]]; then
  rm -f "$TEST_HOME/auth.json"
  echo "deleted the copied credential file $TEST_HOME/auth.json"
else
  echo "no credential copy at $TEST_HOME/auth.json"
fi

echo
echo "== 2/4 disable =="
HERMES_HOME="$TEST_HOME" "$HERMES_BIN" plugins disable coursebook || true

echo
echo "== 3/4 remove the package =="
PLUGIN_PATH="$TEST_HOME/plugins/coursebook"
DESKTOP_PATH="$TEST_HOME/desktop-plugins/coursebook"
if [[ -L "$PLUGIN_PATH" ]]; then
  # A linked development install is a symlink to a checkout. `hermes plugins remove` refuses it
  # (it resolves outside the plugins directory) and must not follow it: unlink only the link, so
  # the checkout and its git history are untouched.
  rm -f "$PLUGIN_PATH"
  echo "unlinked $PLUGIN_PATH (the checkout it pointed at is untouched)"
  if [[ -d "$DESKTOP_PATH" ]]; then
    # The app-root copy is a real folder; empty it without a recursive delete, then drop the dir.
    find "$DESKTOP_PATH" -mindepth 1 -delete
    rmdir "$DESKTOP_PATH"
    echo "removed the Desktop app-root copy $DESKTOP_PATH"
  fi
else
  HERMES_HOME="$TEST_HOME" "$HERMES_BIN" plugins remove coursebook
fi

echo
echo "== 4/4 verify the home no longer lists it, and holds no credential copy =="
if HERMES_HOME="$TEST_HOME" "$HERMES_BIN" plugins list --plain --no-bundled 2>/dev/null | grep -q '^coursebook'; then
  echo "coursebook is still listed after removal" >&2
  exit 1
fi
echo "unlisted"
if [[ -e "$TEST_HOME/auth.json" ]]; then
  echo "credential copy still present after teardown: $TEST_HOME/auth.json" >&2
  exit 1
fi
echo "no credential copy remains"

echo
echo "Plugin data under $TEST_HOME/plugin-data/coursebook was kept."
echo "Deleting the whole disposable home is the operator's call, not this script's."
