#!/usr/bin/env python
"""
服务生命周期和优雅关闭示例

演示改进后的服务生命周期管理和分阶段优雅关闭功能。
"""

# 导入标准库
import asyncio
import os
import signal
import sys
import time
from typing import Dict

# 导入第三方库
from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Request
from injector import Binder, Module, inject, singleton
from loguru import logger
from pydantic import BaseModel, Field


def setup_path_and_import():
    """设置路径并导入项目模块"""
    # 添加项目根目录到路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, project_root)

    # 导入项目模块并返回它们
    from fautil.core.config import Settings
    from fautil.service.api_service import APIService
    from fautil.service.config_manager import ConfigManager
    from fautil.service.discovery_manager import DiscoveryManager
    from fautil.service.injector_manager import InjectorManager
    from fautil.service.lifecycle_manager import (
        ComponentType,
        LifecycleEventType,
        LifecycleManager,
        on_event,
        on_shutdown,
        on_startup,
        post_shutdown,
        pre_startup,
    )
    from fautil.service.service_manager import ServiceManager
    from fautil.service.shutdown_manager import ShutdownManager, ShutdownReason
    from fautil.web.cbv import APIView

    return (
        Settings,
        APIService,
        ConfigManager,
        DiscoveryManager,
        InjectorManager,
        ComponentType,
        LifecycleEventType,
        LifecycleManager,
        on_event,
        on_shutdown,
        on_startup,
        post_shutdown,
        pre_startup,
        ServiceManager,
        ShutdownManager,
        ShutdownReason,
        APIView,
    )


# 导入项目模块
(
    Settings,
    APIService,
    ConfigManager,
    DiscoveryManager,
    InjectorManager,
    ComponentType,
    LifecycleEventType,
    LifecycleManager,
    on_event,
    on_shutdown,
    on_startup,
    post_shutdown,
    pre_startup,
    ServiceManager,
    ShutdownManager,
    ShutdownReason,
    APIView,
) = setup_path_and_import()

# 全局变量定义
ACTIVE_TASKS = {}  # 活跃任务映射
CANCELLED_TASKS = set()  # 已取消任务集合


# 演示配置类
class DemoSettings(Settings):
    """演示配置类"""

    APP_TITLE: str = "生命周期演示服务"
    APP_DESCRIPTION: str = "演示改进后的服务生命周期管理和分阶段优雅关闭功能"
    APP_VERSION: str = "0.1.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    SHUTDOWN_TIMEOUT: int = 60
    GRACEFUL_SHUTDOWN: bool = True
    LOG_LEVEL: str = "INFO"  # 使用大写的日志级别
    WORKERS: int = 1


# 扩展的配置管理器
class ExtendedConfigManager(ConfigManager):
    """扩展的配置管理器，添加了get_app_version方法"""

    def get_app_version(self) -> str:
        """获取应用版本"""
        settings = self.get_settings()
        return getattr(settings, "APP_VERSION", "0.1.0")

    def get_log_level(self) -> str:
        """获取日志级别"""
        settings = self.get_settings()
        log_level = getattr(settings, "LOG_LEVEL", "INFO")
        # 确保日志级别是大写的
        return log_level.upper()

    def get_uvicorn_log_level(self) -> str:
        """获取Uvicorn日志级别"""
        settings = self.get_settings()
        log_level = getattr(settings, "LOG_LEVEL", "INFO")
        # 确保日志级别是小写的
        return log_level.lower()


# 自定义日志管理器
class CustomLoggingManager:
    """自定义日志管理器，用于设置日志级别"""

    @staticmethod
    def setup():
        """设置日志系统"""
        # 移除所有现有处理器
        logger.remove()

        # 添加控制台处理器
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True,
        )


# 异步任务实现
async def long_running_task(task_id: int, duration: float):
    """
    模拟长时间运行的任务

    Args:
        task_id: 任务ID
        duration: 任务持续时间（秒）
    """
    logger.info(f"任务 {task_id} 启动，持续时间: {duration}秒")

    # 在任务映射中记录任务
    ACTIVE_TASKS[task_id] = {
        "id": task_id,
        "start_time": time.time(),
        "duration": duration,
        "task": asyncio.current_task(),
    }

    try:
        # 模拟处理过程
        start_time = time.time()
        while time.time() - start_time < duration:
            # 每0.1秒检查一次是否需要取消
            await asyncio.sleep(0.1)

            # 如果任务被标记为取消，则中断执行
            if task_id in CANCELLED_TASKS:
                logger.info(f"任务 {task_id} 被取消")
                break

        # 如果未被取消且已完成
        if task_id not in CANCELLED_TASKS:
            elapsed = time.time() - start_time
            logger.info(f"任务 {task_id} 完成，实际用时: {elapsed:.2f}秒")
    except asyncio.CancelledError:
        # 捕获取消异常，优雅处理
        logger.info(f"任务 {task_id} 被系统取消")
        # 重新抛出异常以允许正确的异步任务清理
        raise
    finally:
        # 从活跃任务映射中移除
        if task_id in ACTIVE_TASKS:
            del ACTIVE_TASKS[task_id]
        # 从已取消任务集合中移除
        if task_id in CANCELLED_TASKS:
            CANCELLED_TASKS.remove(task_id)


