#!/usr/bin/env bash
# Start one isolated Coursebook backend for the H-210-R2 pack round-trip.
#   serve.sh <home> <port> <token>
set -euo pipefail
HOME_DIR="$1"
PORT="$2"
TOKEN="$3"
HERMES_BIN="${HERMES_BIN:-$(command -v hermes)}"
LOG="$HOME_DIR/serve-$PORT.log"
PIDF="$HOME_DIR/serve-$PORT.pid"
export HERMES_COURSEBOOK_SINGLE_HOME=1
export HERMES_DASHBOARD_SESSION_TOKEN="$TOKEN"
nohup env HERMES_HOME="$HOME_DIR" "$HERMES_BIN" serve --isolated --port "$PORT" --skip-build >>"$LOG" 2>&1 &
echo $! > "$PIDF"
for _ in $(seq 1 180); do
  if grep -q "HERMES_DASHBOARD_READY port=$PORT" "$LOG" 2>/dev/null; then break; fi
  sleep 0.5
done
grep -q "HERMES_DASHBOARD_READY port=$PORT" "$LOG" || { echo "backend not ready; see $LOG" >&2; exit 1; }
echo "ready $PORT pid $(cat "$PIDF") home $HOME_DIR"
