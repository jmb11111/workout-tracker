from cachetools import TTLCache
from typing import Any, Optional

_cache = TTLCache(maxsize=128, ttl=300)


def cache_get(key: str) -> Optional[Any]:
    return _cache.get(key)


def cache_set(key: str, value: Any) -> None:
    _cache[key] = value


def cache_delete(key: str) -> None:
    _cache.pop(key, None)


def cache_clear() -> None:
    _cache.clear()
