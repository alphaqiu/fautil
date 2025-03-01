"""
HTTP服务器管理模块

提供HTTP服务器的生命周期管理，包括配置、启动、停止和请求处理追踪。
支持优雅关闭和请求超时控制。
"""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type

import uvicorn
from fastapi import FastAPI, Request, Response
from injector import inject, singleton
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from fautil.core.config import Settings
from fautil.service.config_manager import ConfigManager


class ServerStatus(str, Enum):
    """HTTP服务器状态枚举"""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    请求追踪中间件

    跟踪处理中的请求，支持优雅关闭。
    """

    def __init__(self, app: FastAPI, server_manager: "HTTPServerManager"):
        """
        初始化中间件

        Args:
            app: FastAPI应用
            server_manager: HTTP服务器管理器
        """
        super().__init__(app)
        self.server_manager = server_manager

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求

        Args:
            request: 请求对象
            call_next: 下一个中间件

        Returns:
            响应对象
        """
        # 生成请求ID
        request_id = f"{time.time()}-{id(request)}"

        # 添加请求到正在处理的请求集合
        self.server_manager.add_request(request_id, request)

        try:
            # 处理请求
            response = await call_next(request)
            return response
        finally:
            # 从正在处理的请求集合中移除请求
            self.server_manager.remove_request(request_id)


