#!/usr/bin/env bash
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Please source this script so activation persists in your shell:"
  echo "  source ./setup_env.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
LOCAL_VENV="$SCRIPT_DIR/.venv"
PARENT_VENV="$(cd "$SCRIPT_DIR/.." && pwd)/.venv"

if [[ ! -f "$REQ_FILE" ]]; then
  echo "requirements.txt not found at: $REQ_FILE"
  exit 1
fi

if [[ -d "$LOCAL_VENV" ]]; then
  VENV_DIR="$LOCAL_VENV"
elif [[ -d "$PARENT_VENV" ]]; then
  VENV_DIR="$PARENT_VENV"
else
  VENV_DIR="$LOCAL_VENV"
  echo "No virtual environment found. Creating one at: $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "$REQ_FILE"

echo "Environment activated: $VENV_DIR"
echo "Requirements installed from: $REQ_FILE"
echo "Virtual environment is active in this shell."
