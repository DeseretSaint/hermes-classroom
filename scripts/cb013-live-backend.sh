#!/usr/bin/env bash
# Start or cycle the isolated Coursebook backend used for live Desktop capture.
#
# This is a DISPOSABLE home (`~/.hermes/coursebook-test/home`), never the root profile and never a
# bot profile. The three env vars are load-bearing:
#   HERMES_HOME                    the isolated home the window is pointed at
#   HERMES_COURSEBOOK_SINGLE_HOME  pin plugin storage to that home when a request scope escapes it
#   HERMES_DESKTOP_DEV_SERVER      makes the API answer the renderer's Origin with CORS headers
#                                  (without it the window reports "Backend offline")
#
#   scripts/cb013-live-backend.sh            # (re)start
#   scripts/cb013-live-backend.sh --stop     # stop only
#   scripts/cb013-live-backend.sh --status   # pid + readiness, no writes
set -euo pipefail

HOME_DIR="${COURSEBOOK_TEST_HOME:-$HOME/.hermes/coursebook-test/home}"
PORT="${CB013_PORT:-44219}"
TOKEN="${CB013_TOKEN:-cb013-test-token}"
STATE_DIR="$(dirname "$HOME_DIR")"
LOG="$STATE_DIR/serve-$PORT.log"
PIDF="$STATE_DIR/serve-$PORT.pid"
HERMES_BIN="${HERMES_BIN:-$(command -v hermes || echo "$HOME/.local/bin/hermes")}"

stop() {
  if [[ -f "$PIDF" ]]; then
    local pid
    pid="$(cat "$PIDF")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      for _ in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
      echo "stopped pid $pid"
    fi
    rm -f "$PIDF"
  fi
}

status() {
  if [[ -f "$PIDF" ]] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
    echo "pid: $(cat "$PIDF")"
  else
    echo "pid: not running"
    return 1
  fi
  curl -s -m 5 -o /dev/null -w 'runtime http: %{http_code}\n' \
    -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$PORT/api/plugins/coursebook/runtime?profile="
}

case "${1:-}" in
  --stop) stop; exit 0 ;;
  --status) status; exit $? ;;
  "") ;;
  *) echo "usage: $0 [--stop|--status]" >&2; exit 2 ;;
esac

[[ -f "$HOME_DIR/coursebook-single-home.env" ]] || {
  echo "no $HOME_DIR/coursebook-single-home.env; run scripts/install-local.sh first" >&2; exit 1; }

stop
set -a
# shellcheck disable=SC1091
. "$HOME_DIR/coursebook-single-home.env"
set +a
HERMES_HOME="$HOME_DIR" \
HERMES_DESKTOP_DEV_SERVER="http://127.0.0.1:5174" \
HERMES_DASHBOARD_SESSION_TOKEN="$TOKEN" \
  nohup "$HERMES_BIN" serve --isolated --port "$PORT" --skip-build >>"$LOG" 2>&1 &
echo $! >"$PIDF"
for _ in $(seq 1 120); do
  if grep -q "HERMES_DASHBOARD_READY port=$PORT" "$LOG" 2>/dev/null; then break; fi
  sleep 0.5
done
grep -q "HERMES_DASHBOARD_READY port=$PORT" "$LOG" || { echo "backend did not report ready; see $LOG" >&2; exit 1; }
echo "backend ready on 127.0.0.1:$PORT (pid $(cat "$PIDF"))"
status || true
