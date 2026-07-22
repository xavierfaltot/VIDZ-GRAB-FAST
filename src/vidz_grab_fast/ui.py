from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .grabber import (
    MAX_BATCH_ITEMS,
    GrabError,
    GrabRequest,
    existing_source_urls,
    expand_source_url,
    grab,
    is_unavailable_error,
    is_playlist_url,
)

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "vidz_grab_fast_logo.png"
LOGO_SIZE = 170
PANEL_WIDTH = 430
PANEL_HEIGHT = 632
WINDOW_WIDTH = 520
WINDOW_HEIGHT = 700


class IndustrialPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")


class GrabWorker(QObject):
    progress = Signal(str, int)
    finished = Signal(int, int, int, object)
    failed = Signal(str)

    def __init__(self, output_dir: Path, artist_account: str, urls: list[str]) -> None:
        super().__init__()
        self.output_dir = output_dir
        self.artist_account = artist_account
        self.input_urls = urls

    def run(self) -> None:
        self.progress.emit("LIST", 1)
        urls: list[str] = []
        errors: list[str] = []
        seen: set[str] = set()
        grabbed = existing_source_urls(self.output_dir)
        skipped_count = 0
        for url in self.input_urls:
            remaining = MAX_BATCH_ITEMS - len(urls)
            if remaining <= 0:
                break
            try:
                expanded_urls = expand_source_url(url, remaining)
            except GrabError as exc:
                if is_playlist_url(url):
                    errors.append(f"LIST: {exc}")
                    continue
                expanded_urls = [url]
            for expanded_url in expanded_urls:
                if expanded_url in seen:
                    continue
                seen.add(expanded_url)
                if expanded_url in grabbed:
                    skipped_count += 1
                    continue
                urls.append(expanded_url)
                if len(urls) >= MAX_BATCH_ITEMS:
                    break

        if not urls:
            if errors:
                self.failed.emit(errors[0])
                return
            if skipped_count:
                self.finished.emit(0, 0, skipped_count, [])
            else:
                self.failed.emit("No URL provided")
            return

        success_count = 0
        total = len(urls)
        for index, url in enumerate(urls, start=1):
            request = GrabRequest(
                output_dir=self.output_dir,
                artist_account=self.artist_account,
                source_url=url,
            )

            def item_progress(message: str, percent: int) -> None:
                done_share = ((index - 1) / total) * 100
                item_share = percent / total
                self.progress.emit(f"{message} {index}/{total}", int(done_share + item_share))

            try:
                grab(request, item_progress)
                success_count += 1
            except (GrabError, OSError, RuntimeError) as exc:
                if is_unavailable_error(exc):
                    skipped_count += 1
                else:
                    errors.append(f"{index}: {exc}")
                self.progress.emit(f"SKIP {index}/{total}", int((index / total) * 100))

        self.finished.emit(success_count, len(errors), skipped_count, errors)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: GrabWorker | None = None
        self.setWindowTitle("VIDZ GRAB FAST")
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._build_ui()
        self._apply_style()
        self._set_status("READY")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(10, 10, 10, 10)
        shell.setSpacing(0)

        self.panel = IndustrialPanel()
        self.panel.setFixedSize(PANEL_WIDTH, PANEL_HEIGHT)
        self.panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        shell.addWidget(self.panel, alignment=Qt.AlignCenter)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        self.unit_label = QLabel("VGF-01")
        self.unit_label.setObjectName("unitLabel")
        header.addWidget(self.unit_label)
        header.addStretch(1)
        self.status_led = QLabel("")
        self.status_led.setObjectName("statusLed")
        self.status_led.setFixedSize(10, 10)
        header.addWidget(self.status_led)
        self.status = QLabel("READY")
        self.status.setObjectName("status")
        header.addWidget(self.status)
        layout.addLayout(header)

        self.logo = QLabel("VIDZ\nGRAB\nFAST")
        self.logo.setObjectName("logo")
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setFixedSize(LOGO_SIZE, LOGO_SIZE)
        if LOGO_PATH.exists():
            pixmap = QPixmap(str(LOGO_PATH))
            self.logo.setPixmap(
                pixmap.scaled(LOGO_SIZE, LOGO_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        layout.addWidget(self.logo, alignment=Qt.AlignCenter)
        layout.addSpacing(8)

        form = QVBoxLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        layout.addLayout(form)

        self.url_input = QPlainTextEdit()
        self.url_input.setObjectName("urlInput")
        self.url_input.setTabChangesFocus(True)
        self.url_input.document().setDocumentMargin(8)
        self.url_input.setFixedHeight(92)
        self.artist_input = self._line("ARTIST NAME")
        self.output_input = self._line("OUTPUT FOLDER")
        self.output_input.setReadOnly(True)
        choose = QPushButton("Choose Folder")
        choose.setObjectName("chooseButton")
        choose.setFixedHeight(36)
        choose.clicked.connect(self._choose_folder)

        form.addWidget(self._field_label("URLS"))
        form.addWidget(self.url_input)
        form.addSpacing(4)
        form.addWidget(self._field_label("ARTIST NAME"))
        form.addWidget(self.artist_input)
        form.addSpacing(4)
        form.addWidget(self._field_label("OUTPUT FOLDER"))

        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.setSpacing(10)
        output_row.addWidget(self.output_input, 1)
        output_row.addWidget(choose)
        form.addLayout(output_row)

        self.grab_button = QPushButton("GRAB")
        self.grab_button.setObjectName("grabButton")
        self.grab_button.setAutoDefault(False)
        self.grab_button.setDefault(False)
        self.grab_button.clicked.connect(self._start_grab)
        layout.addWidget(self.grab_button)

        self.footer = QLabel("URLS + ARTIST + OUTPUT")
        self.footer.setObjectName("footer")
        self.footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.footer)

        for screw_name in ("screwTL", "screwTR", "screwBL", "screwBR"):
            screw = QLabel("+", self.panel)
            screw.setObjectName(screw_name)
            screw.setAlignment(Qt.AlignCenter)
            screw.setFixedSize(0, 0)

    def _line(self, placeholder: str) -> QLineEdit:
        line = QLineEdit()
        line.setPlaceholderText("")
        line.setAccessibleName(placeholder)
        line.setFixedHeight(36)
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
                background: #000000;
            }
            #panel {
                border: 0px;
                border-radius: 0px;
                background: #000000;
            }
            #panel::disabled {
                background: #000000;
            }
            QLabel {
                color: #9d9688;
                font-size: 13px;
                font-weight: 800;
            }
            #unitLabel {
                color: #c53831;
                font-family: "Courier New", monospace;
                font-size: 15px;
                font-weight: 900;
            }
            #status {
                color: #aaa195;
                font-size: 14px;
                font-weight: 900;
            }
            #statusLed {
                border-radius: 5px;
                background: #c1372e;
            }
            #logo {
                color: #d8d0c0;
                font-size: 38px;
                font-weight: 900;
            }
            #fieldLabel {
                color: #9f988d;
                font-size: 13px;
                font-weight: 900;
            }
            QLineEdit, QPlainTextEdit {
                min-height: 34px;
                color: #e7dfcf;
                background: #050505;
                border: 2px solid #302d27;
                border-radius: 0px;
                font-family: "Courier New", monospace;
                font-size: 13px;
                font-weight: 700;
            }
            #urlInput {
                min-height: 92px;
                max-height: 92px;
            }
            QLineEdit:focus, QPlainTextEdit:focus {
                border: 2px solid #8d2a24;
            }
            QPushButton {
                min-height: 34px;
                color: #e7dfcf;
                background: #181716;
                border: 2px solid #343029;
                border-radius: 0px;
                font-size: 13px;
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
                min-width: 132px;
            }
            #grabButton {
                min-height: 64px;
                margin-top: 8px;
                color: #070707;
                background: #9e2e27;
                border: 2px solid #5c1b17;
                border-radius: 0px;
                font-size: 38px;
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
        urls = self._urls()
        if not urls:
            self._set_status("NO SOURCE")
            return
        if len(urls) > MAX_BATCH_ITEMS:
            self._set_status(f"{MAX_BATCH_ITEMS} MAX")
            self.footer.setText(f"{len(urls)} URLS")
            return

        self.grab_button.setEnabled(False)
        self._set_status("GRAB 0%")
        self.footer.setText(f"ACQUIRING {len(urls)} URLS")

        self.thread = QThread()
        self.worker = GrabWorker(
            output_dir=Path(output).expanduser(),
            artist_account=self.artist_input.text().strip(),
            urls=urls,
        )
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

    def _on_finished(
        self,
        success_count: int,
        error_count: int,
        skipped_count: int,
        errors: list[str],
    ) -> None:
        self.grab_button.setEnabled(True)
        if error_count:
            self._set_status("DONE ERR")
            summary = f"{success_count} OK / {error_count} ERR"
            if errors:
                self.footer.setText(errors[0].upper()[:110])
                self.footer.setToolTip("\n".join(errors))
                return
        else:
            self._set_status("DONE")
            summary = f"{success_count} OK"
        if skipped_count:
            summary = f"{summary} / {skipped_count} SKIP"
        self.footer.setText(summary)
        self.footer.setToolTip("")

    def _on_failed(self, message: str) -> None:
        self.grab_button.setEnabled(True)
        self._set_status("ERROR")
        self.footer.setText(message.upper()[:110])
        self.footer.setToolTip(message)
        self.status.setToolTip(message)

    def _clear_worker(self) -> None:
        self.worker = None
        self.thread = None

    def _urls(self) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for line in self.url_input.toPlainText().splitlines():
            url = line.strip()
            if not url or url in seen:
                continue
            seen.add(url)
            urls.append(url)
        return urls
