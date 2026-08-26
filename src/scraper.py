from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests import Response
from requests.exceptions import RequestException, Timeout


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL: Final[str] = "http://books.toscrape.com/"
REQUEST_TIMEOUT: Final[int] = 10

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"

CSV_OUTPUT: Final[Path] = DATA_DIR / "output.csv"
JSON_OUTPUT: Final[Path] = DATA_DIR / "output.json"

LOGGER_NAME: Final[str] = "books_scraper"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(LOGGER_NAME)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Book:
    """Represents a normalized book extracted from the source website."""

    title: str
    price: str
    availability: str


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class BooksToScrape:
    """Web scraper for books.toscrape.com."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "EnterpriseWebScraper/1.0 "
                    "(Educational Portfolio Project)"
                )
            }
        )

    def fetch_page(self, url: str) -> Response | None:
        """
        Fetch a web page and handle common network/HTTP failures.

        Returns:
            Response object when successful, otherwise None.
        """
        logger.info("Fetching page: %s", url)

        

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
            )

            response.raise_for_status()

            # The website uses UTF-8, but requests defaults to ISO-8859-1 
            # if charset is not specified in the Content-Type header.
            response.encoding = "utf-8"

            logger.info(
                "Page fetched successfully | status=%s | url=%s",
                response.status_code,
                url,
            )

            return response

        except Timeout:
            logger.error(
                "Request timeout after %ss | url=%s",
                self.timeout,
                url,
            )

        except requests.HTTPError as exc:
            status_code = (
                exc.response.status_code
                if exc.response is not None
                else "unknown"
            )

            logger.error(
                "HTTP error | status=%s | url=%s | error=%s",
                status_code,
                url,
                exc,
            )

        except RequestException as exc:
            logger.error(
                "Network request failed | url=%s | error=%s",
                url,
                exc,
            )

        return None

    @staticmethod
    def parse_book(book_element) -> Book:
        """
        Extract book information using defensive selectors.

        Missing HTML elements are handled using explicit fallback values.
        """
        title_element = book_element.select_one("h3 a")
        price_element = book_element.select_one(".price_color")
        availability_element = book_element.select_one(
            ".availability"
        )

        title = (
            title_element.get("title", "").strip()
            if title_element
            else "Unknown Title"
        )

        price = (
            price_element.get_text(strip=True)
            if price_element
            else "Unknown Price"
        )

        availability_text = (
            availability_element.get_text(" ", strip=True).lower()
            if availability_element
            else ""
        )

        availability = (
            "yes"
            if "in stock" in availability_text
            else "no"
        )

        return Book(
            title=title,
            price=price,
            availability=availability,
        )

    def parse_books(self, html: str) -> list[Book]:
        """
        Parse all book cards from a page.

        Returns an empty list if no book elements are found.
        """
        soup = BeautifulSoup(html, "html.parser")
        book_elements = soup.select("article.product_pod")

        if not book_elements:
            logger.warning("No book elements found on page.")

        books: list[Book] = []

        for element in book_elements:
            try:
                book = self.parse_book(element)
                books.append(book)

            except Exception as exc:
                logger.warning(
                    "Failed to parse a book element: %s",
                    exc,
                )

        logger.info(
            "Extracted %d books from current page.",
            len(books),
        )

        return books

    def get_next_page(self, html: str) -> str | None:
        """Return the relative URL of the next page, if available."""
        soup = BeautifulSoup(html, "html.parser")

        next_link = soup.select_one("li.next a")

        if not next_link:
            return None

        return next_link.get("href")

    def build_page_url(
        self,
        current_url: str,
        next_page: str,
    ) -> str:
        """Build the absolute URL for a pagination link."""
        from urllib.parse import urljoin

        return urljoin(current_url, next_page)

    def scrape(self) -> list[Book]:
        """
        Scrape books from all available pages.

        If a page fails, the scraper logs the error and stops pagination
        instead of crashing the entire pipeline.
        """
        logger.info("Starting scraping process.")

        all_books: list[Book] = []
        current_url = self.base_url
        page_number = 1

        while current_url:
            logger.info(
                "Processing page %d: %s",
                page_number,
                current_url,
            )

            response = self.fetch_page(current_url)

            if response is None:
                logger.error(
                    "Stopping scraper due to page fetch failure."
                )
                break

            books = self.parse_books(response.text)
            all_books.extend(books)

            next_page = self.get_next_page(response.text)

            if not next_page:
                logger.info("No additional pages found.")
                break

            current_url = self.build_page_url(
                current_url,
                next_page,
            )
            page_number += 1

        logger.info(
            "Scraping completed | total_books=%d",
            len(all_books),
        )

        return all_books

    @staticmethod
    def ensure_output_directory() -> None:
        """Create the output directory when it does not exist."""
        DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            "Output directory ready: %s",
            DATA_DIR,
        )

    @staticmethod
    def export_csv(books: list[Book]) -> None:
        """Export scraped records to CSV using Pandas."""
        dataframe = pd.DataFrame(
            [asdict(book) for book in books]
        )

        dataframe.to_csv(
            CSV_OUTPUT,
            index=False,
            encoding="utf-8",
        )

        logger.info(
            "CSV exported successfully: %s",
            CSV_OUTPUT,
        )

    @staticmethod
    def export_json(books: list[Book]) -> None:
        """Export scraped records to JSON."""
        records = [asdict(book) for book in books]

        with JSON_OUTPUT.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                records,
                file,
                ensure_ascii=False,
                indent=4,
            )

        logger.info(
            "JSON exported successfully: %s",
            JSON_OUTPUT,
        )

    def run(self) -> None:
        """Execute the complete scraping and export pipeline."""
        try:
            self.ensure_output_directory()

            books = self.scrape()

            if not books:
                logger.warning(
                    "No records were extracted. "
                    "Output files will still be generated."
                )

            self.export_csv(books)
            self.export_json(books)

            logger.info(
                "Pipeline completed successfully."
            )

        except Exception as exc:
            logger.exception(
                "Unexpected pipeline failure: %s",
                exc,
            )


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    scraper = BooksToScrape()
    scraper.run()