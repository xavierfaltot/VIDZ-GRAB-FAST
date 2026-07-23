from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .audio import AudioError, convert_folder
from .ui import ASSETS_DIR, IndustrialPanel

AUDIO_LOGO_PATH = ASSETS_DIR / "vidz_turn_sono_logo.png"
AUDIO_ICON_PATH = ASSETS_DIR / "vidz_turn_sono_icon.png"
AUDIO_LOGO_BOTTOM_SPACING = 72


class AudioWorker(QObject):
    progress = Signal(str, int)
    finished = Signal(int, int)
    failed = Signal(str)

    def __init__(self, input_dir: Path, output_dir: Path) -> None:
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir

    def run(self) -> None:
        try:
            ok, errors = convert_folder(self.input_dir, self.output_dir, progress=self.progress.emit)
        except AudioError as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(ok, errors)


class AudioWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: AudioWorker | None = None
        self.setWindowTitle("VIDZ TURN SONO")
        if AUDIO_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(AUDIO_ICON_PATH)))
        self.setMinimumSize(720, 620)
        self.resize(800, 680)
        self._build_ui()
        self._apply_style()
        self._set_status("READY")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(28, 28, 28, 28)

        self.panel = IndustrialPanel()
        self.panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        shell.addWidget(self.panel, alignment=Qt.AlignCenter)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(68, 46, 68, 40)
        layout.setSpacing(16)

        header = QHBoxLayout()
        self.unit_label = QLabel("VAF-01")
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

        self.logo = QLabel("VIDZ\nTURN\nSONO")
        self.logo.setObjectName("logo")
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setFixedSize(260, 205)
        if AUDIO_LOGO_PATH.exists():
            pixmap = QPixmap(str(AUDIO_LOGO_PATH))
            self.logo.setPixmap(pixmap.scaled(260, 205, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.logo, alignment=Qt.AlignCenter)
        layout.addSpacing(AUDIO_LOGO_BOTTOM_SPACING)

        self.input_line = self._line()
        self.output_line = self._line()
        self.input_button = QPushButton("Choose MP4 Folder")
        self.output_button = QPushButton("Choose MP3 Folder")
        self.input_button.clicked.connect(self._choose_input)
        self.output_button.clicked.connect(self._choose_output)

        layout.addWidget(self._field_label("MP4 FOLDER"))
        input_row = QHBoxLayout()
        input_row.setSpacing(16)
        input_row.addWidget(self.input_line, 1)
        input_row.addWidget(self.input_button)
        layout.addLayout(input_row)

        layout.addWidget(self._field_label("MP3 OUTPUT"))
        output_row = QHBoxLayout()
        output_row.setSpacing(16)
        output_row.addWidget(self.output_line, 1)
        output_row.addWidget(self.output_button)
        layout.addLayout(output_row)

        self.convert_button = QPushButton("MP3")
        self.convert_button.setObjectName("grabButton")
        self.convert_button.setAutoDefault(False)
        self.convert_button.setDefault(False)
        self.convert_button.clicked.connect(self._start)
        layout.addWidget(self.convert_button)

        self.footer = QLabel("MP4 TO MP3 + SOURCE")
        self.footer.setObjectName("footer")
        self.footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.footer)

    def _line(self) -> QLineEdit:
        line = QLineEdit()
        line.setReadOnly(True)
        line.setFixedHeight(42)
        return line

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
                min-width: 620px;
                max-width: 720px;
                min-height: 540px;
                max-height: 620px;
                border: 4px solid #35312b;
                border-radius: 18px;
                background: #11110f;
            }
            QLabel { color: #9d9688; font-size: 13px; font-weight: 800; }
            #unitLabel { color: #c53831; font-family: "Courier New", monospace; font-size: 22px; font-weight: 900; }
            #status { color: #aaa195; font-size: 18px; font-weight: 900; }
            #statusLed { border-radius: 6px; background: #c1372e; }
            #logo { color: #d8d0c0; font-size: 42px; font-weight: 900; }
            #fieldLabel { color: #9f988d; font-size: 18px; font-weight: 900; }
            QLineEdit {
                color: #e7dfcf;
                background: #050505;
                border: 2px solid #302d27;
                border-radius: 7px;
                font-family: "Courier New", monospace;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton {
                min-height: 42px;
                color: #e7dfcf;
                background: #181716;
                border: 2px solid #343029;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 900;
            }
            #grabButton {
                min-height: 82px;
                margin-top: 12px;
                color: #070707;
                background: #9e2e27;
                border: 2px solid #5c1b17;
                border-radius: 8px;
                font-size: 48px;
                font-weight: 900;
            }
            #footer {
                color: #5d5750;
                font-family: "Courier New", monospace;
                font-size: 11px;
                font-weight: 900;
            }
            """
        )

    def _choose_input(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "MP4 FOLDER")
        if folder:
            self.input_line.setText(folder)
            if not self.output_line.text().strip():
                self.output_line.setText(folder)

    def _choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "MP3 OUTPUT")
        if folder:
            self.output_line.setText(folder)

    def _set_status(self, text: str) -> None:
        self.status.setText((text or "READY").upper())

    def _start(self) -> None:
        input_dir = self.input_line.text().strip()
        output_dir = self.output_line.text().strip() or input_dir
        if not input_dir:
            self._set_status("NO MP4")
            return

        self.convert_button.setEnabled(False)
        self._set_status("MP3 0%")
        self.footer.setText("CONVERTING")

        self.thread = QThread()
        self.worker = AudioWorker(Path(input_dir), Path(output_dir))
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

    def _on_finished(self, ok: int, errors: int) -> None:
        self.convert_button.setEnabled(True)
        self._set_status("DONE" if not errors else "DONE ERR")
        self.footer.setText(f"{ok} OK / {errors} ERR")

    def _on_failed(self, message: str) -> None:
        self.convert_button.setEnabled(True)
        self._set_status("ERROR")
        self.footer.setText(message.upper()[:80])

    def _clear_worker(self) -> None:
        self.worker = None
        self.thread = None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("VIDZ TURN SONO")
    app.setOrganizationName("RUSH OPERATOR")
    window = AudioWindow()
    window.show()
    return app.exec()
