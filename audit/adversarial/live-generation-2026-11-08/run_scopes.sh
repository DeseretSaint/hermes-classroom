#!/usr/bin/env bash
# H-187 driver: run the remaining scopes one at a time on the isolated homes.
#
# The live provider degraded badly under three concurrent structured calls (measured: a
# plan.generate call hit its 240 s deadline and a plan.validate call hit its 180 s deadline on
# 2026-11-08 10:25-10:26), so the scopes are driven serially and the declared per-purpose
# deadlines are raised for this run. The deadline override is the documented operator knob
# (coursebook/generation.py PROVIDER_TIMEOUT_ENV); it changes no rule and no cap.
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

run_scope() {  # tag, home, out, args...
  local tag="$1" home="$2" out="$3"; shift 3
  HERMES_HOME="$BASE/$home/home" "$PY" "$SOURCE/audit/adversarial/live-generation-2026-11-08/worker.py" \
    --tag "$tag" --result "$EVIDENCE/$out" "$@" \
    >> "$BASE/$home/run-$tag.log" 2>&1
  echo "$tag exit=$?" >&2
}

# Wait for any earlier single-scope process (if still running) to finish first.
while pgrep -f "worker.py --tag single" >/dev/null 2>&1; do sleep 5; done

run_scope short-r3 short short.json \
  --title "Plan and cook a high-protein week" \
  --goal "Plan and cook a week of high-protein meals without repeating a dish" \
  --recipe committed --scope short --subject-domain general --depth working \
  --units 1 --max-seconds 900

run_scope full-r3 full full.json \
  --title "Practical statistics for business reports" \
  --goal "Read a business report statistically: averages, spread, sampling and correlation" \
  --recipe committed --scope full --subject-domain mathematics --depth deep \
  --units 2 --max-seconds 900
