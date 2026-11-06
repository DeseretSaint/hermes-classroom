#!/usr/bin/env bash
# Run every Coursebook check that can run without a live Desktop window.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${COURSEBOOK_PYTHON:-python3}"

echo "== contract + backend tests =="
"$PYTHON" -m unittest discover -s tests -t . -v

echo
echo "== desktop module parses as ESM =="
node --check desktop/plugin.js
echo "desktop/plugin.js: syntax OK"

echo
echo "All checks passed."
