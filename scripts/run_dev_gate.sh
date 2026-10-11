#!/bin/bash
# Development-stage gate runs (training pairs only). Sequential, resumable, and it STOPS on the first failure.
set -o pipefail
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
for model in gemma4:12b qwen2.5vl:7b; do
  for variant in design rgb; do
    echo "=== dev $model $variant"
    if ! .venv/Scripts/python scripts/real_gate.py dev --model "$model" --variant "$variant" 2>&1 | grep -v -i warn; then
      echo "DEV_FAILED at $model $variant"; exit 1
    fi
  done
done
echo DEV_DONE
