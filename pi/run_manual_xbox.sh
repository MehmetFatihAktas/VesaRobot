#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv-manual"
PROFILE_PATH="${SCRIPT_DIR}/manual_profile.json"

if [[ ! -d "${VENV_DIR}" ]]; then
  "${SCRIPT_DIR}/setup_manual_env.sh"
fi

if [[ ! -f "${PROFILE_PATH}" ]]; then
  cp "${SCRIPT_DIR}/manual_profile.example.json" "${PROFILE_PATH}"
fi

source "${VENV_DIR}/bin/activate"

PORT="${1:-}"
if [[ -z "${PORT}" ]]; then
  PORT="$(python - <<'PY'
import glob
ports = sorted(glob.glob('/dev/ttyACM*'))
print(ports[0] if ports else '')
PY
)"
fi

if [[ -z "${PORT}" ]]; then
  echo "Teensy port bulunamadi. /dev/ttyACM0 bekleniyordu." >&2
  exit 1
fi

echo "Using Teensy port: ${PORT}"
echo "Using profile: ${PROFILE_PATH}"
exec python "${SCRIPT_DIR}/manual_xbox_bridge.py" --port "${PORT}" --profile "${PROFILE_PATH}"
