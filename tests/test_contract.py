from __future__ import annotations

import json
import sys

from PySide6.QtWidgets import QApplication

from vidz_grab_fast.filenames import clean_filename_stem
from vidz_grab_fast.grabber import _source_urls_from_info
from vidz_grab_fast.platforms import detect_platform
from vidz_grab_fast.provenance import SourceRecord, write_source_json
from vidz_grab_fast.audio import audio_source_json_path, write_audio_source_json
from vidz_grab_fast.ui import MainWindow


def test_clean_filename_is_ascii_lowercase_snake_case() -> None:
    assert clean_filename_stem("Irena Bräus", "Instagram", "Red Room!") == "irena_braus_instagram_red_room"


def test_platform_detection_supported_sources() -> None:
    assert detect_platform("https://www.instagram.com/reel/abc") == "instagram"
    assert detect_platform("https://youtu.be/abc") == "youtube"
    assert detect_platform("https://www.tiktok.com/@a/video/1") == "tiktok"
    assert detect_platform("https://vimeo.com/123") == "vimeo"
    assert detect_platform("https://x.com/account/status/1") == "x"
    assert detect_platform("https://fb.watch/abc") == "facebook"
    assert detect_platform("https://example.com/video.mp4") == "direct_mp4"


def test_source_json_contract(tmp_path) -> None:
    video = tmp_path / "fredagain_youtube_boiler_room.mp4"
    video.write_bytes(b"")
    source_path = write_source_json(
        video,
        SourceRecord(
            id="abc",
            artist="Fred Again",
            account="@fredagain",
            platform="youtube",
            source_url="https://youtu.be/abc",
            download_date="2026-07-15T15:21:16Z",
            original_filename="",
            clean_filename=video.name,
        ),
    )
    data = json.loads(source_path.read_text(encoding="utf-8"))
    assert list(data) == [
        "id",
        "artist",
        "account",
        "platform",
        "source_url",
        "download_date",
        "grab_version",
        "original_filename",
        "clean_filename",
    ]
    assert source_path.name == "fredagain_youtube_boiler_room.source.json"
    assert data["grab_version"] == "1.0"


def test_ui_collects_multiline_urls(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.url_input.setPlainText(
        "https://example.com/a.mp4\n\nhttps://example.com/b.mp4\nhttps://example.com/a.mp4"
    )
    assert window._urls() == ["https://example.com/a.mp4", "https://example.com/b.mp4"]
    window.close()
    assert app is not None


def test_playlist_info_expands_to_video_urls() -> None:
    info = {
        "entries": [
            {"id": "aaa111"},
            {"url": "https://www.youtube.com/watch?v=bbb222"},
            {"id": "aaa111"},
        ]
    }
    assert _source_urls_from_info(info, "https://www.youtube.com/playlist?list=PL123", 150) == [
        "https://www.youtube.com/watch?v=aaa111",
        "https://www.youtube.com/watch?v=bbb222",
    ]


def test_playlist_expansion_respects_limit() -> None:
    info = {"entries": [{"id": "one"}, {"id": "two"}, {"id": "three"}]}
    assert _source_urls_from_info(info, "https://www.youtube.com/playlist?list=PL123", 2) == [
        "https://www.youtube.com/watch?v=one",
        "https://www.youtube.com/watch?v=two",
    ]


def test_audio_source_json_preserves_grab_source(tmp_path) -> None:
    video = tmp_path / "clip.mp4"
    mp3 = tmp_path / "clip.mp3"
    video.write_bytes(b"")
    mp3.write_bytes(b"")
    source = {
        "id": "abc123",
        "artist": "Artist",
        "account": "artist",
        "platform": "youtube",
        "source_url": "https://youtu.be/abc123",
        "download_date": "2026-07-15T15:21:16Z",
        "grab_version": "1.0",
        "original_filename": "",
        "clean_filename": "clip.mp4",
    }
    video.with_suffix(".source.json").write_text(json.dumps(source), encoding="utf-8")

    audio_source = write_audio_source_json(mp3, video, "320k")
    data = json.loads(audio_source.read_text(encoding="utf-8"))

    assert audio_source == audio_source_json_path(mp3)
    assert audio_source.name == "clip.audio.source.json"
    assert data["derived_from_video"] == "clip.mp4"
    assert data["audio_filename"] == "clip.mp3"
    assert data["bitrate"] == "320k"
    assert data["source"]["id"] == "abc123"
