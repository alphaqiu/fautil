"""
API服务核心模块

提供API服务的生命周期管理、依赖注入和信号处理。
实现优雅启动和停止的核心逻辑。
"""

import asyncio
import atexit
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Set, Type

from fastapi import FastAPI
from injector import Binder, Injector, Module, singleton
from loguru import logger

from fautil.core.config import Settings
from fautil.service.config_manager import ConfigManager
from fautil.service.discovery_manager import DiscoveryManager
from fautil.service.http_server_manager import HTTPServerManager
from fautil.service.injector_manager import DiscoveryModule, InjectorManager
from fautil.service.lifecycle_manager import LifecycleEventType, LifecycleManager
from fautil.service.logging_manager import LoggingManager
from fautil.service.service_manager import ServiceManager
from fautil.service.shutdown_manager import ShutdownManager, ShutdownReason
from fautil.web.cbv import APIView


class ServiceModule(Module):
    """
    服务基础模块

    注册基础服务组件到依赖注入容器。

    此模块负责将核心服务组件绑定到Injector容器，包括:
    * ConfigManager - 配置管理器
    * LoggingManager - 日志管理器
    * ServiceManager - 服务管理器
    * HTTPServerManager - HTTP服务器管理器
    * LifecycleManager - 生命周期管理器
    * ShutdownManager - 关闭流程管理器
    * DiscoveryManager - 组件发现管理器

    使用方法：
    ::

        from fautil.service import APIService

        # 创建服务并自动注册ServiceModule
        service = APIService("my_app")

        # 或者手动创建并注册
        from fautil.service import ServiceModule
        from injector import Injector

        injector = Injector([ServiceModule()])
    """

    def configure(self, binder: Binder) -> None:
        """
        配置依赖注入绑定

        将核心服务组件绑定到依赖注入容器。

        参数：
            binder: 依赖注入绑定器
        """
        # 注册配置管理器（如果尚未注册）
        if not self._has_binding(binder, ConfigManager):
            binder.bind(ConfigManager, to=ConfigManager(), scope=singleton)

        # 注册日志管理器（如果尚未注册）
        if not self._has_binding(binder, LoggingManager):
            binder.bind(
                LoggingManager,
                to=LoggingManager(binder.injector.get(ConfigManager)),
                scope=singleton,
            )

        # 注册生命周期事件管理器（如果尚未注册）
        if not self._has_binding(binder, LifecycleManager):
            binder.bind(
                LifecycleManager,
                to=LifecycleManager(),
                scope=singleton,
            )

        # 注册HTTP服务器管理器（如果尚未注册）
        if not self._has_binding(binder, HTTPServerManager):
            binder.bind(
                HTTPServerManager,
                to=HTTPServerManager(binder.injector.get(ConfigManager)),
                scope=singleton,
            )

        # 注册关闭管理器（如果尚未注册）
        if not self._has_binding(binder, ShutdownManager):
            lifecycle_manager = binder.injector.get(LifecycleManager)
            http_server_manager = binder.injector.get(HTTPServerManager)

            binder.bind(
                ShutdownManager,
                to=ShutdownManager(lifecycle_manager, http_server_manager),
                scope=singleton,
            )

        # 注册服务管理器（如果尚未注册）
        if not self._has_binding(binder, ServiceManager):
            config_manager = binder.injector.get(ConfigManager)
            injector_manager = InjectorManager([])
            discovery_manager = DiscoveryManager()
            lifecycle_manager = binder.injector.get(LifecycleManager)

            service_manager = ServiceManager(
                config_manager,
                injector_manager,
                discovery_manager,
            )
            service_manager.lifecycle_manager = lifecycle_manager
            binder.bind(ServiceManager, to=service_manager, scope=singleton)

    def _has_binding(self, binder: Binder, cls: Type[Any]) -> bool:
        """检查是否已有绑定"""
        try:
            binder.injector.get(cls)
            return True
        except Exception:
            return False


