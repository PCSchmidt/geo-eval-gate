#!/bin/bash
# Download OSCD (Onera Satellite Change Detection, multispectral) from Hugging Face into data/oscd/.
# Data is NOT redistributed in this repo (license listed as unknown): it stays git-ignored.
set -u
cd "$(dirname "$0")/.."
mkdir -p data/oscd
for split in train test; do
  f=data/oscd/$split.parquet
  for attempt in $(seq 1 12); do
    if curl -sSL --fail --retry 3 -C - -o "$f" \
        "https://huggingface.co/datasets/blanchon/OSCD_MSI/resolve/main/data/$split-00000-of-00001.parquet"; then
      echo "$split ok ($(du -h "$f" | cut -f1))"; break
    fi
    echo "$split attempt $attempt failed, retrying"; sleep 10
  done
done
echo FETCH_DONE
