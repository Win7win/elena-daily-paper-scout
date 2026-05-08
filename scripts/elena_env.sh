#!/usr/bin/env bash

# Helper used by run_elena_server.sh and the test scripts to set a few
# environment defaults before invoking python. Edit ELENA_PYTHON if your
# python interpreter is not on $PATH (for example when using a conda env).

set -euo pipefail

ELENA_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ELENA_PYTHON="${ELENA_PYTHON:-python3}"

# Optional HTTP proxy. Leave ELENA_HTTP_PROXY empty to skip.
# Useful inside corporate networks or when arXiv / HuggingFace are blocked.
ELENA_HTTP_PROXY="${ELENA_HTTP_PROXY:-}"

# Where Elena writes runtime state. Override to put state on a different disk.
ELENA_DATA_DIR="${ELENA_DATA_DIR:-$ELENA_PROJECT_ROOT/data}"

elena_prepare_runtime() {
  if ! command -v "$ELENA_PYTHON" >/dev/null 2>&1; then
    echo "Elena python not found on PATH: $ELENA_PYTHON" >&2
    echo "Set ELENA_PYTHON to the absolute path of your interpreter." >&2
    exit 1
  fi

  if [ -n "$ELENA_HTTP_PROXY" ]; then
    export http_proxy="$ELENA_HTTP_PROXY"
    export https_proxy="$ELENA_HTTP_PROXY"
    export HTTP_PROXY="$ELENA_HTTP_PROXY"
    export HTTPS_PROXY="$ELENA_HTTP_PROXY"
    export no_proxy="127.0.0.1,localhost"
    export NO_PROXY="127.0.0.1,localhost"
  fi

  export ELENA_DATA_DIR

  mkdir -p "$ELENA_DATA_DIR" "$ELENA_DATA_DIR/cache" "$ELENA_DATA_DIR/tmp"

  cd "$ELENA_PROJECT_ROOT"
}
