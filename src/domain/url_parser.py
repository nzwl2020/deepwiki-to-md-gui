#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Parses DeepWiki URLs for both CLI and GUI entry points.
"""

from dataclasses import dataclass
import hashlib
import re
from typing import Literal
from urllib.parse import parse_qs, urlparse


DeepWikiMode = Literal["chat", "wiki"]


@dataclass(frozen=True)
class ParsedDeepWikiUrl:
    """
    Unified URL parsing result used by both CLI and GUI.

    The GUI needs a stable result shape so it can auto-switch mode
    and show the user what will be exported before execution starts.
    """

    mode: DeepWikiMode
    original_url: str
    identifier: str
    organization: str | None = None
    repository: str | None = None


def parse_deepwiki_url(url: str) -> ParsedDeepWikiUrl:
    """
    Parses a DeepWiki URL and determines whether it is a chat
    or wiki target.

    This centralizes URL rules so we do not duplicate parsing logic
    across usecases and UI layers.
    """
    parsed_url = urlparse(url)

    if parsed_url.netloc not in {"deepwiki.com", "www.deepwiki.com"}:
        raise ValueError(
            f"Invalid DeepWiki URL: {url}. Expected host deepwiki.com."
        )

    path_parts = [part for part in parsed_url.path.split("/") if part]

    if len(path_parts) >= 1 and path_parts[0] == "search":
        chat_id = _extract_chat_id(parsed_url, url)
        return ParsedDeepWikiUrl(
            mode="chat",
            original_url=url,
            identifier=chat_id,
        )

    if len(path_parts) >= 2:
        organization = path_parts[0]
        repository = path_parts[1]
        return ParsedDeepWikiUrl(
            mode="wiki",
            original_url=url,
            identifier=f"{organization}/{repository}",
            organization=organization,
            repository=repository,
        )

    raise ValueError(
        f"Invalid DeepWiki URL format: {url}. "
        "Expected chat URL like https://deepwiki.com/search/<chat_id> "
        "or wiki URL like https://deepwiki.com/<organization>/<repository>."
    )


def _extract_chat_id(parsed_url, raw_url: str) -> str:
    """
    Extracts a stable chat identifier from a DeepWiki chat URL.

    The fallback hash is intentional so even unexpected URL shapes
    can still map to a deterministic output directory.
    """
    path_parts = [part for part in parsed_url.path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[0] == "search":
        return path_parts[1]

    query_params = parse_qs(parsed_url.query)
    if "id" in query_params and query_params["id"]:
        return query_params["id"][0]

    match = re.search(r"([a-zA-Z0-9_-]{4,})(?:[/?#]|$)", raw_url)
    if match:
        return match.group(1)

    return hashlib.md5(raw_url.encode("utf-8")).hexdigest()[:12]
