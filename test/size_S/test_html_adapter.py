from src.gateway.html_adapter import HtmlAdapter


def test_extract_wiki_navigation_supports_current_sidebar_layout():
    adapter = HtmlAdapter()
    html_content = """
    <html>
      <body>
        <div id="codebase-wiki-repo-page">
          <div>
            <aside>
              <ul class="flex-1 flex-shrink-0 space-y-1 overflow-y-auto py-1">
                <li><a href="/element-plus/element-plus/1-overview">Overview</a></li>
                <li>
                  <a href="/element-plus/element-plus/1.1-repository-structure">
                    Repository Structure
                  </a>
                </li>
                <li><a href="/search/element-plus">Ignored Search Link</a></li>
              </ul>
            </aside>
          </div>
        </div>
      </body>
    </html>
    """

    navigation = adapter.extract_wiki_navigation(html_content)

    assert navigation == [
        {
            "title": "Overview",
            "url": "https://deepwiki.com/element-plus/element-plus/1-overview",
        },
        {
            "title": "Repository Structure",
            "url": "https://deepwiki.com/element-plus/element-plus/1.1-repository-structure",
        },
    ]
