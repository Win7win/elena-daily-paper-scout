#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/scripts/elena_env.sh"

elena_prepare_runtime

if [ -n "${http_proxy:-}" ]; then
  echo "Elena server starting with proxy ${http_proxy}"
else
  echo "Elena server starting (no proxy)"
fi

exec "$ELENA_PYTHON" "$ELENA_PROJECT_ROOT/server.py" "$@"
