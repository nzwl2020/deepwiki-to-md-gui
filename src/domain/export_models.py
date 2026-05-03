#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Shared models for export progress and export results.
"""

from dataclasses import asdict, dataclass, field
from threading import Event
from typing import Callable, Literal


ProgressLevel = Literal["info", "warning", "error"]
ExportMode = Literal["chat", "wiki"]


@dataclass(frozen=True)
class ProgressEvent:
    """
    Represents a structured log/progress message.

    Using structured events keeps the GUI from having to parse
    free-form console output.
    """

    level: ProgressLevel
    message: str
    stage: str | None = None
    task_index: int | None = None
    task_total: int | None = None
    item_current: int | None = None
    item_total: int | None = None


@dataclass(frozen=True)
class ExportResult:
    """
    Represents the final export result for either chat or wiki mode.

    The GUI uses this to enable actions such as opening the output
    directory and summarizing what was generated.
    """

    mode: ExportMode
    source_url: str
    output_dir: str
    markdown_files: list[str] = field(default_factory=list)
    image_dir: str | None = None
    item_count: int = 0
    skipped_count: int = 0
    preferred_markdown_file: str | None = None

    @property
    def primary_markdown_file(self) -> str | None:
        """
        Returns the most relevant markdown file for preview actions.

        The GUI uses the first generated markdown file as the default preview
        target because it is the only file for chats and the index file for wikis.
        """
        if self.preferred_markdown_file:
            return self.preferred_markdown_file
        return self.markdown_files[0] if self.markdown_files else None


@dataclass(frozen=True)
class ExportOptions:
    """
    Represents task-level export options configured by the GUI.
    """

    incremental_export: bool = False
    include_code_references: bool = True
    export_mermaid_diagrams: bool = True
    generate_wiki_index: bool = True
    generate_merged_wiki: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExportTask:
    """
    Represents one GUI export request.
    """

    url: str
    output_dir: str
    options: ExportOptions = field(default_factory=ExportOptions)
    selected_wiki_page_urls: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_page_selection(self) -> bool:
        return bool(self.selected_wiki_page_urls)


@dataclass(frozen=True)
class TaskOutcome:
    """
    Captures the outcome of one export task inside a queue run.
    """

    task: ExportTask
    success: bool
    result: ExportResult | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class BatchExportResult:
    """
    Summarizes a queued export session.
    """

    outcomes: list[TaskOutcome] = field(default_factory=list)
    canceled: bool = False

    @property
    def successful_results(self) -> list[ExportResult]:
        return [outcome.result for outcome in self.outcomes if outcome.result]

    @property
    def failed_outcomes(self) -> list[TaskOutcome]:
        return [outcome for outcome in self.outcomes if not outcome.success]

    @property
    def last_successful_result(self) -> ExportResult | None:
        for outcome in reversed(self.outcomes):
            if outcome.result:
                return outcome.result
        return None


class ExportCancelledError(RuntimeError):
    """
    Raised when the user requests cancellation from the GUI.
    """


class CancellationToken:
    """
    Thread-safe cancellation token shared between the GUI and worker stack.
    """

    def __init__(self):
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise ExportCancelledError("Export canceled by user.")


class ProgressReporter:
    """
    Thin wrapper around a callback so usecases and adapters can report
    progress without knowing who is listening.
    """

    def __init__(
        self,
        callback: Callable[[ProgressEvent], None] | None = None,
        default_context: dict | None = None,
    ):
        self._callback = callback or (lambda event: None)
        self._default_context = default_context or {}

    def child(self, **context) -> "ProgressReporter":
        """
        Creates a new reporter that inherits the current callback and context.

        Child reporters let the worker inject queue metadata without forcing the
        usecases to know anything about GUI task orchestration.
        """
        merged_context = {**self._default_context, **context}
        return ProgressReporter(self._callback, default_context=merged_context)

    def emit(self, level: ProgressLevel, message: str, **context) -> None:
        merged_context = {**self._default_context, **context}
        self._callback(
            ProgressEvent(level=level, message=message, **merged_context)
        )

    def info(self, message: str, **context) -> None:
        self.emit("info", message, **context)

    def warning(self, message: str, **context) -> None:
        self.emit("warning", message, **context)

    def error(self, message: str, **context) -> None:
        self.emit("error", message, **context)
