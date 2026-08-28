"""
Export layer for the Enterprise Web Scraper.

Provides three independent exporters:

- ``export_csv``    — tabular CSV via pandas
- ``export_json``   — pretty-printed JSON via stdlib
- ``export_sqlite`` — SQLite persistence via stdlib sqlite3

Each function is idempotent: running the scraper twice will not produce
duplicate rows in SQLite (``INSERT OR IGNORE`` on the primary key) and will
overwrite the CSV/JSON files.

Usage
-----
    from enterprise_web_scraper.exporters import export_csv, export_json, export_sqlite

    export_csv(books, Path("data/output.csv"))
    export_json(books, Path("data/output.json"))
    export_sqlite(books, Path("data/books.db"))
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from enterprise_web_scraper.parser import Book

logger = logging.getLogger("enterprise_web_scraper.exporters")

# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def export_csv(books: list[Book], path: Path) -> None:
    """
    Export *books* to a UTF-8 CSV file at *path*.

    The file is created (or overwritten) on every call.

    Args:
        books: List of Book records to export.
        path:  Destination file path. Parent directories must exist.
    """
    records = [asdict(book) for book in books]
    dataframe = pd.DataFrame(records)

    dataframe.to_csv(path, index=False, encoding="utf-8")

    logger.info("CSV exported: %s (%d rows)", path, len(books))


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def export_json(books: list[Book], path: Path) -> None:
    """
    Export *books* to a UTF-8 JSON file at *path*.

    The file is created (or overwritten) on every call.

    Args:
        books: List of Book records to export.
        path:  Destination file path. Parent directories must exist.
    """
    records = [asdict(book) for book in books]

    with path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=4)

    logger.info("JSON exported: %s (%d records)", path, len(books))


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS books (
    title        TEXT PRIMARY KEY,
    price        TEXT NOT NULL,
    availability TEXT NOT NULL,
    rating       INTEGER NOT NULL DEFAULT 0,
    url          TEXT NOT NULL DEFAULT ''
);
"""

_UPSERT_SQL = """\
INSERT INTO books (title, price, availability, rating, url)
VALUES (:title, :price, :availability, :rating, :url)
ON CONFLICT(title) DO UPDATE SET
    price        = excluded.price,
    availability = excluded.availability,
    rating       = excluded.rating,
    url          = excluded.url;
"""


def export_sqlite(books: list[Book], db_path: Path) -> None:
    """
    Persist *books* to an SQLite database at *db_path*.

    The table ``books`` is created if it does not exist. On conflict (same
    title), the existing row is updated with the latest values (upsert).

    Args:
        books:   List of Book records to persist.
        db_path: Path to the SQLite database file.
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(_CREATE_TABLE_SQL)

        records = [asdict(book) for book in books]
        conn.executemany(_UPSERT_SQL, records)
        conn.commit()

    logger.info("SQLite exported: %s (%d records)", db_path, len(books))
