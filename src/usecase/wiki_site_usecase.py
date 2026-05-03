#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Usecase for converting a wiki site to markdown.
"""

import os

from src.domain.entities import WikiSite
from src.domain.export_models import ExportResult, ProgressReporter
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
    ):
        self.web_repository = web_repository
        self.html_repository = html_repository
        self.markdown_repository = markdown_repository
        self.file_repository = file_repository
        self.progress = progress_reporter or ProgressReporter()

    async def execute(self, url: str, output_base_dir: str) -> ExportResult:
        self.progress.info("Starting wiki export...")
        self.progress.info(f"Target URL: {url}")
        self.progress.info(f"Output Base Directory: {output_base_dir}")

        wiki_site = WikiSite.from_url(url)
        self.progress.info(
            f"Processing wiki for {wiki_site.organization}/{wiki_site.repository}"
        )

        output_dir = wiki_site.get_output_directory(output_base_dir)
        images_dir = os.path.join(output_dir, "images")
        self.file_repository.ensure_directory(output_dir)
        self.file_repository.ensure_directory(images_dir)

        self.progress.info(f"Output directory: {output_dir}")
        self.progress.info(f"Images directory: {images_dir}")

        main_page_html = await self.web_repository.fetch_content(url)
        if not main_page_html:
            self.progress.error("Failed to retrieve main wiki page.")
            raise RuntimeError("Failed to retrieve main wiki page.")

        navigation_links = self.html_repository.extract_wiki_navigation(main_page_html)
        if not navigation_links:
            self.progress.error("No navigation links found.")
            raise RuntimeError("No navigation links found.")

        self.progress.info(f"Found {len(navigation_links)} wiki pages.")
        markdown_files: list[str] = []

        for page_num, page_link in enumerate(navigation_links, 1):
            page_url = page_link["url"]
            page_title = page_link["title"]

            self.progress.info(
                f"Processing page {page_num}/{len(navigation_links)}: {page_title}"
            )

            page_html = await self.web_repository.fetch_content(page_url)
            if not page_html:
                self.progress.warning(f"Failed to retrieve page: {page_title}. Skipping.")
                continue

            wiki_page = self.html_repository.extract_wiki_page(
                page_html,
                title=page_title,
                url=page_url,
                page_number=page_num,
                output_dir=output_dir,
            )

            processed_content = self.html_repository.process_wiki_page_content(
                wiki_page, output_dir
            )

            markdown_content = self.markdown_repository.convert_wiki_to_markdown(
                wiki_page, processed_content
            )

            page_filename = wiki_page.get_filename()
            page_filepath = os.path.join(output_dir, page_filename)
            self.file_repository.save_markdown(markdown_content, page_filepath)
            markdown_files.append(page_filepath)

            wiki_site.add_page(wiki_page)

        index_content = self.markdown_repository.generate_wiki_index(wiki_site)
        index_filepath = os.path.join(output_dir, "index.md")
        self.file_repository.save_markdown(index_content, index_filepath)
        markdown_files.append(index_filepath)

        self.progress.info(
            f"Wiki export completed. Generated {len(markdown_files)} markdown files."
        )
        return ExportResult(
            mode="wiki",
            output_dir=output_dir,
            markdown_files=markdown_files,
            image_dir=images_dir,
            item_count=len(wiki_site.pages),
        )
