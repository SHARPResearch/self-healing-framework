#!/usr/bin/env bash
# Downloads RCAEval RE1 metrics for Online Boutique (RE1-OB) and Sock Shop (RE1-SS) into
# datasets/rcaeval/raw/. Source: Pham et al., "RCAEval: A Benchmark for Root Cause Analysis of
# Microservice Systems with Telemetry Data" (WWW 2025 companion, arXiv 2412.17015), Zenodo record
# 14590730, CC BY 4.0. Used by ml-pipeline/evaluate_rcaeval.py as real microservice fault data.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="$SCRIPT_DIR/raw"
mkdir -p "$RAW_DIR"

for part in RE1-OB RE1-SS; do
  if [ -d "$RAW_DIR/$part" ]; then
    echo "$part already present, skipping"
    continue
  fi
  curl -L --fail -o "$RAW_DIR/$part.zip" "https://zenodo.org/records/14590730/files/$part.zip?download=1"
  unzip -q "$RAW_DIR/$part.zip" -d "$RAW_DIR"
  rm "$RAW_DIR/$part.zip"
done
echo "RCAEval RE1 downloaded to $RAW_DIR"
