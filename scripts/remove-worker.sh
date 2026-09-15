#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# == 2 ]] || { printf "Usage: %s NODE_NAME SSH_TARGET\n" "$0" >&2; exit 2; }
exec bash "$(dirname "$0")/remove-node.sh" "$1" worker "$2"
