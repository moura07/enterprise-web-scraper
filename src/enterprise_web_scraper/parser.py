"""
HTML parsing layer for the Enterprise Web Scraper.

Extracts structured ``Book`` records from raw HTML using BeautifulSoup with
defensive selectors and explicit fallback values for every field.

Usage
-----
    from enterprise_web_scraper.parser import BookParser

    parser = BookParser()
    books = parser.parse_books(html_string)
    next_url = parser.get_next_page(html_string)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger("enterprise_web_scraper.parser")

# CSS class name → integer star rating mapping
_RATING_MAP: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Book:
    """Normalized book record extracted from books.toscrape.com."""

    title: str
    price: str
    availability: str
    rating: int  # 1–5; 0 if unknown
    url: str  # Absolute URL to the book's detail page


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class BookParser:
    """
    Stateless HTML parser for books.toscrape.com.

    All methods are pure functions over HTML strings; no I/O is performed.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_books(self, html: str, base_url: str = "") -> list[Book]:
        """
        Parse all book cards from a catalogue page.

        Args:
            html: Raw HTML string of the page.
            base_url: Base URL used to resolve relative book detail links.

        Returns:
            List of ``Book`` records. Empty if the page has no book cards.
        """
        soup = BeautifulSoup(html, "html.parser")
        elements = soup.select("article.product_pod")

        if not elements:
            logger.warning("No book elements found on page.")

        books: list[Book] = []
        for element in elements:
            try:
                books.append(self._parse_book(element, base_url))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to parse book element: %s", exc)

        logger.info("Extracted %d books from current page.", len(books))
        return books

    def get_next_page(self, html: str, current_url: str) -> str | None:
        """
        Return the absolute URL of the next catalogue page, if any.

        Args:
            html: Raw HTML of the current page.
            current_url: Absolute URL of the current page (for resolving
                relative ``href`` values).

        Returns:
            Absolute URL string, or ``None`` if this is the last page.
        """
        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.select_one("li.next a")

        if not next_link:
            return None

        href = next_link.get("href")
        if not href:
            return None

        return urljoin(current_url, str(href))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_book(element, base_url: str) -> Book:
        """Extract a single Book from an ``<article class="product_pod">`` element."""
        # --- Title ---
        title_el = element.select_one("h3 a")
        title = (
            str(title_el.get("title", "")).strip()
            if title_el
            else "Unknown Title"
        ) or "Unknown Title"

        # --- Price ---
        price_el = element.select_one(".price_color")
        price = price_el.get_text(strip=True) if price_el else "Unknown Price"

        # --- Availability ---
        avail_el = element.select_one(".availability")
        availability_text = (
            avail_el.get_text(" ", strip=True).lower() if avail_el else ""
        )
        availability = "yes" if "in stock" in availability_text else "no"

        # --- Star rating ---
        # The rating is encoded as a CSS class: "star-rating One", "star-rating Two", …
        rating_el = element.select_one(".star-rating")
        rating = 0
        if rating_el:
            for css_class in rating_el.get("class", []):
                rating = _RATING_MAP.get(css_class.lower(), 0)
                if rating:
                    break

        # --- Book detail URL ---
        book_url = ""
        if title_el:
            href = title_el.get("href", "")
            book_url = urljoin(base_url, str(href)) if href else ""

        return Book(
            title=title,
            price=price,
            availability=availability,
            rating=rating,
            url=book_url,
        )
