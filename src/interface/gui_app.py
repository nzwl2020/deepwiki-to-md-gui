#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PySide6 GUI entry point for deepwiki-to-md.
"""

import os
import sys

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from src.domain.url_parser import parse_deepwiki_url
from src.interface.gui_worker import ExportWorker


class MainWindow(QMainWindow):
    """
    Single-window GUI focused on one export task at a time.

    The first version should optimize for stability and clarity
    rather than packing in advanced features too early.
    """

    def __init__(self):
        super().__init__()
        self.worker = None
        self.last_output_dir = None

        self.setWindowTitle("DeepWiki Exporter")
        self.resize(920, 700)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)

        form_group = QGroupBox("Export Settings")
        form_layout = QGridLayout(form_group)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "https://deepwiki.com/search/... or https://deepwiki.com/<org>/<repo>"
        )
        self.url_input.textChanged.connect(self._on_url_changed)

        self.mode_value = QLabel("Unknown")
        self.output_input = QLineEdit(os.path.abspath("./output"))

        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_output_dir)

        self.start_button = QPushButton("Start Export")
        self.start_button.clicked.connect(self._start_export)

        self.open_button = QPushButton("Open Output")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_output_dir)

        form_layout.addWidget(QLabel("URL"), 0, 0)
        form_layout.addWidget(self.url_input, 0, 1, 1, 3)
        form_layout.addWidget(QLabel("Mode"), 1, 0)
        form_layout.addWidget(self.mode_value, 1, 1, 1, 3)
        form_layout.addWidget(QLabel("Output Directory"), 2, 0)
        form_layout.addWidget(self.output_input, 2, 1, 1, 2)
        form_layout.addWidget(browse_button, 2, 3)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.open_button)

        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)


        root_layout.addWidget(form_group)
        root_layout.addLayout(button_layout)
        root_layout.addWidget(log_group)

        self.setCentralWidget(central)

    def _on_url_changed(self, text: str) -> None:
        """
        Gives immediate mode feedback without starting the export.

        This helps the user catch malformed URLs before a long-running task starts.
        """
        text = text.strip()
        if not text:
            self.mode_value.setText("Unknown")
            return

        try:
            parsed = parse_deepwiki_url(text)
            self.mode_value.setText(parsed.mode.upper())
        except Exception:
            self.mode_value.setText("Invalid URL")

    def _browse_output_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_input.text().strip() or os.getcwd(),
        )
        if selected:
            self.output_input.setText(selected)

    def _start_export(self) -> None:
        url = self.url_input.text().strip()
        output_dir = self.output_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a DeepWiki URL.")
            return

        if not output_dir:
            QMessageBox.warning(
                self,
                "Missing Output Directory",
                "Please choose an output directory.",
            )
            return

        try:
            parse_deepwiki_url(url)
        except Exception as exc:
            QMessageBox.critical(self, "Invalid URL", str(exc))
            return

        self.log_area.clear()
        self._append_log("info", f"Starting export for: {url}")

        self.start_button.setEnabled(False)
        self.open_button.setEnabled(False)

        self.worker = ExportWorker(url=url, output_dir=output_dir)
        self.worker.progress.connect(self._append_log)
        self.worker.finished.connect(self._handle_success)
        self.worker.failed.connect(self._handle_failure)
        self.worker.start()

    def _append_log(self, level: str, message: str) -> None:
        """
        Keeps the GUI log readable by preserving event levels.

        This is intentionally simple for MVP so failures remain easy to diagnose.
        """
        prefix = level.upper()
        self.log_area.appendPlainText(f"[{prefix}] {message}")

    def _handle_success(self, result) -> None:
        self.last_output_dir = result.output_dir
        self.start_button.setEnabled(True)
        self.open_button.setEnabled(True)

        summary = (
            f"Export completed.\n"
            f"Mode: {result.mode}\n"
            f"Output: {result.output_dir}\n"
            f"Items: {result.item_count}"
        )
        self._append_log("info", summary)
        QMessageBox.information(self, "Export Completed", summary)

    def _handle_failure(self, error_message: str) -> None:
        self.start_button.setEnabled(True)
        self._append_log("error", error_message)
        QMessageBox.critical(self, "Export Failed", error_message)

    def _open_output_dir(self) -> None:
        if not self.last_output_dir:
            return
        os.startfile(self.last_output_dir)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
