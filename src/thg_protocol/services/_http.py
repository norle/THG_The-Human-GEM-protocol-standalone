"""Shared bounded HTTP retry."""

import time
from typing import Any

import requests


def request(
    session: Any,
    method: str,
    url: str,
    *,
    timeout: float,
    retries: int,
    backoff: float,
    **kwargs: Any,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = getattr(session, method)(url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error
            if attempt < retries:
                time.sleep(backoff * (2**attempt))
    raise last_error or RuntimeError("HTTP request failed")
