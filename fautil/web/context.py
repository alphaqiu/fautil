"""
请求上下文管理模块

提供请求上下文和跟踪ID的存储和管理功能。
支持在请求处理过程中在不同组件间共享上下文信息。
"""

import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

from fastapi import Request

# 上下文变量
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")
_request_var: ContextVar[Optional[Request]] = ContextVar("request", default=None)
_context_storage: ContextVar[Dict[str, Any]] = ContextVar("context_storage", default={})


class RequestContext:
    """
    请求上下文

    管理请求级别的上下文信息，包括请求ID、路径、方法等。
    提供存储和检索上下文数据的接口。
    """

    @staticmethod
    def get_request_id() -> str:
        """
        获取当前请求ID

        Returns:
            当前请求ID，如果不存在则返回空字符串
        """
        return _request_id_var.get()

    @staticmethod
    def set_request_id(request_id: str) -> None:
        """
        设置当前请求ID

        Args:
            request_id: 请求ID
        """
        _request_id_var.set(request_id)

    @staticmethod
    def get_request() -> Optional[Request]:
        """
        获取当前请求对象

        Returns:
            当前请求对象，如果不存在则返回None
        """
        return _request_var.get()

    @staticmethod
    def set_request(request: Request) -> None:
        """
        设置当前请求对象

        Args:
            request: 请求对象
        """
        _request_var.set(request)

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """
        获取上下文数据

        Args:
            key: 数据键
            default: 默认值

        Returns:
            上下文数据值，如果不存在则返回默认值
        """
        storage = _context_storage.get()
        return storage.get(key, default)

    @staticmethod
    def set(key: str, value: Any) -> None:
        """
        设置上下文数据

        Args:
            key: 数据键
            value: 数据值
        """
        storage = _context_storage.get().copy()
        storage[key] = value
        _context_storage.set(storage)

    @staticmethod
    def get_all() -> Dict[str, Any]:
        """
        获取所有上下文数据

        Returns:
            所有上下文数据的副本
        """
        return _context_storage.get().copy()

    @staticmethod
    def clear() -> None:
        """清除上下文数据"""
        _context_storage.set({})

    @staticmethod
    def generate_request_id() -> str:
        """
        生成新的请求ID

        Returns:
            生成的请求ID
        """
        return str(uuid.uuid4())


class RequestTimer:
    """
    请求计时器

    跟踪请求处理时间。
    """

    __slots__ = ("start_time", "end_time")

    def __init__(self):
        """初始化计时器"""
        self.start_time = time.time()
        self.end_time: Optional[float] = None

    def stop(self) -> float:
        """
        停止计时

        Returns:
            处理时间（毫秒）
        """
        self.end_time = time.time()
        return self.elapsed_ms()

    def elapsed_ms(self) -> float:
        """
        获取已经过时间（毫秒）

        Returns:
            已经过时间（毫秒）
        """
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000


async def get_client_ip(request: Request) -> str:
    """
    获取客户端IP地址

    首先尝试从X-Forwarded-For头获取，然后从请求中获取。

    Args:
        request: 请求对象

    Returns:
        客户端IP地址
    """
    if "X-Forwarded-For" in request.headers:
        return request.headers["X-Forwarded-For"].split(",")[0].strip()

    if hasattr(request, "client") and request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"
