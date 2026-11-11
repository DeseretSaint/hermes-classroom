#!/usr/bin/env bash
# CP-051 — a private Desktop rig that loads a plugin from a worktree checkout.
#
# WHAT THIS IS
#   One disposable Desktop peer: its own isolated Hermes home, its own isolated Desktop
#   user-data dir, its own isolated backend port and its own CDP port. It never reads or writes
#   the operator's ~/.config/Hermes, never signals the default-profile gateway (the host
#   multiplexer, e.g. PID 388977), and never attaches to the main app window.
#
#   The recipe is the REMOTE lane, not the local one:
#     home    : $STATE/home            (isolated HERMES_HOME the plugin is installed into)
#     backend : `hermes serve --isolated --port $BACKEND_PORT`   (headless JSON-RPC + WS only)
#     desktop : connections.json, version 2, primary = kind:"remote" -> 127.0.0.1:$BACKEND_PORT
#     window  : dev Electron from apps/desktop with --remote-debugging-port=$CDP_PORT
#
#   Why remote: a window on the LOCAL connection calls `hermes <home> gateway ensure`. For a home
#   that is not a `<root>/profiles/<name>` profile, that ensure pins `--profile default`
#   (hermes_cli/gateway_runtime_start.spawn_unmanaged_gateway), the CLI re-resolves HERMES_HOME to
#   the real default root, sees the live host multiplexer already serving "default", prints
#   "The host gateway already serves profile 'default' — nothing to start" and exits 0. Desktop
#   reads that as `runtime_exited` / "Gateway inaccessible (runtime_exited). the gateway exited
#   with status 0 before it could serve" and paints no plugin route. A remote connection never
#   makes that call. The full mechanism, with the exact log lines and code paths, is in
#   docs/CP-051-PRIVATE-RIG.md.
#
# PORTS (all loopback, all overridable)
#   CB051_BACKEND_PORT  default 44551   `hermes serve --isolated` for the rig home
#   CB051_CDP_PORT      default 9411    Electron remote debugging for capture scripts
#   HERMES_DESKTOP_DEV_SERVER must already be running (default http://127.0.0.1:5174): the dev
#   Electron renderer is served by Vite, and the backend only answers that Origin with CORS
#   headers when it inherits this variable.
#
# ISOLATION
#   $STATE defaults to ~/.hermes/coursebook-test-cp051 (a sibling of the other cards' states).
#   Nothing here touches ~/.hermes/plugins, ~/.hermes/profiles/*, ~/.config/Hermes or the
#   operator's gateway. Do not delete another card's ~/.hermes/coursebook-test-* home.
#
#   scripts/rig-private-desktop.sh                  # install + start backend + start window
#   scripts/rig-private-desktop.sh --install-only   # home + plugin install, no backend/window
#   scripts/rig-private-desktop.sh --restart        # refresh plugin.js, restart window
#   scripts/rig-private-desktop.sh --status         # ports + shas, no writes
#   scripts/rig-private-desktop.sh --stop           # stop this rig only (window, backend)
#
# TEARDOWN
#   --stop kills exactly the PIDs this script recorded ($STATE/window.pid, $STATE/serve-$PORT.pid).
#   It never uses a pkill pattern and never `hermes gateway stop` (which could target the host
#   multiplexer). Delete the state dir by hand when the card is finished.
#
# FINDING THE CDP PORT
#   `node visual/find-cdp.mjs` lists every Electron CDP port whose page currently carries
#   `[data-cb-route]`; it probes each listener rather than trusting an env var, so a stale window
#   on the same port cannot be mistaken for this one. Use `--port $CDP_PORT` explicitly when you
#   already know this rig owns it.
set -euo pipefail

