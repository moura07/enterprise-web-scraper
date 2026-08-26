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