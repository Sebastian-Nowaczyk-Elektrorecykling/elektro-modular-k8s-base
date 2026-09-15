#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
for tool in kustomize helm; do command -v "$tool" >/dev/null || { printf 'Missing %s\n' "$tool" >&2; exit 1; }; done
python3 scripts/render.py
