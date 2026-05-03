#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web adapter for fetching web pages using Playwright.
"""

# import asyncio
# from playwright.async_api import async_playwright


# class WebAdapter:
#     """
#     Adapter to fetch web page content using Playwright.
#     """

#     async def fetch(self, url: str) -> str:
#         """
#         Fetches the HTML content of a web page.

#         Args:
#             url: The URL of the page to fetch.

#         Returns:
#             The HTML content of the page as a string.
#         """
#         async with async_playwright() as p:
#             browser = await p.chromium.launch(headless=True)
#             page = await browser.new_page()
#             content = ""
#             try:
#                 print(f"Navigating to {url}...")
#                 await page.goto(url, wait_until="networkidle", timeout=60000)
#                 print(
#                     "Page loaded. Waiting for potential dynamic content (e.g., 1 second)..."
#                 )
#                 await page.wait_for_timeout(1000)
#                 print("Retrieving page content...")
#                 content = await page.content()
#                 print("Content retrieved.")
#             except Exception as e:
#                 print(f"Error during Playwright navigation or content retrieval: {e}")
#                 # Let the exception propagate to the repository layer
#                 raise
#             finally:
#                 await browser.close()
#             return content

from playwright.async_api import async_playwright

from src.domain.export_models import CancellationToken, ProgressReporter


class WebAdapter:
    """
    Adapter to fetch web page content using Playwright.
    """

    def __init__(
        self,
        progress_reporter: ProgressReporter | None = None,
        cancellation_token: CancellationToken | None = None,
        timeout_ms: int = 60000,
    ):
        self.progress = progress_reporter or ProgressReporter()
        self.cancellation_token = cancellation_token or CancellationToken()
        self.timeout_ms = timeout_ms

    async def fetch(self, url: str) -> str:
        self.cancellation_token.raise_if_cancelled()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                # The UI needs these milestones to explain "what is happening now"
                # during long-running Playwright work.
                self.progress.info(f"Navigating to {url}...")
                await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                self.cancellation_token.raise_if_cancelled()

                self.progress.info("Page loaded. Waiting for dynamic content...")
                await page.wait_for_timeout(1000)
                self.cancellation_token.raise_if_cancelled()

                self.progress.info("Retrieving page content...")
                content = await page.content()
                self.progress.info("Content retrieved.")
                return content
            except Exception as exc:
                self.progress.error(
                    f"Error during Playwright navigation or content retrieval: {exc}"
                )
                raise
            finally:
                await browser.close()
