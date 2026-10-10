#!/bin/bash
# Retry-pull a vision model (this machine has intermittent DNS failures).
m=${1:-qwen2.5vl:7b}
for attempt in $(seq 1 20); do
  if ollama list | awk '{print $1}' | grep -qx "$m"; then echo "$m present"; break; fi
  ollama pull "$m" 2>&1 | tr '\r' '\n' | sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g' | grep -E "success|Error" | tail -1
  sleep 15
done
echo PULL_DONE
