#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Background worker for GUI exports.
"""

import asyncio

from PySide6.QtCore import QThread, Signal

from src.domain.export_models import (
    BatchExportResult,
    CancellationToken,
    ExportCancelledError,
    ExportTask,
    ProgressEvent,
    TaskOutcome,
)
from src.domain.url_parser import parse_deepwiki_url
from src.interface.bootstrap import build_usecases


class ExportWorker(QThread):
    """
    Runs queued exports in a background thread so the GUI stays responsive.
    """

    progress = Signal(object)
    task_finished = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, tasks: list[ExportTask]):
        super().__init__()
        self.tasks = tasks
        self.cancellation_token = CancellationToken()

    def cancel(self) -> None:
        """
        Signals the worker to stop after the current safe checkpoint.

        Playwright navigation is not interrupted mid-request, so cancellation is
        cooperative and takes effect between major export steps.
        """
        self.cancellation_token.cancel()

    def run(self) -> None:
        """
        Runs an isolated asyncio loop inside the worker thread.

        This avoids blocking the Qt main thread during Playwright work.
        """
        try:
            asyncio.run(self._run_exports())
        except Exception as exc:
            self.failed.emit(str(exc))

    async def _run_exports(self) -> None:
        outcomes: list[TaskOutcome] = []
        task_total = len(self.tasks)
        canceled = False

        for task_index, task in enumerate(self.tasks, 1):
            if self.cancellation_token.is_cancelled():
                canceled = True
                break

            self._emit_progress(
                ProgressEvent(
                    level="info",
                    message=f"Starting task {task_index}/{task_total}: {task.url}",
                    stage="queue",
                    task_index=task_index,
                    task_total=task_total,
                )
            )

            try:
                parsed = parse_deepwiki_url(task.url)
                usecases = build_usecases(
                    progress_callback=self._emit_progress,
                    cancellation_token=self.cancellation_token,
                    reporter_context={
                        "task_index": task_index,
                        "task_total": task_total,
                    },
                )
                result = await usecases[parsed.mode].execute(task)
                outcome = TaskOutcome(task=task, success=True, result=result)
            except ExportCancelledError as exc:
                canceled = True
                self._emit_progress(
                    ProgressEvent(
                        level="warning",
                        message=str(exc),
                        stage="canceled",
                        task_index=task_index,
                        task_total=task_total,
                    )
                )
                break
            except Exception as exc:
                outcome = TaskOutcome(
                    task=task,
                    success=False,
                    error_message=str(exc),
                )
                self._emit_progress(
                    ProgressEvent(
                        level="error",
                        message=f"Task failed for {task.url}: {exc}",
                        stage="failed",
                        task_index=task_index,
                        task_total=task_total,
                    )
                )

            outcomes.append(outcome)
            self.task_finished.emit(outcome)

        self.finished.emit(BatchExportResult(outcomes=outcomes, canceled=canceled))

    def _emit_progress(self, event: ProgressEvent) -> None:
        self.progress.emit(event)
