#!/usr/bin/env python3
"""Launch VIDZ AUDIO FAST from the source checkout."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vidz_grab_fast.audio_ui import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
