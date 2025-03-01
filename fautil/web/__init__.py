"""
Web模块

提供Web应用构建相关功能，包括API视图、中间件、异常处理和请求上下文。
"""

from fautil.web.cbv import APIView
from fautil.web.context import RequestContext
from fautil.web.exception_handlers import APIException, setup_exception_handlers
from fautil.web.metrics import MetricsManager, setup_metrics
from fautil.web.middleware import (
    RequestLoggingMiddleware,
    RequestTrackingMiddleware,
    TracingMiddleware,
)
from fautil.web.models import (
    ApiResponse,
    ErrorDetail,
    PaginatedData,
    create_response_model,
)

__all__ = [
    "APIView",
    "RequestContext",
    "APIException",
    "setup_exception_handlers",
    "RequestLoggingMiddleware",
    "RequestTrackingMiddleware",
    "TracingMiddleware",
    "ApiResponse",
    "ErrorDetail",
    "PaginatedData",
    "create_response_model",
    "MetricsManager",
    "setup_metrics",
]
