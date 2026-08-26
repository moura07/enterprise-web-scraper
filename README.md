# Enterprise Web Scraper & Data Extractor

A production-oriented Python web scraping pipeline designed to demonstrate reliable data extraction, defensive parsing, structured logging, and multi-format data delivery.

The project uses the public test website [Books to Scrape](http://books.toscrape.com/) as its source to demonstrate an end-to-end data extraction workflow into normalized CSV and JSON datasets.

> **Need custom web scraping or data pipeline solutions?**  
> I build resilient, automated data extraction engines tailored to business requirements (e-commerce, real estate, financial data, and market research).  
>  **Contact for Freelance / Contracts:** [matheusmourabr1@gmail.com] | [LinkedIn Profile](https://www.linkedin.com/in/matheus-moura-543180306/) / [Upwork Profile](https://www.upwork.com/freelancers/~015a096ee372c9e094?mp_source=share)]

---

## Key Features

- **Robust Error Handling:** Timeout management, HTTP error handling, and graceful fallback values for missing attributes.
- **Enterprise Design Patterns:** Object-oriented architecture, typed data models (`dataclasses`), and structural logging (zero `print` debugging).
- **Automated Pagination:** Dynamic page navigation and deterministic dataset generation.
- **Modern Package Management:** Built and managed with `uv` for high-performance dependency isolation.

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.10+ | Core application logic |
| `uv` | Dependency and virtual environment management |
| Requests | Robust HTTP client execution |
| BeautifulSoup 4 | Defensive HTML DOM parsing |
| Pandas | CSV processing and structured dataset export |

---

## Design Approach

The scraper follows a simple ingestion pipeline:

```text
HTTP Source
     │
     ▼
Requests Session
     │
     ▼
HTTP Validation
     │
     ▼
BeautifulSoup Parser
     │
     ▼
Typed Book Model
     │
     ├──────────────► CSV
     │
     └──────────────► JSON

---

The implementation intentionally keeps extraction, transformation, and delivery responsibilities separated. This makes the project easier to extend with additional capabilities such as:

- Retry policies
- Rate limiting
- Proxy support
- Data validation
- Database persistence
- Cloud object storage
- Incremental extraction
- Unit and integration tests
- Airflow or Databricks orchestration
- API-based downstream integrations

---

## Error Handling

The scraper is designed to fail gracefully. The following conditions are explicitly handled:

- Request timeouts
- HTTP errors
- Connection failures
- Missing HTML elements
- Empty pages
- Unexpected parsing errors
- Output directory absence

When an individual HTML element is missing, the scraper uses fallback values instead of terminating the pipeline. For example:

- Missing title       -> `Unknown Title`
- Missing price       -> `Unknown Price`
- Missing availability -> `no`

Page-level network failures are logged and stop further pagination without discarding records that were already successfully extracted.

---

## Output Schema

Each extracted record contains the following fields:

| Field | Type | Description |
|---|---|---|
| `title` | string | Book title |
| `price` | string | Book price as displayed by the source |
| `availability` | string | `yes` when the book is in stock, otherwise `no` |

### Example Record:

```json
{
    "title": "A Light in the Attic",
    "price": "£51.77",
    "availability": "yes"
}

---
## Quick Start (Local Setup)

### Prerequisites
- Python 3.10+
- [`uv`](https://github.com/astral-sh/uv) installed

### Execution

```bash
# 1. Clone repository
git clone [https://github.com/moura07/enterprise-web-scraper.git](https://github.com/moura07/enterprise-web-scraper.git)
cd enterprise-web-scraper

# 2. Sync environment & run pipeline via uv
uv run python src/scraper.py