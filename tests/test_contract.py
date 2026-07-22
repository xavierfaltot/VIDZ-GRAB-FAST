from __future__ import annotations

import json
import sys

from PySide6.QtWidgets import QApplication, QLineEdit, QListWidget

from vidz_grab_fast.filenames import clean_filename_stem
from vidz_grab_fast.grabber import MAX_BATCH_ITEMS, _source_urls_from_info, existing_source_urls
from vidz_grab_fast.platforms import detect_platform
from vidz_grab_fast.provenance import SourceRecord, write_source_json
from vidz_grab_fast.audio import audio_source_json_path, write_audio_source_json
from vidz_grab_fast.ui import MainWindow
from sono_play_lite.ui import SonoWindow
from sono_play_lite.bpm import (
    SonoTrack,
    analyze_folder,
    find_tool,
    find_audio_files,
    is_mixable_intro_from_energies,
    sort_tracks_by_bpm,
)


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


def test_large_playlist_limit_supports_500_tracks() -> None:
    entries = [{"id": f"video-{index:03d}"} for index in range(500)]
    info = {"entries": entries}

    urls = _source_urls_from_info(info, "https://www.youtube.com/playlist?list=PL123", MAX_BATCH_ITEMS)

    assert len(urls) == 500
    assert urls[0] == "https://www.youtube.com/watch?v=video-000"
    assert urls[-1] == "https://www.youtube.com/watch?v=video-499"


def test_existing_source_urls_supports_resume_without_duplicates(tmp_path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"")
    write_source_json(
        video,
        SourceRecord(
            source_url="https://www.youtube.com/watch?v=abc123",
            clean_filename=video.name,
        ),
    )

    assert existing_source_urls(tmp_path) == {"https://www.youtube.com/watch?v=abc123"}


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


def test_sono_finds_supported_audio_recursively(tmp_path) -> None:
    (tmp_path / "a.mp3").write_bytes(b"")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.wav").write_bytes(b"")
    (nested / "skip.txt").write_text("no", encoding="utf-8")

    assert [path.name for path in find_audio_files(tmp_path)] == ["a.mp3", "b.wav"]


def test_sono_sorts_from_low_bpm_to_high_bpm(tmp_path) -> None:
    slow = SonoTrack(tmp_path / "slow.mp3", 82.0)
    fast = SonoTrack(tmp_path / "fast.mp3", 132.0)
    unknown = SonoTrack(tmp_path / "unknown.mp3", None)
    mid = SonoTrack(tmp_path / "mid.mp3", 108.0)

    assert sort_tracks_by_bpm([unknown, fast, slow, mid]) == [slow, mid, fast, unknown]


def test_sono_analyze_folder_uses_estimator_and_sorts(tmp_path) -> None:
    for name in ("c.mp3", "a.mp3", "b.mp3"):
        (tmp_path / name).write_bytes(b"")
    bpms = {"a.mp3": 128.0, "b.mp3": 90.0, "c.mp3": 110.0}

    tracks, errors = analyze_folder(tmp_path, estimator=lambda path: bpms[path.name])

    assert errors == []
    assert [(track.path.name, track.bpm) for track in tracks] == [
        ("b.mp3", 90.0),
        ("c.mp3", 110.0),
        ("a.mp3", 128.0),
    ]


def test_sono_mixable_intro_energy_gate() -> None:
    assert is_mixable_intro_from_energies([0.3] * 24)
    assert not is_mixable_intro_from_energies([0.0] * 24)
    assert not is_mixable_intro_from_energies([0.0] * 20 + [0.9])


def test_sono_tool_lookup_returns_none_for_missing_tool() -> None:
    assert find_tool("sndz_missing_tool_for_test") is None


def test_sndz_ui_is_logo_driven_and_minimal(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = SonoWindow()

    assert window.windowTitle() == "SNDZ PLAY MINI"
    assert window.play_button.text() == ""
    assert window.next_button.text() == ""
    assert window.stop_button.text() == ""
    assert window.play_button.accessibleName() == "PLAY"
    assert window.next_button.accessibleName() == "NEXT"
    assert window.stop_button.accessibleName() == "STOP"
    assert window.play_button.size() == window.logo.size()
    assert window.findChildren(QLineEdit) == []
    assert window.findChildren(QListWidget) == []

    window.close()
    assert app is not None
