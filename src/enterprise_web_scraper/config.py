"""
Configuration loader for the Enterprise Web Scraper.

Loads values from a TOML file (default: config/default.toml) and allows
environment-variable overrides using the SCRAPER_ prefix.

Usage
-----
    from enterprise_web_scraper.config import load_config

    cfg = load_config()
    print(cfg.scraper.base_url)
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG: Final[Path] = PROJECT_ROOT / "config" / "default.toml"


# ---------------------------------------------------------------------------
# Sub-config dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ScraperSection:
    base_url: str
    timeout: int
    max_pages: int
    delay_between_requests: float


@dataclass
class RetrySection:
    max_attempts: int
    wait_min: float
    wait_max: float
    jitter: bool
    retry_on_status: list[int] = field(default_factory=list)


@dataclass
class OutputSection:
    data_dir: str
    formats: list[str] = field(default_factory=list)
    sqlite_db: str = "data/books.db"


@dataclass
class ScraperConfig:
    scraper: ScraperSection
    retry: RetrySection
    output: OutputSection

    @property
    def data_dir_path(self) -> Path:
        return PROJECT_ROOT / self.output.data_dir

    @property
    def sqlite_db_path(self) -> Path:
        return PROJECT_ROOT / self.output.sqlite_db


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(config_path: Path | None = None) -> ScraperConfig:
    """
    Load configuration from a TOML file with environment variable overrides.

    Priority (highest wins):
        1. Environment variables (SCRAPER_ prefix)
        2. Provided config file
        3. Default config file

    Args:
        config_path: Optional path to a custom TOML config file.

    Returns:
        Fully populated ScraperConfig instance.
    """
    path = config_path or DEFAULT_CONFIG

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    scraper_raw = raw.get("scraper", {})
    retry_raw = raw.get("retry", {})
    output_raw = raw.get("output", {})

    # ------------------------------------------------------------------
    # Environment variable overrides (SCRAPER_ prefix)
    # ------------------------------------------------------------------
    scraper_section = ScraperSection(
        base_url=os.environ.get(
            "SCRAPER_BASE_URL",
            scraper_raw.get("base_url", "http://books.toscrape.com/"),
        ),
        timeout=int(
            os.environ.get("SCRAPER_TIMEOUT", scraper_raw.get("timeout", 10))
        ),
        max_pages=int(
            os.environ.get(
                "SCRAPER_MAX_PAGES", scraper_raw.get("max_pages", 0)
            )
        ),
        delay_between_requests=float(
            os.environ.get(
                "SCRAPER_DELAY",
                scraper_raw.get("delay_between_requests", 0.5),
            )
        ),
    )

    retry_section = RetrySection(
        max_attempts=int(
            os.environ.get(
                "SCRAPER_RETRY_MAX_ATTEMPTS",
                retry_raw.get("max_attempts", 3),
            )
        ),
        wait_min=float(
            os.environ.get(
                "SCRAPER_RETRY_WAIT_MIN",
                retry_raw.get("wait_min", 1.0),
            )
        ),
        wait_max=float(
            os.environ.get(
                "SCRAPER_RETRY_WAIT_MAX",
                retry_raw.get("wait_max", 10.0),
            )
        ),
        jitter=bool(retry_raw.get("jitter", True)),
        retry_on_status=retry_raw.get(
            "retry_on_status", [429, 500, 502, 503, 504]
        ),
    )

    output_section = OutputSection(
        data_dir=os.environ.get(
            "SCRAPER_DATA_DIR", output_raw.get("data_dir", "data")
        ),
        formats=output_raw.get("formats", ["csv", "json", "sqlite"]),
        sqlite_db=os.environ.get(
            "SCRAPER_SQLITE_DB",
            output_raw.get("sqlite_db", "data/books.db"),
        ),
    )

    return ScraperConfig(
        scraper=scraper_section,
        retry=retry_section,
        output=output_section,
    )
