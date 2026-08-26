# Enterprise Web Scraper & Data Extractor

A production-oriented Python web scraping pipeline designed to demonstrate
reliable data extraction, defensive parsing, structured logging, and
multi-format data delivery.

The project uses the public test website
[Books to Scrape](http://books.toscrape.com/) as its source and extracts
book metadata into reusable CSV and JSON datasets.

Although intentionally lightweight, the architecture follows principles
commonly applied to enterprise data ingestion workloads: separation of
concerns, typed data models, fault tolerance, deterministic output paths,
and observable execution through structured logging.

---

## Key Features

- Object-oriented Python architecture
- Python 3.10+ with full type hinting
- HTTP requests with configurable timeout handling
- HTTP status validation using `raise_for_status()`
- Network and request exception handling
- Defensive HTML parsing with BeautifulSoup
- Fallback values for missing HTML elements
- Automatic pagination across all available pages
- Standard Python `logging` implementation
- No `print()` statements
- Normalized book data model using `dataclass`
- CSV export using Pandas
- JSON export using Python's standard `json` library
- Automatic creation of the `data/` directory
- Reusable scraper class suitable for future extension

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.10+ | Core application |
| Requests | HTTP communication |
| BeautifulSoup 4 | HTML parsing |
| Pandas | CSV data processing and export |
| JSON | Structured data export |
| Logging | Observability and error reporting |
| Dataclasses | Typed domain model |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/moura07/enterprise-web-scraper
cd enterprise-web-scraper