#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
find scripts -name '*.sh' -type f -print0 | while IFS= read -r -d '' script; do bash -n "$script"; done
if command -v shellcheck >/dev/null; then
    # Site/versions variables come from generated, shell-quoted environment files.
    find scripts -name '*.sh' -type f -print0 | xargs -0 shellcheck -x -e SC1091,SC2034
else
    printf 'Bash syntax passed; ShellCheck unavailable locally (required in CI).\n'
fi
