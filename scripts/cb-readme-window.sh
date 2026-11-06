#!/usr/bin/env bash
# Launch the isolated Desktop window used for the README/demo capture set.
#
# Its own HERMES_HOME (~/.hermes/cb-readme/home, installed by scripts/install-local.sh) and its own
# userdata, talking to the isolated backend on 127.0.0.1:44310 (scripts/cb013-live-backend.sh with
# COURSEBOOK_TEST_HOME and CB013_PORT). Nothing here touches the operator's window or profile.
#
#   scripts/cb-readme-window.sh            # (re)start
#   scripts/cb-readme-window.sh --stop
#   scripts/cb-readme-window.sh --status
set -euo pipefail

STATE_DIR="${CB_README_STATE:-$HOME/.hermes/cb-readme}"
HOME_DIR="${CB_README_HERMES_HOME:-$STATE_DIR/home}"
USERDATA="${CB_README_USERDATA:-$STATE_DIR/userdata}"
PORT="${CB_README_CDP_PORT:-9382}"
APP="${HERMES_DESKTOP_APP:-$HOME/.hermes/hermes-agent/apps/desktop}"
ELECTRON="${ELECTRON_BIN:-$HOME/.hermes/hermes-agent/node_modules/electron/dist/electron}"
LOG="$STATE_DIR/window-$PORT.log"
PIDF="$STATE_DIR/window-$PORT.pid"

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
echo $! > "$PIDF"
for _ in $(seq 1 80); do
  curl -s -m 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 && break
  sleep 0.5
done
status || { echo "window did not expose CDP; see $LOG" >&2; exit 1; }
echo "window pid $(cat "$PIDF")"
