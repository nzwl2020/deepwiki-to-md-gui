#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Shared dependency bootstrap for CLI and GUI.
"""

from src.domain.export_models import CancellationToken, ProgressReporter
from src.gateway.file_adapter import FileAdapter
from src.gateway.html_adapter import HtmlAdapter
from src.gateway.markdown_adapter import MarkdownAdapter
from src.gateway.web_adapter import WebAdapter
from src.repository.file_repository import FileRepository
from src.repository.html_repository import HtmlRepository
from src.repository.markdown_repository import MarkdownRepository
from src.repository.web_repository import WebRepository
from src.usecase.chat_page_usecase import ConvertChatPageToMarkdownUsecase
from src.usecase.wiki_site_usecase import ConvertWikiSiteToMarkdownUsecase


def build_usecases(
    progress_callback=None,
    cancellation_token: CancellationToken | None = None,
    reporter_context: dict | None = None,
) -> dict:
    """
    Builds all usecases in one place.

    This keeps CLI and GUI from maintaining duplicated wiring logic.
    """
    reporter = ProgressReporter(progress_callback, default_context=reporter_context)
    cancellation_token = cancellation_token or CancellationToken()

    web_adapter = WebAdapter(
        progress_reporter=reporter,
        cancellation_token=cancellation_token,
    )
    html_adapter = HtmlAdapter()
    markdown_adapter = MarkdownAdapter()
    file_adapter = FileAdapter(progress_reporter=reporter)

    web_repository = WebRepository(web_adapter)
    html_repository = HtmlRepository(html_adapter)
    markdown_repository = MarkdownRepository(markdown_adapter)
    file_repository = FileRepository(file_adapter)

    return {
        "chat": ConvertChatPageToMarkdownUsecase(
            web_repository,
            html_repository,
            markdown_repository,
            file_repository,
            progress_reporter=reporter,
            cancellation_token=cancellation_token,
        ),
        "wiki": ConvertWikiSiteToMarkdownUsecase(
            web_repository,
            html_repository,
            markdown_repository,
            file_repository,
            progress_reporter=reporter,
            cancellation_token=cancellation_token,
        ),
    }
