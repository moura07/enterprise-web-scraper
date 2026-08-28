"""
CLI entry point for the Enterprise Web Scraper.

Usage
-----
    uv run scrape                           # run with defaults
    uv run scrape --max-pages 5             # limit to 5 pages
    uv run scrape --formats csv json        # only CSV + JSON output
    uv run scrape --config my_config.toml   # custom config file
    uv run scrape --no-progress             # disable progress bar (CI mode)
    uv run scrape --version                 # print version and exit

Can also be run directly:
    python -m enterprise_web_scraper.cli
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from enterprise_web_scraper import __version__
from enterprise_web_scraper.config import ScraperConfig, load_config
from enterprise_web_scraper.pipeline import ScraperPipeline

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_FORMATS = ("csv", "json", "sqlite")

console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    """Configure structured logging with rich formatting."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=Console(stderr=True),
                rich_tracebacks=True,
                show_path=verbose,
            )
        ],
        force=True,
    )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scrape",
        description=(
            "Enterprise Web Scraper v%(version)s — "
            "scrapes books.toscrape.com and exports to CSV / JSON / SQLite."
            % {"version": __version__}
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  scrape\n"
            "  scrape --max-pages 5\n"
            "  scrape --formats csv json\n"
            "  scrape --config config/custom.toml --no-progress\n"
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "--config",
        metavar="PATH",
        type=Path,
        default=None,
        help="Path to a custom TOML config file (default: config/default.toml).",
    )

    parser.add_argument(
        "--max-pages",
        metavar="N",
        type=int,
        default=None,
        help="Maximum number of pages to scrape. 0 = no limit (default: from config).",
    )

    parser.add_argument(
        "--formats",
        metavar="FMT",
        nargs="+",
        choices=_VALID_FORMATS,
        default=None,
        help=f"Export formats to produce. Choices: {', '.join(_VALID_FORMATS)} (default: from config).",
    )

    parser.add_argument(
        "--no-progress",
        action="store_true",
        default=False,
        help="Disable the interactive progress bar (useful for CI/log pipelines).",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging.",
    )

    return parser


# ---------------------------------------------------------------------------
# Config overrides from CLI args
# ---------------------------------------------------------------------------


def _apply_cli_overrides(
    config: ScraperConfig,
    args: argparse.Namespace,
) -> ScraperConfig:
    """Overlay CLI arguments on top of the loaded config (mutates in place)."""
    if args.max_pages is not None:
        config.scraper.max_pages = args.max_pages

    if args.formats is not None:
        config.output.formats = list(args.formats)

    return config


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    logger = logging.getLogger("enterprise_web_scraper.cli")

    # ------------------------------------------------------------------
    # Validate --config path (if provided)
    # ------------------------------------------------------------------
    if args.config is not None and not args.config.exists():
        console.print(
            f"[bold red]Error:[/bold red] Config file not found: {args.config}"
        )
        return 1

    # ------------------------------------------------------------------
    # Load and patch config
    # ------------------------------------------------------------------
    try:
        config = load_config(args.config)
    except Exception as exc:
        console.print(f"[bold red]Error loading config:[/bold red] {exc}")
        logger.debug("Config load traceback", exc_info=True)
        return 1

    config = _apply_cli_overrides(config, args)

    # ------------------------------------------------------------------
    # Run pipeline
    # ------------------------------------------------------------------
    show_progress = False if args.no_progress else None  # None = auto-detect

    try:
        result = ScraperPipeline(config, show_progress=show_progress).run()
    except Exception as exc:
        console.print(f"[bold red]Pipeline error:[/bold red] {exc}")
        logger.debug("Pipeline traceback", exc_info=True)
        return 1

    if result.total_books == 0:
        console.print("[yellow]Warning:[/yellow] No books were extracted.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
