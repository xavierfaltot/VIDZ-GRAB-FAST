#!/bin/zsh
set -e

APP_DIR="${0:A:h}"
cd "$APP_DIR"

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

".venv/bin/python" -m pip install -r requirements.txt
exec ".venv/bin/python" run.py
