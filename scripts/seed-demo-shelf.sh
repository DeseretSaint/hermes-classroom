#!/usr/bin/env bash
# Rebuild the four-course demo shelf from the committed exports.
#
# One command, no model, no provider: every course on the shelf is a real `course.export`
# artifact produced by the product's own create flow (`scripts/cp015-demo-courses.py`), and this
# script only drives the learner's import path — grant, preview, import — then reads
# `library.list` back and fails if any of the four is missing.
#
#   scripts/seed-demo-shelf.sh
#   scripts/seed-demo-shelf.sh --base-url http://127.0.0.1:44501 --token "$TOKEN"
#   scripts/seed-demo-shelf.sh --dry-run
#
# The demo backend is the disposable home `~/.hermes/coursebook-test-cp015/home`:
#   COURSEBOOK_TEST_HOME=~/.hermes/coursebook-test-cp015/home \
#   CB013_PORT=44501 CB013_TOKEN=cp015-demo-token scripts/cb013-live-backend.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/seed-demo-shelf.py" "$@"
