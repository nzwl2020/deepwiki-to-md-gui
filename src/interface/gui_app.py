#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PySide6 GUI entry point for deepwiki-to-md.
"""

import asyncio
import json
import os
import socket
import sys
import tempfile
from datetime import datetime

from PySide6.QtCore import QSettings, QSignalBlocker, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.export_models import (
    BatchExportResult,
    CancellationToken,
    ExportOptions,
    ExportTask,
    ProgressEvent,
    TaskOutcome,
)
from src.domain.url_parser import parse_deepwiki_url
from src.interface.bootstrap import build_usecases
from src.interface.gui_worker import ExportWorker


class WikiPageSelectionDialog(QDialog):
    """
    Lets the user choose a subset of wiki pages before exporting.
    """

    def __init__(
        self,
        pages: list[dict[str, str]],
        selected_urls: set[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.pages = pages
        self._is_updating_tree = False

        self.setWindowTitle("Select Wiki Pages")
        self.resize(640, 520)

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(
            QLabel("Choose the wiki pages that should be exported for the current URL.")
        )

        control_layout = QHBoxLayout()
        select_all_button = QPushButton("Select All")
        select_all_button.clicked.connect(lambda: self._set_all_checked(True))
        control_layout.addWidget(select_all_button)

        clear_all_button = QPushButton("Clear All")
        clear_all_button.clicked.connect(lambda: self._set_all_checked(False))
        control_layout.addWidget(clear_all_button)
        control_layout.addStretch(1)
        root_layout.addLayout(control_layout)

        # Use a tree so the dialog mirrors the nested chapter structure
        # shown by DeepWiki's left-hand navigation.
        self.page_tree = QTreeWidget()
        self.page_tree.setHeaderHidden(True)
        self.page_tree.itemChanged.connect(self._on_tree_item_changed)
        self._populate_page_tree(selected_urls)
        self.page_tree.expandAll()
        root_layout.addWidget(self.page_tree)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._accept_if_valid)
        self.button_box.rejected.connect(self.reject)
        root_layout.addWidget(self.button_box)

    def _set_all_checked(self, checked: bool) -> None:
        state = Qt.Checked if checked else Qt.Unchecked
        blocker = QSignalBlocker(self.page_tree)
        try:
            for index in range(self.page_tree.topLevelItemCount()):
                self._set_tree_state(self.page_tree.topLevelItem(index), state)
        finally:
            del blocker

    @staticmethod
    def _page_outline(page: dict[str, str]) -> tuple[list[str], str]:
        """
        Parses the page number from the DeepWiki slug so the chooser can
        preserve the wiki hierarchy instead of flattening everything.
        """
        slug = page["url"].rstrip("/").split("/")[-1]
        number_part, separator, _ = slug.partition("-")
        if not separator or not number_part:
            return [], page["title"]

        outline = number_part.split(".")
        if not all(part.isdigit() for part in outline):
            return [], page["title"]

        return outline, f"{number_part} {page['title']}"

    def _populate_page_tree(self, selected_urls: set[str]) -> None:
        """
        Builds a chapter tree from URL prefixes such as 1, 1.1, and 2.3.4.
        """
        item_lookup: dict[tuple[str, ...], QTreeWidgetItem] = {}

        for page in self.pages:
            outline, label = self._page_outline(page)
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, page)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                0,
                Qt.Checked if page["url"] in selected_urls else Qt.Unchecked,
            )

            parent_item = item_lookup.get(tuple(outline[:-1])) if outline else None
            if parent_item is None:
                self.page_tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)

            if outline:
                item_lookup[tuple(outline)] = item

    def _set_tree_state(
        self,
        item: QTreeWidgetItem,
        state: Qt.CheckState,
    ) -> None:
        """
        Applies one state to a node and all of its descendants.
        """
        item.setCheckState(0, state)
        for child_index in range(item.childCount()):
            self._set_tree_state(item.child(child_index), state)

    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Propagates user changes downward while keeping page selection explicit.

        Parent entries in this dialog are real wiki pages, not synthetic folders,
        so we intentionally avoid forcing parent states from child selections.
        """
        if column != 0 or self._is_updating_tree:
            return

        self._is_updating_tree = True
        try:
            blocker = QSignalBlocker(self.page_tree)
            try:
                for child_index in range(item.childCount()):
                    self._set_tree_state(item.child(child_index), item.checkState(0))
            finally:
                del blocker
        finally:
            self._is_updating_tree = False

    def _accept_if_valid(self) -> None:
        if not self.selected_pages():
            QMessageBox.warning(
                self,
                "No Pages Selected",
                "Please keep at least one wiki page selected.",
            )
            return
        self.accept()

    def selected_pages(self) -> list[dict[str, str]]:
        selected = []

        def collect_checked_pages(item: QTreeWidgetItem) -> None:
            if item.checkState(0) == Qt.Checked:
                selected.append(item.data(0, Qt.UserRole))
            for child_index in range(item.childCount()):
                collect_checked_pages(item.child(child_index))

        for index in range(self.page_tree.topLevelItemCount()):
            collect_checked_pages(self.page_tree.topLevelItem(index))
        return selected


