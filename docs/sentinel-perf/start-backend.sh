#!/usr/bin/env bash
# Sentinel perf rig: isolated Coursebook backend for candidate b476738.
set -euo pipefail
HOME_DIR="$HOME/.hermes/sentinel-perf/home"
PORT="${1:-44221}"
LOG="$HOME/.hermes/sentinel-perf/serve-$PORT.log"
cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_19da8432
set -a
# shellcheck disable=SC1091
. "$HOME_DIR/coursebook-single-home.env"
set +a
export HERMES_HOME="$HOME_DIR"
export HERMES_DESKTOP_DEV_SERVER="http://127.0.0.1:5174"
export HERMES_DASHBOARD_SESSION_TOKEN="sentinel-perf-token"
exec hermes serve --isolated --port "$PORT" --skip-build
