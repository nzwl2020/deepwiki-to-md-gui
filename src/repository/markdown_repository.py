#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Markdown repository for converting entities to markdown using the MarkdownAdapter.
"""

from src.domain.entities import ChatLog, ProcessedAnswer, WikiPage, WikiSite
from src.gateway.markdown_adapter import MarkdownAdapter


class MarkdownRepository:
    """
    Repository for markdown operations, using MarkdownAdapter.
    """

    def __init__(self, markdown_adapter: MarkdownAdapter):
        """
        Initialize the MarkdownRepository with a MarkdownAdapter.

        Args:
            markdown_adapter: The MarkdownAdapter to use for markdown conversions.
        """
        self.markdown_adapter = markdown_adapter

    def convert_processed_answer_to_markdown(
        self, processed_answer: ProcessedAnswer
    ) -> str:
        """
        Converts a ProcessedAnswer entity to markdown.

        Args:
            processed_answer: The ProcessedAnswer entity to convert.

        Returns:
            The markdown representation of the processed answer.
        """
        return processed_answer.to_markdown(self.markdown_adapter)

    def convert_chat_log_to_markdown(self, chat_log: ChatLog) -> str:
        """
        Converts a ChatLog entity to markdown.

        Args:
            chat_log: The ChatLog entity to convert.

        Returns:
            The markdown representation of the chat log.
        """
        return chat_log.to_markdown(self.markdown_adapter)

    # ----- Wiki-related methods -----

    def convert_wiki_to_markdown(
        self, wiki_page: WikiPage, processed_content: ProcessedAnswer
    ) -> str:
        """
        Converts a wiki page to Markdown.

        Args:
            wiki_page: WikiPage entity to convert
            processed_content: Processed page content

        Returns:
            str: Converted Markdown
        """
        # Convert the base content to Markdown.
        markdown_content = self.markdown_adapter.convert_html_to_markdown(
            processed_content.html_content_with_placeholders
        )

        # Replace Mermaid diagram placeholders.
        for (
            placeholder,
            md_link,
        ) in processed_content.placeholder_to_markdown_link_map.items():
            if placeholder in markdown_content:
                markdown_content = markdown_content.replace(placeholder, md_link)
            else:
                print(
                    f"Warning: Placeholder '{placeholder}' not found in markdownified content for replacement."
                )

        # Add the page title to the beginning of the document.
        title_prefix = f"# {wiki_page.title}\n\n"

        return title_prefix + markdown_content

    def generate_wiki_index(self, wiki_site: WikiSite) -> str:
        """
        Generates the table of contents page for the entire wiki.

        Args:
            wiki_site: WikiSite entity

        Returns:
            str: Markdown for the table of contents page
        """
        lines = [
            f"# {wiki_site.repository} Wiki",
            f"Organization: {wiki_site.organization}",
            "",
            "## Pages",
            "",
        ]

        # Build the list of page links.
        for page in wiki_site.pages:
            filename = page.get_filename()
            lines.append(f"- [{page.title}]({filename})")

        return "\n".join(lines)

    def generate_merged_wiki(
        self,
        wiki_site: WikiSite,
        page_documents: list[tuple[WikiPage, str]],
    ) -> str:
        """
        Generates a merged wiki document that keeps the page order intact.

        The merged file gives desktop users a single Markdown artifact while the
        per-page files remain available for incremental updates and navigation.
        """
        lines = [
            f"# {wiki_site.repository} Wiki",
            f"Organization: {wiki_site.organization}",
            "",
            "## Table of Contents",
            "",
        ]

        for page in wiki_site.pages:
            anchor = self._anchor_for_title(page.title)
            lines.append(f"- [{page.title}](#{anchor})")

        lines.append("")

        for page, markdown_content in page_documents:
            lines.append(markdown_content.strip())
            lines.append("")
            lines.append("---")
            lines.append("")

        # The trailing separator is visually noisy in the final document.
        while lines and not lines[-1]:
            lines.pop()
        if lines and lines[-1] == "---":
            lines.pop()

        return "\n".join(lines)

    def _anchor_for_title(self, title: str) -> str:
        anchor = title.strip().lower().replace(" ", "-")
        return "".join(char for char in anchor if char.isalnum() or char == "-")
