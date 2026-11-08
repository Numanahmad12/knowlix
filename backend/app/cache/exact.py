"""Exact-match caching layer with Redis connection pooling and thread-safe in-memory LRU fallback."""

import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None


class InMemoryExactCache:
    """Thread-safe bounded in-memory LRU cache with per-item TTL expiration."""

    def __init__(self, max_entries: int = 1000):
        self._max_entries = max(10, max_entries)
        # map key -> {"data": dict, "expires_at": float}
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            if time.time() >= item["expires_at"]:
                del self._store[key]
                return None
            # Move to end for LRU
            self._store.move_to_end(key)
            return item["data"]

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
        with self._lock:
            # Evict expired items periodically or when full
            now = time.time()
            if key in self._store:
                del self._store[key]
            elif len(self._store) >= self._max_entries:
                # Remove oldest/expired
                self._evict_expired(now)
                if len(self._store) >= self._max_entries:
                    self._store.popitem(last=False)

            self._store[key] = {
                "data": value,
                "expires_at": now + ttl_seconds,
            }

    def _evict_expired(self, now: float) -> None:
        keys_to_del = [k for k, v in self._store.items() if now >= v["expires_at"]]
        for k in keys_to_del:
            del self._store[k]

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def delete_by_prefix(self, prefix: str) -> int:
        with self._lock:
            matched = [k for k in self._store if k.startswith(prefix)]
            for k in matched:
                del self._store[k]
            return len(matched)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def keys(self) -> List[str]:
        with self._lock:
            now = time.time()
            return [k for k, v in self._store.items() if now < v["expires_at"]]

    def size(self) -> int:
        with self._lock:
            now = time.time()
            self._evict_expired(now)
            return len(self._store)


class RedisExactCache:
    """Redis-backed exact cache using connection pooling and JSON serialization."""

    def __init__(self, redis_url: str):
        if redis is None:
            raise RuntimeError("The 'redis' package is required for RedisExactCache.")
        self._pool = redis.ConnectionPool.from_url(redis_url, max_connections=20)
        self._client = redis.Redis(connection_pool=self._pool, decode_responses=True)
        # Test connection
        self._client.ping()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        raw = self._client.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Failed to deserialize redis cache key %s: %s", key, exc)
            return None

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
        raw = json.dumps(value)
        self._client.setex(key, ttl_seconds, raw)

    def delete(self, key: str) -> bool:
        return bool(self._client.delete(key))

    def delete_by_prefix(self, prefix: str) -> int:
        keys = list(self._client.scan_iter(f"{prefix}*"))
        if keys:
            return self._client.delete(*keys)
        return 0

    def clear(self) -> None:
        # Avoid flushall in shared Redis; delete knowlix keys
        keys = list(self._client.scan_iter("knowlix:cache:*"))
        if keys:
            self._client.delete(*keys)

    def keys(self) -> List[str]:
        return list(self._client.scan_iter("knowlix:cache:*"))

    def size(self) -> int:
        return len(self.keys())


class ExactCacheManager:
    """Façade managing Redis exact caching with automatic graceful in-memory fallback."""

    def __init__(self, redis_url: Optional[str] = None, max_entries: int = 1000):
        self._redis_url = redis_url
        self._max_entries = max_entries
        self._backend: Any = None
        self._is_redis = False
        self._init_backend()

    def _init_backend(self) -> None:
        if self._redis_url and redis is not None:
            try:
                self._backend = RedisExactCache(self._redis_url)
                self._is_redis = True
                logger.info("Connected to Redis exact cache at %s", self._redis_url)
                return
            except Exception as exc:
                logger.warning(
                    "Failed to connect to Redis (%s). Falling back to bounded in-memory exact cache.",
                    exc,
                )
        self._backend = InMemoryExactCache(max_entries=self._max_entries)
        self._is_redis = False

    @property
    def is_redis(self) -> bool:
        return self._is_redis

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            return self._backend.get(key)
        except Exception as exc:
            logger.warning("Exact cache get failed (%s). Falling back.", exc)
            return None

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
        try:
            self._backend.set(key, value, ttl_seconds)
        except Exception as exc:
            logger.warning("Exact cache set failed (%s).", exc)

    def delete(self, key: str) -> bool:
        try:
            return self._backend.delete(key)
        except Exception as exc:
            logger.warning("Exact cache delete failed (%s).", exc)
            return False

    def delete_by_prefix(self, prefix: str) -> int:
        try:
            return self._backend.delete_by_prefix(prefix)
        except Exception as exc:
            logger.warning("Exact cache delete_by_prefix failed (%s).", exc)
            return 0

    def clear(self) -> None:
        try:
            self._backend.clear()
        except Exception as exc:
            logger.warning("Exact cache clear failed (%s).", exc)

    def keys(self) -> List[str]:
        try:
            return self._backend.keys()
        except Exception:
            return []

    def size(self) -> int:
        try:
            return self._backend.size()
        except Exception:
            return 0
