from src.domain.url_parser import parse_deepwiki_url


def test_parse_chat_url_returns_chat_mode():
    parsed = parse_deepwiki_url(
        "https://deepwiki.com/search/-eldrawer-zindex_e9d69bbe-23b0-4b4e-ad0e-434b0deeeacd"
    )
    assert parsed.mode == "chat"
    assert parsed.identifier == "-eldrawer-zindex_e9d69bbe-23b0-4b4e-ad0e-434b0deeeacd"


def test_parse_wiki_url_returns_wiki_mode():
    parsed = parse_deepwiki_url(
        "https://deepwiki.com/langchain-ai/langchain"
    )
    assert parsed.mode == "wiki"
    assert parsed.organization == "langchain-ai"
    assert parsed.repository == "langchain"
