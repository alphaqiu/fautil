"""
核心模块

提供框架的核心功能，包括应用程序、配置、事件系统和异常处理。
"""

from fautil.core.app import Application, create_app
from fautil.core.config import Settings, load_settings
from fautil.core.events import Event, EventBus, post, post_async, register
from fautil.core.exceptions import APIError, ErrorCode, ErrorDetail
from fautil.core.logging import get_logger, setup_logging

__all__ = [
    "Application",
    "create_app",
    "Settings",
    "load_settings",
    "Event",
    "EventBus",
    "post",
    "post_async",
    "register",
    "APIError",
    "ErrorCode",
    "ErrorDetail",
    "get_logger",
    "setup_logging",
]
