from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from src.interface.gui_app import MarkdownPreviewBrowser, WikiPageSelectionDialog


def test_markdown_preview_browser_resolves_relative_markdown_links():
    app = QApplication.instance() or QApplication([])
    opened_paths: list[str] = []
    browser = MarkdownPreviewBrowser(opened_paths.append)

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        current_file = temp_path / "index.md"
        target_file = temp_path / "1-overview.md"
        current_file.write_text("# Index\n", encoding="utf-8")
        target_file.write_text("# Overview\n", encoding="utf-8")

        browser.document().setBaseUrl(QUrl.fromLocalFile(str(current_file)))
        browser.set_current_markdown_path(str(current_file))
        browser.setSource(QUrl("1-overview.md"))

        assert len(opened_paths) == 1
        assert Path(opened_paths[0]) == target_file


def test_markdown_preview_browser_handles_anchor_click_navigation():
    app = QApplication.instance() or QApplication([])
    opened_paths: list[str] = []
    browser = MarkdownPreviewBrowser(opened_paths.append)

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        current_file = temp_path / "index.md"
        target_file = temp_path / "1-overview.md"
        current_file.write_text("# Index\n", encoding="utf-8")
        target_file.write_text("# Overview\n", encoding="utf-8")

        browser.document().setBaseUrl(QUrl.fromLocalFile(str(current_file)))
        browser.set_current_markdown_path(str(current_file))
        browser._handle_anchor_clicked(QUrl("1-overview.md"))

        assert len(opened_paths) == 1
        assert Path(opened_paths[0]) == target_file


def test_wiki_page_outline_parses_deepwiki_numbering():
    outline, label = WikiPageSelectionDialog._page_outline(
        {
            "title": "Repository Structure",
            "url": "https://deepwiki.com/element-plus/element-plus/1.1-repository-structure",
        }
    )

    assert outline == ["1", "1"]
    assert label == "1.1 Repository Structure"


def test_wiki_page_outline_falls_back_for_unstructured_slug():
    outline, label = WikiPageSelectionDialog._page_outline(
        {
            "title": "Overview",
            "url": "https://deepwiki.com/element-plus/element-plus/overview",
        }
    )

    assert outline == []
    assert label == "Overview"
