"""
Web模块 (Web Module)
===================

提供Web应用开发相关的组件，包括基于类的视图、中间件、异常处理和API响应模型。

主要组件：
---------
* APIView: 基于类的视图基类，支持路由和方法映射
* RequestContext: 请求上下文，提供请求级别的数据存储和跟踪
* APIException: API异常基类，支持自定义异常和错误响应
* ApiResponse: 统一API响应模型，提供标准化的响应格式
* 中间件集: 包括请求日志、跟踪ID、指标收集等中间件

使用方法：
---------
1. 基于类的视图
   ::

       from fautil.web import APIView, route

       class UserView(APIView):
           path = "/users"
           tags = ["用户管理"]

           @route("/", methods=["GET"])
           async def list_users(self):
               # 业务逻辑
               return {"users": [...]}

           @route("/{user_id}", methods=["GET"])
           async def get_user(self, user_id: int):
               # 业务逻辑
               return {"user": {...}}

2. 请求上下文
   ::

       from fautil.web import get_request_context

       async def some_function():
           context = get_request_context()
           request_id = context.request_id
           # 使用上下文数据...

3. 异常处理
   ::

       from fautil.web import APIException, NotFoundError

       # 抛出预定义异常
       raise NotFoundError(message="用户不存在")

       # 自定义异常
       raise APIException(
           status_code=400,
           error_code="INVALID_FORMAT",
           message="无效的数据格式"
       )
"""

from fautil.web.cbv import APIView, api_route, route
from fautil.web.context import RequestContext, get_request_context, has_request_context
from fautil.web.exception_handlers import setup_exception_handlers
from fautil.web.middleware import RequestLoggingMiddleware, TracingMiddleware, setup_middleware
from fautil.web.models import (
    ApiResponse,
    PaginatedData,
    create_paginated_response_model,
    create_response_model,
)

__all__ = [
    # 基于类的视图
    "APIView",
    "route",
    "api_route",
    # 请求上下文
    "RequestContext",
    "get_request_context",
    "has_request_context",
    # 中间件
    "TracingMiddleware",
    "RequestLoggingMiddleware",
    "setup_middleware",
    # 异常处理
    "setup_exception_handlers",
    # 响应模型
    "ApiResponse",
    "PaginatedData",
    "create_response_model",
    "create_paginated_response_model",
]
