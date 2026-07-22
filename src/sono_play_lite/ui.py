from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QThread, Qt, Signal
from PySide6.QtGui import QIcon
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

from .bpm import SonoError, SonoTrack, analyze_folder


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
        self.player: QProcess | None = None
        self.stop_requested = False
        self.setWindowTitle("SONO PLAY LITE")
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))
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

        self.logo = QLabel("SONO\nPLAY\nLITE")
        self.logo.setObjectName("logo")
        self.logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.logo, alignment=Qt.AlignCenter)
        layout.addSpacing(20)

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
        self.stop_button = QPushButton("STOP")
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.analyze_button.clicked.connect(self._start_analysis)
        self.play_button.clicked.connect(self._start_playback)
        self.stop_button.clicked.connect(self._stop_playback)
        controls.addWidget(self.analyze_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)

        self.footer = QLabel("LOW BPM TO HIGH BPM")
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
                min-height: 172px;
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
            self.track_list.addItem(f"{bpm}  {track.path.name}")

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
        self.stop_button.setEnabled(True)
        self.footer.setText("LOW TO HIGH")
        self._play_current()

    def _play_current(self) -> None:
        if self.play_index >= len(self.tracks):
            self.player = None
            self.play_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self._set_status("DONE")
            return

        track = self.tracks[self.play_index]
        self.track_list.setCurrentRow(self.play_index)
        self._set_status(f"PLAY {self.play_index + 1}/{len(self.tracks)}")
        self.player = QProcess(self)
        self.player.finished.connect(self._on_player_finished)
        self.player.start(
            "ffplay",
            ["-nodisp", "-autoexit", "-loglevel", "quiet", str(track.path)],
        )

    def _on_player_finished(self, *args) -> None:  # noqa: ANN002
        if self.stop_requested:
            return
        self.play_index += 1
        self._play_current()

    def _stop_playback(self, reset_status: bool = True) -> None:
        self.stop_requested = True
        if self.player and self.player.state() != QProcess.NotRunning:
            self.player.kill()
            self.player.waitForFinished(1500)
        self.player = None
        self.play_button.setEnabled(bool(self.tracks))
        self.stop_button.setEnabled(False)
        if reset_status:
            self._set_status("READY")

    def closeEvent(self, event) -> None:  # noqa: ANN001
        self._stop_playback(reset_status=False)
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SONO PLAY LITE")
    app.setOrganizationName("RUSH OPERATOR")
    window = SonoWindow()
    window.show()
    return app.exec()