SOURCE_DEFAULT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="${CB051_STATE:-$HOME/.hermes/coursebook-test-cp051}"
HOME_DIR="$STATE/home"
USERDATA="$STATE/userdata"
BACKEND_PORT="${CB051_BACKEND_PORT:-44551}"
CDP_PORT="${CB051_CDP_PORT:-9411}"
TOKEN="${CB051_TOKEN:-cb051-rig-token}"
DEV_SERVER="${HERMES_DESKTOP_DEV_SERVER:-http://127.0.0.1:5174}"
APP="${HERMES_DESKTOP_APP:-$HOME/.hermes/hermes-agent/apps/desktop}"
ELECTRON="${ELECTRON_BIN:-$HOME/.hermes/hermes-agent/node_modules/electron/dist/electron}"
HERMES_BIN="${HERMES_BIN:-$(command -v hermes || echo "$HOME/.local/bin/hermes")}"
WINDOW_LOG="$STATE/window.log"
WINDOW_PID="$STATE/window.pid"
BACKEND_PID="$STATE/serve-$BACKEND_PORT.pid"
BACKEND_LOG="$STATE/serve-$BACKEND_PORT.log"

die() { echo "rig: $*" >&2; exit 1; }

stop_pidfile() {
  local pidf="$1" label="$2" pid
  [[ -f "$pidf" ]] || return 0
  pid="$(tr -cd '0-9' <"$pidf")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
    echo "stopped $label pid $pid"
  fi
  rm -f "$pidf"
}

stop() { stop_pidfile "$WINDOW_PID" window; stop_pidfile "$BACKEND_PID" backend; }

status() {
  echo "state        : $STATE"
  echo "home         : $HOME_DIR"
  if [[ -f "$HOME_DIR/desktop-plugins/coursebook/plugin.js" ]]; then
    echo "installed sha: $(sha256sum "$HOME_DIR/desktop-plugins/coursebook/plugin.js" | cut -d' ' -f1)"
  fi
  echo "checkout sha : $(sha256sum "$SOURCE_DEFAULT/desktop/plugin.js" | cut -d' ' -f1)"
  curl -s -m 4 -o /dev/null -w 'backend http : %{http_code}\n' \
    -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$BACKEND_PORT/api/plugins/coursebook/runtime?profile=" \
    || echo "backend http : not listening"
  curl -s -m 4 "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null \
    && echo "cdp          : http://127.0.0.1:$CDP_PORT" \
    || echo "cdp          : not listening"
}

case "${1:-}" in
  --stop) stop; exit 0 ;;
  --status) status; exit 0 ;;
  --install-only|--restart|"") ;;
  *) echo "usage: $0 [--install-only|--restart|--status|--stop]" >&2; exit 2 ;;
esac

ACTION="${1:-}"
SOURCE="$(cd "$SOURCE_DEFAULT" && pwd)"
[[ -f "$SOURCE/plugin.yaml" ]] || die "not a Coursebook checkout: $SOURCE"
[[ -x "$ELECTRON" ]] || die "no dev Electron at $ELECTRON"
case "$(realpath -m "$ELECTRON")" in
  */node_modules/electron/dist/electron) ;;
  *) die "refusing non-dev Electron for a test rig: $ELECTRON" ;;
esac
case "$(realpath -m "$USERDATA")" in
  "$HOME/.config/Hermes"|"$HOME/.config/Hermes/"*) die "refusing the operator's main profile: $USERDATA" ;;
esac

if [[ "$ACTION" == "--restart" ]]; then stop; fi

mkdir -p "$STATE" "$USERDATA"

# 1. Install the checkout's plugin into the isolated home. install-local.sh refuses while a
#    process is using the home, so the backend must be down for the install step.
if [[ "$ACTION" == "--restart" ]]; then
  timeout 900 "$SOURCE/scripts/install-local.sh" --home "$HOME_DIR" --source "$SOURCE" | tail -3
fi
if [[ ! -f "$HOME_DIR/desktop-plugins/coursebook/plugin.js" ]]; then
  timeout 900 "$SOURCE/scripts/install-local.sh" --home "$HOME_DIR" --source "$SOURCE" | tail -3
