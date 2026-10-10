"""Bounded local and shared cache containing public catalog JSON only."""
import threading
import time
from redis.exceptions import RedisError

class PublicCatalogCache:
    def __init__(self, ttl=3, max_bytes=2_000_000, shared=None):
        self.ttl, self.max_bytes, self.shared = ttl, max_bytes, shared
        self.key='worktv:v1:catalog'
        self._lock = threading.Lock()
        self._value = None
        self._expires = 0

    def get(self, build):
        with self._lock:
            if self._value is not None and time.monotonic() < self._expires:
                return self._value
            value=None
            if self.shared:
                try:value=self.shared.get(self.key)
                except RedisError:pass # Public reads can fall back to PostgreSQL.
            if value is None:
                value=build()
                if self.shared and len(value)<=self.max_bytes:
                    try:self.shared.set(self.key,value,ex=self.ttl)
                    except RedisError:pass
            self._value=value if len(value)<=self.max_bytes else None
            self._expires=time.monotonic()+self.ttl
            return value

    def invalidate(self):
        with self._lock:
            self._value = None
            self._expires = 0
            if self.shared:
                try:self.shared.delete(self.key)
                except RedisError:pass
