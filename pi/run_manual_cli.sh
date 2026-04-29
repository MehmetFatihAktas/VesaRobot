#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv-manual"

if [[ ! -d "${VENV_DIR}" ]]; then
  "${SCRIPT_DIR}/setup_manual_env.sh"
fi

source "${VENV_DIR}/bin/activate"

PORT="${1:-}"
if [[ -z "${PORT}" ]]; then
  PORT="$(ls /dev/ttyACM* 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "${PORT}" ]]; then
  echo "Teensy port bulunamadi. /dev/ttyACM0 bekleniyordu." >&2
  exit 1
fi

echo "Using Teensy port: ${PORT}"
exec python "${SCRIPT_DIR}/manual_cli.py" --port "${PORT}"
