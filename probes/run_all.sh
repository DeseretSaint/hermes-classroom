#!/usr/bin/env bash
# Run every Coursebook runtime probe and collect verdicts.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$HERE/raw"
LOG="$HERE/raw/RUN.log"
: > "$LOG"

for n in 1 2 3 4 5 6 7; do
  script=$(ls "$HERE"/p${n}_*.sh)
  echo "=== $(basename "$script") ===" | tee -a "$LOG"
  bash "$script" 2>&1 | tee -a "$LOG"
  echo | tee -a "$LOG"
done

echo "=== verdict summary ===" | tee -a "$LOG"
grep '^RESULT ' "$LOG" | tee "$HERE/raw/VERDICTS.txt"
