from __future__ import annotations

import json
import sys

from PySide6.QtWidgets import QApplication, QLineEdit, QListWidget

from vidz_grab_fast.filenames import clean_filename_stem
from vidz_grab_fast.grabber import (
    MAX_BATCH_ITEMS,
    GrabError,
    _source_urls_from_info,
    existing_source_urls,
    is_unavailable_error,
    is_playlist_url,
    ytdlp_options,
)
from vidz_grab_fast.platforms import detect_platform
from vidz_grab_fast.provenance import SourceRecord, write_source_json
from vidz_grab_fast.audio import audio_source_json_path, write_audio_source_json
from vidz_grab_fast.ui import LOGO_SIZE, PANEL_HEIGHT as GRAB_PANEL_HEIGHT, PANEL_WIDTH as GRAB_PANEL_WIDTH, GrabWorker, MainWindow
from sono_play_lite.ui import PANEL_HEIGHT, PANEL_WIDTH, SonoWindow
from sono_play_lite.bpm import (
    SonoTrack,
    analyze_folder,
    find_tool,
    find_audio_files,
    is_mixable_intro_from_energies,
    mixable_region_seconds_from_energies,
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


def test_grab_uses_legacy_compatible_ytdlp_video_format() -> None:
    options = ytdlp_options({"format": "bv*+ba/b"})

    assert options["format"] == "bv*+ba/b"
    assert options["cachedir"] is False


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


def test_ui_rejoins_wrapped_long_url_lines(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.url_input.setPlainText(
        "https://youtube.com/playlist?list=PLYfzPRVpLUq6Z_2riYs-\n"
        "rouU3XICpE5aF&si=_tssHWr8K4Wy6yII\n"
        "https://example.com/video.mp4"
    )

    assert window._urls() == [
        "https://youtube.com/playlist?list=PLYfzPRVpLUq6Z_2riYs-rouU3XICpE5aF&si=_tssHWr8K4Wy6yII",
        "https://example.com/video.mp4",
    ]

    window.close()
    assert app is not None


def test_grab_ui_is_compact_and_centered(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.resize(1000, 900)
    app.processEvents()

    root_rect = window.centralWidget().rect()
    panel_rect = window.panel.geometry()

    assert window.logo.width() == LOGO_SIZE
    assert window.logo.height() == LOGO_SIZE
    assert window.panel.width() == GRAB_PANEL_WIDTH
    assert window.panel.height() == GRAB_PANEL_HEIGHT
    assert abs(panel_rect.center().x() - root_rect.center().x()) <= 1
    assert abs(panel_rect.center().y() - root_rect.center().y()) <= 1

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


def test_playlist_info_skips_unavailable_entries() -> None:
    info = {
        "entries": [
            {"id": "private111", "title": "[Private video]"},
            {"id": "ok222", "title": "Available"},
            {"id": "deleted333", "availability": "private"},
        ]
    }

    assert _source_urls_from_info(info, "https://www.youtube.com/playlist?list=PL123", 150) == [
        "https://www.youtube.com/watch?v=ok222",
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


def test_playlist_url_detection() -> None:
    assert is_playlist_url("https://youtube.com/playlist?list=PL123")
    assert is_playlist_url("https://www.youtube.com/watch?v=abc&list=PL123")
    assert not is_playlist_url("https://www.youtube.com/watch?v=abc")


def test_unavailable_error_detection() -> None:
    assert is_unavailable_error("Video unavailable")
    assert is_unavailable_error("This video is private")
    assert not is_unavailable_error("HTTP Error 500")


def test_worker_counts_unavailable_video_as_failed_skip(monkeypatch, tmp_path) -> None:
    finished: list[tuple[int, int, int, int, list[str], list[str]]] = []

    def fake_expand(url: str, max_items: int) -> list[str]:
        return [
            "https://www.youtube.com/watch?v=ok",
            "https://www.youtube.com/watch?v=private",
            "https://www.youtube.com/watch?v=ok2",
        ]

    def fake_grab(request, progress):  # noqa: ANN001
        if request.source_url.endswith("private"):
            raise GrabError("Video unavailable")
        progress("DONE", 100)

    monkeypatch.setattr("vidz_grab_fast.ui.expand_source_url", fake_expand)
    monkeypatch.setattr("vidz_grab_fast.ui.grab", fake_grab)

    worker = GrabWorker(
        output_dir=tmp_path,
        artist_account="",
        urls=["https://youtube.com/playlist?list=PL123"],
    )
    worker.finished.connect(
        lambda ok, err, skip, failed_skip, errors, failed_errors: finished.append(
            (ok, err, skip, failed_skip, errors, failed_errors)
        )
    )
    worker.run()

    assert finished == [(2, 0, 0, 1, [], ["2: Video unavailable"])]


def test_worker_skips_any_failed_video_from_playlist(monkeypatch, tmp_path) -> None:
    finished: list[tuple[int, int, int, int, list[str], list[str]]] = []

    def fake_expand(url: str, max_items: int) -> list[str]:
        return [
            "https://www.youtube.com/watch?v=ok",
            "https://www.youtube.com/watch?v=broken",
            "https://www.youtube.com/watch?v=ok2",
        ]

    def fake_grab(request, progress):  # noqa: ANN001
        if request.source_url.endswith("broken"):
            raise GrabError("HTTP Error 500")
        progress("DONE", 100)

    monkeypatch.setattr("vidz_grab_fast.ui.expand_source_url", fake_expand)
    monkeypatch.setattr("vidz_grab_fast.ui.grab", fake_grab)

    worker = GrabWorker(
        output_dir=tmp_path,
        artist_account="",
        urls=["https://youtube.com/playlist?list=PL123"],
    )
    worker.finished.connect(
        lambda ok, err, skip, failed_skip, errors, failed_errors: finished.append(
            (ok, err, skip, failed_skip, errors, failed_errors)
        )
    )
    worker.run()

    assert finished == [(2, 0, 0, 1, [], ["2: HTTP Error 500"])]


def test_worker_keeps_direct_video_failure_as_error(monkeypatch, tmp_path) -> None:
    finished: list[tuple[int, int, int, int, list[str], list[str]]] = []

    def fake_expand(url: str, max_items: int) -> list[str]:
        return [url]

    def fake_grab(request, progress):  # noqa: ANN001, ARG001
        raise GrabError("HTTP Error 500")

    monkeypatch.setattr("vidz_grab_fast.ui.expand_source_url", fake_expand)
    monkeypatch.setattr("vidz_grab_fast.ui.grab", fake_grab)

    worker = GrabWorker(
        output_dir=tmp_path,
        artist_account="",
        urls=["https://www.youtube.com/watch?v=broken"],
    )
    worker.finished.connect(
        lambda ok, err, skip, failed_skip, errors, failed_errors: finished.append(
            (ok, err, skip, failed_skip, errors, failed_errors)
        )
    )
    worker.run()

    assert finished == [(0, 1, 0, 0, ["1: HTTP Error 500"], [])]


def test_finished_with_only_failed_playlist_skips_is_error(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    window._on_finished(0, 0, 0, 3, [], [])

    assert window.status.text() == "ERROR"
    assert window.footer.text() == "0 OK / 3 FAILED SKIP"
    assert window.detail.text() == "NO ERROR DETAIL RETURNED BY YT-DLP"

    window.close()
    assert app is not None


def test_finished_with_only_failed_playlist_skips_shows_first_error(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    window._on_finished(0, 0, 0, 88, [], ["1: Sign in to confirm you are not a bot"])

    assert window.status.text() == "ERROR"
    assert window.footer.text() == "0 OK / 88 FAILED SKIP"
    assert window.detail.text() == "1: SIGN IN TO CONFIRM YOU ARE NOT A BOT"

    window.close()
    assert app is not None


def test_playlist_expansion_failure_does_not_download_playlist_url(monkeypatch, tmp_path) -> None:
    failures: list[str] = []

    def fail_expand(url: str, max_items: int) -> list[str]:
        raise GrabError("Playlist not found or not public")

    def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("playlist URL should not be downloaded directly")

    monkeypatch.setattr("vidz_grab_fast.ui.expand_source_url", fail_expand)
    monkeypatch.setattr("vidz_grab_fast.ui.grab", fail_if_called)

    worker = GrabWorker(
        output_dir=tmp_path,
        artist_account="",
        urls=["https://youtube.com/playlist?list=PL404"],
    )
    worker.failed.connect(failures.append)
    worker.run()

    assert failures == ["LIST: Playlist not found or not public"]


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


def test_sono_measures_long_mixable_regions() -> None:
    assert mixable_region_seconds_from_energies([0.3] * 700) >= 28.0
    assert mixable_region_seconds_from_energies([0.0] * 700) == 0.0


def test_sono_tool_lookup_returns_none_for_missing_tool() -> None:
    assert find_tool("sndz_missing_tool_for_test") is None


def test_sndz_ui_is_logo_driven_and_minimal(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = SonoWindow()
    window.show()
    app.processEvents()

    assert window.windowTitle() == "SNDZ PLAY MINI"
    assert window.play_button.text() == ""
    assert window.next_button.text() == ""
    assert window.play_button.accessibleName() == "PLAY"
    assert window.next_button.accessibleName() == "NEXT"
    assert not hasattr(window, "stop_button")
    assert window.play_button.width() == window.logo.width()
    assert window.next_button.width() == window.logo.width()
    assert window.play_button.height() == window.logo.height()
    assert window.next_button.height() == window.logo.height()
    assert window.play_button.y() == window.next_button.y()
    assert window.play_button.x() < window.next_button.x()
    assert window.panel.width() == PANEL_WIDTH
    assert window.panel.height() == PANEL_HEIGHT
    assert window.maximumWidth() > window.minimumWidth()
    assert window.findChildren(QLineEdit) == []
    assert window.findChildren(QListWidget) == []

    window.close()
    assert app is not None


def test_sndz_maximized_layout_keeps_mini_panel_centered(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = SonoWindow()
    window.show()
    window.resize(1000, 800)
    app.processEvents()

    root_rect = window.centralWidget().rect()
    panel_rect = window.panel.geometry()

    assert window.panel.width() == PANEL_WIDTH
    assert window.panel.height() == PANEL_HEIGHT
    assert abs(panel_rect.center().x() - root_rect.center().x()) <= 1
    assert abs(panel_rect.center().y() - root_rect.center().y()) <= 1

    window.close()
    assert app is not None


def test_sndz_status_progress_uses_title_bar(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = SonoWindow()

    window._set_status("BPM 42%")
    assert window.windowTitle() == "SNDZ PLAY MINI - BPM 42%"
    window._set_status("READY")
    assert window.windowTitle() == "SNDZ PLAY MINI"

    window.close()
    assert app is not None


def test_sndz_next_stays_enabled_until_last_track(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = SonoWindow()
    window.tracks = [
        SonoTrack(tmp_path / "one.mp3", 90.0),
        SonoTrack(tmp_path / "two.mp3", 100.0),
        SonoTrack(tmp_path / "three.mp3", 110.0),
    ]

    window.play_index = 0
    window._sync_transport_buttons(playing=True)
    assert window.next_button.isEnabled()

    window.play_index = 1
    window._sync_transport_buttons(playing=True)
    assert window.next_button.isEnabled()

    window.play_index = 2
    window._sync_transport_buttons(playing=True)
    assert not window.next_button.isEnabled()

    window.close()
    assert app is not None


def test_sndz_next_can_advance_multiple_times(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = SonoWindow()
    window.tracks = [
        SonoTrack(tmp_path / "one.mp3", 90.0),
        SonoTrack(tmp_path / "two.mp3", 100.0),
        SonoTrack(tmp_path / "three.mp3", 110.0),
    ]
    played_indexes: list[int] = []

    monkeypatch.setattr(window, "_kill_players", lambda: None)
    monkeypatch.setattr(window, "_play_current", lambda fade_in: played_indexes.append(window.play_index))

    window.play_index = 0
    window._next_track()
    window._next_track()

    assert played_indexes == [1, 2]
    assert window.play_index == 2

    window.close()
    assert app is not None


def test_sndz_uses_long_mix_for_similar_bpm_and_long_regions(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv)
    window = SonoWindow()
    window.tracks = [
        SonoTrack(
            tmp_path / "one.mp3",
            120.0,
            duration_seconds=240.0,
            mixable_intro_seconds=8.0,
            mixable_outro_seconds=28.0,
        ),
        SonoTrack(
            tmp_path / "two.mp3",
            122.0,
            duration_seconds=240.0,
            mixable_intro=True,
            mixable_intro_seconds=28.0,
            mixable_outro_seconds=28.0,
        ),
    ]

    assert window._transition_mix_seconds(window.tracks[0]) == 28.0

    window.tracks[1] = SonoTrack(
        tmp_path / "two.mp3",
        138.0,
        duration_seconds=240.0,
        mixable_intro=True,
        mixable_intro_seconds=28.0,
        mixable_outro_seconds=28.0,
    )
    assert window._transition_mix_seconds(window.tracks[0]) == 16.0

    window.tracks[1] = SonoTrack(
        tmp_path / "two.mp3",
        122.0,
        duration_seconds=240.0,
        mixable_intro=True,
        mixable_intro_seconds=4.0,
        mixable_outro_seconds=28.0,
    )
    assert window._transition_mix_seconds(window.tracks[0]) == 0.0

    window.close()
    assert app is not None
