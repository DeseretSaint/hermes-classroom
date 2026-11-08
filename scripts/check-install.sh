#!/usr/bin/env bash
# Is the Desktop half a Hermes home loads THE Desktop half this package ships?
#
#   bash scripts/check-install.sh --home ~/.hermes/coursebook-test/home
#   bash scripts/check-install.sh --home "$HOME/.hermes"          # read-only, never repairs it
#   bash scripts/check-install.sh --home <home> --refresh-desktop # repair (not while a worker runs)
#
# Why this exists: Hermes runs `<home>/desktop-plugins/coursebook/plugin.js`, a COPY made at
# install/rescan time. Editing or updating the checkout changes nothing on screen until that copy
# is refreshed, and `hermes plugins doctor` reports the divergence as a warning among many, with
# no repair command. This check compares SHA-256 of both files, prints both hashes, and ends with
# one exact command that repairs it.
#
# A refresh is refused while a Hermes/Desktop process is using the home (close it first; --force
# copies the file anyway and leaves the old code loaded), and it is refused for the machine-level
# home (~/.hermes) because installing there is an operator decision.
#
# Exit codes: 0 both halves match; 1 stale/missing (the fix command is printed); 2 usage or setup
# error; 3 the refresh was refused (live worker or machine-level home).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${COURSEBOOK_PYTHON:-python3}"

exec "$PYTHON_BIN" "$REPO/coursebook/install_check.py" --source "$REPO" "$@"