# 生命周期事件处理器


@pre_startup(component_type=ComponentType.CORE, priority=100)
async def pre_startup_handler():
    """服务启动前处理器"""
    logger.info("【生命周期】服务启动前准备工作...")
    await asyncio.sleep(0.5)
    logger.info("【生命周期】服务启动前准备工作完成")


@on_startup(component_type=ComponentType.CORE, priority=100)
async def startup_handler():
    """服务启动后处理器"""
    logger.info("【生命周期】服务已启动，执行初始化工作...")
    await asyncio.sleep(0.5)
    logger.info("【生命周期】初始化工作完成")


@on_event(LifecycleEventType.PRE_HTTP_START, component_type=ComponentType.API)
async def pre_http_start_handler():
    """HTTP服务器启动前处理器"""
    logger.info("【生命周期】HTTP服务器即将启动...")


@on_event(LifecycleEventType.POST_HTTP_START, component_type=ComponentType.API)
async def post_http_start_handler():
    """HTTP服务器启动后处理器"""
    logger.info("【生命周期】HTTP服务器已启动并接受请求")


@on_shutdown(component_type=ComponentType.API, priority=90)
async def api_shutdown_handler(context):
    """API服务关闭处理器"""
    logger.info(f"【生命周期】API服务关闭中... 关闭原因: {context['reason']}")
    await asyncio.sleep(0.5)
    logger.info("【生命周期】API服务已关闭")


@on_shutdown(component_type=ComponentType.SCHEDULER, priority=70)
async def scheduler_shutdown_handler(context):
    """调度器关闭处理器"""
    logger.info(f"【生命周期】调度器关闭中... 关闭阶段: {context['phase']}")
    await asyncio.sleep(0.5)
    logger.info("【生命周期】调度器已关闭")


@on_shutdown(component_type=ComponentType.DATABASE, priority=10)
async def db_shutdown_handler(context):
    """数据库关闭处理器"""
    logger.info(f"【生命周期】数据库关闭中... 消息: {context['message']}")
    await asyncio.sleep(0.5)
    logger.info("【生命周期】数据库已关闭")


@post_shutdown(component_type=ComponentType.CORE)
async def post_shutdown_handler():
    """服务关闭后处理器"""
    logger.info("【生命周期】服务已完全关闭，执行最终清理工作")


# 请求模型


class TaskRequest(BaseModel):
    """任务请求模型"""

    duration: float = Field(..., description="任务持续时间（秒）", gt=0, le=60)


class TaskResponse(BaseModel):
    """任务响应模型"""

    task_id: int
    status: str
    estimated_duration: float


# 视图


class TasksView(APIView):
    """任务管理视图"""

    @inject
    def __init__(self, lifecycle_manager: LifecycleManager = None):
        super().__init__()
        self.router = APIRouter(prefix="/tasks", tags=["任务"])
        self.task_counter = 0
        self.active_tasks: Dict[int, asyncio.Task] = {}
        self.lifecycle_manager = lifecycle_manager

    def register(self, app: FastAPI):
        """注册路由"""

        @self.router.post("/", response_model=TaskResponse)
        async def create_task(
            request: Request, task_data: TaskRequest, background_tasks: BackgroundTasks
        ):
            """创建新任务"""
            self.task_counter += 1
            task_id = self.task_counter

            # 创建后台任务
            task = asyncio.create_task(
                long_running_task(
                    task_id=task_id,
                    duration=task_data.duration,
                )
            )

            # 跟踪任务
            self.active_tasks[task_id] = task

            # 添加任务完成回调
            task.add_done_callback(lambda t: self.active_tasks.pop(task_id, None))

            return TaskResponse(
                task_id=task_id,
                status="running",
                estimated_duration=task_data.duration,
            )

        @self.router.get("/")
        async def list_tasks():
            """列出所有任务"""
            return {
                "active_tasks": len(self.active_tasks),
                "tasks": [
                    {"task_id": task_id, "running": not task.done()}
                    for task_id, task in self.active_tasks.items()
                ],
            }

        @self.router.delete("/{task_id}")
        async def cancel_task(task_id: int):
            """取消任务"""
            if task_id not in self.active_tasks:
                raise HTTPException(status_code=404, detail="Task not found")

            task = self.active_tasks[task_id]
            task.cancel()

            return {"status": "cancelled", "task_id": task_id}

        @self.router.post("/shutdown")
        async def trigger_shutdown(request: Request):
            """触发服务关闭"""
            # 获取关闭管理器
            if hasattr(request.app.state, "injector"):
                shutdown_manager = request.app.state.injector.get(ShutdownManager)

                # 触发关闭
                asyncio.create_task(
                    shutdown_manager.trigger_shutdown(
                        reason=ShutdownReason.API_CALL,
                        message="通过API请求触发关闭",
                    )
                )

                return {"status": "shutdown_initiated"}
            else:
                return {"status": "error", "message": "服务未完全初始化，无法关闭"}

        # 注册路由器
        app.include_router(self.router)

        # 注册关闭事件处理器
        @on_shutdown(component_type=ComponentType.API, priority=95)
        async def cleanup_tasks(context):
            """清理任务处理器"""
            logger.info(f"【任务清理】取消 {len(self.active_tasks)} 个运行中的任务...")

            # 取消所有任务
            for task_id, task in list(self.active_tasks.items()):
                if not task.done():
                    task.cancel()

            # 等待所有任务完成（包括被取消）
            if self.active_tasks:
                pending_tasks = list(self.active_tasks.values())
                await asyncio.gather(*pending_tasks, return_exceptions=True)

            logger.info("【任务清理】所有任务已取消")

        # 将处理器注册到生命周期管理器
        if self.lifecycle_manager:
            self.lifecycle_manager.register_event_listener(
                LifecycleEventType.PRE_SHUTDOWN,
                cleanup_tasks,
                component_type=ComponentType.API,
                priority=95,
            )
            logger.info("已注册任务清理处理器")
        else:
            logger.warning("生命周期管理器未注入，无法注册任务清理处理器")


