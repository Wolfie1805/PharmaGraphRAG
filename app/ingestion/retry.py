"""HTTP Retry mechanism with exponential backoff and rate-limit body inspection.

Handles:
- HTTP 429 Too Many Requests
- HTTP 5xx Server Errors (500, 502, 503, 504)
- Rate-limit error messages in response body (e.g. "API rate limit exceeded")
- Stops cleanly after configured maximum attempts
"""

import logging
import time
from typing import Callable

import httpx

logger = logging.getLogger(__name__)


class RequestFailedError(Exception):
    """Raised when an HTTP request permanently fails after all retries."""
    pass


def execute_with_retry(
    request_func: Callable[[], httpx.Response],
    max_retries: int = 5,
    backoff_factor: float = 1.5,
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
    retry_on_rate_limit_body: bool = True,
) -> httpx.Response:
    """Execute a request callable with exponential backoff.

    If response status code is in status_forcelist or response text contains
    rate limit errors, retries up to max_retries.
    """
    attempt = 0
    last_exception: Exception | None = None

    while attempt < max_retries:
        attempt += 1
        try:
            resp = request_func()

            # Check for retryable HTTP status codes
            if resp.status_code in status_forcelist:
                delay = backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    "HTTP %d on attempt %d/%d. Backing off for %.2fs...",
                    resp.status_code, attempt, max_retries, delay
                )
                time.sleep(delay)
                continue

            # Check for 200 OK with rate limit message in body (e.g. NCBI body error)
            if retry_on_rate_limit_body and resp.is_success:
                body_sample = resp.text[:500].lower()
                if "rate limit exceeded" in body_sample or "api rate limit" in body_sample:
                    delay = backoff_factor * (2 ** (attempt - 1))
                    logger.warning(
                        "Rate limit message in response body on attempt %d/%d. "
                        "Backing off for %.2fs...",
                        attempt, max_retries, delay
                    )
                    time.sleep(delay)
                    continue

            # Check for non-2xx client error that is not in forcelist
            resp.raise_for_status()
            return resp

        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            last_exception = exc
            delay = backoff_factor * (2 ** (attempt - 1))
            logger.warning(
                "Request error '%s' on attempt %d/%d. Retrying in %.2fs...",
                str(exc), attempt, max_retries, delay
            )
            time.sleep(delay)

    raise RequestFailedError(
        f"Request failed permanently after {max_retries} attempts: {last_exception}"
    )

