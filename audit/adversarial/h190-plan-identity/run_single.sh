#!/usr/bin/env bash
# H-190 live driver: one isolated home, the real product path, real provider seams.
#
# The home is fresh: no demo pack, no recorded transcripts, its own SQLite store. It is seeded
# with a config.yaml only (the host's author model plus the Coursebook validator route), which is
# how ``register(ctx)`` reads its settings; nothing else is copied. Deadlines use the documented
# operator knobs only; no rule, bound, cap or validator behaviour changes here.
set -uo pipefail

SOURCE="$(cd "$(dirname "$0")/../../.." && pwd)"
HERE="$SOURCE/audit/adversarial/h190-plan-identity"
EVIDENCE="$HERE/evidence"
BASE=/home/deseretsaint/.hermes/h190-plan-identity
HOME_DIR="$BASE/single-r3/home"
PY=/home/deseretsaint/.hermes/installs/4d8bf4040d63cdfa/environments/12913d7d436b4c0fb0877aaefcb88e69/venv/bin/python

mkdir -p "$EVIDENCE" "$HOME_DIR"
cat > "$HOME_DIR/config.yaml" <<'CONFIG'
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

export HERMES_DISABLE_LAZY_INSTALLS=1
export HERMES_AGENT_ROOT=/home/deseretsaint/.hermes/hermes-agent
export COURSEBOOK_SOURCE="$SOURCE"
export H190_VALIDATOR_PROVIDER=nous
export H190_VALIDATOR_MODEL=z-ai/glm-5.3-flash
export COURSEBOOK_PLAN_GENERATE_TIMEOUT_SECONDS=420
export COURSEBOOK_PLAN_VALIDATE_TIMEOUT_SECONDS=300

HERMES_HOME="$HOME_DIR" "$PY" "$HERE/worker.py" \
  --tag single-h190 \
  --title "Sharpen a kitchen knife on a whetstone" \
  --goal "Sharpen a kitchen knife on a whetstone without rolling the edge" \
  --recipe one_off --scope single --subject-domain technical_procedure --depth working \
  --max-seconds 900 \
  --result "$EVIDENCE/single.json" > "$BASE/single-r3/run-single.log" 2>&1
echo "single exit=$?" >&2
