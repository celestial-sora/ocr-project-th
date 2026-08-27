#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "ไม่พบ virtual environment: .venv"
  echo "กรุณารัน: python3 -m venv .venv"
  exit 1
fi

echo "Starting Flask web UI at http://127.0.0.1:5000"
exec .venv/bin/python app.py
