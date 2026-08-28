"""
Unit tests for enterprise_web_scraper.http_client.

Uses the ``responses`` library to mock HTTP at the socket level so that no
real network requests are made during the test suite.

Tests cover:
- Successful fetch
- 404 raises HTTPError (non-retriable)
- 429 triggers retry and eventually returns None after max_attempts
- 500 triggers retry and eventually returns None after max_attempts
- Timeout triggers retry and eventually returns None after max_attempts
- Retry-After header is respected for 429 responses
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import responses as resp_mock
from requests.exceptions import Timeout

from enterprise_web_scraper.config import (
    OutputSection,
    RetrySection,
    ScraperConfig,
    ScraperSection,
)
from enterprise_web_scraper.http_client import ScraperSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

URL = "http://books.toscrape.com/"


def _make_config(max_attempts: int = 2, wait_max: float = 0.0) -> ScraperConfig:
    """Minimal config with fast retry for tests."""
    return ScraperConfig(
        scraper=ScraperSection(
            base_url=URL,
            timeout=1,
            max_pages=0,
            delay_between_requests=0.0,
        ),
        retry=RetrySection(
            max_attempts=max_attempts,
            wait_min=0.0,
            wait_max=wait_max,
            jitter=False,
            retry_on_status=[429, 500, 502, 503, 504],
        ),
        output=OutputSection(
            data_dir="data",
            formats=[],
            sqlite_db="data/books.db",
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScraperSessionFetch:
    @resp_mock.activate
    def test_successful_200_returns_response(self) -> None:
        resp_mock.add(resp_mock.GET, URL, body="<html/>", status=200)
        with ScraperSession(_make_config()) as client:
            response = client.fetch(URL)
        assert response is not None
        assert response.status_code == 200

    @resp_mock.activate
    def test_404_returns_none_no_retry(self) -> None:
        # 404 is NOT in retry_on_status, so it should NOT retry.
        resp_mock.add(resp_mock.GET, URL, status=404)
        with ScraperSession(_make_config()) as client:
            response = client.fetch(URL)
        # raise_for_status() propagates; fetch() catches and returns None.
        assert response is None
        assert len(resp_mock.calls) == 1  # exactly one attempt

    @resp_mock.activate
    def test_500_retries_and_returns_none(self) -> None:
        resp_mock.add(resp_mock.GET, URL, status=500)
        resp_mock.add(resp_mock.GET, URL, status=500)
        cfg = _make_config(max_attempts=2)
        with ScraperSession(cfg) as client:
            response = client.fetch(URL)
        assert response is None
        assert len(resp_mock.calls) == 2

    @resp_mock.activate
    def test_429_retries_and_returns_none(self) -> None:
        resp_mock.add(resp_mock.GET, URL, status=429)
        resp_mock.add(resp_mock.GET, URL, status=429)
        cfg = _make_config(max_attempts=2)
        with ScraperSession(cfg) as client:
            response = client.fetch(URL)
        assert response is None
        assert len(resp_mock.calls) == 2

    @resp_mock.activate
    def test_429_then_200_succeeds(self) -> None:
        resp_mock.add(resp_mock.GET, URL, status=429)
        resp_mock.add(resp_mock.GET, URL, body="<html/>", status=200)
        cfg = _make_config(max_attempts=3)
        with ScraperSession(cfg) as client:
            response = client.fetch(URL)
        assert response is not None
        assert response.status_code == 200
        assert len(resp_mock.calls) == 2

    @resp_mock.activate
    def test_500_then_200_succeeds(self) -> None:
        resp_mock.add(resp_mock.GET, URL, status=500)
        resp_mock.add(resp_mock.GET, URL, body="<html/>", status=200)
        cfg = _make_config(max_attempts=3)
        with ScraperSession(cfg) as client:
            response = client.fetch(URL)
        assert response is not None
        assert response.status_code == 200

    @resp_mock.activate
    def test_timeout_retries_and_returns_none(self) -> None:
        resp_mock.add(resp_mock.GET, URL, body=Timeout())
        resp_mock.add(resp_mock.GET, URL, body=Timeout())
        cfg = _make_config(max_attempts=2)
        with ScraperSession(cfg) as client:
            response = client.fetch(URL)
        assert response is None

    @resp_mock.activate
    def test_retry_after_header_is_honoured(self) -> None:
        """Verify _handle_retry_after sleeps for the specified number of seconds."""
        resp_mock.add(
            resp_mock.GET,
            URL,
            status=429,
            headers={"Retry-After": "1"},
        )
        resp_mock.add(resp_mock.GET, URL, body="<html/>", status=200)

        # wait_max=5 ensures the Retry-After value (1s) is not zeroed out.
        cfg = _make_config(max_attempts=3, wait_max=5.0)
        with patch("enterprise_web_scraper.http_client.time.sleep") as mock_sleep:
            with ScraperSession(cfg) as client:
                response = client.fetch(URL)

        # sleep(1) must appear among the calls (there may also be tenacity sleeps).
        sleep_args = [call.args[0] for call in mock_sleep.call_args_list]
        assert 1 in sleep_args, f"Expected sleep(1) in calls, got: {sleep_args}"
        assert response is not None
        assert response.status_code == 200

    @resp_mock.activate
    def test_encoding_set_to_utf8(self) -> None:
        resp_mock.add(resp_mock.GET, URL, body="<html/>", status=200)
        with ScraperSession(_make_config()) as client:
            response = client.fetch(URL)
        assert response is not None
        assert response.encoding == "utf-8"