class APIService:
    """
    API服务核心类

    管理API服务的生命周期，包括启动、停止和组件发现。
    提供依赖注入、信号处理和优雅关闭功能。

    属性：
        app_name: str
            应用名称，用于日志和指标标识
        injector: Injector
            依赖注入容器实例
        app: Optional[FastAPI]
            FastAPI应用实例，在start()方法调用后可用
        _view_classes: Set[Type[APIView]]
            已注册的视图类集合

    示例：
    ::

        from fautil.service import APIService

        # 创建API服务
        service = APIService(
            app_name="my_app",
            discovery_packages=["my_app"]
        )

        # 注册自定义视图
        from my_app.views import UserView
        service.register_view(UserView)

        # 启动服务
        await service.start(
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )

        # 停止服务
        await service.stop()
    """

    def __init__(
        self,
        app_name: str,
        modules: Optional[List[Module]] = None,
        settings_class: Type[Settings] = Settings,
        discovery_packages: Optional[List[str]] = None,
    ):
        """
        初始化API服务

        参数：
            app_name: str
                应用名称，用于日志和指标标识
            modules: Optional[List[Module]]
                额外的依赖注入模块列表，默认为None
            settings_class: Type[Settings]
                配置类，默认为Settings基类
            discovery_packages: Optional[List[str]]
                要自动发现组件的包列表，默认为None
        """
        self.app_name = app_name
        self._app: Optional[FastAPI] = None
        self._injector: Optional[Injector] = None
        self._settings_class = settings_class
        self._modules = modules or []
        self._discovery_packages = discovery_packages or []
        self._started = False
        self._stopping = False
        self._views: Set[Type[APIView]] = set()

        # 记录服务启动时间
        self._start_time = time.time()

        # 添加服务基础模块
        if not any(isinstance(module, ServiceModule) for module in self._modules):
            self._modules.append(ServiceModule())

        # 创建核心管理器实例
        self._injector_manager = InjectorManager(self._modules)
        self._discovery_manager = DiscoveryManager()

        # 添加发现模块
        if not any(isinstance(module, DiscoveryModule) for module in self._modules):
            self._modules.append(DiscoveryModule(self._discovery_manager))

    async def start(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        log_level: str = "info",
        reload: bool = False,
        workers: Optional[int] = None,
        block: bool = True,
    ) -> None:
        """
        启动API服务

        启动HTTP服务器并运行FastAPI应用。
        如果设置了block=True，则会阻塞直到服务停止。

        参数：
            host: str
                监听主机地址，默认为"127.0.0.1"
            port: int
                监听端口，默认为8000
            log_level: str
                日志级别，默认为"info"
            reload: bool
                是否启用自动重载，默认为False（开发环境推荐）
            workers: Optional[int]
                工作进程数，默认为None（自动决定）
            block: bool
                是否阻塞等待服务停止，默认为True

        示例：
        ::

            # 基本用法
            await service.start()

            # 自定义配置
            await service.start(
                host="0.0.0.0",
                port=8000,
                log_level="debug",
                reload=True,
                block=False
            )

            # 非阻塞启动
            await service.start(block=False)
            # 执行其他操作...
            await service.stop()
        """
        if self._started:
            logger.warning("服务已经在运行中")
            return

        # 确保注入器已初始化
        if self._injector is None:
            self._injector = self._injector_manager.create_injector()

        # 确保应用已创建
        if self._app is None:
            self._app = self._create_app()

        # 注册已添加的视图
        for view_cls in self._views:
            # 确保视图被注册到应用
            view_instance = self._injector.get(view_cls)
            view_instance.register(self._app)
            logger.info(f"视图已注册到应用: {view_cls.__name__}")

        try:
            # 获取服务管理器
            service_manager = self._injector.get(ServiceManager)

            # 触发服务启动前事件
            await service_manager.lifecycle_manager.trigger_event(LifecycleEventType.PRE_STARTUP)

            # 获取HTTP服务器管理器
            http_server_manager = self._injector.get(HTTPServerManager)
            http_server_manager.app = self._app

            # 配置服务器
            http_server_manager.configure_server(
                host=host,
                port=port,
                log_level=log_level,
                reload=reload,
                workers=workers,
            )

            # 注册关闭管理器
            shutdown_manager = self._injector.get(ShutdownManager)
            shutdown_manager.register_signal_handlers()

            # 注册退出处理器
            atexit.register(self._run_atexit_handler)

            # 触发HTTP服务器启动前事件
            await service_manager.lifecycle_manager.trigger_event(LifecycleEventType.PRE_HTTP_START)

            # 启动HTTP服务器
            logger.info(f"正在启动API服务 - 地址: {host}:{port}")
            self._started = True
            self._stopping = False

            # 启动HTTP服务器
            await http_server_manager.start()

            # 触发HTTP服务器启动后事件
            await service_manager.lifecycle_manager.trigger_event(
                LifecycleEventType.POST_HTTP_START
            )

            # 触发服务启动后事件
            await service_manager.lifecycle_manager.trigger_event(LifecycleEventType.POST_STARTUP)

            # 如果是阻塞模式，等待服务器的serve任务完成
            if block and http_server_manager._serve_task:
                try:
                    await http_server_manager._serve_task
                except asyncio.CancelledError:
                    logger.info("服务器任务被取消")
                    await self.stop()
                except Exception as e:
                    logger.error(f"服务器运行时出错: {str(e)}")
                    await self.stop()
                    raise

        except Exception as e:
            logger.error(f"启动API服务时出错: {str(e)}")
            self._started = False
            self._stopping = False
            raise

    async def stop(self) -> None:
        """
        停止API服务

        按照优先级顺序优雅地停止所有服务组件：
        1. 首先停止HTTP服务器，等待处理中的请求完成
        2. 然后停止应用级服务，如定时任务
        3. 最后停止底层服务，如数据库连接

        示例：
        ::

            # 正常关闭服务
            await service.stop()

            # 在异步上下文管理器中使用
            async with contextlib.AsyncExitStack():
                service = APIService("my_app")
                await service.start(block=False)
                # 退出上下文时自动调用stop()
        """
        if not self._started or self._stopping:
            return

        # 标记停止状态
        self._stopping = True

        try:
            # 使用关闭管理器
            logger.info("正在停止API服务...")
            if self._injector:
                try:
                    # 获取关闭管理器
                    shutdown_manager = self._injector.get(ShutdownManager)

                    # 如果关闭流程尚未开始，触发关闭
                    if not shutdown_manager.is_shutting_down:
                        await shutdown_manager.trigger_shutdown(
                            reason=ShutdownReason.API_CALL,
                            message="API服务停止调用",
                        )

                    # 等待关闭完成
                    logger.info("等待关闭流程完成...")
                    await shutdown_manager.wait_for_shutdown()

                except Exception as e:
                    logger.error(f"使用关闭管理器时出错: {str(e)}")

                    # 如果关闭管理器失败，尝试直接停止HTTP服务器
                    try:
                        http_server_manager = self._injector.get(HTTPServerManager)
                        await http_server_manager.stop()
                    except Exception as e2:
                        logger.error(f"尝试直接停止HTTP服务器时出错: {str(e2)}")

                # 移除退出处理器
                try:
                    atexit.unregister(self._run_atexit_handler)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"停止API服务时出错: {str(e)}")
        finally:
            # 无论如何，重置服务状态
            self._started = False
            self._stopping = False
            logger.info("API服务已停止")

    def _create_app(self) -> FastAPI:
        """
        创建FastAPI应用实例

        Returns:
            FastAPI应用实例
        """
        assert self._injector is not None, "依赖注入器未初始化"

        # 获取配置
        config_manager = self._injector.get(ConfigManager)
        settings = config_manager.get_settings()

        # 应用标题和描述
        app_title = getattr(settings, "APP_TITLE", self.app_name)
        app_desc = getattr(settings, "APP_DESCRIPTION", "API服务")
        app_version = getattr(settings, "APP_VERSION", "0.1.0")

        # 文档URL配置
        docs_url = getattr(settings, "DOCS_URL", "/docs")
        redoc_url = getattr(settings, "REDOC_URL", "/redoc")
        openapi_url = getattr(settings, "OPENAPI_URL", "/openapi.json")

        # 创建FastAPI应用实例
        app = FastAPI(
            title=app_title,
            description=app_desc,
            version=app_version,
            docs_url=docs_url,
            redoc_url=redoc_url,
            openapi_url=openapi_url,
            lifespan=self._create_lifespan_context(),  # 新增: 使用自定义lifespan上下文
        )

        # 设置依赖注入容器
        app.state.injector = self._injector

        # 设置应用
        self._setup_app(app)

        return app

    def _create_lifespan_context(self):
        """
        创建FastAPI的lifespan上下文

        创建一个异步上下文管理器，用于处理应用的生命周期事件。
        这确保了应用在启动和关闭时能够执行必要的设置和清理操作。

        Returns:
            AsyncContextManager: lifespan上下文管理器
        """
        logger.debug("创建lifespan上下文管理器")

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # 启动时的操作
            logger.info("应用启动中: lifespan上下文开始")

            # 触发应用启动前的所有处理器
            if self._injector and hasattr(self._injector, "get"):
                try:
                    lifecycle_manager = self._injector.get(LifecycleManager)
                    await lifecycle_manager.trigger_event(LifecycleEventType.PRE_STARTUP)
                except Exception as e:
                    logger.error(f"触发应用启动前事件时出错: {str(e)}")

            yield  # 应用运行时

            # 关闭时的操作
            logger.info("应用关闭中: lifespan上下文结束")

            # 触发应用关闭前的所有处理器
            if self._injector and hasattr(self._injector, "get"):
                try:
                    # 触发HTTP服务器关闭前事件
                    lifecycle_manager = self._injector.get(LifecycleManager)
                    await lifecycle_manager.trigger_event(LifecycleEventType.PRE_HTTP_STOP)

                    # 不再尝试等待活跃请求，因为这可能导致STATE_TRANSITION_ERROR
                    # 触发关闭后事件
                    await lifecycle_manager.trigger_event(LifecycleEventType.POST_HTTP_STOP)
                    logger.info("lifespan关闭流程完成")
                except Exception as e:
                    logger.error(f"lifespan关闭流程中出错: {str(e)}")

        return lifespan

    def _setup_app(self, app: FastAPI) -> None:
        """
        设置FastAPI应用

        Args:
            app: FastAPI应用
        """
        # 添加健康检查路由
        app.add_api_route("/health", self._health_check, methods=["GET"])

        # 可以添加其他全局设置，如CORS、异常处理等

    async def _discover_components(self) -> None:
        """
        发现和注册组件
        """
        logger.info(f"开始发现组件，包列表: {self._discovery_packages}")

        # 获取服务管理器
        service_manager = self._injector.get(ServiceManager)

        # 扫描包
        for package_name in self._discovery_packages:
            logger.info(f"扫描包: {package_name}")
            try:
                # 发现组件
                await service_manager.discover_components(package_name)
            except Exception as e:
                logger.error(f"扫描包 {package_name} 时出错: {str(e)}")

        logger.info("组件发现完成")

    async def _health_check(self) -> Dict[str, Any]:
        """
        健康检查处理器

        Returns:
            健康状态信息
        """
        if self._injector:
            # 如果有服务管理器，使用其健康状态
            try:
                service_manager = self._injector.get(ServiceManager)
                return service_manager.get_health_status()
            except Exception:
                pass

        # 默认健康状态
        uptime = time.time() - self._start_time
        return {
            "status": "ok",
            "app_name": self.app_name,
            "uptime_seconds": int(uptime),
            "timestamp": int(time.time()),
        }

    def register_view(self, view_cls: Type[APIView]) -> None:
        """
        注册API视图

        将视图类添加到待注册列表，在服务启动时注册到FastAPI应用。

        参数：
            view_cls: Type[APIView]
                要注册的视图类，必须是APIView的子类

        示例：
        ::

            from my_app.views import UserView, ProductView

            # 单个注册
            service.register_view(UserView)

            # 批量注册
            for view_cls in [UserView, ProductView]:
                service.register_view(view_cls)

        注意：
            此方法可以在start()方法调用前或之后调用。
            也可以使用自动发现机制，无需手动注册视图类。
        """
        if view_cls in self._views:
            logger.warning(f"视图 {view_cls.__name__} 已注册，跳过")
            return

        # 将视图添加到待注册列表
        logger.info(f"添加视图到注册列表: {view_cls.__name__}")
        self._views.add(view_cls)

        # 如果应用已创建，立即注册视图
        if self._app is not None and self._injector is not None:
            view_instance = self._injector.get(view_cls)
            view_instance.register(self._app)
            logger.info(f"视图已注册: {view_cls.__name__}")

    def _run_atexit_handler(self) -> None:
        """在程序退出时运行的处理器"""
        if self._started and not self._stopping:
            logger.warning("检测到程序退出，但服务未正常关闭，尝试优雅关闭")

            # 在主线程中无法使用asyncio.run，所以只能尝试同步关闭
            if self._injector:
                try:
                    # 记录关闭
                    logger.info("正在执行同步关闭...")

                    # 标记停止状态
                    self._stopping = True
                    self._started = False

                    # 如果有关闭管理器，设置关闭标志
                    try:
                        shutdown_manager = self._injector.get(ShutdownManager)
                        # 仅设置标志，不触发异步流程
                        shutdown_manager._is_shutting_down = True
                        logger.info("已设置关闭标志")
                    except Exception:
                        pass

                    # 记录日志
                    logger.info("服务已通过atexit处理器关闭")
                except Exception as e:
                    logger.error(f"atexit处理器关闭服务时出错: {str(e)}")
