#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Usecase for converting a chat page to markdown.
"""

import os

from src.domain.entities import ChatLog
from src.domain.export_models import (
    CancellationToken,
    ExportTask,
    ExportResult,
    ProgressReporter,
)
from src.domain.url_parser import parse_deepwiki_url
from src.repository.file_repository import FileRepository
from src.repository.html_repository import HtmlRepository
from src.repository.markdown_repository import MarkdownRepository
from src.repository.web_repository import WebRepository

class ConvertChatPageToMarkdownUsecase:
    """
    Usecase for converting a web page's chat content to a Markdown document.
    """

    def __init__(
        self,
        web_repository: WebRepository,
        html_repository: HtmlRepository,
        markdown_repository: MarkdownRepository,
        file_repository: FileRepository,
        progress_reporter: ProgressReporter | None = None,
        cancellation_token: CancellationToken | None = None,
    ):
        self.web_repository = web_repository
        self.html_repository = html_repository
        self.markdown_repository = markdown_repository
        self.file_repository = file_repository
        # The reporter keeps UI concerns out of the usecase while still
        # making progress visible to CLI and GUI callers.
        self.progress = progress_reporter or ProgressReporter()
        self.cancellation_token = cancellation_token or CancellationToken()

    async def execute(self, task: ExportTask) -> ExportResult:
        self.cancellation_token.raise_if_cancelled()
        url = task.url
        output_base_dir = task.output_dir
        options = task.options
        parsed_url = parse_deepwiki_url(url)
        if parsed_url.mode != "chat":
            raise ValueError(f"Expected chat URL, got: {url}")

        self.progress.info("Starting chat export...", stage="prepare")
        self.progress.info(f"Target URL: {url}", stage="prepare")
        self.progress.info(
            f"Output Base Directory: {output_base_dir}",
            stage="prepare",
        )

        chat_id = parsed_url.identifier

        output_dir = os.path.join(output_base_dir, "chat", chat_id)
        images_dir = (
            os.path.join(output_dir, "images")
            if options.export_mermaid_diagrams
            else None
        )
        self.file_repository.ensure_directory(output_dir)
        if images_dir:
            self.file_repository.ensure_directory(images_dir)

        output_md_filepath = os.path.join(output_dir, "chat.md")
        self.progress.info(
            f"Output Markdown File: {output_md_filepath}",
            stage="prepare",
        )

        if options.incremental_export and self.file_repository.file_exists(output_md_filepath):
            self.progress.info(
                "Incremental export enabled. Existing chat markdown found, skipping regeneration.",
                stage="skip",
            )
            return ExportResult(
                mode="chat",
                source_url=url,
                output_dir=output_dir,
                markdown_files=[output_md_filepath],
                image_dir=images_dir,
                item_count=0,
                skipped_count=1,
                preferred_markdown_file=output_md_filepath,
            )

        self.cancellation_token.raise_if_cancelled()
        page_html = await self.web_repository.fetch_content(url)
        if not page_html:
            self.progress.error("Failed to retrieve page content.")
            raise RuntimeError("Failed to retrieve page content.")

        self.cancellation_token.raise_if_cancelled()
        self.progress.info("Page content retrieved. Parsing HTML...", stage="parse")
        chat_blocks = self.html_repository.extract_chat_blocks(
            page_html,
            output_dir,
            include_code_references=options.include_code_references,
            export_mermaid_diagrams=options.export_mermaid_diagrams,
        )

        if not chat_blocks:
            self.progress.error("No chat blocks found.")
            raise RuntimeError("No chat blocks found.")

        self.progress.info(
            f"Found {len(chat_blocks)} chat block(s).",
            stage="parse",
            item_current=len(chat_blocks),
            item_total=len(chat_blocks),
        )

        chat_log = ChatLog()
        for block_index, block in enumerate(chat_blocks, 1):
            self.cancellation_token.raise_if_cancelled()
            chat_log.add_chat_block(block)
            self.progress.info(
                f"Prepared chat block {block_index}/{len(chat_blocks)}.",
                stage="export",
                item_current=block_index,
                item_total=len(chat_blocks),
            )

        final_markdown = self.markdown_repository.convert_chat_log_to_markdown(chat_log)

        if not final_markdown.strip():
            self.progress.error("No content was extracted to Markdown.")
            raise RuntimeError("No content was extracted to Markdown.")

        self.cancellation_token.raise_if_cancelled()
        self.file_repository.save_markdown(final_markdown, output_md_filepath)

        self.progress.info(
            "Chat export completed successfully.",
            stage="completed",
            item_current=len(chat_blocks),
            item_total=len(chat_blocks),
        )
        return ExportResult(
            mode="chat",
            source_url=url,
            output_dir=output_dir,
            markdown_files=[output_md_filepath],
            image_dir=images_dir,
            item_count=len(chat_blocks),
            preferred_markdown_file=output_md_filepath,
        )
