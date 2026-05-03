#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTML adapter for parsing HTML content using BeautifulSoup.
"""

import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin, urlparse


class HtmlAdapter:
    """
    Adapter for parsing HTML content using BeautifulSoup.
    """

    def parse_html(self, page_html: str) -> BeautifulSoup:
        """
        Parses HTML content into a BeautifulSoup object.

        Args:
            page_html: HTML content as a string.

        Returns:
            A BeautifulSoup object.
        """
        return BeautifulSoup(page_html, "html.parser")

    def extract_chat_block_snippets(self, page_html: str) -> List[str]:
        """
        Extracts HTML snippets for each chat block.

        Args:
            page_html: HTML content of the page.

        Returns:
            A list of HTML snippet strings for each chat block.
        """
        soup = self.parse_html(page_html)
        return [str(block) for block in soup.select('div[data-query-display="true"]')]

    def extract_query_from_block(self, block_soup: BeautifulSoup) -> Optional[str]:
        """
        Extracts the query text from a chat block.

        Args:
            block_soup: BeautifulSoup object of a chat block.

        Returns:
            The query text, or None if not found.
        """
        left_pane = block_soup.select_one(":scope > div:nth-child(1)")
        if left_pane:
            query_span = left_pane.select_one("span.text-xl, span.xl\\:text-2xl")
            if query_span:
                for button in query_span.select("button"):
                    button.decompose()
                return query_span.get_text(strip=True)
        return None

    def extract_answer_area(self, block_soup: BeautifulSoup) -> Optional[Tag]:
        """
        Extracts the answer area from a chat block.

        Args:
            block_soup: BeautifulSoup object of a chat block.

        Returns:
            The answer area as a Tag, or None if not found.
        """
        left_pane = block_soup.select_one(":scope > div:nth-child(1)")
        if not left_pane:
            return None

        answer_area_soup = left_pane.select_one("div.prose-custom")
        return answer_area_soup

    def extract_code_references(self, block_soup: BeautifulSoup) -> List[dict]:
        """
        Extracts code references from a chat block.

        Args:
            block_soup: BeautifulSoup object of a chat block.

        Returns:
            A list of dictionaries containing code reference information.
        """
        references = []
        right_pane = block_soup.select_one(":scope > div:nth-child(2)")
        if right_pane:
            file_blocks = right_pane.select('div[id^="file-Repo"]')
            if not file_blocks:
                file_blocks = right_pane.select(
                    "div.flex.flex-col.gap-3.p-0 > div.flex.flex-col.gap-2.scroll-smooth.rounded-md"
                )

            for file_block in file_blocks:
                header_div = file_block.select_one('div[class*="sticky"]')
                file_name = "Unknown File"
                github_url = "#"
                repo_name = None

                if header_div:
                    repo_link_tag = header_div.select_one(
                        'a[href^="https://github.com/"]:not([href*="/blob/"])'
                    )
                    file_link_tag = header_div.select_one('a[href*="/blob/"]')

                    if repo_link_tag:
                        repo_name = repo_link_tag.get_text(strip=True)
                    if file_link_tag:
                        file_name = file_link_tag.get_text(strip=True)
                        github_url = file_link_tag["href"]

                references.append(
                    {
                        "repo_name": repo_name,
                        "file_name": file_name,
                        "github_url": github_url,
                    }
                )
        return references

    def extract_mermaid_diagrams(self, answer_area_soup: Tag) -> List[dict]:
        """
        Extracts Mermaid diagrams from the answer area.

        Args:
            answer_area_soup: The answer area as a BeautifulSoup Tag.

        Returns:
            A list of dictionaries containing information about each Mermaid diagram.
        """
        diagrams = []
        if not answer_area_soup:
            return diagrams

        for i, pre_tag_mermaid in enumerate(
            answer_area_soup.select(
                'pre:has(div[type="button"] > div > svg[id^="mermaid-"])'
            )
        ):
            svg_bs_tag_original = pre_tag_mermaid.select_one(
                'div[type="button"] > div > svg[id^="mermaid-"]'
            )
            if svg_bs_tag_original:
                fresh_svg_soup = BeautifulSoup(str(svg_bs_tag_original), "xml")
                svg_tag_for_diagram = fresh_svg_soup.find("svg")

                if svg_tag_for_diagram:
                    diagrams.append(
                        {
                            "svg_tag": svg_tag_for_diagram,
                            "pre_tag": pre_tag_mermaid,
                            "index": i,
                        }
                    )
                else:
                    print(f"Warning: Failed to re-parse SVG for diagram {i}. Skipping.")

        return diagrams

    def create_placeholder(self, chat_block_index: int, diagram_index: int) -> str:
        """
        Creates a placeholder for a Mermaid diagram.

        Args:
            chat_block_index: The index of the chat block.
            diagram_index: The index of the diagram within the chat block.

        Returns:
            A unique placeholder string for the diagram.
        """
        return f"HTMLPARSERMERMAIDPLACEHOLDER{chat_block_index}{diagram_index}ENDHTMLPARSER"

    def replace_svg_with_placeholder(self, pre_tag: Tag, placeholder: str) -> None:
        """
        Replaces an SVG container with a placeholder in the HTML.

        Args:
            pre_tag: The pre tag containing the SVG.
            placeholder: The placeholder to use.
        """
        pre_tag.replace_with(BeautifulSoup(f"<p>{placeholder}</p>", "html.parser").p)

    def unwrap_nested_pre_tags(self, answer_area_soup: Tag) -> None:
        """
        Unwraps nested pre tags in the answer area.

        Args:
            answer_area_soup: The answer area as a BeautifulSoup Tag.
        """
        unwrapped = True
        while unwrapped:
            unwrapped = False
            for pre_tag in answer_area_soup.find_all("pre"):
                children = [
                    child
                    for child in pre_tag.children
                    if isinstance(child, Tag) or child.strip()
                ]
                if len(children) == 1 and children[0].name == "pre":
                    pre_tag.replace_with(children[0])
                    unwrapped = True
                    break
            if not unwrapped:
                break

    def remove_empty_pre_tags(self, answer_area_soup: Tag) -> None:
        """
        Removes empty pre tags from the answer area.

        Args:
            answer_area_soup: The answer area as a BeautifulSoup Tag.
        """
        for pre_tag in answer_area_soup.find_all("pre"):
            if not pre_tag.get_text(strip=True):
                pre_tag.decompose()

    # ----- Wiki-related methods -----

    def extract_wiki_navigation(self, html_content: str) -> List[Dict[str, str]]:
        """
        Extracts all page links from the wiki page navigation menu.

        Args:
            html_content: Full HTML of the wiki page

        Returns:
            List[Dict[str, str]]: [{"title": "Page Title", "url": "Page URL"}, ...]
        """
        soup = self.parse_html(html_content)
        root = soup.select_one("#codebase-wiki-repo-page") or soup.body or soup

        selector_candidates = [
            # Legacy selector kept for backwards compatibility.
            "#codebase-wiki-repo-page > div:nth-child(2) > div > div > div:nth-child(1) > div > ul",
            # The current DeepWiki layout uses a flatter sidebar list.
            "#codebase-wiki-repo-page ul.flex-1.flex-shrink-0.space-y-1.overflow-y-auto.py-1",
            "#codebase-wiki-repo-page aside ul",
            "#codebase-wiki-repo-page nav ul",
        ]

        for selector in selector_candidates:
            for container in root.select(selector):
                navigation_links = self._extract_navigation_links_from_container(
                    container
                )
                if navigation_links:
                    print(
                        f"Found {len(navigation_links)} navigation links using selector: {selector}"
                    )
                    return navigation_links

        navigation_links = self._extract_navigation_links_from_all_lists(root)
        if navigation_links:
            print(
                f"Found {len(navigation_links)} navigation links using fallback list discovery"
            )
            return navigation_links

        print(
            "Navigation container not found. Check if the page structure has changed."
        )
        return []

    def _extract_navigation_links_from_container(
        self,
        container: Tag,
    ) -> List[Dict[str, str]]:
        """
        Extracts wiki-like links from one navigation container.

        The current DeepWiki DOM is not stable enough to rely on a single CSS
        path, so this helper validates links by structure and repo prefix.
        """
        entries: List[Dict[str, str]] = []
        seen_urls: set[str] = set()

        for link in container.select("li a[href]"):
            href = self._normalize_deepwiki_href(link.get("href"))
            title = link.get_text(strip=True)
            if not href or not title:
                continue

            parsed_href = urlparse(href)
            path_parts = [part for part in parsed_href.path.split("/") if part]
            if len(path_parts) < 3:
                continue

            entries.append(
                {
                    "title": title,
                    "url": href,
                    "prefix": f"{path_parts[0]}/{path_parts[1]}",
                }
            )

        if not entries:
            return []

        prefix_counts: Dict[str, int] = {}
        prefix_order: List[str] = []
        for entry in entries:
            prefix = entry["prefix"]
            if prefix not in prefix_counts:
                prefix_counts[prefix] = 0
                prefix_order.append(prefix)
            prefix_counts[prefix] += 1

        dominant_prefix = max(
            prefix_order,
            key=lambda prefix: prefix_counts[prefix],
        )

        filtered_links: List[Dict[str, str]] = []
        for entry in entries:
            if entry["prefix"] != dominant_prefix:
                continue
            if entry["url"] in seen_urls:
                continue
            seen_urls.add(entry["url"])
            filtered_links.append({"title": entry["title"], "url": entry["url"]})

        return filtered_links if len(filtered_links) >= 2 else []

    def _extract_navigation_links_from_all_lists(
        self,
        root: Tag,
    ) -> List[Dict[str, str]]:
        """
        Searches every list in the wiki root and returns the strongest candidate.
        """
        best_links: List[Dict[str, str]] = []

        for container in root.find_all("ul"):
            candidate_links = self._extract_navigation_links_from_container(container)
            if len(candidate_links) > len(best_links):
                best_links = candidate_links

        return best_links

    def _normalize_deepwiki_href(self, href: str | None) -> str | None:
        """
        Converts relative wiki links to absolute DeepWiki URLs and filters noise.
        """
        if not href:
            return None

        normalized_href = urljoin("https://deepwiki.com", href)
        parsed_href = urlparse(normalized_href)

        if parsed_href.netloc not in {"deepwiki.com", "www.deepwiki.com"}:
            return None

        path_parts = [part for part in parsed_href.path.split("/") if part]
        if len(path_parts) < 3:
            return None
        if path_parts[0] == "search":
            return None

        return normalized_href

    def extract_wiki_content(self, html_content: str) -> str:
        """
        Extracts the main content from a wiki page.

        Args:
            html_content: Full HTML of the wiki page

        Returns:
            str: HTML for the extracted content section
        """
        soup = self.parse_html(html_content)

        # Selector for the DeepWiki content area.
        # Note: This may need adjustment if the page structure changes.
        content_area = soup.select_one(".wiki-content, .main-content, article, main")

        if content_area:
            # Remove unnecessary elements such as edit and action buttons.
            for button in content_area.select("button, .edit-button, .action-button"):
                button.decompose()

            return str(content_area)

        # If no dedicated content area is found, fall back to the full body.
        return str(soup.body) if soup.body else ""

    def extract_wiki_mermaid_diagrams(self, html_content: str) -> List[dict]:
        """
        Extracts Mermaid diagrams from a wiki page.

        Args:
            html_content: Full HTML of the wiki page

        Returns:
            List[dict]: A list of extracted Mermaid diagram metadata
        """
        soup = self.parse_html(html_content)
        diagrams = []

        # Locate the content area based on the current DeepWiki structure.
        content_area = soup.select_one("#codebase-wiki-repo-page")
        if not content_area:
            content_area = soup.body

        if not content_area:
            return diagrams

        print("Searching for Mermaid diagrams in Wiki content...")

        # Selector tuned to the current DeepWiki Mermaid diagram structure.
        # XPath: //*[@id="codebase-wiki-repo-page"]/div[2]/div/div/div[2]/div[2]/div/div/div/div/pre[1]
        diagram_selector = 'pre:has(div[type="button"][aria-haspopup="dialog"] > div > svg[id^="mermaid-"])'

        # Find all pre tags for debugging output.
        all_pre_tags = content_area.find_all("pre")
        print(f"Found {len(all_pre_tags)} pre tags in content")

        # Search for Mermaid diagrams.
        diagram_candidates = content_area.select(diagram_selector)
        print(f"Found {len(diagram_candidates)} potential Mermaid diagrams")

        for i, pre_tag_mermaid in enumerate(diagram_candidates):
            # Extract the SVG tag.
            svg_bs_tag_original = pre_tag_mermaid.select_one(
                'div[type="button"][aria-haspopup="dialog"] > div > svg[id^="mermaid-"]'
            )

            if svg_bs_tag_original:
                svg_id = svg_bs_tag_original.get("id", f"unknown-{i}")
                print(f"Processing Mermaid diagram: {svg_id}")

                fresh_svg_soup = BeautifulSoup(str(svg_bs_tag_original), "xml")
                svg_tag_for_diagram = fresh_svg_soup.find("svg")

                if svg_tag_for_diagram:
                    diagrams.append(
                        {
                            "svg_tag": svg_tag_for_diagram,
                            "pre_tag": pre_tag_mermaid,
                            "index": i,
                        }
                    )
                    print(f"Successfully extracted SVG for diagram {i}")
                else:
                    print(f"Warning: Failed to re-parse SVG for diagram {i}. Skipping.")

        print(f"Total Mermaid diagrams successfully extracted: {len(diagrams)}")
        return diagrams
