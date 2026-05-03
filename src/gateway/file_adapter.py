#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File adapter for file system operations.
"""

import os

from src.domain.export_models import ProgressReporter

# class FileAdapter:
#     """
#     Adapter for file system operations.
#     """

#     def write_file(self, filepath: str, content: str) -> None:
#         """
#         Writes content to a file.

#         Args:
#             filepath: The path to the file.
#             content: The content to write.
#         """
#         try:
#             with open(filepath, "w", encoding="utf-8") as f:
#                 f.write(content)
#             print(f"\n--- Content saved to {filepath} ---")
#         except IOError as e:
#             print(f"Error writing to file {filepath}: {e}")
#             raise

#     def create_directory(self, dir_path: str) -> None:
#         """
#         Creates a directory if it doesn't exist.

#         Args:
#             dir_path: The path to the directory.
#         """
#         try:
#             os.makedirs(dir_path, exist_ok=True)
#         except IOError as e:
#             print(f"Error creating directory {dir_path}: {e}")
#             raise

class FileAdapter:
    """
    Adapter for file system operations.
    """

    def __init__(self, progress_reporter: ProgressReporter | None = None):
        self.progress = progress_reporter or ProgressReporter()

    def write_file(self, filepath: str, content: str) -> None:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            # We keep file save notifications structured so the GUI log stays consistent.
            self.progress.info(f"Saved file: {filepath}")
        except IOError as exc:
            self.progress.error(f"Error writing to file {filepath}: {exc}")
            raise

    def create_directory(self, dir_path: str) -> None:
        try:
            os.makedirs(dir_path, exist_ok=True)
        except IOError as exc:
            self.progress.error(f"Error creating directory {dir_path}: {exc}")
            raise

    def read_file(self, filepath: str) -> str:
        """
        Reads content from a file.

        Args:
            filepath: The path to the file.

        Returns:
            The content of the file.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except IOError as e:
            print(f"Error reading file {filepath}: {e}")
            raise

    def file_exists(self, filepath: str) -> bool:
        """
        Checks if a file exists.

        Args:
            filepath: The path to the file.

        Returns:
            True if the file exists, False otherwise.
        """
        return os.path.isfile(filepath)

    def directory_exists(self, dir_path: str) -> bool:
        """
        Checks if a directory exists.

        Args:
            dir_path: The path to the directory.

        Returns:
            True if the directory exists, False otherwise.
        """
        return os.path.isdir(dir_path)
