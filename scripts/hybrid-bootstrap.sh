#!/usr/bin/env bash
set -Eeuo pipefail
exec bash "$(dirname "$0")/install-node.sh" hybrid bootstrap "$@"
