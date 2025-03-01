"""
FastAPI Utility 基础框架库

此框架提供了构建FastAPI应用的通用组件和工具。
"""

import importlib.util

# 使用importlib.util.find_spec检查_version模块是否存在
if importlib.util.find_spec("fautil._version") is not None:
    # 当模块确实存在时才导入
    from ._version import __version__  # type: ignore
else:
    # 如果_version.py不存在（例如在开发环境中初次克隆后），使用默认版本
    __version__ = "0.0.0.dev0"

# 导出主要模块
from fautil import (
    cache,
    cli,
    core,
    db,
    messaging,
    scheduler,
    service,
    storage,
    utils,
    web,
)

__all__ = [
    "cache",
    "cli",
    "core",
    "db",
    "messaging",
    "scheduler",
    "service",
    "storage",
    "utils",
    "web",
]
