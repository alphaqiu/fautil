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
from typing import List, Optional

from injector import Module, provider, singleton
from pydantic import BaseModel

from fautil.service import APIService
from fautil.web import ApiResponse, APIView, create_response_model, route

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
    # 创建API服务
    service = APIService(app_name="quickstart", modules=[AppModule()])

    # 注册视图
    service.register_view(UserView)
    service.register_view(HealthView)

    # 启动服务
    await service.start(host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
