from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class ProbeError(RuntimeError):
    pass


def verify_media(path: Path) -> None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ProbeError("ffprobe not found on PATH")

    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or "video" not in result.stdout.lower():
        details = (result.stderr or result.stdout or "").strip()
        raise ProbeError(details or "ffprobe could not verify video stream")
