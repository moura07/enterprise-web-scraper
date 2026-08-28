"""
Shared pytest fixtures for the Enterprise Web Scraper test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from enterprise_web_scraper.config import (
    OutputSection,
    RetrySection,
    ScraperConfig,
    ScraperSection,
)
from enterprise_web_scraper.parser import Book

# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

# Minimal catalogue page with 2 books
CATALOGUE_PAGE_HTML = """
<html><body>
<article class="product_pod">
  <div class="image_container">
    <a href="catalogue/a-light-in-the-attic_1000/index.html">
      <img class="thumbnail" src="/media/cache/a.jpg" alt="A Light in the Attic">
    </a>
  </div>
  <p class="star-rating Three"></p>
  <h3><a href="catalogue/a-light-in-the-attic_1000/index.html"
         title="A Light in the Attic">A Light in the Attic</a></h3>
  <div class="product_price">
    <p class="price_color">£51.77</p>
    <p class="instock availability">In stock</p>
  </div>
</article>

<article class="product_pod">
  <p class="star-rating One"></p>
  <h3><a href="catalogue/tipping-the-velvet_999/index.html"
         title="Tipping the Velvet">Tipping the Velvet</a></h3>
  <div class="product_price">
    <p class="price_color">£53.74</p>
    <p class="instock availability">
        <i class="icon-ok"></i>
        In stock
    </p>
  </div>
</article>

<ul class="pager">
  <li class="next"><a href="catalogue/page-2.html">next</a></li>
</ul>
</body></html>
"""

LAST_PAGE_HTML = """
<html><body>
<article class="product_pod">
  <p class="star-rating Five"></p>
  <h3><a href="catalogue/last-book_1/index.html"
         title="Last Book">Last Book</a></h3>
  <div class="product_price">
    <p class="price_color">£10.00</p>
    <p class="instock availability">In stock</p>
  </div>
</article>
</body></html>
"""

EMPTY_PAGE_HTML = "<html><body><p>Nothing here</p></body></html>"


# ---------------------------------------------------------------------------
# Config fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_config(tmp_path: Path) -> ScraperConfig:
    """A minimal ScraperConfig pointing outputs to a temp directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    return ScraperConfig(
        scraper=ScraperSection(
            base_url="http://books.toscrape.com/",
            timeout=5,
            max_pages=0,
            delay_between_requests=0.0,
        ),
        retry=RetrySection(
            max_attempts=1,
            wait_min=0.0,
            wait_max=0.0,
            jitter=False,
            retry_on_status=[429, 500, 502, 503, 504],
        ),
        output=OutputSection(
            data_dir=str(data_dir),
            formats=["csv", "json", "sqlite"],
            sqlite_db=str(data_dir / "books.db"),
        ),
    )


# ---------------------------------------------------------------------------
# Book fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_books() -> list[Book]:
    return [
        Book(
            title="A Light in the Attic",
            price="£51.77",
            availability="yes",
            rating=3,
            url="http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        ),
        Book(
            title="Tipping the Velvet",
            price="£53.74",
            availability="yes",
            rating=1,
            url="http://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html",
        ),
    ]
