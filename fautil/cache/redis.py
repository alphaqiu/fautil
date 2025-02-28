"""
Redis缓存模块

提供基于Redis的缓存实现，支持分布式缓存和异步操作。
"""

import asyncio
import functools
import inspect
import json
import pickle
from functools import wraps
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar, Union, cast

import redis.asyncio as aioredis
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from fautil.core.config import RedisConfig
from fautil.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RedisCache:
    """基于Redis的缓存实现

    支持同步和异步操作，提供序列化和反序列化功能。
    """

    def __init__(
        self,
        config: RedisConfig,
        namespace: str = "fautil",
        serializer: str = "json",
    ):
        """初始化Redis缓存

        Args:
            config: Redis配置
            namespace: 缓存命名空间，用于隔离不同应用的缓存
            serializer: 序列化器类型，可选"json"或"pickle"
        """
        self.namespace = namespace
        self.config = config

        # 创建连接
        self.redis: Optional[Redis] = None
        self.async_redis: Optional[AsyncRedis] = None

        # 设置序列化器
        if serializer == "json":
            self.serialize = self._serialize_json
            self.deserialize = self._deserialize_json
        elif serializer == "pickle":
            self.serialize = self._serialize_pickle
            self.deserialize = self._deserialize_pickle
        else:
            raise ValueError(f"不支持的序列化器: {serializer}")

        logger.debug(f"创建Redis缓存，命名空间: {namespace}, 序列化器: {serializer}")

    def _make_key(self, key: str) -> str:
        """生成带命名空间的缓存键

        Args:
            key: 原始键

        Returns:
            str: 带命名空间的键
        """
        return f"{self.namespace}:{key}"

    def _serialize_json(self, value: Any) -> bytes:
        """使用JSON序列化值

        Args:
            value: 要序列化的值

        Returns:
            bytes: 序列化后的字节
        """
        return json.dumps(value).encode("utf-8")

    def _deserialize_json(self, value: bytes) -> Any:
        """使用JSON反序列化值

        Args:
            value: 要反序列化的字节

        Returns:
            Any: 反序列化后的值
        """
        if value is None:
            return None
        return json.loads(value.decode("utf-8"))

    def _serialize_pickle(self, value: Any) -> bytes:
        """使用Pickle序列化值

        Args:
            value: 要序列化的值

        Returns:
            bytes: 序列化后的字节
        """
        return pickle.dumps(value)

    def _deserialize_pickle(self, value: bytes) -> Any:
        """使用Pickle反序列化值

        Args:
            value: 要反序列化的字节

        Returns:
            Any: 反序列化后的值
        """
        if value is None:
            return None
        return pickle.loads(value)

    def connect(self) -> Redis:
        """连接到Redis（同步）

        Returns:
            Redis: Redis客户端实例
        """
        if self.redis is None:
            self.redis = Redis(
                host=self.config.url,
                port=6379,
                db=self.config.db,
                password=self.config.password,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                retry_on_timeout=self.config.retry_on_timeout,
                encoding=self.config.encoding,
                decode_responses=False,
            )
            logger.debug("已连接到Redis服务器（同步）")
        return self.redis

    async def connect_async(self) -> AsyncRedis:
        """连接到Redis（异步）

        Returns:
            AsyncRedis: 异步Redis客户端实例
        """
        if self.async_redis is None:
            self.async_redis = await aioredis.from_url(
                f"redis://{self.config.url}",
                db=self.config.db,
                password=self.config.password,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                retry_on_timeout=self.config.retry_on_timeout,
                encoding=self.config.encoding,
                decode_responses=False,
            )
            logger.debug("已连接到Redis服务器（异步）")
        return self.async_redis

    def close(self) -> None:
        """关闭Redis连接（同步）"""
        if self.redis:
            self.redis.close()
            self.redis = None
            logger.debug("已关闭Redis连接（同步）")

    async def close_async(self) -> None:
        """关闭Redis连接（异步）"""
        if self.async_redis:
            await self.async_redis.close()
            self.async_redis = None
            logger.debug("已关闭Redis连接（异步）")

    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """获取缓存值（同步）

        Args:
            key: 缓存键
            default: 默认值，如果键不存在则返回此值

        Returns:
            Optional[T]: 缓存值或默认值
        """
        redis = self.connect()
        value = redis.get(self._make_key(key))
        if value is None:
            return default

        try:
            return cast(T, self.deserialize(value))
        except Exception as e:
            logger.error(f"反序列化缓存值失败: {e}")
            return default

    async def get_async(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """获取缓存值（异步）

        Args:
            key: 缓存键
            default: 默认值，如果键不存在则返回此值

        Returns:
            Optional[T]: 缓存值或默认值
        """
        redis = await self.connect_async()
        value = await redis.get(self._make_key(key))
        if value is None:
            return default

        try:
            return cast(T, self.deserialize(value))
        except Exception as e:
            logger.error(f"反序列化缓存值失败: {e}")
            return default

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值（同步）

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），如果未指定则使用永久缓存

        Returns:
            bool: 是否设置成功
        """
        redis = self.connect()

        try:
            serialized = self.serialize(value)
            if ttl:
                return redis.setex(self._make_key(key), ttl, serialized)
            else:
                return redis.set(self._make_key(key), serialized)
        except Exception as e:
            logger.error(f"序列化缓存值失败: {e}")
            return False

    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值（异步）

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），如果未指定则使用永久缓存

        Returns:
            bool: 是否设置成功
        """
        redis = await self.connect_async()

        try:
            serialized = self.serialize(value)
            if ttl:
                return await redis.setex(self._make_key(key), ttl, serialized)
            else:
                return await redis.set(self._make_key(key), serialized)
        except Exception as e:
            logger.error(f"序列化缓存值失败: {e}")
            return False

    def delete(self, key: str) -> bool:
        """删除缓存值（同步）

        Args:
            key: 缓存键

        Returns:
            bool: 是否删除成功
        """
        redis = self.connect()
        return bool(redis.delete(self._make_key(key)))

    async def delete_async(self, key: str) -> bool:
        """删除缓存值（异步）

        Args:
            key: 缓存键

        Returns:
            bool: 是否删除成功
        """
        redis = await self.connect_async()
        return bool(await redis.delete(self._make_key(key)))

    def exists(self, key: str) -> bool:
        """检查键是否存在（同步）

        Args:
            key: 缓存键

        Returns:
            bool: 如果键存在则返回True，否则返回False
        """
        redis = self.connect()
        return bool(redis.exists(self._make_key(key)))

    async def exists_async(self, key: str) -> bool:
        """检查键是否存在（异步）

        Args:
            key: 缓存键

        Returns:
            bool: 如果键存在则返回True，否则返回False
        """
        redis = await self.connect_async()
        return bool(await redis.exists(self._make_key(key)))

    def expire(self, key: str, ttl: int) -> bool:
        """设置键的过期时间（同步）

        Args:
            key: 缓存键
            ttl: 过期时间（秒）

        Returns:
            bool: 是否设置成功
        """
        redis = self.connect()
        return redis.expire(self._make_key(key), ttl)

    async def expire_async(self, key: str, ttl: int) -> bool:
        """设置键的过期时间（异步）

        Args:
            key: 缓存键
            ttl: 过期时间（秒）

        Returns:
            bool: 是否设置成功
        """
        redis = await self.connect_async()
        return await redis.expire(self._make_key(key), ttl)


def make_cache_key(args: tuple, kwargs: dict) -> str:
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


def redis_cache(
    cache: RedisCache,
    ttl: int = 3600,
    key_prefix: str = "",
    key_func: Optional[Callable] = None,
) -> Callable:
    """Redis缓存装饰器

    可用于装饰同步和异步函数，对函数结果进行缓存。

    Args:
        cache: Redis缓存实例
        ttl: 缓存过期时间（秒）
        key_prefix: 缓存键前缀
        key_func: 自定义键生成函数，默认使用函数参数生成键

    Returns:
        Callable: 装饰器函数
    """
    key_maker = key_func or make_cache_key

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func_name = func.__name__

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # 生成缓存键
                raw_key = key_maker(args, kwargs)
                key = (
                    f"{key_prefix}:{func_name}:{raw_key}"
                    if key_prefix
                    else f"{func_name}:{raw_key}"
                )

                # 检查缓存
                result = await cache.get_async(key)
                if result is not None:
                    logger.debug(f"Redis缓存命中: {key}")
                    return result

                # 调用函数
                logger.debug(f"Redis缓存未命中: {key}")
                result = await func(*args, **kwargs)

                # 缓存结果
                await cache.set_async(key, result, ttl)
                return result

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                # 生成缓存键
                raw_key = key_maker(args, kwargs)
                key = (
                    f"{key_prefix}:{func_name}:{raw_key}"
                    if key_prefix
                    else f"{func_name}:{raw_key}"
                )

                # 检查缓存
                result = cache.get(key)
                if result is not None:
                    logger.debug(f"Redis缓存命中: {key}")
                    return result

                # 调用函数
                logger.debug(f"Redis缓存未命中: {key}")
                result = func(*args, **kwargs)

                # 缓存结果
                cache.set(key, result, ttl)
                return result

            return sync_wrapper

    return decorator
