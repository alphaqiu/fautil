"""
FastAPI Utility 基础框架库

此框架提供了构建FastAPI应用的通用组件和工具。
"""

try:
    # 尝试从自动生成的_version.py导入版本
    from ._version import __version__
except ImportError:
    # 如果_version.py不存在（例如在开发环境中初次克隆后），使用默认版本
    __version__ = "0.0.0.dev0"

# 导出主要模块
from fautil import cache, cli, core, db, messaging, scheduler, storage, utils, web
