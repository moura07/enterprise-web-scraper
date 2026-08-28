"""
Integration tests for enterprise_web_scraper.pipeline.

The full pipeline (fetch → parse → export) is tested end-to-end using the
``responses`` library to intercept HTTP calls, so no real network access
is made.

Tests cover:
- Successful 2-page scrape with all 3 exporters
- Pipeline stops gracefully when a page fetch fails
- max_pages limit is honoured
- Output files are created with the correct content
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
import responses as resp_mock

from enterprise_web_scraper.pipeline import ScraperPipeline
from tests.conftest import CATALOGUE_PAGE_HTML, EMPTY_PAGE_HTML, LAST_PAGE_HTML

BASE = "http://books.toscrape.com/"
PAGE2_URL = "http://books.toscrape.com/catalogue/page-2.html"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_config_paths(config, tmp_path: Path):
    """Override config output paths to point at tmp_path."""
    config.output.data_dir = str(tmp_path / "data")
    config.output.sqlite_db = str(tmp_path / "data" / "books.db")
    (tmp_path / "data").mkdir(exist_ok=True)
    return config


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPipelineRun:
    @resp_mock.activate
    def test_two_page_scrape_collects_all_books(
        self, test_config, tmp_path: Path
    ) -> None:
        """Pipeline should accumulate books from all pages."""
        test_config = _patch_config_paths(test_config, tmp_path)

        resp_mock.add(resp_mock.GET, BASE, body=CATALOGUE_PAGE_HTML, status=200)
        resp_mock.add(resp_mock.GET, PAGE2_URL, body=LAST_PAGE_HTML, status=200)

        result = ScraperPipeline(test_config, show_progress=False).run()

        # CATALOGUE_PAGE_HTML has 2 books, LAST_PAGE_HTML has 1
        assert result.total_books == 3
        assert result.pages_scraped == 2

    @resp_mock.activate
    def test_csv_is_created(self, test_config, tmp_path: Path) -> None:
        test_config = _patch_config_paths(test_config, tmp_path)

        resp_mock.add(resp_mock.GET, BASE, body=LAST_PAGE_HTML, status=200)

        ScraperPipeline(test_config, show_progress=False).run()

        csv_path = tmp_path / "data" / "output.csv"
        assert csv_path.exists()
        content = csv_path.read_text(encoding="utf-8")
        assert "Last Book" in content

    @resp_mock.activate
    def test_json_is_created_with_correct_structure(
        self, test_config, tmp_path: Path
    ) -> None:
        test_config = _patch_config_paths(test_config, tmp_path)

        resp_mock.add(resp_mock.GET, BASE, body=LAST_PAGE_HTML, status=200)

        ScraperPipeline(test_config, show_progress=False).run()

        json_path = tmp_path / "data" / "output.json"
        assert json_path.exists()
        records = json.loads(json_path.read_text(encoding="utf-8"))
        assert isinstance(records, list)
        assert len(records) == 1
        assert records[0]["title"] == "Last Book"
        assert records[0]["rating"] == 5

    @resp_mock.activate
    def test_sqlite_is_created_with_correct_rows(
        self, test_config, tmp_path: Path
    ) -> None:
        test_config = _patch_config_paths(test_config, tmp_path)

        resp_mock.add(resp_mock.GET, BASE, body=CATALOGUE_PAGE_HTML, status=200)
        resp_mock.add(resp_mock.GET, PAGE2_URL, body=LAST_PAGE_HTML, status=200)

        ScraperPipeline(test_config, show_progress=False).run()

        db_path = tmp_path / "data" / "books.db"
        assert db_path.exists()

        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("SELECT title, rating FROM books ORDER BY title").fetchall()

        titles = [r[0] for r in rows]
        assert "A Light in the Attic" in titles
        assert "Last Book" in titles
        assert len(rows) == 3

    @resp_mock.activate
    def test_pipeline_stops_gracefully_on_fetch_failure(
        self, test_config, tmp_path: Path
    ) -> None:
        """If a page fetch fails, already-collected books are exported."""
        test_config = _patch_config_paths(test_config, tmp_path)

        # First page OK, second page fails
        resp_mock.add(resp_mock.GET, BASE, body=CATALOGUE_PAGE_HTML, status=200)
        resp_mock.add(resp_mock.GET, PAGE2_URL, status=500)

        result = ScraperPipeline(test_config, show_progress=False).run()

        # 2 books from page 1 should be exported despite page 2 failure
        assert result.total_books == 2

    @resp_mock.activate
    def test_max_pages_limit_is_honoured(
        self, test_config, tmp_path: Path
    ) -> None:
        test_config = _patch_config_paths(test_config, tmp_path)
        test_config.scraper.max_pages = 1

        resp_mock.add(resp_mock.GET, BASE, body=CATALOGUE_PAGE_HTML, status=200)
        # Page 2 should never be requested
        resp_mock.add(resp_mock.GET, PAGE2_URL, body=LAST_PAGE_HTML, status=200)

        result = ScraperPipeline(test_config, show_progress=False).run()

        assert result.pages_scraped == 1
        assert result.total_books == 2
        # Only 1 HTTP call should have been made
        assert len(resp_mock.calls) == 1

    @resp_mock.activate
    def test_empty_result_does_not_create_export_files(
        self, test_config, tmp_path: Path
    ) -> None:
        test_config = _patch_config_paths(test_config, tmp_path)

        resp_mock.add(resp_mock.GET, BASE, body=EMPTY_PAGE_HTML, status=200)

        result = ScraperPipeline(test_config, show_progress=False).run()

        assert result.total_books == 0
        assert result.exports == []
        assert not (tmp_path / "data" / "output.csv").exists()

    @resp_mock.activate
    def test_sqlite_upsert_is_idempotent(
        self, test_config, tmp_path: Path
    ) -> None:
        """Running the pipeline twice should not duplicate SQLite rows."""
        test_config = _patch_config_paths(test_config, tmp_path)

        for _ in range(2):
            resp_mock.add(resp_mock.GET, BASE, body=LAST_PAGE_HTML, status=200)
            ScraperPipeline(test_config, show_progress=False).run()

        db_path = tmp_path / "data" / "books.db"
        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]

        assert count == 1  # upsert — no duplicates
