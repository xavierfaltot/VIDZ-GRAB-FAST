from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ProgressCallback = Callable[[str, int], None]
AUDIO_VERSION = "1.0"
DEFAULT_BITRATE = "320k"


class AudioError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioResult:
    mp3_path: Path
    source_path: Path


def utc_conversion_date() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def source_json_for_video(video_path: Path) -> Path:
    return video_path.with_suffix(".source.json")


def audio_source_json_path(mp3_path: Path) -> Path:
    return mp3_path.with_suffix(".audio.source.json")


def unique_mp3_path(output_dir: Path, stem: str) -> Path:
    candidate = output_dir / f"{stem}.mp3"
    index = 2
    while candidate.exists() or audio_source_json_path(candidate).exists():
        candidate = output_dir / f"{stem}_{index:02d}.mp3"
        index += 1
    return candidate


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_audio_source_json(mp3_path: Path, video_path: Path, bitrate: str) -> Path:
    original_source = read_json(source_json_for_video(video_path))
    payload = {
        "audio_version": AUDIO_VERSION,
        "derived_from_video": video_path.name,
        "audio_filename": mp3_path.name,
        "conversion_date": utc_conversion_date(),
        "bitrate": bitrate,
        "source": original_source,
    }
    path = audio_source_json_path(mp3_path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def require_tool(name: str) -> str:
    tool = shutil.which(name)
    if not tool:
        raise AudioError(f"{name} not found on PATH")
    return tool


def verify_mp3(mp3_path: Path) -> None:
    ffprobe = require_tool("ffprobe")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=nw=1:nk=1",
            str(mp3_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or "audio" not in result.stdout.lower():
        details = (result.stderr or result.stdout or "").strip()
        raise AudioError(details or "ffprobe could not verify audio stream")


def convert_mp4_to_mp3(
    video_path: Path,
    output_dir: Path | None = None,
    bitrate: str = DEFAULT_BITRATE,
) -> AudioResult:
    source = video_path.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise AudioError("MP4 not found")
    if source.suffix.lower() != ".mp4":
        raise AudioError("VIDZ TURN SONO accepts .mp4 files only")

    ffmpeg = require_tool("ffmpeg")
    target_dir = (output_dir or source.parent).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    mp3_path = unique_mp3_path(target_dir, source.stem)

    result = subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            str(mp3_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        mp3_path.unlink(missing_ok=True)
        raise AudioError((result.stderr or result.stdout or "ffmpeg failed").strip())

    try:
        verify_mp3(mp3_path)
    except Exception:
        mp3_path.unlink(missing_ok=True)
        raise

    source_path = write_audio_source_json(mp3_path, source, bitrate)
    return AudioResult(mp3_path=mp3_path, source_path=source_path)


def mp4_files(folder: Path) -> list[Path]:
    root = folder.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise AudioError("Input folder not found")
    return sorted(path for path in root.iterdir() if path.is_file() and path.suffix.lower() == ".mp4")


def convert_folder(
    input_dir: Path,
    output_dir: Path | None = None,
    bitrate: str = DEFAULT_BITRATE,
    progress: ProgressCallback | None = None,
) -> tuple[int, int]:
    videos = mp4_files(input_dir)
    if not videos:
        raise AudioError("No MP4 in input folder")

    ok = 0
    errors = 0
    total = len(videos)
    for index, video_path in enumerate(videos, start=1):
        if progress:
            progress(f"MP3 {index}/{total}", int(((index - 1) / total) * 100))
        try:
            convert_mp4_to_mp3(video_path, output_dir, bitrate)
            ok += 1
        except AudioError:
            errors += 1
        if progress:
            progress(f"MP3 {index}/{total}", int((index / total) * 100))
    return ok, errors
