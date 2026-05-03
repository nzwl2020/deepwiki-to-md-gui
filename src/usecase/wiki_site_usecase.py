#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Usecase for converting a wiki site to markdown.
"""

import os

from src.domain.entities import WikiPage, WikiSite
from src.domain.export_models import (
    CancellationToken,
    ExportTask,
    ExportResult,
    ProgressReporter,
)
from src.repository.file_repository import FileRepository
from src.repository.html_repository import HtmlRepository
from src.repository.markdown_repository import MarkdownRepository
from src.repository.web_repository import WebRepository


class ConvertWikiSiteToMarkdownUsecase:
    """
    Usecase for converting a DeepWiki site to a collection of Markdown documents.
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
        self.progress = progress_reporter or ProgressReporter()
        self.cancellation_token = cancellation_token or CancellationToken()

    async def discover_navigation(self, url: str) -> list[dict[str, str]]:
        """
        Fetches and parses the top-level wiki navigation for page selection.
        """
        self.cancellation_token.raise_if_cancelled()
        self.progress.info("Loading wiki navigation for page selection...", stage="discover")
        main_page_html = await self.web_repository.fetch_content(url)
        if not main_page_html:
            raise RuntimeError("Failed to retrieve main wiki page.")

        navigation_links = self.html_repository.extract_wiki_navigation(main_page_html)
        if not navigation_links:
            raise RuntimeError("No navigation links found.")

        return navigation_links

    async def execute(self, task: ExportTask) -> ExportResult:
        self.cancellation_token.raise_if_cancelled()
        url = task.url
        output_base_dir = task.output_dir
        options = task.options
        self.progress.info("Starting wiki export...", stage="prepare")
        self.progress.info(f"Target URL: {url}", stage="prepare")
        self.progress.info(
            f"Output Base Directory: {output_base_dir}",
            stage="prepare",
        )

        wiki_site = WikiSite.from_url(url)
        self.progress.info(
            f"Processing wiki for {wiki_site.organization}/{wiki_site.repository}",
            stage="prepare",
        )

        output_dir = wiki_site.get_output_directory(output_base_dir)
        images_dir = (
            os.path.join(output_dir, "images")
            if options.export_mermaid_diagrams
            else None
        )
        self.file_repository.ensure_directory(output_dir)
        if images_dir:
            self.file_repository.ensure_directory(images_dir)

        self.progress.info(f"Output directory: {output_dir}", stage="prepare")
        if images_dir:
            self.progress.info(f"Images directory: {images_dir}", stage="prepare")

        discovered_links = await self.discover_navigation(url)
        navigation_links = [
            {
                "title": link["title"],
                "url": link["url"],
                # The original page number is preserved so selective exports
                # keep stable filenames and work better with incremental mode.
                "page_number": index,
            }
            for index, link in enumerate(discovered_links, 1)
        ]
        selected_urls = set(task.selected_wiki_page_urls)
        if selected_urls:
            navigation_links = [
                link for link in navigation_links if link["url"] in selected_urls
            ]
            self.progress.info(
                f"Filtered wiki export to {len(navigation_links)} selected page(s).",
                stage="discover",
                item_current=0,
                item_total=len(navigation_links),
            )
            if not navigation_links:
                raise RuntimeError("The selected wiki pages no longer match the current navigation.")

        self.progress.info(
            f"Found {len(navigation_links)} wiki pages.",
            stage="discover",
            item_current=0,
            item_total=len(navigation_links),
        )
        markdown_files: list[str] = []
        merged_page_documents: list[tuple[WikiPage, str]] = []
        skipped_count = 0
        preview_file: str | None = None

        for progress_index, page_link in enumerate(navigation_links, 1):
            self.cancellation_token.raise_if_cancelled()
            page_url = page_link["url"]
            page_title = page_link["title"]
            page_number = page_link["page_number"]
            planned_page = WikiPage(
                title=page_title,
                content="",
                url=page_url,
                page_number=page_number,
            )
            page_filename = planned_page.get_filename()
            page_filepath = os.path.join(output_dir, page_filename)

            self.progress.info(
                f"Processing page {progress_index}/{len(navigation_links)}: {page_title}",
                stage="export",
                item_current=progress_index,
                item_total=len(navigation_links),
            )

            if options.incremental_export and self.file_repository.file_exists(page_filepath):
                existing_markdown = None
                if options.generate_merged_wiki:
                    try:
                        existing_markdown = self.file_repository.read_file(page_filepath)
                    except OSError as exc:
                        self.progress.warning(
                            (
                                f"Existing markdown for {page_title} could not be read "
                                f"({exc}). The page will be regenerated."
                            ),
                            stage="skip",
                            item_current=progress_index,
                            item_total=len(navigation_links),
                        )

                if existing_markdown is not None or not options.generate_merged_wiki:
                    skipped_count += 1
                    self.progress.info(
                        f"Incremental export enabled. Reusing existing file for {page_title}.",
                        stage="skip",
                        item_current=progress_index,
                        item_total=len(navigation_links),
                    )
                    wiki_site.add_page(planned_page)
                    markdown_files.append(page_filepath)
                    if existing_markdown is not None:
                        merged_page_documents.append((planned_page, existing_markdown))
                    continue

            page_html = await self.web_repository.fetch_content(page_url)
            if not page_html:
                self.progress.warning(f"Failed to retrieve page: {page_title}. Skipping.")
                continue

            wiki_page = self.html_repository.extract_wiki_page(
                page_html,
                title=page_title,
                url=page_url,
                page_number=page_number,
                output_dir=output_dir,
            )

            processed_content = self.html_repository.process_wiki_page_content(
                wiki_page,
                output_dir,
                export_mermaid_diagrams=options.export_mermaid_diagrams,
            )

            markdown_content = self.markdown_repository.convert_wiki_to_markdown(
                wiki_page, processed_content
            )

            self.file_repository.save_markdown(markdown_content, page_filepath)
            markdown_files.append(page_filepath)
            merged_page_documents.append((wiki_page, markdown_content))

            wiki_site.add_page(wiki_page)
            if preview_file is None:
                preview_file = page_filepath

        if options.generate_wiki_index:
            self.cancellation_token.raise_if_cancelled()
            index_content = self.markdown_repository.generate_wiki_index(wiki_site)
            index_filepath = os.path.join(output_dir, "index.md")
            self.file_repository.save_markdown(index_content, index_filepath)
            markdown_files.append(index_filepath)
            preview_file = index_filepath

        if options.generate_merged_wiki:
            self.cancellation_token.raise_if_cancelled()
            merged_content = self.markdown_repository.generate_merged_wiki(
                wiki_site,
                merged_page_documents,
            )
            merged_filepath = os.path.join(output_dir, "wiki.md")
            self.file_repository.save_markdown(merged_content, merged_filepath)
            markdown_files.append(merged_filepath)
            preview_file = merged_filepath

        self.progress.info(
            f"Wiki export completed. Generated {len(markdown_files)} markdown files.",
            stage="completed",
            item_current=len(wiki_site.pages),
            item_total=len(navigation_links),
        )
        return ExportResult(
            mode="wiki",
            source_url=url,
            output_dir=output_dir,
            markdown_files=markdown_files,
            image_dir=images_dir,
            item_count=len(wiki_site.pages),
            skipped_count=skipped_count,
            preferred_markdown_file=preview_file or (markdown_files[0] if markdown_files else None),
        )