# 自定义服务模块
class CustomServiceModule(Module):
    """自定义服务模块，用于解决配置加载问题"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.injector_manager = InjectorManager([])
        self.discovery_manager = DiscoveryManager()
        self.lifecycle_manager = LifecycleManager()  # 创建生命周期管理器实例

    def configure(self, binder: Binder) -> None:
        """配置依赖注入绑定"""
        # 绑定已加载的配置管理器
        binder.bind(ConfigManager, to=self.config_manager, scope=singleton)

        # 绑定其他必要的管理器
        binder.bind(InjectorManager, to=self.injector_manager, scope=singleton)
        binder.bind(DiscoveryManager, to=self.discovery_manager, scope=singleton)
        binder.bind(
            LifecycleManager, to=self.lifecycle_manager, scope=singleton
        )  # 绑定生命周期管理器

        # 绑定服务管理器
        service_manager = ServiceManager(
            self.config_manager, self.injector_manager, self.discovery_manager
        )
        # 将生命周期管理器设置为服务管理器的属性
        service_manager.lifecycle_manager = self.lifecycle_manager
        binder.bind(ServiceManager, to=service_manager, scope=singleton)


# 主函数
async def main():
    """主函数"""
    # 设置日志
    CustomLoggingManager.setup()

    # 创建配置管理器
    config_manager = ExtendedConfigManager(DemoSettings)

    try:
        # 加载配置
        settings = await config_manager.load()

        # 创建服务模块
        service_module = CustomServiceModule(config_manager)

        # 创建API服务
        service = APIService(
            app_name=settings.APP_TITLE,
            modules=[service_module],
            settings_class=DemoSettings,
            discovery_packages=["examples"],
        )

        # 注册视图
        service._injector = service._injector_manager.create_injector()
        service._app = service._create_app()
        service.register_view(TasksView)

        logger.info("启动服务，按 Ctrl+C 停止")

        # 获取主机和端口
        host = settings.HOST
        port = settings.PORT

        # 启动服务
        try:
            # 创建关闭事件
            shutdown_event = asyncio.Event()

            # 启动服务，不阻塞主线程
            await service.start(host=host, port=port, log_level="info", block=False)

            # 获取shutdown_manager用于优雅关闭
            shutdown_manager = service._injector.get(ShutdownManager)

            # 设置信号处理器
            def signal_handler(sig, frame):
                logger.info(f"收到信号 {sig}，触发关闭流程")
                # 使用事件循环安全方式创建异步任务
                asyncio.create_task(
                    shutdown_manager.trigger_shutdown(
                        reason=ShutdownReason.SIGNAL, message=f"收到信号 {sig}"
                    )
                )
                # 设置关闭事件，使主循环退出
                shutdown_event.set()

            # 注册信号处理器
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    signal.signal(sig, signal_handler)
                except (NotImplementedError, ValueError, AttributeError):
                    logger.warning(f"无法注册信号 {sig} 处理器")

            logger.info("服务已启动，等待关闭信号...")

            try:
                # 等待关闭事件
                await shutdown_event.wait()
                logger.info("接收到关闭事件，准备优雅关闭...")

                # 等待服务完全关闭
                await service.stop()

                # 等待一小段时间确保所有清理工作完成
                await asyncio.sleep(1.0)

                logger.info("服务已完全关闭")

            except asyncio.CancelledError:
                logger.info("主循环被取消，执行优雅关闭...")
                await service.stop()

        except Exception as e:
            logger.error(f"服务运行期间出错: {str(e)}")
            if service._started:
                await service.stop()

    except Exception as e:
        logger.error(f"初始化失败: {str(e)}")

    logger.info("服务生命周期示例结束")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
