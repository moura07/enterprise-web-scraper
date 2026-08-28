"""
Unit tests for enterprise_web_scraper.parser.

Tests cover:
- Correct field extraction from valid HTML
- Fallback values for missing elements
- Star rating parsing from CSS classes
- Absolute URL construction for book detail links
- Pagination: next-page URL extraction
- Edge cases: empty page, malformed HTML
"""

from __future__ import annotations

import pytest

from enterprise_web_scraper.parser import Book, BookParser
from tests.conftest import (
    CATALOGUE_PAGE_HTML,
    EMPTY_PAGE_HTML,
    LAST_PAGE_HTML,
)


@pytest.fixture()
def parser() -> BookParser:
    return BookParser()


BASE = "http://books.toscrape.com/"


class TestParseBooks:
    def test_returns_two_books_from_catalogue_page(self, parser: BookParser) -> None:
        books = parser.parse_books(CATALOGUE_PAGE_HTML, base_url=BASE)
        assert len(books) == 2

    def test_first_book_title(self, parser: BookParser) -> None:
        books = parser.parse_books(CATALOGUE_PAGE_HTML, base_url=BASE)
        assert books[0].title == "A Light in the Attic"

    def test_first_book_price(self, parser: BookParser) -> None:
        books = parser.parse_books(CATALOGUE_PAGE_HTML, base_url=BASE)
        assert books[0].price == "£51.77"

    def test_first_book_availability_in_stock(self, parser: BookParser) -> None:
        books = parser.parse_books(CATALOGUE_PAGE_HTML, base_url=BASE)
        assert books[0].availability == "yes"

    def test_first_book_rating_three(self, parser: BookParser) -> None:
        books = parser.parse_books(CATALOGUE_PAGE_HTML, base_url=BASE)
        assert books[0].rating == 3

    def test_second_book_rating_one(self, parser: BookParser) -> None:
        books = parser.parse_books(CATALOGUE_PAGE_HTML, base_url=BASE)
        assert books[1].rating == 1

    def test_book_url_is_absolute(self, parser: BookParser) -> None:
        books = parser.parse_books(CATALOGUE_PAGE_HTML, base_url=BASE)
        assert books[0].url.startswith("http://books.toscrape.com/")

    def test_last_page_book_rating_five(self, parser: BookParser) -> None:
        books = parser.parse_books(LAST_PAGE_HTML, base_url=BASE)
        assert books[0].rating == 5

    def test_empty_page_returns_empty_list(self, parser: BookParser) -> None:
        books = parser.parse_books(EMPTY_PAGE_HTML, base_url=BASE)
        assert books == []

    def test_returns_list_of_book_instances(self, parser: BookParser) -> None:
        books = parser.parse_books(CATALOGUE_PAGE_HTML, base_url=BASE)
        assert all(isinstance(b, Book) for b in books)


class TestParseBookFallbacks:
    """Missing HTML elements should produce explicit fallback values."""

    MISSING_PRICE_HTML = """
    <article class="product_pod">
      <p class="star-rating Two"></p>
      <h3><a href="catalogue/x_1/index.html" title="No Price Book">No Price Book</a></h3>
      <div class="product_price">
        <p class="instock availability">In stock</p>
      </div>
    </article>
    """

    MISSING_TITLE_HTML = """
    <article class="product_pod">
      <p class="star-rating Four"></p>
      <h3><a href="catalogue/x_2/index.html">No title attr</a></h3>
      <div class="product_price">
        <p class="price_color">£9.99</p>
        <p class="instock availability">In stock</p>
      </div>
    </article>
    """

    def test_missing_price_falls_back(self, parser: BookParser) -> None:
        books = parser.parse_books(self.MISSING_PRICE_HTML, base_url=BASE)
        assert books[0].price == "Unknown Price"

    def test_missing_title_attr_falls_back(self, parser: BookParser) -> None:
        # No `title` attribute on the <a> tag → falls back to "Unknown Title"
        books = parser.parse_books(self.MISSING_TITLE_HTML, base_url=BASE)
        assert books[0].title == "Unknown Title"

    def test_out_of_stock_mapped_to_no(self, parser: BookParser) -> None:
        html = """
        <article class="product_pod">
          <p class="star-rating One"></p>
          <h3><a href="x.html" title="Unavailable">Unavailable</a></h3>
          <div class="product_price">
            <p class="price_color">£5.00</p>
            <p class="availability">Out of stock</p>
          </div>
        </article>
        """
        books = parser.parse_books(html, base_url=BASE)
        assert books[0].availability == "no"


class TestGetNextPage:
    def test_returns_next_page_url(self, parser: BookParser) -> None:
        url = parser.get_next_page(CATALOGUE_PAGE_HTML, BASE)
        assert url is not None
        assert "page-2" in url

    def test_last_page_returns_none(self, parser: BookParser) -> None:
        url = parser.get_next_page(LAST_PAGE_HTML, BASE)
        assert url is None

    def test_empty_page_returns_none(self, parser: BookParser) -> None:
        url = parser.get_next_page(EMPTY_PAGE_HTML, BASE)
        assert url is None

    def test_next_url_is_absolute(self, parser: BookParser) -> None:
        url = parser.get_next_page(CATALOGUE_PAGE_HTML, BASE)
        assert url is not None
        assert url.startswith("http://")
