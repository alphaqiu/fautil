"""
应用核心模块

提供应用程序的核心功能，包括启动、停止、信号处理等。
"""

import atexit
import signal
import sys
from contextlib import asynccontextmanager
from typing import Callable, Optional

import fastapi
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.middleware.base import BaseHTTPMiddleware

from fautil.core.config import Settings
from fautil.core.events import AppStartEvent, AppStopEvent, post, post_async
from fautil.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """健康检查中间件

    为应用程序添加健康检查端点
    """

    def __init__(self, app: fastapi.FastAPI, path: str = "/health", status_code: int = 200) -> None:
        super().__init__(app)
        self.path = path
        self.status_code = status_code

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求

        如果是健康检查请求，则返回健康状态
        否则继续处理请求

        Args:
            request: 请求对象
            call_next: 下一个处理函数

        Returns:
            Response: 响应对象
        """
        if request.url.path == self.path:
            return Response(
                content='{"status": "ok"}',
                status_code=self.status_code,
                media_type="application/json",
            )
        return await call_next(request)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """应用程序生命周期管理

    Args:
        app: FastAPI应用实例
    """
    # 启动应用
    logger.info("开始启动应用...")

    # 触发应用启动事件
    event = AppStartEvent(app)
    await post_async(event)

    logger.info("应用已启动")

    try:
        yield
    finally:
        # 停止应用
        logger.info("开始关闭应用...")

        # 触发应用停止事件
        event = AppStopEvent(app)
        await post_async(event)

        logger.info("应用已关闭")


class Application:
    """应用程序类

    管理FastAPI应用实例和相关资源
    """

    def __init__(self, settings: Settings) -> None:
        """初始化应用

        Args:
            settings: 应用设置
        """
        self.settings = settings
        self.app_config = settings.app

        # 设置日志
        setup_logging(settings.log)

        # 创建FastAPI实例
        self.app = FastAPI(
            title=self.app_config.title,
            description=self.app_config.description,
            version=self.app_config.version,
            debug=self.app_config.debug,
            lifespan=app_lifespan,
        )

        # 自定义OpenAPI文档
        self._setup_openapi()

        # 添加中间件
        self._setup_middlewares()

        # 添加健康检查
        self._setup_health_check()

        # 注册信号处理
        self._setup_signal_handlers()

        # 注册请求事件钩子
        self._setup_request_hooks()

        logger.info(f"应用 {self.app_config.title} 初始化完成")

    def _setup_openapi(self) -> None:
        """配置OpenAPI文档"""

        def custom_openapi():
            if self.app.openapi_schema:
                return self.app.openapi_schema

            openapi_schema = get_openapi(
                title=self.app.title,
                version=self.app.version,
                description=self.app.description,
                routes=self.app.routes,
            )

            # 自定义文档
            openapi_schema["info"]["x-logo"] = {
                "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
            }

            self.app.openapi_schema = openapi_schema
            return self.app.openapi_schema

        self.app.openapi = custom_openapi

    def _setup_middlewares(self) -> None:
        """配置中间件"""
        # 添加CORS中间件
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.app_config.cors_origins,
            allow_credentials=self.app_config.cors_allow_credentials,
            allow_methods=self.app_config.cors_allow_methods,
            allow_headers=self.app_config.cors_allow_headers,
        )

    def _setup_health_check(self) -> None:
        """配置健康检查"""
        self.app.add_middleware(HealthCheckMiddleware)

    def _setup_signal_handlers(self) -> None:
        """配置信号处理器"""
        # 注册SIGINT和SIGTERM信号处理器
        # 这些信号在Docker容器中用于优雅关闭
        if sys.platform != "win32":
            signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
            for sig in signals:
                signal.signal(sig, self._handle_exit)

        # Windows平台使用atexit确保清理工作
        atexit.register(self._cleanup)

    def _handle_exit(self, sig, frame) -> None:
        """处理退出信号

        Args:
            sig: 信号
            frame: 帧
        """
        logger.info(f"接收到信号 {sig}, 正在关闭...")
        self._cleanup()
        sys.exit(0)

    def _cleanup(self) -> None:
        """执行清理工作"""
        logger.info("正在执行应用清理工作...")
        # 同步触发应用停止事件
        post(AppStopEvent(self.app))

    def _setup_request_hooks(self) -> None:
        """设置请求钩子"""
        pass

    def run(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """运行应用

        Args:
            host: 主机地址，默认使用配置中的host
            port: 端口号，默认使用配置中的port
        """
        import uvicorn

        host = host or self.app_config.host
        port = port or self.app_config.port

        logger.info(f"应用启动中，监听地址: {host}:{port}")

        uvicorn.run(
            app=self.app,
            host=host,
            port=port,
            log_level=self.settings.log.level.value.lower(),
            reload=self.app_config.debug,
        )

    def mount_app(self, path: str, app: FastAPI) -> None:
        """挂载子应用

        Args:
            path: 路径前缀
            app: 要挂载的FastAPI应用
        """
        self.app.mount(path, app)
        logger.info(f"已挂载子应用到路径: {path}")

    def include_router(self, router: fastapi.APIRouter, **kwargs) -> None:
        """包含路由器

        Args:
            router: FastAPI路由器
            **kwargs: 传递给include_router的附加参数
        """
        self.app.include_router(router, **kwargs)
        logger.info(f"已注册路由器: {router}")


def create_app(settings: Optional[Settings] = None) -> Application:
    """创建应用实例

    Args:
        settings: 应用设置，如果未提供则创建默认设置

    Returns:
        Application: 应用实例
    """
    if settings is None:
        from fautil.core.config import load_settings

        settings = load_settings(Settings)

    return Application(settings)
