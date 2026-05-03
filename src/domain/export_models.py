#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Shared models for export progress and export results.
"""

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class ExportResult:
    """
    Represents the final export result for either chat or wiki mode.

    The GUI uses this to enable actions such as opening the output
    directory and summarizing what was generated.
    """

    mode: ExportMode
    output_dir: str
    markdown_files: list[str] = field(default_factory=list)
    image_dir: str | None = None
    item_count: int = 0


class ProgressReporter:
    """
    Thin wrapper around a callback so usecases and adapters can report
    progress without knowing who is listening.
    """

    def __init__(self, callback: Callable[[ProgressEvent], None] | None = None):
        self._callback = callback or (lambda event: None)

    def emit(self, level: ProgressLevel, message: str) -> None:
        self._callback(ProgressEvent(level=level, message=message))

    def info(self, message: str) -> None:
        self.emit("info", message)

    def warning(self, message: str) -> None:
        self.emit("warning", message)

    def error(self, message: str) -> None:
        self.emit("error", message)
