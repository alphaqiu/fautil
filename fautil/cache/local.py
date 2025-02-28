"""
本地缓存模块

提供基于LRU(最近最少使用)算法的本地缓存实现。
"""

import asyncio
import functools
import inspect
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar, Union, cast

from fautil.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """基于LRU算法的本地缓存

    使用OrderedDict实现LRU缓存，支持设置缓存大小和过期时间。
    """

    def __init__(self, maxsize: int = 128, ttl: int = 0):
        """初始化LRU缓存

        Args:
            maxsize: 最大缓存条目数
            ttl: 缓存过期时间（秒），0表示不过期
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict[K, tuple[V, float]] = OrderedDict()
        logger.debug(f"创建LRU缓存，最大大小: {maxsize}, TTL: {ttl}秒")

    def __contains__(self, key: K) -> bool:
        """检查键是否在缓存中

        Args:
            key: 缓存键

        Returns:
            bool: 如果键在缓存中且未过期则返回True，否则返回False
        """
        if key not in self._cache:
            return False

        # 检查是否过期
        if self.ttl > 0:
            _, timestamp = self._cache[key]
            if time.time() - timestamp > self.ttl:
                self._cache.pop(key)
                return False

        return True

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """获取缓存值

        Args:
            key: 缓存键
            default: 默认值，如果键不存在则返回此值

        Returns:
            Optional[V]: 缓存值或默认值
        """
        if key not in self:
            return default

        # 移动到最后（表示最近使用）
        value, _ = self._cache.pop(key)
        self._cache[key] = (value, time.time())

        return value

    def set(self, key: K, value: V) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
        """
        # 如果键已存在，则移除
        if key in self._cache:
            self._cache.pop(key)

        # 如果缓存已满，则移除最早使用的条目
        if len(self._cache) >= self.maxsize:
            self._cache.popitem(last=False)

        # 添加新条目
        self._cache[key] = (value, time.time())

    def remove(self, key: K) -> None:
        """移除缓存值

        Args:
            key: 缓存键
        """
        if key in self._cache:
            self._cache.pop(key)

    def clear(self) -> None:
        """清除所有缓存"""
        self._cache.clear()

    def items(self) -> list[tuple[K, V]]:
        """返回所有缓存项

        Returns:
            list[tuple[K, V]]: 缓存项列表
        """
        return [(k, v) for k, (v, _) in self._cache.items()]

    def prune(self) -> int:
        """清除过期的缓存项

        Returns:
            int: 清除的缓存项数量
        """
        if self.ttl <= 0:
            return 0

        now = time.time()
        expired_keys = [
            k for k, (_, timestamp) in self._cache.items() if now - timestamp > self.ttl
        ]

        for key in expired_keys:
            self._cache.pop(key)

        return len(expired_keys)

    def __len__(self) -> int:
        """返回缓存中的条目数

        Returns:
            int: 缓存条目数
        """
        return len(self._cache)


def make_key(args: tuple, kwargs: dict) -> str:
    """根据函数参数生成缓存键

    Args:
        args: 位置参数
        kwargs: 关键字参数

    Returns:
        str: 缓存键
    """
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return ":".join(key_parts)


def lru_cache(
    maxsize: int = 128, ttl: int = 0, key_func: Optional[Callable] = None
) -> Callable:
    """LRU缓存装饰器

    可用于装饰同步和异步函数，对函数结果进行缓存。

    Args:
        maxsize: 最大缓存条目数
        ttl: 缓存过期时间（秒），0表示不过期
        key_func: 自定义键生成函数，默认使用函数参数生成键

    Returns:
        Callable: 装饰器函数
    """
    cache = LRUCache(maxsize=maxsize, ttl=ttl)
    key_maker = key_func or make_key

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = key_maker(args, kwargs)

                # 检查缓存
                result = cache.get(key)
                if result is not None:
                    logger.debug(f"缓存命中: {func.__name__}:{key}")
                    return result

                # 调用函数
                logger.debug(f"缓存未命中: {func.__name__}:{key}")
                result = await func(*args, **kwargs)

                # 缓存结果
                cache.set(key, result)
                return result

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = key_maker(args, kwargs)

                # 检查缓存
                result = cache.get(key)
                if result is not None:
                    logger.debug(f"缓存命中: {func.__name__}:{key}")
                    return result

                # 调用函数
                logger.debug(f"缓存未命中: {func.__name__}:{key}")
                result = func(*args, **kwargs)

                # 缓存结果
                cache.set(key, result)
                return result

            return sync_wrapper

    return decorator
