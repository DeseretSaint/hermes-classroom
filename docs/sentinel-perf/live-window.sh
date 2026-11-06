#!/usr/bin/env bash
# Launch the isolated Sentinel perf window (candidate b476738) against the 44241 backend.
# Own HERMES_HOME and userdata: no other worker's window or installed plugin is touched.
set -euo pipefail

STATE_DIR="$HOME/.hermes/sentinel-perf"
HOME_DIR="$STATE_DIR/home"
USERDATA="$STATE_DIR/userdata"
PORT="${SENTINEL_CDP_PORT:-9351}"
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
  if curl -s -m 4 "http://127.0.0.1:$PORT/json/version" >/dev/null; then
    echo "cdp: http://127.0.0.1:$PORT"; return 0
  fi
  echo "cdp: not listening"; return 1
}
case "${1:-}" in
  --stop) stop; exit 0 ;;
  --status) status; exit $? ;;
  "") ;;
  *) echo "usage: $0 [--stop|--status]" >&2; exit 2 ;;
esac

[[ -x "$ELECTRON" ]] || { echo "no electron binary at $ELECTRON" >&2; exit 1; }
[[ -f "$USERDATA/connections.json" ]] || { echo "no $USERDATA/connections.json" >&2; exit 1; }

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
