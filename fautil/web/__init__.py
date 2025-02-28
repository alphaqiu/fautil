"""
Web模块包括API路由、中间件、CBV实现等功能。
"""

# 导出公共API
from fautil.web.cbv import APIView, api_route
from fautil.web.middleware import setup_middlewares

__all__ = [
    "APIView",
    "api_route",
    "setup_middlewares",
]
