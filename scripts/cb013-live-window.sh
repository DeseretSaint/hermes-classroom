#!/usr/bin/env bash
# Launch (or relaunch) the isolated Desktop window that talks to scripts/cb013-live-backend.sh.
#
# The window is a REMOTE connection (`connections.json` kind:"remote" -> 127.0.0.1:44219), not the
# machine-level local backend, so nothing here touches the operator's window or gateway.
# CDP is on 127.0.0.1:9337 for the capture scripts in this directory.
#
#   scripts/cb013-live-window.sh            # start
#   scripts/cb013-live-window.sh --stop
#   scripts/cb013-live-window.sh --status
#   scripts/cb013-live-window.sh --print-bin   # print the Electron it would launch, start nothing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HERMES_AGENT="${HERMES_AGENT_HOME:-$HOME/.hermes/hermes-agent}"
STATE_DIR="${COURSEBOOK_TEST_STATE:-$HOME/.hermes/coursebook-test}"
HOME_DIR="$STATE_DIR/home"
USERDATA="$STATE_DIR/userdata"
PORT="${CB013_CDP_PORT:-9337}"
APP="${HERMES_DESKTOP_APP:-$HERMES_AGENT/apps/desktop}"

# The dev Electron is a host tool and pnpm does not hoist it: it lives under
# `node_modules/.pnpm/electron@<version>/node_modules/electron/dist`. Looking only at the
# hoisted path made Gate 5 stop with "no electron binary at .../node_modules/electron/dist/electron"
# while the binary was installed all along. Resolve in this order:
#   1. ELECTRON_BIN, when set and executable;
#   2. this repo's own pnpm store;
#   3. the hermes-agent install (pnpm stores, then the desktop workspace copy);
#   4. the hoisted hermes-agent path the script used to hardcode.
# Prints the chosen path on stdout; tried paths go to stderr. Returns 1 when nothing is found.
resolve_electron() {
  local candidates=() candidate store
  [[ -n "${ELECTRON_BIN:-}" ]] && candidates+=("$ELECTRON_BIN")
  for store in \
    "$REPO_ROOT/node_modules/.pnpm" \
    "$HERMES_AGENT/node_modules/.pnpm" \
    "$HERMES_AGENT/apps/desktop/node_modules/.pnpm"; do
    for candidate in "$store"/electron@*/node_modules/electron/dist/electron; do
      [[ -x "$candidate" ]] && candidates+=("$candidate")
    done
  done
  candidates+=("$HERMES_AGENT/apps/desktop/node_modules/electron/dist/electron")
  candidates+=("$HERMES_AGENT/node_modules/electron/dist/electron")
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" && -x "$candidate" ]] && { printf '%s\n' "$candidate"; return 0; }
  done
  local tried=("${candidates[@]}")
  [[ ${#tried[@]} -eq 0 ]] && tried=("$REPO_ROOT/node_modules/.pnpm/electron@*/node_modules/electron/dist/electron" "$HERMES_AGENT/node_modules/.pnpm/electron@*/node_modules/electron/dist/electron")
  for candidate in "${tried[@]}"; do
    [[ -n "$candidate" ]] && printf '  tried %s\n' "$candidate" >&2
  done
  return 1
}

LOG="$STATE_DIR/window.log"
PIDF="$STATE_DIR/window.pid"

stop() {
  if [[ -f "$PIDF" ]]; then
    local pid
    pid="$(cat "$PIDF")"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
    rm -f "$PIDF"
    echo "stopped window pid $pid"
  fi
}

status() {
  curl -s -m 4 "http://127.0.0.1:$PORT/json/version" >/dev/null && {
    echo "cdp: http://127.0.0.1:$PORT"; return 0; }
  echo "cdp: not listening"; return 1
}

case "${1:-}" in
  --print-bin)
    ELECTRON="$(resolve_electron)" || {
      echo "no electron binary for the rig; set ELECTRON_BIN to apps/desktop/node_modules/electron/dist/electron" >&2
      exit 1
    }
    printf '%s\n' "$ELECTRON"
    exit 0
    ;;
  --stop) stop; exit 0 ;;
  --status) status; exit $? ;;
  --restart) ;;
  "") ;;
  *) echo "usage: $0 [--restart|--stop|--status|--print-bin]" >&2; exit 2 ;;
esac

ELECTRON="$(resolve_electron)" || {
  echo "no electron binary for the rig; set ELECTRON_BIN to apps/desktop/node_modules/electron/dist/electron" >&2
  exit 1
}
# A test rig must never launch the operator's packaged app or default profile.
# The packaged binary shares the main app's WM class; `hermes desktop` would
# bring the real window to the front and make a test look like a main-window
# adjustment.
case "$(realpath -m "$ELECTRON")" in
  */node_modules/electron/dist/electron) ;;
  *) echo "refusing non-dev Electron for a test rig: $ELECTRON" >&2; exit 1 ;;
esac
case "$(realpath -m "$APP")" in
  */apps/desktop) ;;
  *) echo "refusing non-dev app path for a test rig: $APP" >&2; exit 1 ;;
esac
case "$(realpath -m "$USERDATA")" in
  "$HOME/.config/Hermes"|"$HOME/.config/Hermes/"*) echo "refusing the operator's main profile: $USERDATA" >&2; exit 1 ;;
esac
[[ -f "$USERDATA/connections.json" ]] || { echo "no $USERDATA/connections.json (remote connection)" >&2; exit 1; }

# A harness that runs several scripts should not flash a new window on every
# invocation. If this state already has a live CDP window, reuse it unless the
# caller explicitly asks to restart (for a plugin.js swap).
if [[ "${1:-}" != "--restart" && -f "$PIDF" ]]; then
  existing_pid="$(cat "$PIDF" 2>/dev/null || true)"
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null && status >/dev/null 2>&1; then
    echo "reusing window pid $existing_pid (CDP $PORT)"
    exit 0
  fi
fi

stop
cd "$APP"
HERMES_HOME="$HOME_DIR" \
HERMES_DESKTOP_USER_DATA_DIR="$USERDATA" \
HERMES_DESKTOP_DEV_SERVER="http://127.0.0.1:5174" \
XCURSOR_SIZE=24 \
  nohup "$ELECTRON" --disable-gpu --no-sandbox --ozone-platform=wayland \
    --remote-debugging-port="$PORT" . >>"$LOG" 2>&1 &
echo $! >"$PIDF"
for _ in $(seq 1 80); do
  curl -s -m 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 && break
  sleep 0.5
done
status || { echo "window did not expose CDP; see $LOG" >&2; exit 1; }
echo "window pid $(cat "$PIDF")"
