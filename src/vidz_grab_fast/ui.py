from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .grabber import GrabError, GrabRequest, grab

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "vidz_grab_fast_logo.png"


class IndustrialPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")


class GrabWorker(QObject):
    progress = Signal(str, int)
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(self, request: GrabRequest) -> None:
        super().__init__()
        self.request = request

    def run(self) -> None:
        try:
            result = grab(self.request, self.progress.emit)
        except (GrabError, OSError, RuntimeError) as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result.video_path, result.source_path)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: GrabWorker | None = None
        self.setWindowTitle("VIDZ GRAB FAST")
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.setMinimumSize(820, 820)
        self.resize(900, 900)
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
        layout.setContentsMargins(78, 58, 78, 50)
        layout.setSpacing(24)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        self.unit_label = QLabel("VGF-01")
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

        self.logo = QLabel("VIDZ\nGRAB\nFAST")
        self.logo.setObjectName("logo")
        self.logo.setAlignment(Qt.AlignCenter)
        if LOGO_PATH.exists():
            pixmap = QPixmap(str(LOGO_PATH))
            self.logo.setPixmap(
                pixmap.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        layout.addWidget(self.logo, alignment=Qt.AlignCenter)

        form = QGridLayout()
        form.setHorizontalSpacing(22)
        form.setVerticalSpacing(13)
        layout.addLayout(form)

        self.url_input = self._line("URL")
        self.artist_input = self._line("ARTIST NAME")
        self.output_input = self._line("OUTPUT FOLDER")
        self.output_input.setReadOnly(True)
        choose = QPushButton("Choose Folder")
        choose.setObjectName("chooseButton")
        choose.clicked.connect(self._choose_folder)

        form.addWidget(self._field_label("URL"), 0, 0)
        form.addWidget(self.url_input, 1, 0, 1, 2)
        form.addWidget(self._field_label("ARTIST NAME"), 2, 0)
        form.addWidget(self.artist_input, 3, 0, 1, 2)
        form.addWidget(self._field_label("OUTPUT FOLDER"), 4, 0)
        form.addWidget(self.output_input, 5, 0)
        form.addWidget(choose, 5, 1)

        self.grab_button = QPushButton("GRAB")
        self.grab_button.setObjectName("grabButton")
        self.grab_button.clicked.connect(self._start_grab)
        layout.addWidget(self.grab_button)

        self.footer = QLabel("URL + ARTIST + OUTPUT")
        self.footer.setObjectName("footer")
        self.footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.footer)

        for screw_name in ("screwTL", "screwTR", "screwBL", "screwBR"):
            screw = QLabel("+", self.panel)
            screw.setObjectName(screw_name)
            screw.setAlignment(Qt.AlignCenter)
            screw.setFixedSize(34, 34)

    def _line(self, placeholder: str) -> QLineEdit:
        line = QLineEdit()
        line.setPlaceholderText(placeholder)
        return line

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        if not hasattr(self, "panel"):
            return
        margin = 20
        positions = {
            "screwTL": (margin, margin),
            "screwTR": (self.panel.width() - margin - 34, margin),
            "screwBL": (margin, self.panel.height() - margin - 34),
            "screwBR": (self.panel.width() - margin - 34, self.panel.height() - margin - 34),
        }
        for name, (x_pos, y_pos) in positions.items():
            screw = self.panel.findChild(QLabel, name)
            if screw:
                screw.move(x_pos, y_pos)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            * {
                font-family: "Arial Narrow", "Arial", "Helvetica", sans-serif;
            }
            #root {
                background: #050505;
            }
            #panel {
                min-width: 720px;
                max-width: 850px;
                min-height: 720px;
                max-height: 850px;
                border: 4px solid #35312b;
                border-radius: 18px;
                background: #11110f;
            }
            #panel::disabled {
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
                min-height: 310px;
                color: #d8d0c0;
                font-size: 48px;
                font-weight: 900;
            }
            #fieldLabel {
                color: #9f988d;
                font-size: 18px;
                font-weight: 900;
            }
            QLineEdit {
                min-height: 38px;
                padding: 0 14px;
                color: #e7dfcf;
                background: #050505;
                border: 2px solid #302d27;
                border-radius: 7px;
                font-family: "Courier New", monospace;
                font-size: 16px;
                font-weight: 700;
            }
            QLineEdit:focus {
                border: 2px solid #8d2a24;
            }
            QPushButton {
                min-height: 38px;
                color: #e7dfcf;
                background: #181716;
                border: 2px solid #343029;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #24211d;
            }
            QPushButton:disabled {
                color: #686157;
                background: #151513;
            }
            #chooseButton {
                min-width: 170px;
            }
            #grabButton {
                min-height: 96px;
                margin-top: 14px;
                color: #070707;
                background: #9e2e27;
                border: 2px solid #5c1b17;
                border-radius: 8px;
                font-size: 48px;
                font-weight: 900;
            }
            #grabButton:hover {
                background: #b83830;
            }
            #footer {
                color: #5d5750;
                font-family: "Courier New", monospace;
                font-size: 11px;
                font-weight: 900;
            }
            #screwTL, #screwTR, #screwBL, #screwBR {
                color: #070707;
                background: #2c2a26;
                border: 3px solid #090909;
                border-radius: 17px;
                font-size: 22px;
                font-weight: 900;
            }
            """
        )

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "OUTPUT FOLDER")
        if folder:
            self.output_input.setText(folder)
            self._set_status("READY")

    def _set_status(self, text: str) -> None:
        self.status.setText((text or "READY").upper())

    def _start_grab(self) -> None:
        output = self.output_input.text().strip()
        if not output:
            self._set_status("NO FOLDER")
            return
        source_url = self.url_input.text().strip()
        if not source_url:
            self._set_status("NO SOURCE")
            return

        request = GrabRequest(
            output_dir=Path(output).expanduser(),
            artist_account=self.artist_input.text().strip(),
            source_url=source_url,
        )
        self.grab_button.setEnabled(False)
        self._set_status("GRAB 0%")
        self.footer.setText("ACQUIRING")

        self.thread = QThread()
        self.worker = GrabWorker(request)
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

    def _on_finished(self, video_path: Path, source_path: Path) -> None:
        self.grab_button.setEnabled(True)
        self._set_status("DONE")
        self.footer.setText(f"{video_path.name} + {source_path.name}")
        self.status.setToolTip(f"{video_path.name}\n{source_path.name}")

    def _on_failed(self, message: str) -> None:
        self.grab_button.setEnabled(True)
        self._set_status("ERROR")
        self.footer.setText(message.upper()[:80])
        self.status.setToolTip(message)

    def _clear_worker(self) -> None:
        self.worker = None
        self.thread = None
