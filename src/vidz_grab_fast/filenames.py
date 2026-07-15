from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def ascii_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return re.sub(r"_+", "_", slug)


def clean_filename_stem(*parts: str) -> str:
    cleaned = [ascii_slug(part) for part in parts if ascii_slug(part)]
    stem = "_".join(cleaned)
    return stem[:160].strip("_") or "video"


def unique_mp4_path(destination: Path, stem: str) -> Path:
    candidate = destination / f"{stem}.mp4"
    index = 2
    while candidate.exists() or candidate.with_suffix(".source.json").exists():
        candidate = destination / f"{stem}_{index:02d}.mp4"
        index += 1
    return candidate
