#!/bin/sh
# Local development only; all Home Assistant state stays outside tracked source.
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_ROOT="$PROJECT_ROOT/private/local-hass"
VENV_ROOT="${DISKPILOT_VENV:-$PROJECT_ROOT/.venv}"
PYTHON_BIN="${DISKPILOT_PYTHON:-python3.14}"

mkdir -p "$TEST_ROOT/custom_components" "$TEST_ROOT/cache"
export UV_CACHE_DIR="$TEST_ROOT/cache/uv"
export PIP_CACHE_DIR="$TEST_ROOT/cache/pip"

if [ ! -x "$VENV_ROOT/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_ROOT"
fi
"$VENV_ROOT/bin/python" -m pip install -q -r "$PROJECT_ROOT/dev/requirements-local.txt"

if [ ! -f "$TEST_ROOT/configuration.yaml" ]; then
  cp "$PROJECT_ROOT/dev/configuration.yaml" "$TEST_ROOT/configuration.yaml"
fi
"$VENV_ROOT/bin/python" "$PROJECT_ROOT/dev/prepare_local.py" "$TEST_ROOT"
COMPONENT="$TEST_ROOT/custom_components/dishwasher_optimizer"
if [ ! -e "$COMPONENT" ]; then
  ln -s "$PROJECT_ROOT/custom_components/dishwasher_optimizer" "$COMPONENT"
fi

printf '%s\n' 'Diskpilot TEST: http://127.0.0.1:8124 (stoppa med Ctrl+C)'
while :; do
  if "$VENV_ROOT/bin/hass" --config "$TEST_ROOT" --log-file "$TEST_ROOT/home-assistant.log"; then
    exit 0
  else
    result=$?
    if [ "$result" -ne 100 ]; then
      exit "$result"
    fi
    printf '%s\n' 'Startar om den lokala testmiljön...'
  fi
done
