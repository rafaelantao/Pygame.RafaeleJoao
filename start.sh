#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv_run"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cleanup() {
    if [[ -n "${VENV_ACTIVE:-}" ]]; then
        deactivate >/dev/null 2>&1 || true
    fi
    if [[ -d "$VENV_DIR" ]]; then
        rm -rf "$VENV_DIR"
        echo "Removed temporary virtual environment at $VENV_DIR"
    fi
}
trap cleanup EXIT

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Error: PYTHON_BIN='$PYTHON_BIN' not found on PATH." >&2
    exit 1
fi

echo "Creating temporary virtual environment..."
"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
VENV_ACTIVE=1

echo "Upgrading pip and installing requirements..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$REPO_DIR/requirements.txt"

echo "Launching game (Ctrl+C to quit)..."
python "$REPO_DIR/game.py"
