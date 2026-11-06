#!/usr/bin/env bash
# Full enable/disable/re-enable lifecycle in a THROWAWAY HERMES_HOME.
#
# Why isolated: the acceptance criterion is "clean install/enable/disable/re-enable works", and
# proving it must not touch the operator's profile, plugin-data, or config. This creates a temp
# home, links the checkout in (the documented dev flow), and drives the real `hermes plugins`
# commands against it.
#
# The gateway is never started and never restarted: backend routes mount at gateway startup, which
# is the operator's call, not a test's.
set -euo pipefail
cd "$(dirname "$0")/.."

SOURCE="$(pwd)"
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/coursebook-lifecycle.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT

echo "isolated HERMES_HOME: $SANDBOX"
mkdir -p "$SANDBOX/plugins"

echo
echo "== 0/6 source gates =="
"${COURSEBOOK_PYTHON:-python3}" -m unittest discover -s tests -t . >/dev/null
echo "unit tests: OK"
node --check desktop/plugin.js
echo "desktop ESM syntax: OK"
hermes plugins validate . >/dev/null
echo "plugins validate: OK"
hermes plugins doctor . >/dev/null
echo "plugins doctor: OK"

echo
echo "== 1/6 link the package (documented dev flow) =="
ln -sfn "$SOURCE" "$SANDBOX/plugins/coursebook"
ls -l "$SANDBOX/plugins" | sed 's/^/  /'

echo
echo "== 2/6 discover it in the isolated home =="
HERMES_HOME="$SANDBOX" hermes plugins list --plain --no-bundled | grep -q coursebook
echo "  discovered: coursebook"

echo
echo "== 3/6 enable (backend half) =="
HERMES_HOME="$SANDBOX" hermes plugins enable coursebook >/dev/null
grep -A3 '^plugins:' "$SANDBOX/config.yaml" | sed 's/^/  /'
grep -q 'coursebook' "$SANDBOX/config.yaml"
echo "  enabled in config.yaml"

echo
echo "== 4/6 disable =="
HERMES_HOME="$SANDBOX" hermes plugins disable coursebook >/dev/null
grep -A4 '^plugins:' "$SANDBOX/config.yaml" | sed 's/^/  /'
"${COURSEBOOK_PYTHON:-python3}" - "$SANDBOX/config.yaml" <<'PY'
import sys, hermes_yaml as yaml
cfg = yaml.safe_load(open(sys.argv[1])) or {}
plugins = cfg.get("plugins") or {}
assert "coursebook" not in (plugins.get("enabled") or []), "still in plugins.enabled"
assert "coursebook" in (plugins.get("disabled") or []), "not recorded in plugins.disabled"
PY
echo "  moved enabled -> disabled"

echo
echo "== 5/6 re-enable =="
HERMES_HOME="$SANDBOX" hermes plugins enable coursebook >/dev/null
grep -A4 '^plugins:' "$SANDBOX/config.yaml" | sed 's/^/  /'
"${COURSEBOOK_PYTHON:-python3}" - "$SANDBOX/config.yaml" <<'PY'
import sys, hermes_yaml as yaml
cfg = yaml.safe_load(open(sys.argv[1])) or {}
plugins = cfg.get("plugins") or {}
assert "coursebook" in (plugins.get("enabled") or []), "not re-enabled"
assert "coursebook" not in (plugins.get("disabled") or []), "still disabled"
PY
echo "  enabled again"

echo
echo "== 6/6 clean removal leaves no state behind =="
HERMES_HOME="$SANDBOX" hermes plugins disable coursebook >/dev/null
rm "$SANDBOX/plugins/coursebook"
HERMES_HOME="$SANDBOX" hermes plugins list --plain --no-bundled | grep -q coursebook && {
  echo "  FAIL: coursebook still listed after removal" >&2
  exit 1
}
echo "  unlisted; operator state never touched"

echo
echo "Lifecycle passed (isolated home deleted on exit)."
