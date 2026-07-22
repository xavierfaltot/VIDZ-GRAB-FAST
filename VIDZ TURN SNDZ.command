#!/bin/zsh
cd "${0:A:h}"
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
if ! ".venv/bin/python" -c "import PySide6.QtWidgets" >/dev/null 2>&1; then
  ".venv/bin/python" -m pip install -r requirements.txt
fi
exec ".venv/bin/python" run_audio.py
