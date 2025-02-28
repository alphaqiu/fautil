"""
中间件模块

提供API中间件实现，包括CORS、JWT认证等。
"""

import logging
import time
from typing import Callable, List, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from fautil.core.config import AppConfig

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件

    记录请求的处理时间和状态码
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        处理请求

        Args:
            request: 请求对象
            call_next: 下一个处理函数

        Returns:
            Response: 响应对象
        """
        # 记录开始时间
        start_time = time.time()

        # 处理请求
        try:
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求信息
            logger.info(
                f"{request.method} {request.url.path} "
                f"- {response.status_code} - {process_time:.4f}s"
            )

            # 添加处理时间头
            response.headers["X-Process-Time"] = str(process_time)

            return response
        except Exception as e:
            # 计算处理时间
            process_time = time.time() - start_time

            # 记录错误信息
            logger.error(
                f"{request.method} {request.url.path} "
                f"- 500 - {process_time:.4f}s - {str(e)}"
            )

            # 重新抛出异常
            raise e


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    JWT认证中间件

    验证请求头中的JWT令牌
    """

    def __init__(
        self,
        app: FastAPI,
        jwt_secret: str,
        exclude_paths: List[str] = None,
    ):
        """
        初始化中间件

        Args:
            app: FastAPI应用
            jwt_secret: JWT密钥
            exclude_paths: 排除的路径列表
        """
        super().__init__(app)
        self.jwt_secret = jwt_secret
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json"]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        处理请求

        Args:
            request: 请求对象
            call_next: 下一个处理函数

        Returns:
            Response: 响应对象
        """
        # 检查是否需要排除
        for path in self.exclude_paths:
            if request.url.path.startswith(path):
                return await call_next(request)

        # 获取认证头
        auth_header = request.headers.get("Authorization")

        # 验证认证头
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"code": "UNAUTHORIZED", "message": "未提供有效的认证令牌"},
            )

        # 提取令牌
        token = auth_header.replace("Bearer ", "")

        # 验证令牌
        try:
            import jwt

            # 解码令牌
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])

            # 将用户信息添加到请求状态
            request.state.user = payload

            # 继续处理
            return await call_next(request)
        except jwt.PyJWTError as e:
            return JSONResponse(
                status_code=401,
                content={
                    "code": "UNAUTHORIZED",
                    "message": f"无效的认证令牌: {str(e)}",
                },
            )


def setup_middlewares(app: FastAPI, config: AppConfig) -> None:
    """
    设置中间件

    Args:
        app: FastAPI应用
        config: 应用配置
    """
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=config.cors_allow_methods,
        allow_headers=config.cors_allow_headers,
    )

    # 添加请求日志中间件
    app.add_middleware(RequestLoggingMiddleware)

    # 添加健康检查路由
    @app.get("/health")
    async def health() -> dict:
        """健康检查接口"""
        return {"status": "ok", "timestamp": time.time()}