class MarkdownPreviewBrowser(QTextBrowser):
    """
    Resolves local Markdown links inside the preview pane.

    QTextBrowser can render Markdown content, but when a wiki index links to
    sibling files such as ``1-overview.md`` it does not know how to reload the
    preview through the application's Markdown loader. This browser delegates
    Markdown navigation back to the main window while preserving the default
    behavior for non-Markdown links.
    """

    def __init__(
        self,
        open_markdown_callback,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._open_markdown_callback = open_markdown_callback
        self._current_markdown_path: str | None = None
        # Handle navigation ourselves so local markdown links always route
        # through the app's preview loader instead of QTextBrowser's generic
        # document resolver.
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._handle_anchor_clicked)

    def set_current_markdown_path(self, markdown_path: str) -> None:
        """
        Stores the current Markdown file so fragment links stay within it.
        """
        self._current_markdown_path = markdown_path

    def setSource(self, name: QUrl, resource_type=None) -> None:
        """
        Redirects local Markdown navigation back through the preview loader.
        """
        if self._navigate_to_url(name):
            return
        resolved_url = self._resolve_url(name)
        if resource_type is None:
            super().setSource(resolved_url)
        else:
            super().setSource(resolved_url, resource_type)

    def _handle_anchor_clicked(self, url: QUrl) -> None:
        """
        Ensures clicks inside the preview use the same navigation rules.
        """
        if not self._navigate_to_url(url):
            QDesktopServices.openUrl(self._resolve_url(url))

    def _resolve_url(self, url: QUrl) -> QUrl:
        """
        Resolves relative links against the currently previewed markdown file.
        """
        if url.isRelative():
            return self.document().baseUrl().resolved(url)
        return url

    def _navigate_to_url(self, url: QUrl) -> bool:
        """
        Returns True when the preview handled the link internally.
        """
        if url.isEmpty():
            return False

        if not url.path() and url.fragment():
            self.scrollToAnchor(url.fragment())
            return True

        resolved_url = self._resolve_url(url)
        if resolved_url.isLocalFile():
            local_path = resolved_url.toLocalFile()
            if (
                resolved_url.fragment()
                and self._current_markdown_path
                and os.path.normcase(local_path)
                == os.path.normcase(self._current_markdown_path)
            ):
                self.scrollToAnchor(resolved_url.fragment())
                return True

            if local_path.lower().endswith(".md") and os.path.exists(local_path):
                self._open_markdown_callback(local_path)
                if resolved_url.fragment():
                    self.scrollToAnchor(resolved_url.fragment())
                return True

        return False


