#!/usr/bin/env bash
# Downloads the Server Machine Dataset (SMD) into datasets/smd/raw/.
# Source: docs/Doc1_Technical_Architecture.md §9, docs/Doc3_Execution_Guide.md Phase 2.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="$SCRIPT_DIR/raw"
TMP_DIR="$(mktemp -d)"

git clone --depth 1 https://github.com/NetManAIOps/OmniAnomaly.git "$TMP_DIR/omnianomaly"

mkdir -p "$RAW_DIR"
cp -r "$TMP_DIR/omnianomaly/ServerMachineDataset/train" "$RAW_DIR/train"
cp -r "$TMP_DIR/omnianomaly/ServerMachineDataset/test" "$RAW_DIR/test"
cp -r "$TMP_DIR/omnianomaly/ServerMachineDataset/test_label" "$RAW_DIR/test_label"

rm -rf "$TMP_DIR"
echo "SMD dataset downloaded to $RAW_DIR"
