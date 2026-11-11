"""Tests for HTTP retry and backoff behavior with mocked failures."""

from unittest.mock import MagicMock

import httpx
import pytest

from app.ingestion.retry import RequestFailedError, execute_with_retry


def test_retry_on_500_then_success():
    mock_func = MagicMock()
    # First returns 500, then 502, then 200 OK
    resp_500 = httpx.Response(status_code=500, request=httpx.Request("GET", "https://example.com"))
    resp_502 = httpx.Response(status_code=502, request=httpx.Request("GET", "https://example.com"))
    resp_200 = httpx.Response(status_code=200, text="OK", request=httpx.Request("GET", "https://example.com"))

    mock_func.side_effect = [resp_500, resp_502, resp_200]

    result = execute_with_retry(mock_func, max_retries=3, backoff_factor=0.01)
    assert result.status_code == 200
    assert result.text == "OK"
    assert mock_func.call_count == 3


def test_retry_on_rate_limit_body():
    mock_func = MagicMock()
    # NCBI sometimes returns 200 with "API rate limit exceeded" body
    resp_rate_limit = httpx.Response(
        status_code=200,
        text="ERROR: API rate limit exceeded. Please try again later.",
        request=httpx.Request("GET", "https://example.com"),
    )
    resp_success = httpx.Response(
        status_code=200,
        text='{"header": {"type": "esearch"}}',
        request=httpx.Request("GET", "https://example.com"),
    )

    mock_func.side_effect = [resp_rate_limit, resp_success]

    result = execute_with_retry(mock_func, max_retries=3, backoff_factor=0.01)
    assert result.status_code == 200
    assert "esearch" in result.text
    assert mock_func.call_count == 2


def test_retry_exceeds_max_retries():
    mock_func = MagicMock()
    resp_429 = httpx.Response(status_code=429, request=httpx.Request("GET", "https://example.com"))
    mock_func.side_effect = [resp_429, resp_429]

    with pytest.raises(RequestFailedError):
        execute_with_retry(mock_func, max_retries=2, backoff_factor=0.01)
    assert mock_func.call_count == 2

