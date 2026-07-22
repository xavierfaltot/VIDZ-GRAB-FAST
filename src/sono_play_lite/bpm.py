from __future__ import annotations

import shutil
import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

SONO_VERSION = "1.0"
SAMPLE_RATE = 11025
WINDOW_SAMPLES = 1024
HOP_SAMPLES = 512
MIN_BPM = 60
MAX_BPM = 190
MAX_ANALYSIS_SECONDS = 120
INTRO_ANALYSIS_SECONDS = 18
MIX_SECONDS = 8.0
MIN_MIX_DURATION_SECONDS = 24.0
SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".wav",
}


class SonoError(RuntimeError):
    pass


@dataclass(frozen=True)
class SonoTrack:
    path: Path
    bpm: float | None
    duration_seconds: float | None = None
    mixable_intro: bool = False


Estimator = Callable[[Path], float | None]
ProgressCallback = Callable[[str, int], None]


def require_tool(name: str) -> str:
    tool = shutil.which(name)
    if not tool:
        raise SonoError(f"{name} not found on PATH")
    return tool


def find_audio_files(folder: Path) -> list[Path]:
    root = folder.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SonoError("Sound folder not found")
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part.startswith(".") for part in path.relative_to(root).parts)
        and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    ]
    return sorted(files, key=lambda path: str(path).lower())


def probe_duration_seconds(path: Path) -> float | None:
    ffprobe = require_tool("ffprobe")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None
    return duration if duration > 0 else None


def decode_audio_pcm(
    path: Path,
    max_seconds: int = MAX_ANALYSIS_SECONDS,
    start_seconds: float = 0.0,
) -> bytes:
    ffmpeg = require_tool("ffmpeg")
    command = [ffmpeg, "-nostdin", "-v", "error"]
    if start_seconds > 0:
        command.extend(["-ss", f"{start_seconds:.3f}"])
    command.extend(
        [
            "-i",
            str(path),
            "-t",
            str(max_seconds),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "s16le",
            "pipe:1",
        ]
    )
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode != 0 or not result.stdout:
        details = result.stderr.decode("utf-8", errors="ignore").strip()
        raise SonoError(details or f"Could not decode {path.name}")
    return result.stdout


def energy_envelope(pcm: bytes) -> list[float]:
    window_bytes = WINDOW_SAMPLES * 2
    hop_bytes = HOP_SAMPLES * 2
    if len(pcm) < window_bytes * 8:
        return []

    values: list[float] = []
    for offset in range(0, len(pcm) - window_bytes, hop_bytes):
        values.append(float(audioop.rms(pcm[offset : offset + window_bytes], 2)))

    peak = max(values, default=0.0)
    if peak <= 0:
        return []
    return [value / peak for value in values]


def onset_envelope(energies: list[float]) -> list[float]:
    if len(energies) < 4:
        return []
    onsets = [0.0]
    previous = energies[0]
    for value in energies[1:]:
        change = value - previous
        onsets.append(change if change > 0 else 0.0)
        previous = value

    peak = max(onsets, default=0.0)
    if peak <= 0:
        return []
    return [value / peak for value in onsets]


def bpm_score(onsets: list[float], bpm: int) -> float:
    frames_per_second = SAMPLE_RATE / HOP_SAMPLES
    lag = round((60.0 / bpm) * frames_per_second)
    if lag <= 1 or len(onsets) <= lag * 3:
        return 0.0
    return sum(onsets[index] * onsets[index - lag] for index in range(lag, len(onsets)))


def estimate_bpm(path: Path, min_bpm: int = MIN_BPM, max_bpm: int = MAX_BPM) -> float | None:
    pcm = decode_audio_pcm(path)
    onsets = onset_envelope(energy_envelope(pcm))
    if not onsets or sum(onsets) < 0.2:
        return None

    scores = [(bpm_score(onsets, bpm), bpm) for bpm in range(min_bpm, max_bpm + 1)]
    best_score, best_bpm = max(scores, key=lambda item: item[0])
    if best_score <= 0:
        return None
    return float(best_bpm)


def is_mixable_intro_from_energies(energies: list[float]) -> bool:
    if len(energies) < 12:
        return False
    active = [value for value in energies if value > 0.08]
    active_ratio = len(active) / len(energies)
    mean_energy = sum(energies) / len(energies)
    peak_energy = max(energies, default=0.0)
    return active_ratio >= 0.35 and mean_energy >= 0.08 and peak_energy >= 0.22


def has_mixable_intro(path: Path) -> bool:
    try:
        pcm = decode_audio_pcm(path, max_seconds=INTRO_ANALYSIS_SECONDS)
    except SonoError:
        return False
    return is_mixable_intro_from_energies(energy_envelope(pcm))


def sort_tracks_by_bpm(tracks: list[SonoTrack]) -> list[SonoTrack]:
    return sorted(
        tracks,
        key=lambda track: (
            track.bpm is None,
            track.bpm if track.bpm is not None else 9999.0,
            track.path.name.lower(),
        ),
    )


def analyze_folder(
    folder: Path,
    estimator: Estimator = estimate_bpm,
    progress: ProgressCallback | None = None,
) -> tuple[list[SonoTrack], list[str]]:
    files = find_audio_files(folder)
    if not files:
        raise SonoError("No supported sound file")

    tracks: list[SonoTrack] = []
    errors: list[str] = []
    total = len(files)
    for index, path in enumerate(files, start=1):
        if progress:
            progress(f"BPM {index}/{total}", int(((index - 1) / total) * 100))
        try:
            bpm = estimator(path)
            duration = probe_duration_seconds(path)
            mixable_intro = has_mixable_intro(path)
        except SonoError as exc:
            bpm = None
            duration = None
            mixable_intro = False
            errors.append(f"{path.name}: {exc}")
        tracks.append(
            SonoTrack(
                path=path,
                bpm=bpm,
                duration_seconds=duration,
                mixable_intro=mixable_intro,
            )
        )
        if progress:
            progress(f"BPM {index}/{total}", int((index / total) * 100))

    return sort_tracks_by_bpm(tracks), errors
