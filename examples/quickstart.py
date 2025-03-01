"""
快速入门示例

展示fautil框架的基本用法，包括：
- 创建API服务
- 定义API视图
- 使用依赖注入
- 异常处理
- 响应模型

运行方法：
python -m examples.quickstart
"""

import asyncio
import logging
from typing import List, Optional, TypeVar

from injector import Binder, Module, inject, provider, singleton
from pydantic import BaseModel

from fautil.core.config import Settings
from fautil.service import APIService
from fautil.service.config_manager import ConfigManager
from fautil.service.http_server_manager import HTTPServerManager, ServerStatus
from fautil.web import ApiResponse, APIView, create_response_model, route

# 获取日志记录器
logger = logging.getLogger(__name__)

# ---- 配置管理 ----

T = TypeVar("T", bound=Settings)


class ExtendedConfigManager(ConfigManager):
    """扩展的配置管理器，添加app_version方法"""

    def get_app_version(self) -> str:
        """获取应用版本"""
        return "1.0.0"


# 创建扩展的HTTPServerManager类
class ExtendedHTTPServerManager(HTTPServerManager):
    """扩展的HTTP服务器管理器，解决app参数问题和STATE_TRANSITION_ERROR"""

    def configure_server(
        self,
        app=None,  # 允许app为可选参数
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
        配置HTTP服务器（处理app参数问题）

        如果app参数为None，则使用已设置的self._app
        """
        # 如果app参数为None，则使用已设置的self._app
        if app is None:
            app = self._app

        # 调用父类方法
        super().configure_server(
            app=app,
            host=host,
            port=port,
            workers=workers,
            log_level=log_level,
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
            timeout_keep_alive=timeout_keep_alive,
            **kwargs,
        )

    async def stop(self) -> None:
        """
        停止HTTP服务器

        重写父类方法，确保返回协程而不是Future对象，
        解决STATE_TRANSITION_ERROR错误。
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

                # 如果有lifespan处理，确保完成lifespan关闭流程
                if hasattr(self._server, "lifespan") and self._server.lifespan is not None:
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
                    # 直接等待服务器任务完成，不使用asyncio.shield
                    # 这是修复的关键点，确保返回的是协程而不是Future
                    await asyncio.wait_for(self._serve_task, timeout=5.0)
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


# 创建自定义服务模块
class CustomServiceModule(Module):
    """自定义服务模块，使用扩展的配置管理器和正确设置lifecycle_manager"""

    def configure(self, binder: Binder):
        """配置绑定"""
        from injector import singleton

        from fautil.service.config_manager import ConfigManager
        from fautil.service.discovery_manager import DiscoveryManager
        from fautil.service.http_server_manager import HTTPServerManager
        from fautil.service.injector_manager import InjectorManager
        from fautil.service.lifecycle_manager import LifecycleManager
        from fautil.service.service_manager import ServiceManager

        # 创建管理器实例
        config_manager = ExtendedConfigManager()
        lifecycle_manager = LifecycleManager()
        http_server_manager = ExtendedHTTPServerManager(config_manager)

        # 绑定扩展的配置管理器
        binder.bind(ConfigManager, to=config_manager, scope=singleton)

        # 绑定生命周期管理器
        binder.bind(LifecycleManager, to=lifecycle_manager, scope=singleton)

        # 绑定HTTP服务器管理器
        binder.bind(HTTPServerManager, to=http_server_manager, scope=singleton)

        # 获取或创建InjectorManager和DiscoveryManager
        injector_manager = None
        discovery_manager = None

        try:
            injector_manager = binder.injector.get(InjectorManager)
            discovery_manager = binder.injector.get(DiscoveryManager)
        except Exception:
            injector_manager = InjectorManager([])
            discovery_manager = DiscoveryManager()
            binder.bind(InjectorManager, to=injector_manager, scope=singleton)
            binder.bind(DiscoveryManager, to=discovery_manager, scope=singleton)

        # 创建并绑定ServiceManager
        service_manager = ServiceManager(config_manager, injector_manager, discovery_manager)

        # 设置lifecycle_manager属性
        service_manager.lifecycle_manager = lifecycle_manager

        # 绑定ServiceManager
        binder.bind(ServiceManager, to=service_manager, scope=singleton)


# ---- 定义模型 ----


class UserBase(BaseModel):
    """用户基础模型"""

    name: str
    email: str


class UserCreate(UserBase):
    """用户创建模型"""

    password: str


class User(UserBase):
    """用户模型"""

    id: int
    is_active: bool = True

    class Config:
        from_attributes = True


# 创建响应模型
UserResponse = create_response_model(User)
UsersResponse = create_response_model(List[User])


# ---- 定义服务 ----


class UserService:
    """用户服务"""

    def __init__(self):
        # 模拟的用户数据库
        self._users = [
            User(id=1, name="张三", email="zhangsan@example.com"),
            User(id=2, name="李四", email="lisi@example.com"),
        ]
        self._next_id = 3

    async def get_users(self) -> List[User]:
        """获取所有用户"""
        return self._users

    async def get_user(self, user_id: int) -> Optional[User]:
        """获取指定用户"""
        for user in self._users:
            if user.id == user_id:
                return user
        return None

    async def create_user(self, user: UserCreate) -> User:
        """创建新用户"""
        new_user = User(id=self._next_id, name=user.name, email=user.email)
        self._users.append(new_user)
        self._next_id += 1
        return new_user


# ---- 依赖注入模块 ----


class AppModule(Module):
    """应用依赖注入模块"""

    @singleton
    @provider
    def provide_user_service(self) -> UserService:
        """提供用户服务实例"""
        return UserService()


# ---- 定义视图 ----


class UserView(APIView):
    """用户管理视图"""

    path = "/users"
    tags = ["用户管理"]

    @inject
    def __init__(self, user_service: UserService):
        super().__init__()
        self.user_service = user_service

    @route(
        "/",
        methods=["GET"],
        response_model=UsersResponse,
        summary="获取所有用户",
        description="返回系统中所有用户的列表",
    )
    async def list_users(self):
        """获取所有用户"""
        users = await self.user_service.get_users()
        return ApiResponse.success(data=users)

    @route(
        "/{user_id}",
        methods=["GET"],
        response_model=UserResponse,
        summary="获取用户详情",
        description="根据用户ID获取用户详细信息",
    )
    async def get_user(self, user_id: int):
        """获取指定用户"""
        user = await self.user_service.get_user(user_id)
        if not user:
            from fautil.web.exception_handlers import NotFoundError

            raise NotFoundError(message=f"用户 {user_id} 不存在")
        return ApiResponse.success(data=user)

    @route(
        "/",
        methods=["POST"],
        response_model=UserResponse,
        summary="创建新用户",
        description="创建一个新用户并返回用户信息",
    )
    async def create_user(self, user: UserCreate):
        """创建新用户"""
        new_user = await self.user_service.create_user(user)
        return ApiResponse.success(data=new_user, message="用户创建成功")


class HealthView(APIView):
    """健康检查视图"""

    path = "/health"
    tags = ["系统"]

    @route("/", methods=["GET"])
    async def health_check(self):
        """健康检查"""
        return {"status": "ok", "version": "1.0.0"}


# ---- 创建并启动应用 ----


async def main():
    """主函数"""
    # 创建API服务，使用自定义模块
    service = APIService(app_name="quickstart", modules=[AppModule(), CustomServiceModule()])

    # 注册视图
    service.register_view(UserView)
    service.register_view(HealthView)

    # 启动服务
    await service.start(host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
