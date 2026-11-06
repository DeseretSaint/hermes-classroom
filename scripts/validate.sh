#!/usr/bin/env bash
# The admission gate. Run before every merge into master.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1/5 unit tests + contract audit =="
"${COURSEBOOK_PYTHON:-python3}" -m unittest discover -s tests -t . -v

echo
echo "== 2/5 desktop module parses as ESM =="
node --check desktop/plugin.js
echo "desktop/plugin.js: syntax OK"

echo
echo "== 3/5 catalog admission =="
hermes plugins validate .

echo
echo "== 4/5 runtime contracts (doctor) =="
hermes plugins doctor .

echo
echo "== 5/5 mounted backend trace (isolated HERMES_HOME) =="
"${COURSEBOOK_PYTHON:-python3}" scripts/probe-backend.py

echo
echo "Validation passed."
