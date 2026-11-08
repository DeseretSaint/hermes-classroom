#!/usr/bin/env bash
# H-187 driver (part 2): run the single scope once the short scope has finished.
#
# The live provider could not author a plan inside the declared 240 s deadline on 2026-11-08
# 10:24-10:28, so this run raises the per-purpose declared deadlines through the documented
# operator knob and waits for the short scope so that no more than two structured calls are ever
# in flight. No rule, cap or bound changes here.
set -uo pipefail

SOURCE="$(cd "$(dirname "$0")/../../.." && pwd)"
EVIDENCE="$SOURCE/audit/adversarial/live-generation-2026-11-08/evidence"
BASE=/home/deseretsaint/.hermes/h187-live-gen
PY=/home/deseretsaint/.hermes/installs/4d8bf4040d63cdfa/environments/12913d7d436b4c0fb0877aaefcb88e69/venv/bin/python

export HERMES_DISABLE_LAZY_INSTALLS=1
export HERMES_AGENT_ROOT=/home/deseretsaint/.hermes/hermes-agent
export COURSEBOOK_SOURCE="$SOURCE"
export H187_VALIDATOR_PROVIDER=nous
export H187_VALIDATOR_MODEL=z-ai/glm-5.3-flash
export COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS=420
export COURSEBOOK_PLAN_VALIDATE_TIMEOUT_SECONDS=300
export COURSEBOOK_UNIT_SECTIONS_GENERATE_TIMEOUT_SECONDS=420
export COURSEBOOK_UNIT_SECTIONS_VALIDATE_TIMEOUT_SECONDS=300
export COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS=420
export COURSEBOOK_LESSON_VALIDATE_TIMEOUT_SECONDS=300

while pgrep -f "worker.py --tag short-r3" >/dev/null 2>&1; do sleep 5; done

HERMES_HOME="$BASE/single/home" "$PY" "$SOURCE/audit/adversarial/live-generation-2026-11-08/worker.py" \
  --tag single-r3 \
  --title "Sharpen a kitchen knife on a whetstone" \
  --goal "Sharpen a kitchen knife on a whetstone without rolling the edge" \
  --recipe one_off --scope single --subject-domain technical_procedure --depth working \
  --units 1 --max-seconds 900 \
  --result "$EVIDENCE/single.json" >> "$BASE/single/run-single-r3.log" 2>&1
echo "single-r3 exit=$?" >&2
