#!/usr/bin/env bash
# The admission gate. Run before every merge into master.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1/4 unit tests + contract audit =="
"${COURSEBOOK_PYTHON:-python3}" -m unittest discover -s tests -t . -v

echo
echo "== 2/4 desktop module parses as ESM =="
node --check desktop/plugin.js
echo "desktop/plugin.js: syntax OK"

echo
echo "== 3/4 catalog admission =="
hermes plugins validate .

echo
echo "== 4/4 runtime contracts (doctor) =="
hermes plugins doctor .

echo
echo "Validation passed."
