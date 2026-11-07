#!/usr/bin/env bash
# Launch the M1 Textbook/Guided evidence window for THIS checkout.
#
# REMOTE mode against the isolated backend from scripts/cb013-live-backend.sh, so the Python half
# that answers `lesson.page` is the checkout under test and nothing touches the operator's window,
# gateway or home. `HERMES_DESKTOP_REMOTE_URL` is the documented env override (main.ts
# sanitizeDesktopConnectionConfig): no connections.json edit, no renderer LevelDB rewrite.
#
#   RIG=~/.hermes/coursebook-m1-views-<id> BACKEND_PORT=44301 bash scripts/m1v-live-window.sh
set -euo pipefail

RIG="${RIG:?set RIG to an isolated rig directory}"
PORT="${PORT:-9351}"
BACKEND_PORT="${BACKEND_PORT:-44301}"
TOKEN="${CB013_TOKEN:-cb013-test-token}"
APP="${APP:-$HOME/.hermes/hermes-agent/apps/desktop}"
ELECTRON="${ELECTRON:-$HOME/.hermes/hermes-agent/node_modules/electron/dist/electron}"
PIDF="$RIG/window-$PORT.pid"
LOG="$RIG/window-$PORT.log"

if [[ "${1:-}" == "--stop" ]]; then
  [[ -f "$PIDF" ]] && kill "$(cat "$PIDF")" 2>/dev/null || true
  rm -f "$PIDF"
  exit 0
fi

[[ -x "$ELECTRON" ]] || { echo "no electron at $ELECTRON" >&2; exit 1; }
# Never launch the operator's packaged app or default profile from a test rig.
case "$(realpath -m "$ELECTRON")" in
  */node_modules/electron/dist/electron) ;;
  *) echo "refusing non-dev Electron for a test rig: $ELECTRON" >&2; exit 1 ;;
esac
case "$(realpath -m "$APP")" in
  */apps/desktop) ;;
  *) echo "refusing non-dev app path for a test rig: $APP" >&2; exit 1 ;;
esac
case "$(realpath -m "$RIG/userdata")" in
  "$HOME/.config/Hermes"|"$HOME/.config/Hermes/"*) echo "refusing the operator's main profile: $RIG/userdata" >&2; exit 1 ;;
esac
# A copied userdata dir carries a SingletonLock naming the process it came from; a live PID there
# makes Chromium refuse the launch with no useful message.
rm -f "$RIG/userdata/SingletonLock" "$RIG/userdata/SingletonSocket" "$RIG/userdata/SingletonCookie"

cd "$APP"
HERMES_HOME="$RIG/home" \
HERMES_DESKTOP_USER_DATA_DIR="$RIG/userdata" \
HERMES_DESKTOP_REMOTE_URL="http://127.0.0.1:$BACKEND_PORT" \
HERMES_DESKTOP_REMOTE_TOKEN="$TOKEN" \
HERMES_DESKTOP_DEV_SERVER="http://127.0.0.1:5174" \
XCURSOR_SIZE=24 \
  nohup "$ELECTRON" --disable-gpu --no-sandbox --ozone-platform=wayland \
    --user-data-dir="$RIG/userdata" \
    --remote-debugging-port="$PORT" . >>"$LOG" 2>&1 &
echo $! >"$PIDF"
for _ in $(seq 1 120); do
  curl -s -m 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -s -m 2 "http://127.0.0.1:$PORT/json/version" >/dev/null || {
  echo "cdp did not open; see $LOG" >&2; exit 1; }
echo "window pid $(cat "$PIDF") cdp http://127.0.0.1:$PORT"
