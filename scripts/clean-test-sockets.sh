#!/usr/bin/env bash
# Remove stale Chromium Singleton* entries from this checkout's disposable audit profiles.
#
#   bash scripts/clean-test-sockets.sh [--dry-run]
#
# The frame scripts launch Chromium with `--user-data-dir=<audit dir>/.chromium` and kill it
# without a graceful shutdown, which leaves SingletonLock, SingletonSocket and SingletonCookie
# behind. A worktree copied into a Hermes home then carries those entries, and any tool that
# copies the tree (Plugin Doctor stages a copy of the package it is given) fails on the socket:
# `[Errno 6] No such device or address`.
#
# Only entries whose name starts with `Singleton` inside a directory named `.chromium` are
# touched, and a profile whose lock names a live PID is kept (the process is still using it).
# Pass --dry-run to list what would go without removing anything.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${COURSEBOOK_PYTHON:-python3}"

if [[ "${1:-}" == "--dry-run" ]]; then
  shift
  exec "$PYTHON_BIN" "$REPO/coursebook/install_check.py" --source "$REPO" --clean-sockets --dry-run "$@"
fi

exec "$PYTHON_BIN" "$REPO/coursebook/install_check.py" --source "$REPO" --clean-sockets "$@"