fi
INSTALLED_SHA="$(sha256sum "$HOME_DIR/desktop-plugins/coursebook/plugin.js" | cut -d' ' -f1)"
CHECKOUT_SHA="$(sha256sum "$SOURCE/desktop/plugin.js" | cut -d' ' -f1)"
[[ "$INSTALLED_SHA" == "$CHECKOUT_SHA" ]] || die "installed plugin.js ($INSTALLED_SHA) != checkout ($CHECKOUT_SHA)"

[[ "$ACTION" == "--install-only" ]] && { status; exit 0; }

# 2. Reference the window at an isolated backend, not at a local gateway: see the header.
cat >"$USERDATA/connections.json" <<JSON
{
  "version": 2,
  "primary": "remote-cp051",
  "launchMode": "primary",
  "lastUsed": "remote-cp051",
  "connections": [
    {
      "id": "local",
      "kind": "local",
      "label": "This device"
    },
    {
      "id": "remote-cp051",
      "kind": "remote",
      "label": "127.0.0.1:$BACKEND_PORT",
      "url": "http://127.0.0.1:$BACKEND_PORT",
      "authMode": "token",
      "token": { "encoding": "plain", "value": "$TOKEN" }
    }
  ]
}
JSON

# 3. Backend. HERMES_COURSEBOOK_SINGLE_HOME pins plugin storage to this home; without it an
#    isolated backend's unscoped request falls through to the operator's profile store.
set -a
# shellcheck disable=SC1091
. "$HOME_DIR/coursebook-single-home.env"
set +a
stop_pidfile "$BACKEND_PID" backend
if ss -ltn 2>/dev/null | grep -q "127.0.0.1:$BACKEND_PORT "; then
  die "port $BACKEND_PORT is already in use (not by this rig's pid file); stop that process or set CB051_BACKEND_PORT"
fi
HERMES_HOME="$HOME_DIR" \
HERMES_DESKTOP_DEV_SERVER="$DEV_SERVER" \
HERMES_DASHBOARD_SESSION_TOKEN="$TOKEN" \
  nohup "$HERMES_BIN" serve --isolated --port "$BACKEND_PORT" --skip-build >>"$BACKEND_LOG" 2>&1 &
echo $! >"$BACKEND_PID"
for _ in $(seq 1 120); do
  grep -q "HERMES_DASHBOARD_READY port=$BACKEND_PORT" "$BACKEND_LOG" 2>/dev/null && break
  sleep 0.5
done
grep -q "HERMES_DASHBOARD_READY port=$BACKEND_PORT" "$BACKEND_LOG" \
  || die "backend did not report ready; see $BACKEND_LOG"

# 4. Window. `hermes serve` is headless BY DESIGN (it answers the frontend catch-all with
#    "Headless backend (hermes serve): web UI disabled"); that message is not the fault. The
#    Desktop renderer comes from the Vite dev server, and the backend is reached over the remote
#    connection written above.
stop_pidfile "$WINDOW_PID" window
cd "$APP"
HERMES_HOME="$HOME_DIR" \
HERMES_DESKTOP_USER_DATA_DIR="$USERDATA" \
HERMES_DESKTOP_DEV_SERVER="$DEV_SERVER" \
XCURSOR_SIZE=24 \
  nohup "$ELECTRON" --disable-gpu --no-sandbox --ozone-platform=wayland \
    --remote-debugging-port="$CDP_PORT" . >>"$WINDOW_LOG" 2>&1 &
echo $! >"$WINDOW_PID"
for _ in $(seq 1 80); do
  curl -s -m 2 "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -s -m 2 "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null \
  || die "window did not expose CDP; see $WINDOW_LOG"

status
echo
echo "window pid $(cat "$WINDOW_PID") on http://127.0.0.1:$CDP_PORT"
echo "next : node visual/find-cdp.mjs   # confirms the route is painted before any capture"