class MainWindow(QMainWindow):
    """
    Single-window GUI focused on export queues that remain easy to inspect.
    """

    HISTORY_LIMIT = 20

    def __init__(self):
        super().__init__()
        self.settings = QSettings("deepwiki-to-md-gui", "DeepWikiExporter")
        self.worker: ExportWorker | None = None
        self.history_entries: list[dict] = []
        self.wiki_page_selections: dict[str, tuple[str, ...]] = {}
        self.wiki_page_catalogs: dict[str, list[dict[str, str]]] = {}
        self.last_submitted_tasks: list[ExportTask] = []
        self.last_failed_tasks: list[ExportTask] = []
        self.last_output_dir: str | None = None
        self.last_preview_file: str | None = None
        self.completed_tasks_count = 0
        self.current_task_total = 0

        self.setWindowTitle("DeepWiki Exporter")
        self.resize(1280, 920)
        self._build_ui()
        self._load_persisted_state()
        self._run_environment_check(log_result=False)

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)

        form_group = QGroupBox("Export Queue")
        form_layout = QGridLayout(form_group)

        self.urls_input = QPlainTextEdit()
        self.urls_input.setPlaceholderText(
            "Paste one DeepWiki URL per line.\n"
            "Examples:\n"
            "https://deepwiki.com/search/...\n"
            "https://deepwiki.com/<org>/<repo>"
        )
        self.urls_input.textChanged.connect(self._on_urls_changed)

        self.mode_value = QLabel("Unknown")
        self.queue_value = QLabel("0 task(s)")
        self.env_value = QLabel("Checking...")
        self.output_input = QLineEdit(self._default_output_dir())
        self.output_input.editingFinished.connect(self._persist_output_directory)

        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_output_dir)

        self.self_check_button = QPushButton("Run Self-Check")
        self.self_check_button.clicked.connect(
            lambda: self._run_environment_check(log_result=True)
        )

        form_layout.addWidget(QLabel("URLs"), 0, 0, alignment=Qt.AlignTop)
        form_layout.addWidget(self.urls_input, 0, 1, 1, 3)
        form_layout.addWidget(QLabel("Mode Summary"), 1, 0)
        form_layout.addWidget(self.mode_value, 1, 1)
        form_layout.addWidget(QLabel("Queue Size"), 1, 2)
        form_layout.addWidget(self.queue_value, 1, 3)
        form_layout.addWidget(QLabel("Output Directory"), 2, 0)
        form_layout.addWidget(self.output_input, 2, 1, 1, 2)
        form_layout.addWidget(browse_button, 2, 3)
        form_layout.addWidget(QLabel("Environment"), 3, 0)
        form_layout.addWidget(self.env_value, 3, 1, 1, 2)
        form_layout.addWidget(self.self_check_button, 3, 3)

        options_group = QGroupBox("Export Options")
        options_layout = QGridLayout(options_group)

        self.incremental_checkbox = QCheckBox("Incremental export")
        self.incremental_checkbox.stateChanged.connect(self._persist_export_preferences)
        options_layout.addWidget(self.incremental_checkbox, 0, 0)

        self.generate_index_checkbox = QCheckBox("Generate wiki index")
        self.generate_index_checkbox.stateChanged.connect(self._persist_export_preferences)
        options_layout.addWidget(self.generate_index_checkbox, 0, 1)

        self.generate_merged_checkbox = QCheckBox("Generate merged wiki file")
        self.generate_merged_checkbox.stateChanged.connect(self._persist_export_preferences)
        options_layout.addWidget(self.generate_merged_checkbox, 0, 2)

        self.export_diagrams_checkbox = QCheckBox("Export Mermaid diagrams")
        self.export_diagrams_checkbox.stateChanged.connect(self._persist_export_preferences)
        options_layout.addWidget(self.export_diagrams_checkbox, 1, 0)

        self.include_code_refs_checkbox = QCheckBox("Include chat code references")
        self.include_code_refs_checkbox.stateChanged.connect(self._persist_export_preferences)
        options_layout.addWidget(self.include_code_refs_checkbox, 1, 1, 1, 2)

        self.page_filter_value = QLabel(
            "Enter exactly one wiki URL to choose a page subset."
        )
        self.select_wiki_pages_button = QPushButton("Select Wiki Pages")
        self.select_wiki_pages_button.clicked.connect(self._select_wiki_pages)
        self.clear_wiki_pages_button = QPushButton("Clear Page Filter")
        self.clear_wiki_pages_button.clicked.connect(self._clear_wiki_page_selection)

        options_layout.addWidget(QLabel("Wiki Page Filter"), 2, 0)
        options_layout.addWidget(self.page_filter_value, 2, 1)

        page_filter_button_layout = QHBoxLayout()
        page_filter_button_layout.addWidget(self.select_wiki_pages_button)
        page_filter_button_layout.addWidget(self.clear_wiki_pages_button)
        options_layout.addLayout(page_filter_button_layout, 2, 2)

        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Export")
        # Ignore the button's checked state so export startup always builds
        # tasks from the current URL list unless a retry flow passes them in.
        self.start_button.clicked.connect(lambda: self._start_export())
        button_layout.addWidget(self.start_button)

        self.cancel_button = QPushButton("Cancel Export")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_export)
        button_layout.addWidget(self.cancel_button)

        self.retry_button = QPushButton("Retry Failed")
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(self._retry_failed_tasks)
        button_layout.addWidget(self.retry_button)

        self.use_history_button = QPushButton("Use Selected History")
        self.use_history_button.setEnabled(False)
        self.use_history_button.clicked.connect(self._restore_selected_history)
        button_layout.addWidget(self.use_history_button)

        self.open_button = QPushButton("Open Output")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_output_dir)
        button_layout.addWidget(self.open_button)

        self.open_markdown_button = QPushButton("Open Markdown")
        self.open_markdown_button.setEnabled(False)
        self.open_markdown_button.clicked.connect(self._open_markdown_file)
        button_layout.addWidget(self.open_markdown_button)

        progress_group = QGroupBox("Progress")
        progress_layout = QGridLayout(progress_group)
        self.current_task_value = QLabel("Idle")
        self.current_stage_value = QLabel("Idle")
        self.current_action_value = QLabel("Waiting for work")
        self.queue_progress = QProgressBar()
        self.queue_progress.setFormat("%v/%m tasks")
        self.queue_progress.setRange(0, 1)
        self.queue_progress.setValue(0)
        self.item_progress = QProgressBar()
        self.item_progress.setFormat("%v/%m items")
        self.item_progress.setRange(0, 1)
        self.item_progress.setValue(0)

        progress_layout.addWidget(QLabel("Current Task"), 0, 0)
        progress_layout.addWidget(self.current_task_value, 0, 1)
        progress_layout.addWidget(QLabel("Current Stage"), 0, 2)
        progress_layout.addWidget(self.current_stage_value, 0, 3)
        progress_layout.addWidget(QLabel("Current Action"), 1, 0)
        progress_layout.addWidget(self.current_action_value, 1, 1, 1, 3)
        progress_layout.addWidget(QLabel("Queue Progress"), 2, 0)
        progress_layout.addWidget(self.queue_progress, 2, 1, 1, 3)
        progress_layout.addWidget(QLabel("Task Progress"), 3, 0)
        progress_layout.addWidget(self.item_progress, 3, 1, 1, 3)

        lower_splitter = QSplitter(Qt.Horizontal)

        history_group = QGroupBox("Export History")
        history_layout = QVBoxLayout(history_group)
        self.history_list = QListWidget()
        self.history_list.itemSelectionChanged.connect(
            self._on_history_selection_changed
        )
        self.history_list.itemDoubleClicked.connect(
            lambda _: self._restore_selected_history()
        )
        history_layout.addWidget(self.history_list)

        lower_splitter.addWidget(history_group)

        output_tabs = QTabWidget()

        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)
        output_tabs.addTab(log_tab, "Logs")

        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        self.preview_browser = MarkdownPreviewBrowser(self._load_preview)
        preview_layout.addWidget(self.preview_browser)
        output_tabs.addTab(preview_tab, "Preview")

        lower_splitter.addWidget(output_tabs)
        lower_splitter.setSizes([340, 900])

        root_layout.addWidget(form_group)
        root_layout.addWidget(options_group)
        root_layout.addLayout(button_layout)
        root_layout.addWidget(progress_group)
        root_layout.addWidget(lower_splitter, 1)

        self.setCentralWidget(central)

    def _default_output_dir(self) -> str:
        return os.path.abspath("./output")

    def _load_persisted_state(self) -> None:
        output_dir = self.settings.value("output_directory", self._default_output_dir())
        self.output_input.setText(str(output_dir))

        raw_history = self.settings.value("export_history", "[]")
        try:
            loaded_history = json.loads(raw_history)
        except (TypeError, json.JSONDecodeError):
            loaded_history = []

        if isinstance(loaded_history, list):
            self.history_entries = loaded_history[: self.HISTORY_LIMIT]

        raw_options = self.settings.value("export_options", "")
        try:
            options_data = json.loads(raw_options) if raw_options else {}
        except (TypeError, json.JSONDecodeError):
            options_data = {}
        self._apply_export_options(ExportOptions(**options_data))

        raw_selections = self.settings.value("wiki_page_selections", "{}")
        try:
            loaded_selections = json.loads(raw_selections)
        except (TypeError, json.JSONDecodeError):
            loaded_selections = {}

        if isinstance(loaded_selections, dict):
            self.wiki_page_selections = {
                str(url): tuple(selected_urls)
                for url, selected_urls in loaded_selections.items()
                if isinstance(selected_urls, list)
            }

        self._refresh_history_list()
        self._on_urls_changed()

    def _persist_output_directory(self) -> None:
        self.settings.setValue("output_directory", self.output_input.text().strip())

    def _persist_export_preferences(self) -> None:
        self.settings.setValue(
            "export_options",
            json.dumps(self._current_export_options().to_dict(), ensure_ascii=False),
        )
        self.settings.setValue(
            "wiki_page_selections",
            json.dumps(
                {
                    url: list(selected_urls)
                    for url, selected_urls in self.wiki_page_selections.items()
                },
                ensure_ascii=False,
            ),
        )
        self._update_wiki_page_controls()

    def _current_export_options(self) -> ExportOptions:
        return ExportOptions(
            incremental_export=self.incremental_checkbox.isChecked(),
            include_code_references=self.include_code_refs_checkbox.isChecked(),
            export_mermaid_diagrams=self.export_diagrams_checkbox.isChecked(),
            generate_wiki_index=self.generate_index_checkbox.isChecked(),
            generate_merged_wiki=self.generate_merged_checkbox.isChecked(),
        )

    def _apply_export_options(self, options: ExportOptions) -> None:
        self.incremental_checkbox.setChecked(options.incremental_export)
        self.include_code_refs_checkbox.setChecked(options.include_code_references)
        self.export_diagrams_checkbox.setChecked(options.export_mermaid_diagrams)
        self.generate_index_checkbox.setChecked(options.generate_wiki_index)
        self.generate_merged_checkbox.setChecked(options.generate_merged_wiki)

    def _on_urls_changed(self) -> None:
        urls = self._collect_urls()
        valid_modes = []
        invalid_count = 0

        for url in urls:
            try:
                valid_modes.append(parse_deepwiki_url(url).mode)
            except Exception:
                invalid_count += 1

        self.queue_value.setText(f"{len(urls)} task(s)")

        if not urls:
            self.mode_value.setText("Unknown")
            self._update_wiki_page_controls()
            return

        unique_modes = sorted(set(valid_modes))
        mode_labels = {"chat": "CHAT", "wiki": "WIKI"}

        if invalid_count and not valid_modes:
            summary = f"{invalid_count} invalid"
        elif invalid_count:
            joined_modes = ", ".join(
                mode_labels.get(mode, mode.upper()) for mode in unique_modes
            )
            summary = f"{joined_modes} with {invalid_count} invalid"
        elif len(unique_modes) == 1:
            summary = mode_labels.get(unique_modes[0], unique_modes[0].upper())
        else:
            summary = "MIXED"

        self.mode_value.setText(summary)
        self._update_wiki_page_controls()

    def _collect_urls(self) -> list[str]:
        return [
            line.strip()
            for line in self.urls_input.toPlainText().splitlines()
            if line.strip()
        ]

    def _current_single_wiki_url(self) -> str | None:
        urls = self._collect_urls()
        if len(urls) != 1:
            return None

        try:
            parsed = parse_deepwiki_url(urls[0])
        except Exception:
            return None

        return urls[0] if parsed.mode == "wiki" else None

    def _update_wiki_page_controls(self) -> None:
        current_wiki_url = self._current_single_wiki_url()
        if current_wiki_url:
            selected_urls = self.wiki_page_selections.get(current_wiki_url, ())
            catalog = self.wiki_page_catalogs.get(current_wiki_url, [])
            if selected_urls:
                if catalog:
                    self.page_filter_value.setText(
                        f"{len(selected_urls)}/{len(catalog)} page(s) selected for the current wiki URL."
                    )
                else:
                    self.page_filter_value.setText(
                        f"{len(selected_urls)} stored page filter(s) for the current wiki URL."
                    )
            else:
                self.page_filter_value.setText(
                    "All wiki pages will be exported for the current wiki URL."
                )
            self.select_wiki_pages_button.setEnabled(True)
            self.clear_wiki_pages_button.setEnabled(bool(selected_urls))
            return

        stored_filter_count = len(self.wiki_page_selections)
        if stored_filter_count:
            self.page_filter_value.setText(
                f"Stored page filters exist for {stored_filter_count} wiki URL(s). Enter one wiki URL to edit a filter."
            )
        else:
            self.page_filter_value.setText(
                "Enter exactly one wiki URL to choose a page subset."
            )
        self.select_wiki_pages_button.setEnabled(False)
        self.clear_wiki_pages_button.setEnabled(False)

    def _collect_tasks(self) -> tuple[list[ExportTask], list[str]]:
        output_dir = self.output_input.text().strip()
        tasks: list[ExportTask] = []
        errors: list[str] = []
        options = self._current_export_options()

        for line_number, url in enumerate(self._collect_urls(), 1):
            try:
                parsed = parse_deepwiki_url(url)
            except Exception as exc:
                errors.append(f"Line {line_number}: {exc}")
                continue

            selected_wiki_page_urls = (
                self.wiki_page_selections.get(url, ())
                if parsed.mode == "wiki"
                else ()
            )
            tasks.append(
                ExportTask(
                    url=url,
                    output_dir=output_dir,
                    options=options,
                    selected_wiki_page_urls=selected_wiki_page_urls,
                )
            )

        return tasks, errors

    def _browse_output_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_input.text().strip() or os.getcwd(),
        )
        if selected:
            self.output_input.setText(selected)
            self._persist_output_directory()
            self._run_environment_check(log_result=False)

    def _select_wiki_pages(self) -> None:
        wiki_url = self._current_single_wiki_url()
        if not wiki_url:
            QMessageBox.information(
                self,
                "Wiki Page Filter",
                "Enter exactly one valid wiki URL before choosing wiki pages.",
            )
            return

        self.current_stage_value.setText("Discover")
        self.current_action_value.setText("Loading wiki pages for selection")
        self._append_log_line("info", f"Loading wiki pages for selection: {wiki_url}")
        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            usecases = build_usecases(
                progress_callback=None,
                cancellation_token=CancellationToken(),
            )
            pages = asyncio.run(usecases["wiki"].discover_navigation(wiki_url))
        except Exception as exc:
            self._append_log_line(
                "error",
                f"Failed to discover wiki pages for {wiki_url}: {exc}",
            )
            QMessageBox.critical(
                self,
                "Wiki Discovery Failed",
                str(exc),
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.wiki_page_catalogs[wiki_url] = pages
        existing_selection = set(
            self.wiki_page_selections.get(
                wiki_url,
                tuple(page["url"] for page in pages),
            )
        )

        dialog = WikiPageSelectionDialog(
            pages=pages,
            selected_urls=existing_selection,
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            self.current_stage_value.setText("Idle")
            self.current_action_value.setText("Wiki page selection canceled")
            return

        selected_pages = dialog.selected_pages()
        selected_urls = tuple(page["url"] for page in selected_pages)

        if len(selected_urls) == len(pages):
            # Storing no filter is simpler than keeping a full-page allowlist.
            self.wiki_page_selections.pop(wiki_url, None)
            self._append_log_line(
                "info",
                f"Wiki page filter cleared because all {len(pages)} page(s) were selected.",
            )
        else:
            self.wiki_page_selections[wiki_url] = selected_urls
            self._append_log_line(
                "info",
                f"Selected {len(selected_urls)} wiki page(s) for {wiki_url}.",
            )

        self._persist_export_preferences()
        self._update_wiki_page_controls()
        self.current_stage_value.setText("Ready")
        self.current_action_value.setText("Wiki page selection updated")

    def _clear_wiki_page_selection(self) -> None:
        wiki_url = self._current_single_wiki_url()
        if not wiki_url:
            return

        self.wiki_page_selections.pop(wiki_url, None)
        self._persist_export_preferences()
        self._append_log_line("info", f"Cleared wiki page filter for {wiki_url}.")
        self._update_wiki_page_controls()

    def _start_export(self, tasks: list[ExportTask] | None = None) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self,
                "Export Running",
                "Please wait for the current queue to finish or cancel it first.",
            )
            return

        output_dir = self.output_input.text().strip()
        if not output_dir:
            QMessageBox.warning(
                self,
                "Missing Output Directory",
                "Please choose an output directory.",
            )
            return

        if tasks is None:
            tasks, errors = self._collect_tasks()
            if errors:
                QMessageBox.critical(
                    self,
                    "Invalid URL List",
                    "\n".join(errors[:10]),
                )
                return
        else:
            errors = []

        if not tasks:
            QMessageBox.warning(
                self,
                "Missing URL",
                "Please enter at least one valid DeepWiki URL.",
            )
            return

        self._persist_output_directory()
        self._persist_export_preferences()
        self.last_submitted_tasks = list(tasks)
        self.last_failed_tasks = []
        self.last_output_dir = None
        self.last_preview_file = None
        self.completed_tasks_count = 0
        self.current_task_total = len(tasks)
        self.queue_progress.setRange(0, max(len(tasks), 1))
        self.queue_progress.setValue(0)
        self.item_progress.setRange(0, 1)
        self.item_progress.setValue(0)
        self.current_task_value.setText(f"0/{len(tasks)}")
        self.current_stage_value.setText("Queued")
        self.current_action_value.setText("Preparing export queue")
        self.log_area.clear()
        self.preview_browser.setMarkdown(
            "## Preview Pending\n\nThe latest successful export will appear here."
        )
        self._append_log_line("info", f"Queued {len(tasks)} export task(s).")
        self._append_log_line(
            "info",
            f"Active options: {self._format_options_summary(tasks[0].options)}",
        )
        for task in tasks:
            page_filter_note = (
                f" | wiki pages: {len(task.selected_wiki_page_urls)} selected"
                if task.selected_wiki_page_urls
                else ""
            )
            self._append_log_line(
                "info",
                f"Queued URL: {task.url}{page_filter_note}",
            )

        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.retry_button.setEnabled(False)
        self.use_history_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.open_markdown_button.setEnabled(False)

        self.worker = ExportWorker(tasks=tasks)
        self.worker.progress.connect(self._append_progress)
        self.worker.task_finished.connect(self._handle_task_finished)
        self.worker.finished.connect(self._handle_batch_finished)
        self.worker.failed.connect(self._handle_fatal_failure)
        self.worker.start()

    def _cancel_export(self) -> None:
        if not self.worker or not self.worker.isRunning():
            return

        self.worker.cancel()
        self.cancel_button.setEnabled(False)
        self.current_stage_value.setText("Cancel Requested")
        self.current_action_value.setText(
            "Waiting for the current step to stop safely"
        )
        self._append_log_line("warning", "Cancellation requested by user.")

    def _retry_failed_tasks(self) -> None:
        if not self.last_failed_tasks:
            QMessageBox.information(
                self,
                "Nothing to Retry",
                "No failed tasks are available.",
            )
            return

        self._start_export(tasks=list(self.last_failed_tasks))

    def _append_progress(self, event: ProgressEvent) -> None:
        task_prefix = ""
        if event.task_index is not None and event.task_total is not None:
            task_prefix = f"Task {event.task_index}/{event.task_total} "
            self.current_task_value.setText(f"{event.task_index}/{event.task_total}")
            self.queue_progress.setRange(0, max(event.task_total, 1))

        if event.stage:
            self.current_stage_value.setText(event.stage.replace("_", " ").title())

        if event.item_total is not None and event.item_total > 0:
            self.item_progress.setRange(0, max(event.item_total, 1))
            self.item_progress.setValue(min(event.item_current or 0, event.item_total))
        elif event.stage in {"prepare", "queue"}:
            # An indeterminate bar communicates that work has started before the
            # exporter discovers the actual number of pages or chat blocks.
            self.item_progress.setRange(0, 0)

        self.current_action_value.setText(event.message)
        if event.stage == "completed" and event.item_total:
            self.item_progress.setRange(0, event.item_total)
            self.item_progress.setValue(event.item_total)

        log_message = f"{task_prefix}{event.message}".strip()
        self._append_log_line(event.level, log_message)

    def _append_log_line(self, level: str, message: str) -> None:
        prefix = level.upper()
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.appendPlainText(f"{timestamp} [{prefix}] {message}")

    def _handle_task_finished(self, outcome: TaskOutcome) -> None:
        self.completed_tasks_count += 1
        self.queue_progress.setValue(
            min(self.completed_tasks_count, self.current_task_total)
        )

        if outcome.success and outcome.result:
            result = outcome.result
            self.last_output_dir = result.output_dir
            self.last_preview_file = result.primary_markdown_file
            self.open_button.setEnabled(True)
            self.open_markdown_button.setEnabled(bool(self.last_preview_file))

            detail_parts = [f"Processed {result.item_count} item(s)"]
            if result.skipped_count:
                detail_parts.append(f"reused {result.skipped_count} existing item(s)")
            detail_summary = "; ".join(detail_parts)

            self._append_log_line(
                "info",
                f"Finished {result.mode} export for {result.source_url}. {detail_summary}.",
            )

            if self.last_preview_file:
                self._load_preview(self.last_preview_file)
        else:
            self._append_log_line(
                "error",
                f"Failed export for {outcome.task.url}: {outcome.error_message}",
            )

        self._record_history(outcome)

    def _handle_batch_finished(self, batch_result: BatchExportResult) -> None:
        self.worker = None
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.use_history_button.setEnabled(bool(self.history_list.selectedItems()))
        self.last_failed_tasks = [
            outcome.task for outcome in batch_result.failed_outcomes
        ]
        self.retry_button.setEnabled(bool(self.last_failed_tasks))
        self.open_button.setEnabled(bool(self.last_output_dir))
        self.open_markdown_button.setEnabled(bool(self.last_preview_file))

        success_count = len(batch_result.successful_results)
        failure_count = len(batch_result.failed_outcomes)
        total_skipped = sum(
            result.skipped_count for result in batch_result.successful_results
        )
        canceled_suffix = " The queue was canceled." if batch_result.canceled else ""
        skip_suffix = f" Reused existing items: {total_skipped}." if total_skipped else ""
        summary = (
            f"Queue finished. Success: {success_count}. Failed: {failure_count}."
            f"{skip_suffix}{canceled_suffix}"
        )
        self.current_stage_value.setText(
            "Canceled" if batch_result.canceled else "Completed"
        )
        self.current_action_value.setText(summary)
        self._append_log_line("info", summary)

        if batch_result.canceled:
            QMessageBox.warning(self, "Export Canceled", summary)
        elif failure_count:
            QMessageBox.warning(self, "Export Completed with Errors", summary)
        else:
            QMessageBox.information(self, "Export Completed", summary)

    def _handle_fatal_failure(self, error_message: str) -> None:
        self.worker = None
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.retry_button.setEnabled(bool(self.last_failed_tasks))
        self.use_history_button.setEnabled(bool(self.history_list.selectedItems()))
        self._append_log_line("error", error_message)
        self.current_stage_value.setText("Failed")
        self.current_action_value.setText(error_message)
        QMessageBox.critical(self, "Export Failed", error_message)

    def _record_history(self, outcome: TaskOutcome) -> None:
        mode = None
        item_count = 0
        skipped_count = 0
        preview_file = None
        if outcome.result:
            mode = outcome.result.mode
            item_count = outcome.result.item_count
            skipped_count = outcome.result.skipped_count
            preview_file = outcome.result.primary_markdown_file
        else:
            try:
                mode = parse_deepwiki_url(outcome.task.url).mode
            except Exception:
                mode = "unknown"

        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": outcome.task.url,
            "output_dir": outcome.task.output_dir,
            "success": outcome.success,
            "mode": mode,
            "item_count": item_count,
            "skipped_count": skipped_count,
            "preview_file": preview_file,
            "error_message": outcome.error_message,
            "options": outcome.task.options.to_dict(),
            "selected_wiki_page_urls": list(outcome.task.selected_wiki_page_urls),
        }

        self.history_entries.insert(0, entry)
        self.history_entries = self.history_entries[: self.HISTORY_LIMIT]
        self.settings.setValue(
            "export_history",
            json.dumps(self.history_entries, ensure_ascii=False),
        )
        self._refresh_history_list()

    def _refresh_history_list(self) -> None:
        self.history_list.clear()

        for entry in self.history_entries:
            status = "OK" if entry.get("success") else "FAIL"
            mode = str(entry.get("mode", "unknown")).upper()
            item_count = entry.get("item_count", 0)
            skipped_count = entry.get("skipped_count", 0)
            filter_count = len(entry.get("selected_wiki_page_urls", []))
            filter_suffix = (
                f" | filter: {filter_count}"
                if filter_count
                else ""
            )
            skipped_suffix = f" | reused: {skipped_count}" if skipped_count else ""
            label = (
                f"[{status}] {entry.get('timestamp', '')} | {mode} | "
                f"{item_count} item(s){skipped_suffix}{filter_suffix} | {entry.get('url', '')}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entry)
            self.history_list.addItem(item)

    def _on_history_selection_changed(self) -> None:
        self.use_history_button.setEnabled(bool(self.history_list.selectedItems()))

    def _restore_selected_history(self) -> None:
        selected_items = self.history_list.selectedItems()
        if not selected_items:
            return

        entry = selected_items[0].data(Qt.UserRole) or {}
        self.urls_input.setPlainText(entry.get("url", ""))
        self.output_input.setText(entry.get("output_dir", self._default_output_dir()))

        options_data = entry.get("options", {})
        try:
            self._apply_export_options(ExportOptions(**options_data))
        except TypeError:
            self._apply_export_options(ExportOptions())

        restored_url = entry.get("url", "")
        selected_wiki_page_urls = entry.get("selected_wiki_page_urls", [])
        if selected_wiki_page_urls:
            self.wiki_page_selections[restored_url] = tuple(selected_wiki_page_urls)
        else:
            self.wiki_page_selections.pop(restored_url, None)

        self._persist_output_directory()
        self._persist_export_preferences()
        self._on_urls_changed()

        preview_file = entry.get("preview_file")
        if preview_file and os.path.exists(preview_file):
            self.last_preview_file = preview_file
            self._load_preview(preview_file)
            self.open_markdown_button.setEnabled(True)
        else:
            self.last_preview_file = None
            self.open_markdown_button.setEnabled(False)
            self.preview_browser.setMarkdown(
                "## No Preview Available\n\nThe selected history entry does not have a saved markdown preview."
            )

        output_dir = entry.get("output_dir")
        if output_dir and os.path.isdir(output_dir):
            self.last_output_dir = output_dir
            self.open_button.setEnabled(True)
        else:
            self.last_output_dir = None
            self.open_button.setEnabled(False)

    def _load_preview(self, markdown_path: str) -> None:
        try:
            with open(markdown_path, "r", encoding="utf-8") as markdown_file:
                markdown_content = markdown_file.read()
        except OSError as exc:
            self.preview_browser.setMarkdown(
                f"## Preview Error\n\nUnable to open `{markdown_path}`.\n\n{exc}"
            )
            return

        # Use the current markdown file as the base URL so sibling markdown
        # files and in-document anchors can both resolve correctly.
        self.preview_browser.document().setBaseUrl(QUrl.fromLocalFile(markdown_path))
        self.preview_browser.setMarkdown(markdown_content)
        self.preview_browser.set_current_markdown_path(markdown_path)
        self.last_preview_file = markdown_path
        self.open_markdown_button.setEnabled(True)

    def _open_output_dir(self) -> None:
        if self.last_output_dir:
            os.startfile(self.last_output_dir)

    def _open_markdown_file(self) -> None:
        if self.last_preview_file and os.path.exists(self.last_preview_file):
            os.startfile(self.last_preview_file)

    def _run_environment_check(self, log_result: bool) -> None:
        checks = [
            self._check_playwright_environment(),
            self._check_output_directory(),
            self._check_network_access(),
        ]

        overall_ok = all(status == "OK" for status, _ in checks)
        summary = "Ready" if overall_ok else "Needs Attention"
        details = " | ".join(
            f"{name}: {status}"
            for name, (status, _) in zip(["Chromium", "Output", "Network"], checks)
        )
        self.env_value.setText(f"{summary} ({details})")

        if log_result:
            for name, (status, message) in zip(
                ["Chromium", "Output", "Network"], checks
            ):
                level = "info" if status == "OK" else "warning"
                self._append_log_line(level, f"Self-check {name}: {message}")

    def _check_playwright_environment(self) -> tuple[str, str]:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                chromium_path = playwright.chromium.executable_path

            if chromium_path and os.path.exists(chromium_path):
                return "OK", f"Chromium is available at {chromium_path}"

            return "WARN", "Chromium is not installed for Playwright."
        except Exception as exc:
            return "WARN", f"Unable to verify Playwright Chromium: {exc}"

    def _check_output_directory(self) -> tuple[str, str]:
        output_dir = self.output_input.text().strip() or self._default_output_dir()

        try:
            os.makedirs(output_dir, exist_ok=True)
            temp_file = tempfile.NamedTemporaryFile(dir=output_dir, delete=False)
            temp_path = temp_file.name
            temp_file.close()
            os.remove(temp_path)
            return "OK", f"Output directory is writable: {output_dir}"
        except OSError as exc:
            return "WARN", f"Output directory is not writable: {exc}"

    def _check_network_access(self) -> tuple[str, str]:
        try:
            with socket.create_connection(("deepwiki.com", 443), timeout=3):
                return "OK", "Network access to deepwiki.com is available."
        except OSError as exc:
            return "WARN", f"Unable to reach deepwiki.com: {exc}"

    def _format_options_summary(self, options: ExportOptions) -> str:
        flags = []
        if options.incremental_export:
            flags.append("incremental")
        if options.generate_wiki_index:
            flags.append("wiki-index")
        if options.generate_merged_wiki:
            flags.append("wiki-merged")
        if options.export_mermaid_diagrams:
            flags.append("mermaid")
        if options.include_code_references:
            flags.append("code-references")
        return ", ".join(flags) if flags else "default"

    def closeEvent(self, event) -> None:
        self._persist_output_directory()
        self._persist_export_preferences()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
