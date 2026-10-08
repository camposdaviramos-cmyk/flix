"""Bounded process-local cache for user-independent catalog JSON only."""
import threading
import time

class PublicCatalogCache:
    def __init__(self, ttl=3, max_bytes=2_000_000):
        self.ttl, self.max_bytes = ttl, max_bytes
        self._lock = threading.Lock()
        self._value = None
        self._expires = 0

    def get(self, build):
        # One builder per process prevents a cold-cache burst from duplicating SQL work.
        with self._lock:
            if self._value is not None and time.monotonic() < self._expires:
                return self._value
            value = build()
            self._value = value if len(value) <= self.max_bytes else None
            self._expires = time.monotonic() + self.ttl
            return value

    def invalidate(self):
        with self._lock:
            self._value = None
            self._expires = 0
