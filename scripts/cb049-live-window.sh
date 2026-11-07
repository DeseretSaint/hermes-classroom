#!/usr/bin/env bash
# Launch (or relaunch) an isolated Desktop window for the CB-049 polish pass.
# Same remote backend (127.0.0.1:44219) and dev renderer as the CB-015 window, but its own
# HERMES_HOME/userdata so no other worker's window or installed plugin is disturbed.
set -euo pipefail

STATE_DIR="${CB049_TEST_STATE:-$HOME/.hermes/cb049-test}"
HOME_DIR="${CB049_HERMES_HOME:-$STATE_DIR/home}"
USERDATA="$STATE_DIR/userdata"
PORT="${CB049_CDP_PORT:-9341}"
APP="${HERMES_DESKTOP_APP:-$HOME/.hermes/hermes-agent/apps/desktop}"
ELECTRON="${ELECTRON_BIN:-$HOME/.hermes/hermes-agent/node_modules/electron/dist/electron}"
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
  --stop) stop; exit 0 ;;
  --status) status; exit $? ;;
  --restart) ;;
  "") ;;
  *) echo "usage: $0 [--restart|--stop|--status]" >&2; exit 2 ;;
esac

[[ -x "$ELECTRON" ]] || { echo "no electron binary at $ELECTRON" >&2; exit 1; }
# Never launch the operator's packaged app or default profile from a test rig.
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

# Reuse this state's existing window instead of flashing a new one on every
# harness invocation; --restart is for an intentional plugin.js swap.
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
