from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vidz_grab_fast.ui import LOGO_PATH

from .bpm import MIN_MIX_DURATION_SECONDS, MIX_SECONDS, SonoError, SonoTrack, analyze_folder

SNDZ_LOGO_PATH = LOGO_PATH.parent / "sndz_play_lite_logo.png"


class IndustrialPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")


class AnalysisWorker(QObject):
    progress = Signal(str, int)
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self.folder = folder

    def run(self) -> None:
        try:
            tracks, errors = analyze_folder(self.folder, progress=self.progress.emit)
        except SonoError as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(tracks, errors)


class SonoWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: AnalysisWorker | None = None
        self.tracks: list[SonoTrack] = []
        self.play_index = 0
        self.current_player: QProcess | None = None
        self.players: list[QProcess] = []
        self.mix_timer = QTimer(self)
        self.mix_timer.setSingleShot(True)
        self.mix_timer.timeout.connect(self._auto_next_mix)
        self.stop_requested = False
        self.setWindowTitle("SNDZ PLAY LITE")
        if SNDZ_LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(SNDZ_LOGO_PATH)))
        self.setMinimumSize(800, 780)
        self.resize(860, 860)
        self._build_ui()
        self._apply_style()
        self._set_status("READY")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(28, 28, 28, 28)
        shell.setSpacing(18)

        self.panel = IndustrialPanel()
        self.panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        shell.addWidget(self.panel, alignment=Qt.AlignCenter)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(70, 48, 70, 40)
        layout.setSpacing(14)

        header = QHBoxLayout()
        self.unit_label = QLabel("SPL-01")
        self.unit_label.setObjectName("unitLabel")
        header.addWidget(self.unit_label)
        header.addStretch(1)
        self.status_led = QLabel("")
        self.status_led.setObjectName("statusLed")
        self.status_led.setFixedSize(12, 12)
        header.addWidget(self.status_led)
        self.status = QLabel("READY")
        self.status.setObjectName("status")
        header.addWidget(self.status)
        layout.addLayout(header)

        self.logo = QLabel("SNDZ\nPLAY\nLITE")
        self.logo.setObjectName("logo")
        self.logo.setAlignment(Qt.AlignCenter)
        if SNDZ_LOGO_PATH.exists():
            pixmap = QPixmap(str(SNDZ_LOGO_PATH))
            self.logo.setPixmap(pixmap.scaled(190, 190, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.logo, alignment=Qt.AlignCenter)
        layout.addSpacing(18)

        layout.addWidget(self._field_label("SOUND FOLDER"))
        folder_row = QHBoxLayout()
        folder_row.setSpacing(18)
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        self.folder_input.setFixedHeight(42)
        self.choose_button = QPushButton("Choose Folder")
        self.choose_button.clicked.connect(self._choose_folder)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.choose_button)
        layout.addLayout(folder_row)

        self.track_list = QListWidget()
        self.track_list.setObjectName("trackList")
        self.track_list.setMinimumHeight(260)
        layout.addWidget(self.track_list, 1)

        controls = QHBoxLayout()
        controls.setSpacing(14)
        self.analyze_button = QPushButton("BPM")
        self.play_button = QPushButton("PLAY")
        self.next_button = QPushButton("NEXT")
        self.stop_button = QPushButton("STOP")
        self.play_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.analyze_button.clicked.connect(self._start_analysis)
        self.play_button.clicked.connect(self._start_playback)
        self.next_button.clicked.connect(self._next_track)
        self.stop_button.clicked.connect(self._stop_playback)
        controls.addWidget(self.analyze_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)

        self.footer = QLabel("LOW BPM TO HIGH BPM / AUTO MIX")
        self.footer.setObjectName("footer")
        self.footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.footer)

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            * { font-family: "Arial Narrow", "Arial", "Helvetica", sans-serif; }
            #root { background: #050505; }
            #panel {
                min-width: 700px;
                max-width: 820px;
                min-height: 700px;
                max-height: 820px;
                border: 4px solid #35312b;
                border-radius: 18px;
                background: #11110f;
            }
            QLabel {
                color: #9d9688;
                font-size: 13px;
                font-weight: 800;
            }
            #unitLabel {
                color: #c53831;
                font-family: "Courier New", monospace;
                font-size: 22px;
                font-weight: 900;
            }
            #status {
                color: #aaa195;
                font-size: 18px;
                font-weight: 900;
            }
            #statusLed {
                border-radius: 6px;
                background: #c1372e;
            }
            #logo {
                color: #d8d0c0;
                font-size: 56px;
                font-weight: 900;
                line-height: 0.9;
                min-height: 190px;
            }
            #fieldLabel {
                color: #9f988d;
                font-size: 18px;
                font-weight: 900;
            }
            QLineEdit {
                color: #e7dfcf;
                background: #050505;
                border: 2px solid #302d27;
                border-radius: 7px;
                font-family: "Courier New", monospace;
                font-size: 14px;
                font-weight: 700;
                padding-left: 10px;
            }
            QListWidget {
                color: #e7dfcf;
                background: #050505;
                border: 2px solid #302d27;
                border-radius: 7px;
                font-family: "Courier New", monospace;
                font-size: 13px;
                font-weight: 700;
                padding: 10px;
            }
            QListWidget::item {
                min-height: 26px;
            }
            QListWidget::item:selected {
                background: #912c26;
                color: #050505;
            }
            QPushButton {
                min-height: 58px;
                color: #e7dfcf;
                background: #181716;
                border: 2px solid #343029;
                border-radius: 6px;
                font-size: 20px;
                font-weight: 900;
            }
            QPushButton:disabled {
                color: #5f594f;
                background: #0b0b0a;
            }
            QPushButton:hover:!disabled {
                border-color: #6b6256;
            }
            QPushButton:pressed:!disabled {
                background: #9e2e27;
                color: #050505;
            }
            #footer {
                color: #5d5750;
                font-family: "Courier New", monospace;
                font-size: 11px;
                font-weight: 900;
            }
            """
        )

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "SOUND FOLDER")
        if folder:
            self.folder_input.setText(folder)
            self.tracks = []
            self.track_list.clear()
            self.play_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self._set_status("READY")

    def _set_status(self, text: str) -> None:
        self.status.setText((text or "READY").upper())

    def _start_analysis(self) -> None:
        folder = self.folder_input.text().strip()
        if not folder:
            self._set_status("NO FOLDER")
            return
        self._stop_playback()
        self.analyze_button.setEnabled(False)
        self.play_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.track_list.clear()
        self.footer.setText("ANALYZING")
        self._set_status("BPM 0%")

        self.thread = QThread()
        self.worker = AnalysisWorker(Path(folder))
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._clear_worker)
        self.thread.start()

    def _on_progress(self, message: str, percent: int) -> None:
        self._set_status(f"{message} {percent}%")

    def _on_finished(self, tracks: list[SonoTrack], errors: list[str]) -> None:
        self.analyze_button.setEnabled(True)
        self.tracks = tracks
        self._render_tracks()
        self.play_button.setEnabled(bool(self.tracks))
        self.next_button.setEnabled(False)
        self._set_status("READY" if not errors else "PARTIAL")
        self.footer.setText(f"{len(self.tracks)} TRACKS / {len(errors)} ERR")

    def _on_failed(self, message: str) -> None:
        self.analyze_button.setEnabled(True)
        self._set_status("ERROR")
        self.footer.setText(message.upper()[:80])

    def _clear_worker(self) -> None:
        self.worker = None
        self.thread = None

    def _render_tracks(self) -> None:
        self.track_list.clear()
        for track in self.tracks:
            bpm = f"{track.bpm:03.0f} BPM" if track.bpm is not None else "--- BPM"
            mix = "MIX" if track.mixable_intro else "---"
            self.track_list.addItem(f"{bpm}  {mix}  {track.path.name}")

    def _start_playback(self) -> None:
        if not self.tracks:
            self._set_status("NO TRACKS")
            return
        if not shutil.which("ffplay"):
            self._set_status("NO FFPLAY")
            self.footer.setText("INSTALL FFMPEG")
            return
        self._stop_playback(reset_status=False)
        self.stop_requested = False
        self.play_index = 0
        self.play_button.setEnabled(False)
        self.next_button.setEnabled(len(self.tracks) > 1)
        self.stop_button.setEnabled(True)
        self.footer.setText("LOW TO HIGH")
        self._play_current(fade_in=False)

    def _play_current(self, fade_in: bool) -> None:
        if self.play_index >= len(self.tracks):
            self.current_player = None
            self.play_button.setEnabled(True)
            self.next_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self._set_status("DONE")
            return

        track = self.tracks[self.play_index]
        fade_out = self._should_auto_mix(track)
        self.track_list.setCurrentRow(self.play_index)
        self._set_status(f"PLAY {self.play_index + 1}/{len(self.tracks)}")
        player = QProcess(self)
        player.finished.connect(lambda *args, process=player: self._on_player_finished(process))
        self.players.append(player)
        self.current_player = player
        player.start("ffplay", self._ffplay_args(track, fade_in=fade_in, fade_out=fade_out))

        if fade_out and track.duration_seconds:
            self.mix_timer.start(max(1, int((track.duration_seconds - MIX_SECONDS) * 1000)))
        else:
            self.mix_timer.stop()

    def _should_auto_mix(self, track: SonoTrack) -> bool:
        next_index = self.play_index + 1
        if next_index >= len(self.tracks):
            return False
        if not self.tracks[next_index].mixable_intro:
            return False
        return bool(track.duration_seconds and track.duration_seconds >= MIN_MIX_DURATION_SECONDS)

    def _ffplay_args(self, track: SonoTrack, fade_in: bool, fade_out: bool) -> list[str]:
        args = ["-nodisp", "-autoexit", "-loglevel", "quiet"]
        filters: list[str] = []
        if fade_in:
            filters.append(f"afade=t=in:st=0:d={MIX_SECONDS:g}")
        if fade_out and track.duration_seconds:
            start = max(0.0, track.duration_seconds - MIX_SECONDS)
            filters.append(f"afade=t=out:st={start:.3f}:d={MIX_SECONDS:g}")
        if filters:
            args.extend(["-af", ",".join(filters)])
        args.append(str(track.path))
        return args

    def _auto_next_mix(self) -> None:
        if self.stop_requested or self.play_index + 1 >= len(self.tracks):
            return
        self.play_index += 1
        self.footer.setText("AUTO MIX")
        self._play_current(fade_in=True)

    def _on_player_finished(self, process: QProcess) -> None:
        if process in self.players:
            self.players.remove(process)
        if self.stop_requested:
            return
        if process is not self.current_player:
            process.deleteLater()
            return
        process.deleteLater()
        self.mix_timer.stop()
        self.play_index += 1
        self._play_current(fade_in=False)

    def _next_track(self) -> None:
        if not self.tracks:
            return
        self.mix_timer.stop()
        self.play_index += 1
        self.stop_requested = True
        self._kill_players()
        self.stop_requested = False
        if self.play_index >= len(self.tracks):
            self._set_status("DONE")
            self.play_button.setEnabled(True)
            self.next_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            return
        self.footer.setText("NEXT")
        self._play_current(fade_in=False)

    def _stop_playback(self, reset_status: bool = True) -> None:
        self.stop_requested = True
        self.mix_timer.stop()
        self._kill_players()
        self.current_player = None
        self.play_button.setEnabled(bool(self.tracks))
        self.next_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        if reset_status:
            self._set_status("READY")

    def _kill_players(self) -> None:
        for player in list(self.players):
            if player.state() != QProcess.NotRunning:
                player.kill()
                player.waitForFinished(1500)
            if player in self.players:
                self.players.remove(player)
            player.deleteLater()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        self._stop_playback(reset_status=False)
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SNDZ PLAY LITE")
    app.setOrganizationName("RUSH OPERATOR")
    window = SonoWindow()
    window.show()
    return app.exec()
