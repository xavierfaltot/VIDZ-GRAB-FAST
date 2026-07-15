from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import GRAB_VERSION


SOURCE_KEYS = (
    "id",
    "artist",
    "account",
    "platform",
    "source_url",
    "download_date",
    "grab_version",
    "original_filename",
    "clean_filename",
)


@dataclass(frozen=True)
class SourceRecord:
    id: str = ""
    artist: str = ""
    account: str = ""
    platform: str = ""
    source_url: str = ""
    download_date: str = ""
    grab_version: str = GRAB_VERSION
    original_filename: str = ""
    clean_filename: str = ""

    def to_dict(self) -> dict[str, str]:
        values = {
            "id": self.id,
            "artist": self.artist,
            "account": self.account,
            "platform": self.platform,
            "source_url": self.source_url,
            "download_date": self.download_date,
            "grab_version": self.grab_version,
            "original_filename": self.original_filename,
            "clean_filename": self.clean_filename,
        }
        return {key: values[key] or "" for key in SOURCE_KEYS}


def utc_download_date() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def source_json_path(video_path: Path) -> Path:
    return video_path.with_suffix(".source.json")


def write_source_json(video_path: Path, record: SourceRecord) -> Path:
    path = source_json_path(video_path)
    path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
