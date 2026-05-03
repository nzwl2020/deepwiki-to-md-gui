from src.domain.entities import WikiPage, WikiSite
from src.repository.markdown_repository import MarkdownRepository
from src.gateway.markdown_adapter import MarkdownAdapter


def test_generate_merged_wiki_keeps_page_order_and_toc():
    repository = MarkdownRepository(MarkdownAdapter())
    wiki_site = WikiSite(organization="langchain-ai", repository="langchain")
    page_one = WikiPage(title="Overview", content="", url="u1", page_number=1)
    page_two = WikiPage(title="API Guide", content="", url="u2", page_number=2)
    wiki_site.add_page(page_one)
    wiki_site.add_page(page_two)

    merged = repository.generate_merged_wiki(
        wiki_site,
        [
            (page_one, "# Overview\n\nFirst page"),
            (page_two, "# API Guide\n\nSecond page"),
        ],
    )

    assert "# langchain Wiki" in merged
    assert "- [Overview](#overview)" in merged
    assert "- [API Guide](#api-guide)" in merged
    assert merged.index("# Overview") < merged.index("# API Guide")
