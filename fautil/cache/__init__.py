"""
缓存模块

提供Redis缓存和本地LRU缓存的支持。
"""

from fautil.cache.local import LRUCache, lru_cache
from fautil.cache.redis import RedisCache, redis_cache

__all__ = ["LRUCache", "lru_cache", "RedisCache", "redis_cache"]
