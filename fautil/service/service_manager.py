"""
服务管理模块

负责管理API服务的生命周期、组件发现和连接、优雅启动和关闭。
提供服务健康检查和状态跟踪功能。
"""

import asyncio
import signal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import FastAPI
from injector import Injector, inject, singleton
from loguru import logger

from fautil.service.config_manager import ConfigManager
from fautil.service.discovery_manager import DiscoveryManager
from fautil.service.injector_manager import InjectorManager


class ServiceStatus(str, Enum):
    """服务状态枚举"""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@singleton
class ServiceManager:
    """
    服务管理器

    负责管理API服务的生命周期、组件发现和连接、优雅启动和关闭。
    提供服务健康检查和状态跟踪功能。
    """

    @inject
    def __init__(
        self,
        config_manager: ConfigManager,
        injector_manager: InjectorManager,
        discovery_manager: DiscoveryManager,
    ):
        """
        初始化服务管理器

        Args:
            config_manager: 配置管理器
            injector_manager: 依赖注入管理器
            discovery_manager: 组件发现管理器
        """
        self.config_manager = config_manager
        self.injector_manager = injector_manager
        self.discovery_manager = discovery_manager

        # 服务状态
        self._status = ServiceStatus.CREATED

        # 组件
        self._app: Optional[FastAPI] = None
        self._injector: Optional[Injector] = None

        # 启动和停止钩子
        self._startup_hooks: List[Callable] = []
        self._shutdown_hooks: List[Callable] = []

        # 服务健康状态
        self._health_status: Dict[str, Any] = {
            "status": "ok",
            "version": config_manager.get_app_version(),
            "components": {},
        }

    @property
    def status(self) -> ServiceStatus:
        """
        获取服务状态

        Returns:
            当前服务状态
        """
        return self._status

    @property
    def app(self) -> FastAPI:
        """
        获取FastAPI应用实例

        Returns:
            FastAPI应用实例

        Raises:
            RuntimeError: 如果应用尚未创建
        """
        if self._app is None:
            raise RuntimeError("FastAPI应用尚未创建")

        return self._app

    @property
    def injector(self) -> Injector:
        """
        获取依赖注入器

        Returns:
            依赖注入器

        Raises:
            RuntimeError: 如果依赖注入器尚未创建
        """
        if self._injector is None:
            raise RuntimeError("依赖注入器尚未创建")

        return self._injector

    def setup(self, app: FastAPI) -> None:
        """
        设置服务

        Args:
            app: FastAPI应用实例
        """
        self._app = app
        self._setup_lifecycle_events()

    def add_startup_hook(self, hook: Callable) -> None:
        """
        添加启动钩子

        Args:
            hook: 启动钩子函数
        """
        self._startup_hooks.append(hook)

    def add_shutdown_hook(self, hook: Callable) -> None:
        """
        添加关闭钩子

        Args:
            hook: 关闭钩子函数
        """
        self._shutdown_hooks.append(hook)

    async def discover_components(self, package_name: str) -> Dict[str, Set[Any]]:
        """
        发现组件

        Args:
            package_name: 包名称

        Returns:
            发现的组件字典
        """
        logger.info(f"开始发现组件，包名: {package_name}")

        # 更新状态
        self._update_status(ServiceStatus.STARTING)

        # 发现组件
        components = self.discovery_manager.discover(package_name)

        # 注册组件
        self._injector = self.injector_manager.get_injector()
        self.discovery_manager.register_components(self.app, self._injector, components)

        return components

    def get_health_status(self) -> Dict[str, Any]:
        """
        获取健康状态

        Returns:
            健康状态字典
        """
        # 更新状态
        self._health_status["status"] = "ok" if self._status == ServiceStatus.RUNNING else "error"

        return self._health_status

    def update_component_health(self, component_name: str, status: Dict[str, Any]) -> None:
        """
        更新组件健康状态

        Args:
            component_name: 组件名称
            status: 状态字典
        """
        self._health_status["components"][component_name] = status

    def _setup_lifecycle_events(self) -> None:
        """
        设置生命周期事件
        """
        if not self._app:
            return

        # 启动事件
        @self._app.on_event("startup")
        async def startup_event():
            """启动事件处理"""
            logger.info("服务启动中...")

            # 运行启动钩子
            for hook in self._startup_hooks:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        await hook()
                    else:
                        hook()
                except Exception as e:
                    logger.error(f"运行启动钩子时出错: {str(e)}")
                    self._update_status(ServiceStatus.ERROR)
                    raise

            # 更新状态
            self._update_status(ServiceStatus.RUNNING)
            logger.info("服务已成功启动")

        # 关闭事件
        @self._app.on_event("shutdown")
        async def shutdown_event():
            """关闭事件处理"""
            logger.info("服务关闭中...")
            self._update_status(ServiceStatus.STOPPING)

            # 运行关闭钩子
            for hook in self._shutdown_hooks:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        await hook()
                    else:
                        hook()
                except Exception as e:
                    logger.error(f"运行关闭钩子时出错: {str(e)}")

            # 更新状态
            self._update_status(ServiceStatus.STOPPED)
            logger.info("服务已成功关闭")

    def _update_status(self, status: ServiceStatus) -> None:
        """
        更新服务状态

        Args:
            status: 新状态
        """
        old_status = self._status
        self._status = status

        if old_status != status:
            logger.info(f"服务状态已更新: {old_status} -> {status}")

    def setup_signal_handlers(self) -> None:
        """
        设置信号处理器

        为SIGINT和SIGTERM信号设置处理器，确保优雅关闭。
        """
        # 获取当前事件循环
        loop = asyncio.get_event_loop()

        # 设置信号处理器
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._handle_signal(s)))

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """
        处理信号

        Args:
            sig: 信号
        """
        logger.info(f"收到信号 {sig.name}，准备关闭服务...")

        # 触发关闭过程
        if self._app:
            # 更新状态
            self._update_status(ServiceStatus.STOPPING)

            # 运行关闭钩子
            for hook in self._shutdown_hooks:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        await hook()
                    else:
                        hook()
                except Exception as e:
                    logger.error(f"运行关闭钩子时出错: {str(e)}")

            # 更新状态
            self._update_status(ServiceStatus.STOPPED)

        # 停止事件循环
        asyncio.get_event_loop().stop()
