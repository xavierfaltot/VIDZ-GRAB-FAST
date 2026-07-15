from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .grabber import GrabError, GrabRequest, grab


class DropZone(QFrame):
    local_file_dropped = Signal(object)
    url_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)
        top = QLabel("DROP VIDEO")
        middle = QLabel("OR")
        bottom = QLabel("DROP LINK")
        for label in (top, middle, bottom):
            label.setAlignment(Qt.AlignCenter)
            label.setObjectName("dropText")
            layout.addWidget(label)
        middle.setObjectName("dropOr")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            first = mime.urls()[0]
            if first.isLocalFile():
                self.local_file_dropped.emit(Path(first.toLocalFile()))
            else:
                self.url_dropped.emit(first.toString())
            event.acceptProposedAction()
            return
        text = mime.text().strip()
        if text:
            self.url_dropped.emit(text)
            event.acceptProposedAction()


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
        self.local_file: Path | None = None
        self.thread: QThread | None = None
        self.worker: GrabWorker | None = None
        self.setWindowTitle("VIDZ GRAB FAST")
        self.setMinimumSize(420, 640)
        self.resize(480, 720)
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

        panel = QFrame()
        panel.setObjectName("panel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        shell.addWidget(panel, alignment=Qt.AlignCenter)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(26, 26, 26, 22)
        layout.setSpacing(16)

        title = QLabel("VIDZ\nGRAB\nFAST")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.drop_zone = DropZone()
        self.drop_zone.local_file_dropped.connect(self._set_local_file)
        self.drop_zone.url_dropped.connect(self._set_url)
        layout.addWidget(self.drop_zone)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)
        layout.addLayout(form)

        self.url_input = self._line("URL")
        self.artist_input = self._line("ARTIST / ACCOUNT")
        self.output_input = self._line("OUTPUT FOLDER")
        self.output_input.setReadOnly(True)
        choose = QPushButton("Choose Folder")
        choose.clicked.connect(self._choose_folder)

        form.addWidget(QLabel("URL"), 0, 0)
        form.addWidget(self.url_input, 1, 0, 1, 2)
        form.addWidget(QLabel("ARTIST / ACCOUNT"), 2, 0)
        form.addWidget(self.artist_input, 3, 0, 1, 2)
        form.addWidget(QLabel("OUTPUT FOLDER"), 4, 0)
        form.addWidget(self.output_input, 5, 0)
        form.addWidget(choose, 5, 1)

        self.grab_button = QPushButton("GRAB")
        self.grab_button.setObjectName("grabButton")
        self.grab_button.clicked.connect(self._start_grab)
        layout.addWidget(self.grab_button)

        self.status = QLabel("READY")
        self.status.setObjectName("status")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

    def _line(self, placeholder: str) -> QLineEdit:
        line = QLineEdit()
        line.setPlaceholderText(placeholder)
        return line

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            * {
                font-family: "Arial", "Helvetica", sans-serif;
                letter-spacing: 0px;
            }
            #root {
                background: #050505;
            }
            #panel {
                min-width: 360px;
                max-width: 430px;
                border: 2px solid #4b463d;
                border-radius: 6px;
                background: #10100e;
            }
            #title {
                color: #d8d0c0;
                font-size: 46px;
                font-weight: 900;
                line-height: 0.88;
            }
            QLabel {
                color: #8d8578;
                font-size: 10px;
                font-weight: 800;
            }
            #dropZone {
                min-height: 168px;
                border: 2px solid #5b554a;
                border-radius: 4px;
                background: #161614;
            }
            #dropText {
                color: #d8d0c0;
                font-size: 24px;
                font-weight: 900;
            }
            #dropOr {
                color: #777064;
                font-size: 12px;
                font-weight: 900;
            }
            QLineEdit {
                min-height: 34px;
                padding: 0 10px;
                color: #e7dfcf;
                background: #050505;
                border: 1px solid #5b554a;
                border-radius: 3px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton {
                min-height: 34px;
                color: #e7dfcf;
                background: #24231f;
                border: 1px solid #5b554a;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #302e28;
            }
            QPushButton:disabled {
                color: #686157;
                background: #151513;
            }
            #grabButton {
                min-height: 62px;
                color: #080808;
                background: #d8d0c0;
                border: 0;
                font-size: 26px;
            }
            #status {
                color: #e74a3f;
                font-size: 13px;
                font-weight: 900;
            }
            """
        )

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "OUTPUT FOLDER")
        if folder:
            self.output_input.setText(folder)
            self._set_status("READY")

    def _set_local_file(self, path: Path) -> None:
        self.local_file = path
        self.url_input.clear()
        self._set_status(path.name.upper())

    def _set_url(self, url: str) -> None:
        self.local_file = None
        self.url_input.setText(url.strip())
        self._set_status("LINK READY")

    def _set_status(self, text: str) -> None:
        self.status.setText((text or "READY").upper())

    def _start_grab(self) -> None:
        output = self.output_input.text().strip()
        if not output:
            self._set_status("NO FOLDER")
            return
        source_url = self.url_input.text().strip()
        if not self.local_file and not source_url:
            self._set_status("NO SOURCE")
            return

        request = GrabRequest(
            output_dir=Path(output).expanduser(),
            artist_account=self.artist_input.text().strip(),
            local_file=self.local_file,
            source_url=source_url,
        )
        self.grab_button.setEnabled(False)
        self._set_status("GRAB 0%")

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
        self.local_file = None
        self._set_status("DONE")
        self.status.setToolTip(f"{video_path.name}\n{source_path.name}")

    def _on_failed(self, message: str) -> None:
        self.grab_button.setEnabled(True)
        self._set_status("ERROR")
        self.status.setToolTip(message)

    def _clear_worker(self) -> None:
        self.worker = None
        self.thread = None
