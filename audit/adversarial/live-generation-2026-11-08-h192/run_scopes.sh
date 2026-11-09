#!/usr/bin/env bash
# H-192 driver: three scopes, one isolated home each, the real product path.
#
# The home is fresh: no demo pack, no recorded transcripts, its own SQLite store. It is seeded
# with a config.yaml only (the host's author model plus the Coursebook validator route), which is
# how ``register(ctx)`` reads its settings; nothing else is copied. Deadlines use the documented
# operator knobs only; no rule, bound, cap or validator behaviour changes here.
#
# Scopes are driven serially: the live provider degrades under concurrent structured calls
# (measured by H-187), and a serial run is what makes a per-scope latency number meaningful.
set -uo pipefail

SOURCE="$(cd "$(dirname "$0")/../../.." && pwd)"
HERE="$SOURCE/audit/adversarial/live-generation-2026-11-08-h192"
EVIDENCE="$HERE/evidence"
BASE=/home/deseretsaint/.hermes/h192-live-acceptance
PY=/home/deseretsaint/.hermes/installs/4d8bf4040d63cdfa/environments/12913d7d436b4c0fb0877aaefcb88e69/venv/bin/python

mkdir -p "$EVIDENCE"

seed_home() {  # dir
  mkdir -p "$1"
  cat > "$1/config.yaml" <<'CONFIG'
model:
  default: deepseek/deepseek-v4.1-flash-1017
  provider: nous
  base_url: https://inference-api.nousresearch.com/v1
plugins:
  enabled:
    - coursebook
  entries:
    coursebook:
      enabled: true
      llm:
        allow_model_override: true
        allow_provider_override: true
        allowed_models:
        - "*"
        allowed_providers:
        - "*"
      settings:
        validator_provider: nous
        validator_model: z-ai/glm-5.3-flash
CONFIG
}

export HERMES_DISABLE_LAZY_INSTALLS=1
export HERMES_AGENT_ROOT=/home/deseretsaint/.hermes/hermes-agent
export COURSEBOOK_SOURCE="$SOURCE"
export H187_VALIDATOR_PROVIDER=nous
export H187_VALIDATOR_MODEL=z-ai/glm-5.3-flash
export COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS=600
export COURSEBOOK_PLAN_VALIDATE_TIMEOUT_SECONDS=600
export COURSEBOOK_UNIT_SECTIONS_GENERATE_TIMEOUT_SECONDS=600
export COURSEBOOK_UNIT_SECTIONS_VALIDATE_TIMEOUT_SECONDS=600
export COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS=600
export COURSEBOOK_LESSON_VALIDATE_TIMEOUT_SECONDS=600

run_scope() {  # tag, home-name, out, args...
  local tag="$1" home="$2" out="$3"; shift 3
  local dir="$BASE/$home"
  mkdir -p "$dir"
  seed_home "$dir/home"
  echo "=== $tag start $(date -u +%FT%TZ) ==="
  HERMES_HOME="$dir/home" "$PY" "$HERE/worker.py" \
    --tag "$tag" --result "$EVIDENCE/$out" "$@" > "$dir/run-$tag.log" 2>&1
  echo "=== $tag exit=$? at $(date -u +%FT%TZ) ==="
}

run_scope single single single.json \
  --title "Brew a pour-over coffee consistently" \
  --goal "Brew a pour-over coffee whose strength stays consistent from cup to cup" \
  --recipe one_off --scope single --subject-domain technical_procedure --depth working \
  --units 1 --max-seconds 1100

run_scope short short short.json \
  --title "Plan and cook a high-protein week" \
  --goal "Plan and cook a week of high-protein meals without repeating a dish" \
  --recipe committed --scope short --subject-domain general --depth working \
  --units 1 --max-seconds 1100

run_scope full full full.json \
  --title "Practical statistics for business reports" \
  --goal "Read a business report statistically: averages, spread, sampling and correlation" \
  --recipe committed --scope full --subject-domain mathematics --depth deep \
  --units 2 --max-seconds 1100
