#!/usr/bin/env bash
# Run every Coursebook check that can run without a live Desktop window.
#
# The suite imports the host seam `plugins.plugin_storage`; this repo does not
# ship that package, so the host checkout must be importable. Without it 1344
# tests error with `ModuleNotFoundError: No module named 'plugins'` and the run
# looks red for a reason that has nothing to do with this tree. The host path is
# prepended to the *existing* PYTHONPATH (never replacing it: the interpreter's
# own site-packages - jsonschema, Pillow - live there on this box).
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${COURSEBOOK_PYTHON:-python3}"
HOST_ROOT="${COURSEBOOK_HOST_ROOT:-$HOME/.hermes/hermes-agent}"
if [ -f "$HOST_ROOT/plugins/plugin_storage.py" ]; then
  export PYTHONPATH="$HOST_ROOT${PYTHONPATH:+:$PYTHONPATH}"
else
  echo "warning: no host checkout at $HOST_ROOT/plugins/plugin_storage.py;" >&2
  echo "         tests that need the host storage seam will error." >&2
fi

echo "== contract + backend tests =="
"$PYTHON" -m unittest discover -s tests -t . -v

echo
echo "== desktop module parses as ESM =="
node --check desktop/plugin.js
echo "desktop/plugin.js: syntax OK"

echo
echo "All checks passed."
