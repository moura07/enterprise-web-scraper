"""
HTTP client with retry/backoff for the Enterprise Web Scraper.

Wraps a ``requests.Session`` with tenacity-powered retry logic that handles:
- Transient network errors (timeout, connection reset)
- Rate limiting (HTTP 429) with respect for the ``Retry-After`` header
- Server errors (5xx codes)

Usage
-----
    from enterprise_web_scraper.config import load_config
    from enterprise_web_scraper.http_client import ScraperSession

    cfg = load_config()
    client = ScraperSession(cfg)

    response = client.fetch("http://books.toscrape.com/")
"""

from __future__ import annotations

import logging
import time
from typing import Final

import requests
import tenacity
from requests import Response
from requests.exceptions import ConnectionError, RequestException, Timeout

from enterprise_web_scraper.config import ScraperConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_AGENT: Final[str] = (
    "EnterpriseWebScraper/2.0 (Portfolio Project; "
    "github.com/moura07/enterprise-web-scraper)"
)

logger = logging.getLogger("enterprise_web_scraper.http_client")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _RetryableHTTPError(Exception):
    """Raised inside tenacity retry context for retriable HTTP errors."""

    def __init__(self, response: Response) -> None:
        self.response = response
        super().__init__(
            f"Retriable HTTP error: status={response.status_code} url={response.url}"
        )


def _log_retry_attempt(retry_state: tenacity.RetryCallState) -> None:
    """Tenacity before-sleep callback — logs each retry with context."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "Retry attempt %d/%s | sleeping %.1fs | reason=%s",
        retry_state.attempt_number,
        retry_state.retry_object.stop.max_attempt_number
        if hasattr(retry_state.retry_object.stop, "max_attempt_number")
        else "∞",
        retry_state.next_action.sleep if retry_state.next_action else 0,
        exc,
    )


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class ScraperSession:
    """
    Requests session with automatic retry/backoff.

    Retry behaviour is driven entirely by ``ScraperConfig.retry``.
    All configuration is read once at construction time, so creating a new
    ``ScraperSession`` per run is cheap and safe.
    """

    def __init__(self, config: ScraperConfig) -> None:
        self._config = config
        self._session = self._build_session()
        self._retry_on_status: frozenset[int] = frozenset(
            config.retry.retry_on_status
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, url: str) -> Response | None:
        """
        Fetch *url* with automatic retry/backoff on transient failures.

        Returns:
            ``Response`` on success, ``None`` if all attempts are exhausted.
        """
        logger.info("Fetching: %s", url)

        try:
            return self._fetch_with_retry(url)
        except tenacity.RetryError as exc:
            logger.error(
                "All retry attempts exhausted | url=%s | last_error=%s",
                url,
                exc.last_attempt.exception(),
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Unexpected error during fetch | url=%s | error=%s",
                url,
                exc,
            )
            return None

    def close(self) -> None:
        """Release the underlying requests session."""
        self._session.close()

    def __enter__(self) -> "ScraperSession":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})
        return session

    def _build_retry_decorator(
        self,
    ) -> tenacity.retry:  # type: ignore[type-arg]
        """Build a tenacity retry decorator from config."""
        r = self._config.retry

        wait_strategy: tenacity.wait.wait_base
        if r.jitter:
            wait_strategy = tenacity.wait_random_exponential(
                min=r.wait_min, max=r.wait_max
            )
        else:
            wait_strategy = tenacity.wait_exponential(
                min=r.wait_min, max=r.wait_max
            )

        return tenacity.retry(
            stop=tenacity.stop_after_attempt(r.max_attempts),
            wait=wait_strategy,
            # Retry only on transient network errors or explicitly retriable
            # HTTP status codes (_RetryableHTTPError).
            # requests.HTTPError (raised by raise_for_status for 4xx/5xx that
            # are NOT in retry_on_status) must NOT be retried.
            retry=(
                tenacity.retry_if_exception_type((Timeout, ConnectionError))
                | tenacity.retry_if_exception_type(_RetryableHTTPError)
            ),
            before_sleep=_log_retry_attempt,
            reraise=False,
        )

    def _fetch_with_retry(self, url: str) -> Response:
        """
        Internal fetch that raises on every retriable failure so that
        tenacity can intercept and retry.

        Raises:
            Timeout: On request timeout.
            RequestException: On network-level failure.
            _RetryableHTTPError: On retriable HTTP status codes.
        """
        decorator = self._build_retry_decorator()

        @decorator
        def _attempt() -> Response:
            try:
                response = self._session.get(
                    url,
                    timeout=self._config.scraper.timeout,
                )
            except Timeout:
                logger.warning(
                    "Timeout after %ss | url=%s",
                    self._config.scraper.timeout,
                    url,
                )
                raise

            if response.status_code in self._retry_on_status:
                self._handle_retry_after(response)
                raise _RetryableHTTPError(response)

            response.raise_for_status()
            response.encoding = "utf-8"

            logger.info(
                "OK | status=%s | url=%s",
                response.status_code,
                url,
            )
            return response

        return _attempt()

    def _handle_retry_after(self, response: Response) -> None:
        """
        If the server sent a ``Retry-After`` header (common with 429),
        sleep for the requested duration before tenacity retries.
        """
        retry_after_raw = response.headers.get("Retry-After")
        if retry_after_raw is None:
            return

        try:
            wait_seconds = int(retry_after_raw)
        except ValueError:
            return

        # Only honour Retry-After when it is positive and within config bounds.
        configured_max = self._config.retry.wait_max
        if configured_max > 0:
            wait_seconds = min(wait_seconds, int(configured_max))

        if wait_seconds <= 0:
            return

        logger.warning(
            "Rate limited (429) — honouring Retry-After: %ds | url=%s",
            wait_seconds,
            response.url,
        )
        time.sleep(wait_seconds)
