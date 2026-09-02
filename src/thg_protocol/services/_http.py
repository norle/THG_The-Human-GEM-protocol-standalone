"""Shared bounded HTTP retry."""

import time
from typing import Any

try:  # Keep package imports safe in no-dependency wheel smoke tests.
    import requests
except ImportError:  # pragma: no cover - covered by subprocess smoke test
    requests = None  # type: ignore[assignment]


class _UnavailableRequestMixin:
    def _unavailable(self, error: Exception) -> bool:
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        if status_code == 404:
            return True
        if status_code in {408, 425, 429} or (
            isinstance(status_code, int) and status_code >= 500
        ):
            self.failed_requests += 1
            return True
        if (
            requests is not None and isinstance(error, requests.RequestException)
        ) or isinstance(error, ValueError):
            self.failed_requests += 1
            return True
        return False


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
    if requests is None:
        raise RuntimeError("HTTP requests require the 'requests' dependency")
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
