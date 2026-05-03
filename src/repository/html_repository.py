#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTML repository for parsing HTML content and creating domain entities.
"""

from typing import List, Dict, Optional
from bs4 import BeautifulSoup

from src.domain.entities import (
    ChatBlockContent,
    CodeReference,
    CodeReferenceCollection,
    ProcessedAnswer,
    MermaidDiagram,
    WikiPage,
    WikiSite,
)
from src.gateway.html_adapter import HtmlAdapter


class HtmlRepository:
    """
    Repository for HTML operations, using HtmlAdapter.
    """

    def __init__(self, html_adapter: HtmlAdapter):
        """
        Initialize the HtmlRepository with an HtmlAdapter.

        Args:
            html_adapter: The HtmlAdapter to use for HTML operations.
        """
        self.html_adapter = html_adapter

    def extract_chat_blocks(
        self,
        html_content: str,
        output_dir: str,
        chat_block_indices: Optional[List[int]] = None,
        include_code_references: bool = True,
        export_mermaid_diagrams: bool = True,
    ) -> List[ChatBlockContent]:
        """
        Extracts chat blocks from HTML content and creates ChatBlockContent entities.

        Args:
            html_content: The HTML content to parse.
            output_dir: Directory where output files (e.g., SVGs) will be saved.
            chat_block_indices: Indices of chat blocks to parse. If None, all blocks are parsed.

        Returns:
            A list of ChatBlockContent objects.
        """
        # Extract chat block snippets
        snippets = self.html_adapter.extract_chat_block_snippets(html_content)

        # If specific indices were requested, filter the snippets
        if chat_block_indices is not None:
            filtered_snippets = [
                (i, s) for i, s in enumerate(snippets) if i in chat_block_indices
            ]
        else:
            filtered_snippets = enumerate(snippets)

        # Parse each snippet into a ChatBlockContent object
        chat_blocks = []
        for i, snippet in filtered_snippets:
            chat_block = self.parse_chat_block(
                snippet,
                output_dir,
                i,
                include_code_references=include_code_references,
                export_mermaid_diagrams=export_mermaid_diagrams,
            )
            if chat_block:
                chat_blocks.append(chat_block)

        return chat_blocks

    def parse_chat_block(
        self,
        html_snippet: str,
        output_dir: str,
        chat_block_index: int,
        include_code_references: bool = True,
        export_mermaid_diagrams: bool = True,
    ) -> ChatBlockContent:
        """
        Parses a single chat block HTML into a ChatBlockContent entity.

        Args:
            html_snippet: The HTML snippet for a chat block.
            output_dir: Directory where output files will be saved.
            chat_block_index: The index of this chat block.

        Returns:
            A ChatBlockContent object.
        """
        # Parse HTML snippet
        block_soup = self.html_adapter.parse_html(html_snippet)

        # Extract query
        query = self.html_adapter.extract_query_from_block(block_soup)

        # Extract answer area
        answer_area = self.html_adapter.extract_answer_area(block_soup)

        # Extract code references
        code_references = (
            self._create_code_references(block_soup)
            if include_code_references
            else CodeReferenceCollection()
        )

        # Process answer if available
        processed_answer = None
        if answer_area:
            processed_answer = self._process_answer_area(
                answer_area,
                output_dir,
                chat_block_index,
                export_mermaid_diagrams=export_mermaid_diagrams,
            )

        # Create and return ChatBlockContent
        return ChatBlockContent(
            query=query,
            processed_answer=processed_answer,
            code_references=code_references,
        )

    def _create_code_references(
        self, block_soup: BeautifulSoup
    ) -> CodeReferenceCollection:
        """
        Creates CodeReference entities from a chat block.

        Args:
            block_soup: The BeautifulSoup object for a chat block.

        Returns:
            A CodeReferenceCollection object.
        """
        collection = CodeReferenceCollection()
        ref_data_list = self.html_adapter.extract_code_references(block_soup)

        for ref_data in ref_data_list:
            code_ref = CodeReference(
                repo_name=ref_data["repo_name"],
                file_name=ref_data["file_name"],
                github_url=ref_data["github_url"],
            )
            collection.add(code_ref)

        return collection

    def _process_answer_area(
        self,
        answer_area: BeautifulSoup,
        output_dir: str,
        chat_block_index: int,
        export_mermaid_diagrams: bool = True,
    ) -> ProcessedAnswer:
        """
        Processes the answer area, extracting and saving Mermaid diagrams.

        Args:
            answer_area: The BeautifulSoup object for the answer area.
            output_dir: Directory where diagram files will be saved.
            chat_block_index: The index of the chat block.

        Returns:
            A ProcessedAnswer object.
        """
        # Copy the answer area to avoid modifying the original
        answer_area_copy = BeautifulSoup(str(answer_area), "html.parser")

        # Extract Mermaid diagrams
        diagrams = self.html_adapter.extract_mermaid_diagrams(answer_area_copy)

        # Process each diagram
        placeholder_map = {}
        for diagram_data in diagrams:
            svg_tag = diagram_data["svg_tag"]
            pre_tag = diagram_data["pre_tag"]
            diagram_index = diagram_data["index"]

            # Create MermaidDiagram entity
            diagram = MermaidDiagram(
                original_id=svg_tag.get("id", ""),
                svg_content=svg_tag,
                chat_block_index=chat_block_index,
                diagram_index=diagram_index,
            )

            # Save the diagram and get the file path
            relative_svg_path = (
                diagram.prepare_and_save(output_dir)
                if export_mermaid_diagrams
                else None
            )

            # Create a placeholder for this diagram
            placeholder = self.html_adapter.create_placeholder(
                chat_block_index, diagram_index
            )

            # Add the placeholder and corresponding markdown link to the map
            if relative_svg_path:
                placeholder_map[placeholder] = (
                    f"![Mermaid Diagram]({relative_svg_path})"
                )
            else:
                placeholder_map[placeholder] = (
                    "_Mermaid diagram omitted from export._"
                    if not export_mermaid_diagrams
                    else ""
                )

            # Replace the SVG with a placeholder in the HTML
            self.html_adapter.replace_svg_with_placeholder(pre_tag, placeholder)

        # Clean up the HTML
        self.html_adapter.unwrap_nested_pre_tags(answer_area_copy)
        self.html_adapter.remove_empty_pre_tags(answer_area_copy)

        # Create and return ProcessedAnswer
        return ProcessedAnswer(
            html_content_with_placeholders=str(answer_area_copy),
            placeholder_to_markdown_link_map=placeholder_map,
        )

    # ----- Wiki-related methods -----

    def extract_wiki_navigation(self, html_content: str) -> List[Dict[str, str]]:
        """
        Extracts navigation link information for a wiki site.

        Args:
            html_content: Full HTML of the wiki page

        Returns:
            List[Dict[str, str]]: [{"title": "Page Title", "url": "Page URL"}, ...]
        """
        return self.html_adapter.extract_wiki_navigation(html_content)

    def extract_wiki_page(
        self, html_content: str, title: str, url: str, page_number: int, output_dir: str
    ) -> WikiPage:
        """
        Parses wiki page content and creates a WikiPage entity.

        Args:
            html_content: Wiki page HTML
            title: Page title
            url: Page URL
            page_number: Page number
            output_dir: Output directory

        Returns:
            WikiPage: The created WikiPage entity
        """
        # Extract the page content.
        content_html = self.html_adapter.extract_wiki_content(html_content)

        # Extract and prepare Mermaid diagrams.
        diagram_infos = self.html_adapter.extract_wiki_mermaid_diagrams(html_content)
        diagrams = []

        # Create a content copy for placeholder replacement.
        content_copy = BeautifulSoup(content_html, "html.parser")

        # Process each Mermaid diagram.
        for diagram_idx, diagram_info in enumerate(diagram_infos):
            svg_tag = diagram_info["svg_tag"]
            pre_tag = diagram_info["pre_tag"]

            # Create a MermaidDiagram, using page_number instead of chat_block_index.
            diagram = MermaidDiagram(
                original_id=svg_tag.get("id", ""),
                svg_content=svg_tag,
                chat_block_index=page_number,  # Reuse page_number as the chat block index.
                diagram_index=diagram_idx,
            )

            # Add the diagram to the list.
            diagrams.append(diagram)

            # Replace SVG with a placeholder if needed.
            # Depending on the HTML parsing result, diagram replacement may need adjustment.

        # Create the WikiPage.
        return WikiPage(
            title=title,
            content=content_html,
            url=url,
            page_number=page_number,
            diagrams=diagrams,
        )

    def process_wiki_page_content(
        self,
        wiki_page: WikiPage,
        output_dir: str,
        export_mermaid_diagrams: bool = True,
    ) -> ProcessedAnswer:
        """
        Processes wiki page content for Markdown output and saves Mermaid diagrams.

        Args:
            wiki_page: WikiPage entity to process
            output_dir: Output directory

        Returns:
            ProcessedAnswer: HTML with placeholders and a placeholder mapping
        """
        # Create a copy of the content.
        content_copy = BeautifulSoup(wiki_page.content, "html.parser")
        placeholder_map = {}

        # Extract Mermaid diagrams again so pre_tag references are available.
        diagram_infos = self.html_adapter.extract_wiki_mermaid_diagrams(
            wiki_page.content
        )

        # Process each Mermaid diagram.
        for i, (diagram, diagram_info) in enumerate(
            zip(wiki_page.diagrams, diagram_infos)
        ):
            # Save the diagram and get its relative path.
            relative_svg_path = (
                diagram.prepare_and_save(output_dir)
                if export_mermaid_diagrams
                else None
            )

            # Create a placeholder.
            placeholder = self.html_adapter.create_placeholder(
                diagram.chat_block_index, diagram.diagram_index
            )

            # Add the placeholder and Markdown link to the mapping.
            if relative_svg_path:
                placeholder_map[placeholder] = (
                    f"![Mermaid Diagram]({relative_svg_path})"
                )
            else:
                placeholder_map[placeholder] = (
                    "_Mermaid diagram omitted from export._"
                    if not export_mermaid_diagrams
                    else ""
                )

            # Important: replace Mermaid diagrams in the HTML with placeholders.
            if "pre_tag" in diagram_info and "svg_tag" in diagram_info:
                pre_tag = diagram_info["pre_tag"]
                svg_tag = diagram_info["svg_tag"]
                svg_id = svg_tag.get("id", "")

                # Find the pre tag using a Mermaid-specific selector.
                mermaid_selector = (
                    f'pre:has(div[type="button"] > div > svg[id="{svg_id}"])'
                )
                matching_pre = content_copy.select(mermaid_selector)

                if matching_pre:
                    # Replace the matched pre tag with the placeholder.
                    self.html_adapter.replace_svg_with_placeholder(
                        matching_pre[0], placeholder
                    )
                    print(
                        f"Replaced diagram with id {svg_id} with placeholder: {placeholder}"
                    )
                else:
                    # Fall back to a position-based approach if ID matching fails.
                    print(
                        f"Could not find exact match for diagram {i} with id {svg_id}, trying position-based approach"
                    )
                    # Look up pre tags using a Mermaid-specific selector.
                    mermaid_pre_tags = content_copy.select(
                        'pre:has(div[type="button"][aria-haspopup="dialog"] > div > svg[id^="mermaid-"])'
                    )
                    if i < len(mermaid_pre_tags):
                        self.html_adapter.replace_svg_with_placeholder(
                            mermaid_pre_tags[i], placeholder
                        )
                        print(
                            f"Replaced diagram at position {i} with placeholder: {placeholder}"
                        )
                    else:
                        print(
                            f"Warning: Could not find appropriate pre tag for diagram {i}"
                        )

        # Clean up the content.
        if isinstance(content_copy, BeautifulSoup):
            self.html_adapter.unwrap_nested_pre_tags(content_copy)
            self.html_adapter.remove_empty_pre_tags(content_copy)

        # Return HTML with placeholders and the placeholder map.
        return ProcessedAnswer(
            html_content_with_placeholders=str(content_copy),
            placeholder_to_markdown_link_map=placeholder_map,
        )