@singleton
class HTTPServerManager:
    """
    HTTP服务器管理器

    提供HTTP服务器的生命周期管理，包括配置、启动、停止和请求处理追踪。
    支持优雅关闭和请求超时控制。
    """

    @inject
    def __init__(self, config_manager: ConfigManager):
        """
        初始化HTTP服务器管理器

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.settings = config_manager.get_settings()

        # 服务器状态
        self._status = ServerStatus.CREATED

        # 服务器配置
        self._server_config: Optional[uvicorn.Config] = None
        self._server: Optional[uvicorn.Server] = None
        self._serve_task: Optional[asyncio.Task] = None  # 新增：服务器运行任务

        # 应用实例
        self._app: Optional[FastAPI] = None

        # 处理中的请求
        self._active_requests: Dict[str, Request] = {}

        # 请求队列信息
        self._request_queue_size = 0
        self._max_request_queue_size = getattr(
            self.settings, "MAX_REQUEST_QUEUE_SIZE", 100
        )

        # 关闭控制
        self._shutdown_event = asyncio.Event()
        self._shutdown_timeout = getattr(self.settings, "SHUTDOWN_TIMEOUT", 60)
        self._graceful_shutdown = getattr(self.settings, "GRACEFUL_SHUTDOWN", True)

    @property
    def status(self) -> ServerStatus:
        """当前服务器状态"""
        return self._status

    @property
    def app(self) -> FastAPI:
        """FastAPI应用实例"""
        if self._app is None:
            raise RuntimeError("FastAPI应用尚未创建")
        return self._app

    @app.setter
    def app(self, app: FastAPI) -> None:
        """设置FastAPI应用实例"""
        self._app = app

        # 添加请求追踪中间件
        app.add_middleware(RequestTrackingMiddleware, server_manager=self)

    @property
    def active_request_count(self) -> int:
        """当前活跃请求数量"""
        return len(self._active_requests)

    @property
    def request_queue_size(self) -> int:
        """当前请求队列大小"""
        return self._request_queue_size

    def add_request(self, request_id: str, request: Request) -> None:
        """
        添加请求到活跃请求集合

        Args:
            request_id: 请求ID
            request: 请求对象
        """
        self._active_requests[request_id] = request

    def remove_request(self, request_id: str) -> None:
        """
        从活跃请求集合中移除请求

        Args:
            request_id: 请求ID
        """
        if request_id in self._active_requests:
            del self._active_requests[request_id]

    def configure_server(
        self,
        app: FastAPI,
        host: str = None,
        port: int = None,
        workers: int = None,
        log_level: str = None,
        ssl_certfile: str = None,
        ssl_keyfile: str = None,
        timeout_keep_alive: int = None,
        **kwargs,
    ) -> None:
        """
        配置HTTP服务器

        Args:
            app: FastAPI应用
            host: 监听主机
            port: 监听端口
            workers: 工作进程数
            log_level: 日志级别
            ssl_certfile: SSL证书文件
            ssl_keyfile: SSL密钥文件
            timeout_keep_alive: keep-alive超时时间
            **kwargs: 其他uvicorn配置参数
        """
        # 设置应用
        self.app = app

        # 从配置获取默认值
        host = host or getattr(self.settings, "HOST", "127.0.0.1")
        port = port or getattr(self.settings, "PORT", 8000)
        workers = workers or getattr(self.settings, "WORKERS", 1)
        log_level = log_level or getattr(self.settings, "LOG_LEVEL", "info")
        ssl_certfile = ssl_certfile or getattr(self.settings, "SSL_CERTFILE", None)
        ssl_keyfile = ssl_keyfile or getattr(self.settings, "SSL_KEYFILE", None)
        timeout_keep_alive = timeout_keep_alive or getattr(
            self.settings, "TIMEOUT_KEEP_ALIVE", 5
        )

        # 创建服务器配置
        config = {
            "app": app,
            "host": host,
            "port": port,
            "workers": workers,
            "log_level": log_level,
            "loop": "asyncio",
            "timeout_keep_alive": timeout_keep_alive,
            "lifespan": "on",
            **kwargs,
        }

        # 添加SSL配置
        if ssl_certfile and ssl_keyfile:
            config["ssl_certfile"] = ssl_certfile
            config["ssl_keyfile"] = ssl_keyfile

        # 创建uvicorn配置
        self._server_config = uvicorn.Config(**config)

        # 创建uvicorn服务器
        self._server = uvicorn.Server(self._server_config)

        # 禁用标准uvicorn信号处理，由我们的框架处理
        self._server.install_signal_handlers = lambda: None

    async def start(self) -> None:
        """
        启动HTTP服务器

        Raises:
            RuntimeError: 如果服务器未配置
        """
        if self._server_config is None or self._server is None:
            raise RuntimeError("HTTP服务器未配置")

        # 更新状态
        self._update_status(ServerStatus.STARTING)

        # 重置关闭事件
        self._shutdown_event.clear()

        try:
            # 启动服务器 - 改为使用asyncio.create_task
            logger.info(
                f"启动HTTP服务器 - "
                f"地址: {self._server_config.host}:{self._server_config.port}"
            )

            # 创建服务器任务
            self._serve_task = asyncio.create_task(self._server.serve())

            # 更新状态
            self._update_status(ServerStatus.RUNNING)
        except Exception as e:
            # 更新状态
            self._update_status(ServerStatus.ERROR)
            logger.error(f"启动HTTP服务器失败: {str(e)}")
            raise

    async def stop(self) -> None:
        """
        停止HTTP服务器

        支持优雅关闭，等待处理中的请求完成。
        """
        if self._status == ServerStatus.STOPPED:
            return

        # 更新状态
        self._update_status(ServerStatus.STOPPING)

        # 设置关闭事件
        self._shutdown_event.set()

        # 如果需要优雅关闭，等待处理中的请求完成
        if self._graceful_shutdown and self.active_request_count > 0:
            await self._wait_for_active_requests()

        # 安全停止服务器任务
        if self._serve_task and not self._serve_task.done():
            try:
                # 通知服务器应该退出
                if hasattr(self._server, "should_exit"):
                    self._server.should_exit = True

                # 新增: 如果有lifespan处理，确保完成lifespan关闭流程
                if (
                    hasattr(self._server, "lifespan")
                    and self._server.lifespan is not None
                ):
                    try:
                        # 等待lifespan关闭事件完成
                        logger.info("等待lifespan关闭事件完成...")
                        if (
                            hasattr(self._server.lifespan, "shutdown_event")
                            and not self._server.lifespan.shutdown_event.is_set()
                        ):
                            self._server.lifespan.shutdown_event.set()

                        # 如果有shutdown_complete属性，设置它以发出完成信号
                        if (
                            hasattr(self._server.lifespan, "shutdown_complete")
                            and not self._server.lifespan.shutdown_complete.is_set()
                        ):
                            await asyncio.sleep(0.5)  # 给应用一点时间处理关闭
                            self._server.lifespan.shutdown_complete.set()
                            logger.info("已发送lifespan.shutdown.complete信号")
                    except Exception as e:
                        logger.warning(f"处理lifespan关闭时出错: {str(e)}")

                # 等待服务器任务完成
                try:
                    # 给服务器一个合理的时间来完成关闭
                    await asyncio.wait_for(
                        asyncio.shield(self._serve_task), timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("等待服务器任务完成超时，尝试取消任务")
                    self._serve_task.cancel()
                    try:
                        await self._serve_task
                    except asyncio.CancelledError:
                        logger.info("服务器任务已取消")
                    except Exception as e:
                        logger.error(f"取消服务器任务时出错: {str(e)}")
            except Exception as e:
                logger.error(f"停止服务器时出错: {str(e)}")

        # 更新状态
        self._update_status(ServerStatus.STOPPED)
        logger.info("HTTP服务器已停止")

    async def _wait_for_active_requests(self) -> None:
        """等待活跃请求完成，带超时控制"""
        logger.info(f"等待 {self.active_request_count} 个处理中的请求完成...")

        # 等待时间
        timeout = self._shutdown_timeout
        start_time = time.time()

        # 检查是否有活跃请求
        while self.active_request_count > 0:
            # 检查超时
            if time.time() - start_time > timeout:
                logger.warning(
                    f"等待处理中的请求超时（{timeout}秒），"
                    f"仍有 {self.active_request_count} 个请求未完成"
                )
                break

            # 等待一小段时间
            await asyncio.sleep(0.1)

    def get_status_info(self) -> Dict[str, Any]:
        """
        获取服务器状态信息

        Returns:
            状态信息字典
        """
        info = {
            "status": self._status,
            "active_requests": self.active_request_count,
            "request_queue_size": self.request_queue_size,
        }

        # 添加服务器配置信息
        if self._server_config:
            info["host"] = self._server_config.host
            info["port"] = self._server_config.port
            info["workers"] = self._server_config.workers

            # 添加SSL信息
            if (
                hasattr(self._server_config, "ssl_certfile")
                and self._server_config.ssl_certfile
            ):
                info["ssl_enabled"] = True

        return info

    def _update_status(self, status: ServerStatus) -> None:
        """
        更新服务器状态

        Args:
            status: 新状态
        """
        old_status = self._status
        self._status = status

        if old_status != status:
            logger.info(f"HTTP服务器状态已更新: {old_status} -> {status}")
