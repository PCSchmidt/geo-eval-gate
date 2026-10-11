#!/bin/bash
# Test-split gate runs: ONE run per (model, screen). Needs the frozen development entries; stops on failure.
set -o pipefail
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
for variant in design rgb; do
  for model in gemma4:12b qwen2.5vl:7b; do
    echo "=== test $model $variant"
    if ! .venv/Scripts/python scripts/real_gate.py test --model "$model" --variant "$variant" 2>&1 | grep -v -i warn; then
      echo "TEST_FAILED at $model $variant"; exit 1
    fi
  done
done
echo TEST_DONE
