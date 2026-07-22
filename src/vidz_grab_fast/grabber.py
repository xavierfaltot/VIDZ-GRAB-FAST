from __future__ import annotations

import shutil
import tempfile
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .filenames import clean_filename_stem, unique_mp4_path
from .platforms import detect_platform
from .probe import verify_media
from .provenance import SourceRecord, utc_download_date, write_source_json

ProgressCallback = Callable[[str, int], None]
MAX_BATCH_ITEMS = 600


class GrabError(RuntimeError):
    pass


@dataclass(frozen=True)
class GrabRequest:
    output_dir: Path
    artist_account: str = ""
    local_file: Path | None = None
    source_url: str = ""


@dataclass(frozen=True)
class GrabResult:
    video_path: Path
    source_path: Path


def _emit(progress: ProgressCallback | None, message: str, percent: int) -> None:
    if progress:
        progress(message, max(0, min(100, percent)))


def _safe_info_value(info: dict, *keys: str) -> str:
    for key in keys:
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _entry_source_url(entry: dict, parent_url: str) -> str:
    for key in ("webpage_url", "url"):
        value = entry.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value

    video_id = _safe_info_value(entry, "id", "url")
    if video_id and detect_platform(parent_url) == "youtube":
        return f"https://www.youtube.com/watch?v={video_id}"
    return ""


def _source_urls_from_info(info: dict, parent_url: str, max_items: int) -> list[str]:
    entries = info.get("entries")
    if entries is None or isinstance(entries, (str, bytes)):
        return [parent_url]

    urls: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source_url = _entry_source_url(entry, parent_url)
        if not source_url or source_url in seen:
            continue
        seen.add(source_url)
        urls.append(source_url)
        if len(urls) >= max_items:
            break
    return urls or [parent_url]


def existing_source_urls(output_dir: Path) -> set[str]:
    root = output_dir.expanduser()
    if not root.exists() or not root.is_dir():
        return set()

    urls: set[str] = set()
    for source_json in root.glob("*.source.json"):
        try:
            data = json.loads(source_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        source_url = data.get("source_url")
        if isinstance(source_url, str) and source_url.strip():
            urls.add(source_url.strip())
    return urls


def expand_source_url(source_url: str, max_items: int = MAX_BATCH_ITEMS) -> list[str]:
    url = source_url.strip()
    if not url:
        return []

    try:
        import yt_dlp
    except ImportError as exc:
        raise GrabError("yt-dlp is not installed") from exc

    options = {
        "cachedir": False,
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
        "no_warnings": True,
        "noplaylist": False,
        "playlistend": max_items,
        "quiet": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001
        raise GrabError(str(exc)) from exc
    if not isinstance(info, dict):
        return [url]
    return _source_urls_from_info(info, url, max_items)


def _finalize(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise GrabError(f"Output already exists: {target.name}")
    shutil.move(str(source), str(target))


def grab_local_file(request: GrabRequest, progress: ProgressCallback | None = None) -> GrabResult:
    if not request.local_file:
        raise GrabError("No local file provided")

    source = request.local_file.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise GrabError("Local file not found")
    if source.suffix.lower() != ".mp4":
        raise GrabError("Local import must be .mp4 because VIDZ GRAB FAST never transcodes")

    _emit(progress, "COPY", 20)
    platform = ""
    stem = clean_filename_stem(request.artist_account, platform, source.stem)
    target = unique_mp4_path(request.output_dir, stem)
    request.output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

    _emit(progress, "VERIFY", 75)
    try:
        verify_media(target)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    _emit(progress, "SOURCE", 90)
    record = SourceRecord(
        artist=request.artist_account,
        account=request.artist_account,
        platform=platform,
        source_url="",
        download_date=utc_download_date(),
        original_filename=source.name,
        clean_filename=target.name,
    )
    source_path = write_source_json(target, record)
    _emit(progress, "DONE", 100)
    return GrabResult(video_path=target, source_path=source_path)


def _find_downloaded_mp4(tmpdir: Path) -> Path:
    mp4s = sorted(tmpdir.glob("*.mp4"))
    if not mp4s:
        raise GrabError("yt-dlp did not produce an mp4 file")
    return max(mp4s, key=lambda path: path.stat().st_mtime)


def grab_url(request: GrabRequest, progress: ProgressCallback | None = None) -> GrabResult:
    if not request.source_url.strip():
        raise GrabError("No URL provided")

    try:
        import yt_dlp
    except ImportError as exc:
        raise GrabError("yt-dlp is not installed") from exc

    url = request.source_url.strip()
    platform = detect_platform(url)
    latest_percent = {"value": 5}

    def hook(event: dict) -> None:
        status = event.get("status")
        if status == "downloading":
            total = event.get("total_bytes") or event.get("total_bytes_estimate") or 0
            downloaded = event.get("downloaded_bytes") or 0
            if total:
                latest_percent["value"] = 10 + int((downloaded / total) * 60)
            _emit(progress, "GRAB", latest_percent["value"])
        elif status == "finished":
            _emit(progress, "VERIFY", 78)

    request.output_dir.mkdir(parents=True, exist_ok=True)
    _emit(progress, "GRAB", 5)

    with tempfile.TemporaryDirectory(prefix="vidz_grab_fast_") as temp_name:
        tmpdir = Path(temp_name)
        outtmpl = str(tmpdir / "download.%(ext)s")
        options = {
            "cachedir": False,
            "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "no_warnings": True,
            "outtmpl": outtmpl,
            "progress_hooks": [hook],
            "quiet": True,
            "restrictfilenames": False,
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:  # noqa: BLE001
            raise GrabError(str(exc)) from exc

        downloaded = _find_downloaded_mp4(tmpdir)
        verify_media(downloaded)

        title = _safe_info_value(info, "title")
        uploader = _safe_info_value(info, "uploader", "channel")
        account = request.artist_account or _safe_info_value(info, "uploader_id", "channel_id", "channel")
        artist = request.artist_account or _safe_info_value(info, "artist", "creator", "uploader")
        filename_seed = title or Path(url.split("?", 1)[0]).stem or "video"
        stem = clean_filename_stem(artist or account, platform, filename_seed)
        target = unique_mp4_path(request.output_dir, stem)

        _emit(progress, "WRITE", 88)
        _finalize(downloaded, target)

    record = SourceRecord(
        id=_safe_info_value(info, "id"),
        artist=artist,
        account=account or uploader,
        platform=platform,
        source_url=url,
        download_date=utc_download_date(),
        original_filename="",
        clean_filename=target.name,
    )
    source_path = write_source_json(target, record)
    _emit(progress, "DONE", 100)
    return GrabResult(video_path=target, source_path=source_path)


def grab(request: GrabRequest, progress: ProgressCallback | None = None) -> GrabResult:
    if request.local_file:
        return grab_local_file(request, progress)
    return grab_url(request, progress)
