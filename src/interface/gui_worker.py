#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Background worker for GUI exports.
"""

import asyncio

from PySide6.QtCore import QThread, Signal

from src.domain.export_models import ProgressEvent
from src.domain.url_parser import parse_deepwiki_url
from src.interface.bootstrap import build_usecases


class ExportWorker(QThread):
    """
    Runs the export in a background thread so the GUI stays responsive.
    """

    progress = Signal(str, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, url: str, output_dir: str):
        super().__init__()
        self.url = url
        self.output_dir = output_dir

    def run(self) -> None:
        """
        Runs an isolated asyncio loop inside the worker thread.

        This avoids blocking the Qt main thread during Playwright work.
        """
        try:
            asyncio.run(self._run_export())
        except Exception as exc:
            self.failed.emit(str(exc))

    async def _run_export(self) -> None:
        parsed = parse_deepwiki_url(self.url)
        usecases = build_usecases(progress_callback=self._emit_progress)
        usecase = usecases[parsed.mode]
        result = await usecase.execute(self.url, self.output_dir)
        self.finished.emit(result)

    def _emit_progress(self, event: ProgressEvent) -> None:
        self.progress.emit(event.level, event.message)
