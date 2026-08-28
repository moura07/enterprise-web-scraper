"""
Scraping pipeline orchestrator for the Enterprise Web Scraper.

``ScraperPipeline`` coordinates the full lifecycle:
    Config → HTTP fetch → HTML parse → Export

It emits a ``rich`` progress bar when running in an interactive terminal and
falls back to plain logging in non-TTY environments (CI/CD, log aggregators).

Usage
-----
    from enterprise_web_scraper.config import load_config
    from enterprise_web_scraper.pipeline import ScraperPipeline

    cfg = load_config()
    result = ScraperPipeline(cfg).run()
    print(f"Done: {result.total_books} books, {result.pages_scraped} pages.")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from enterprise_web_scraper.config import ScraperConfig
from enterprise_web_scraper.exporters import export_csv, export_json, export_sqlite
from enterprise_web_scraper.http_client import ScraperSession
from enterprise_web_scraper.parser import Book, BookParser

logger = logging.getLogger("enterprise_web_scraper.pipeline")
console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class ScraperResult:
    """Summary of a completed scraping run."""

    total_books: int = 0
    pages_scraped: int = 0
    parse_errors: int = 0
    exports: list[str] = field(default_factory=list)

    def print_summary(self) -> None:
        """Render a rich table summary to stderr."""
        table = Table(
            title="[bold green]Scraping Complete[/bold green]",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")
        table.add_row("Books extracted", str(self.total_books))
        table.add_row("Pages scraped", str(self.pages_scraped))
        table.add_row("Parse errors", str(self.parse_errors))
        table.add_row("Exports", ", ".join(self.exports) if self.exports else "—")
        console.print(table)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class ScraperPipeline:
    """
    Orchestrates the full scraping → parsing → export workflow.

    Args:
        config:      Fully loaded ``ScraperConfig``.
        show_progress: Override TTY detection for progress bar display.
                       ``None`` = auto-detect (default).
    """

    def __init__(
        self,
        config: ScraperConfig,
        show_progress: bool | None = None,
    ) -> None:
        self._config = config
        self._parser = BookParser()
        self._show_progress = (
            show_progress if show_progress is not None else console.is_terminal
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> ScraperResult:
        """
        Execute the complete scraping and export pipeline.

        Returns:
            ``ScraperResult`` with counts and export paths.
        """
        result = ScraperResult()
        all_books: list[Book] = []

        self._ensure_output_dir()

        with ScraperSession(self._config) as session:
            all_books, result.pages_scraped, result.parse_errors = (
                self._scrape_all_pages(session)
            )

        result.total_books = len(all_books)

        if not all_books:
            logger.warning("No books were extracted — skipping export.")
        else:
            result.exports = self._export(all_books)

        if self._show_progress:
            result.print_summary()

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_output_dir(self) -> None:
        data_dir: Path = self._config.data_dir_path
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Output directory ready: %s", data_dir)

    def _scrape_all_pages(
        self, session: ScraperSession
    ) -> tuple[list[Book], int, int]:
        """
        Paginate through all catalogue pages and collect Book records.

        Returns:
            (books, pages_scraped, parse_errors)
        """
        cfg = self._config.scraper
        max_pages = cfg.max_pages  # 0 = no limit

        all_books: list[Book] = []
        parse_errors = 0
        current_url: str | None = cfg.base_url
        pages_scraped = 0

        progress = self._build_progress()

        with progress:
            task = progress.add_task("Scraping pages…", total=None)

            while current_url:
                next_page_num = pages_scraped + 1
                if max_pages and next_page_num > max_pages:
                    logger.info("Reached max_pages limit (%d).", max_pages)
                    break

                progress.update(
                    task,
                    description=f"Page {next_page_num}"
                    + (f"/{max_pages}" if max_pages else ""),
                )

                logger.info("Fetching page %d: %s", next_page_num, current_url)
                response = session.fetch(current_url)

                if response is None:
                    logger.error(
                        "Stopping: page %d could not be fetched.", next_page_num
                    )
                    break

                pages_scraped += 1

                books_on_page = self._parser.parse_books(
                    response.text, base_url=current_url
                )
                all_books.extend(books_on_page)
                parse_errors += max(0, 20 - len(books_on_page))  # rough heuristic

                current_url = self._parser.get_next_page(
                    response.text, current_url
                )

                progress.advance(task)

                if current_url and cfg.delay_between_requests > 0:
                    time.sleep(cfg.delay_between_requests)

        return all_books, pages_scraped, parse_errors

    def _export(self, books: list[Book]) -> list[str]:
        """Run configured exporters and return list of created file paths."""
        cfg = self._config
        data_dir = cfg.data_dir_path
        formats = cfg.output.formats
        exported: list[str] = []

        if "csv" in formats:
            path = data_dir / "output.csv"
            export_csv(books, path)
            exported.append(str(path))

        if "json" in formats:
            path = data_dir / "output.json"
            export_json(books, path)
            exported.append(str(path))

        if "sqlite" in formats:
            db_path = cfg.sqlite_db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            export_sqlite(books, db_path)
            exported.append(str(db_path))

        return exported

    def _build_progress(self) -> Progress:
        """Build a rich Progress instance (real or no-op based on config)."""
        if not self._show_progress:
            # Return a disabled progress bar for non-TTY environments.
            return Progress(disable=True)

        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        )
