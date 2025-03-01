"""
中间件实现模块

提供FastAPI应用的各种中间件实现。
包括请求日志、跟踪ID、性能监控等。
"""

import logging
import time
import uuid
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from fautil.web.context import RequestContext, RequestTimer, get_client_ip

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """
    请求跟踪中间件

    处理请求跟踪ID的生成、传播和记录，支持分布式请求跟踪。
    """

    def __init__(self, app: FastAPI, header_name: str = "X-Request-ID"):
        """
        初始化请求跟踪中间件

        Args:
            app: FastAPI应用实例
            header_name: 请求ID的HTTP头名称
        """
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 初始化请求ID：从请求头获取或生成新的
        request_id = request.headers.get(self.header_name, str(uuid.uuid4()))

        # 初始化上下文
        RequestContext.set_request_id(request_id)

        # 处理请求
        response = await call_next(request)

        # 添加请求ID到响应头
        response.headers[self.header_name] = request_id

        # 清理上下文
        RequestContext.clear()

        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    请求上下文中间件

    处理请求上下文的初始化和清理，包括：
    - 生成和传播请求ID
    - 初始化请求上下文
    - 在响应头中添加跟踪ID
    """

    def __init__(self, app: FastAPI, header_name: str = "X-Request-ID"):
        """
        初始化请求上下文中间件

        Args:
            app: FastAPI应用实例
            header_name: 请求ID的HTTP头名称
        """
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 初始化请求ID：从请求头获取或生成新的
        request_id = request.headers.get(self.header_name, RequestContext.generate_request_id())

        # 设置请求ID
        RequestContext.set_request_id(request_id)

        # 记录客户端IP
        client_ip = get_client_ip(request)
        RequestContext.set("client_ip", client_ip)

        # 记录请求开始时间
        start_time = time.time()
        RequestContext.set_timer(RequestTimer(start_time))

        # 处理请求
        response = await call_next(request)

        # 添加请求ID到响应头
        response.headers[self.header_name] = request_id

        # 清理上下文
        RequestContext.clear()

        return response


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    请求跟踪中间件

    跟踪处理中的请求，用于优雅关闭和请求统计。
    """

    def __init__(self, app: FastAPI):
        """
        初始化请求跟踪中间件

        Args:
            app: FastAPI应用实例
        """
        super().__init__(app)
        self.active_requests: Dict[str, Request] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 生成请求ID
        request_id = f"{time.time()}-{id(request)}"

        # 添加请求到活跃请求集合
        self.active_requests[request_id] = request

        try:
            # 处理请求
            response = await call_next(request)
            return response
        finally:
            # 从活跃请求集合中移除请求
            self.active_requests.pop(request_id, None)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件

    记录请求和响应的详细信息，包括：
    - 请求方法和路径
    - 响应状态码
    - 处理时间
    - 客户端IP
    - 请求ID
    """

    def __init__(
        self,
        app: FastAPI,
        exclude_paths: Optional[Set[str]] = None,
        log_request_body: bool = False,
    ):
        """
        初始化请求日志中间件

        Args:
            app: FastAPI应用实例
            exclude_paths: 排除的路径集合
            log_request_body: 是否记录请求体
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or {"/health", "/metrics"}
        self.log_request_body = log_request_body

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 如果路径在排除列表中，直接处理请求
        path = request.url.path
        if path in self.exclude_paths:
            return await call_next(request)

        # 获取请求信息
        method = request.method
        # str(request.url)
        client_ip = get_client_ip(request)
        request_id = RequestContext.get_request_id()

        # 日志开始记录
        start_time = time.time()
        logger.info(f"开始处理请求 | {method} {path} | Client: {client_ip} | ID: {request_id}")

        # 可选：记录请求体
        if self.log_request_body and method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    logger.debug(f"请求体: {body.decode('utf-8')}")
            except Exception as e:
                logger.warning(f"读取请求体时出错: {str(e)}")

        # 处理请求
        try:
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time
            status_code = response.status_code

            # 记录响应信息
            logger.info(
                f"完成请求 | {method} {path} | "
                f"状态: {status_code} | "
                f"耗时: {process_time:.4f}秒 | "
                f"ID: {request_id}"
            )

            return response
        except Exception as e:
            # 记录异常信息
            process_time = time.time() - start_time
            logger.error(
                f"请求处理异常 | {method} {path} | "
                f"异常: {str(e)} | "
                f"耗时: {process_time:.4f}秒 | "
                f"ID: {request_id}"
            )
            raise


def setup_middleware(
    app: FastAPI,
    cors_origins: List[str] = None,
    enable_tracing: bool = True,
    enable_request_context: bool = True,
    enable_request_logging: bool = True,
    enable_request_tracking: bool = True,
    request_id_header: str = "X-Request-ID",
    log_request_body: bool = False,
    exclude_log_paths: Optional[Set[str]] = None,
) -> None:
    """
    设置FastAPI应用的中间件

    Args:
        app: FastAPI应用实例
        cors_origins: CORS源列表
        enable_tracing: 是否启用跟踪中间件
        enable_request_context: 是否启用请求上下文中间件
        enable_request_logging: 是否启用请求日志中间件
        enable_request_tracking: 是否启用请求跟踪中间件
        request_id_header: 请求ID的HTTP头名称
        log_request_body: 是否记录请求体
        exclude_log_paths: 排除日志记录的路径
    """
    # 添加CORS中间件
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 添加请求跟踪中间件
    if enable_request_tracking:
        app.add_middleware(RequestTrackingMiddleware)

    # 添加请求日志中间件
    if enable_request_logging:
        app.add_middleware(
            RequestLoggingMiddleware,
            exclude_paths=exclude_log_paths,
            log_request_body=log_request_body,
        )

    # 添加跟踪中间件
    if enable_tracing:
        app.add_middleware(TracingMiddleware, header_name=request_id_header)

    # 添加请求上下文中间件
    if enable_request_context:
        app.add_middleware(RequestContextMiddleware, header_name=request_id_header)

    logger.info(f"Middleware setup completed for {app}")
