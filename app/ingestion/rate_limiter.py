"""Rate limiter for polite API access.

Strictly enforces requests-per-second ceilings:
- PubMed: default 2.0 req/s without key, 8.0 req/s with key (safely under 3 and 10)
- ClinPGx: configurable request delay
"""

import threading
import time


class RateLimiter:
    """Thread-safe rate limiter enforcing requests per second."""

    def __init__(self, requests_per_second: float):
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self.interval = 1.0 / requests_per_second
        self.lock = threading.Lock()
        self.last_request_time = 0.0

    def wait(self) -> float:
        """Block until next request window is available. Returns sleep duration."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_request_time
            sleep_needed = self.interval - elapsed
            if sleep_needed > 0:
                time.sleep(sleep_needed)
                self.last_request_time = time.monotonic()
                return sleep_needed
            else:
                self.last_request_time = now
                return 0.0

