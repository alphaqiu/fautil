"""
基于类的视图实现模块

提供基于类的视图（CBV）实现，支持路由、依赖注入、认证等功能。
"""

import inspect
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
)

from fastapi import APIRouter, FastAPI, params
from injector import Injector
from loguru import logger

T = TypeVar("T", bound="APIView")


class route:
    """
    路由装饰器类

    用于装饰 APIView 类的方法，将方法注册为路由处理函数。

    属性：
        path: str
            路由路径，将与APIView.path组合
        methods: List[str]
            HTTP方法列表，如["GET", "POST"]
        response_model: Any
            响应模型类型
        status_code: Optional[int]
            HTTP响应状态码
        tags: Optional[List[str]]
            API标签列表，用于文档分组
        dependencies: Optional[List[params.Depends]]
            路由依赖项列表
        summary: Optional[str]
            API摘要，用于文档
        description: Optional[str]
            API描述，用于文档
        response_description: str
            响应描述，用于文档

    示例：
    ::

        from fautil.web import APIView, route

        class UserView(APIView):
            path = "/users"

            @route("/", methods=["GET"])
            async def list_users(self):
                return {"users": [...]}

            @route("/{user_id}", methods=["GET"])
            async def get_user(self, user_id: int):
                return {"user": {...}}

            @route("/", methods=["POST"])
            async def create_user(self, user: UserCreate):
                # 创建用户逻辑
                return {"id": new_id}
    """

    def __init__(
        self,
        path: str,
        *,
        response_model: Any = None,
        status_code: Optional[int] = None,
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[params.Depends]] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        response_description: str = "成功",
        responses: Optional[Dict[int, Dict[str, Any]]] = None,
        deprecated: Optional[bool] = None,
        methods: Optional[List[str]] = None,
        operation_id: Optional[str] = None,
        include_in_schema: bool = True,
        response_model_exclude_none: bool = False,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude: Optional[Set[str]] = None,
        response_model_include: Optional[Set[str]] = None,
        name: Optional[str] = None,
    ):
        """
        初始化路由装饰器

        参数：
            path: str
                路由路径，将与APIView.path组合
            response_model: Any
                响应模型类型
            status_code: Optional[int]
                HTTP响应状态码
            tags: Optional[List[str]]
                API标签列表，用于文档分组
            dependencies: Optional[List[params.Depends]]
                路由依赖项列表
            summary: Optional[str]
                API摘要，用于文档
            description: Optional[str]
                API描述，用于文档
            response_description: str
                响应描述，用于文档
            responses: Optional[Dict[int, Dict[str, Any]]]
                额外的响应定义，用于文档
            deprecated: Optional[bool]
                是否标记为已弃用
            methods: Optional[List[str]]
                HTTP方法列表，如["GET", "POST"]
            operation_id: Optional[str]
                操作ID，用于文档
            include_in_schema: bool
                是否包含在API文档中
            response_model_exclude_none: bool
                是否从响应中排除None值
            response_model_exclude_unset: bool
                是否从响应中排除未设置的值
            response_model_exclude_defaults: bool
                是否从响应中排除默认值
            response_model_exclude: Optional[Set[str]]
                要从响应中排除的字段集合
            response_model_include: Optional[Set[str]]
                要包含在响应中的字段集合
            name: Optional[str]
                路由名称
        """
        self.path = path
        self.response_model = response_model
        self.status_code = status_code
        self.tags = tags or []
        self.dependencies = dependencies or []
        self.summary = summary
        self.description = description
        self.response_description = response_description
        self.responses = responses or {}
        self.deprecated = deprecated
        self.methods = methods
        self.operation_id = operation_id
        self.include_in_schema = include_in_schema
        self.response_model_exclude_none = response_model_exclude_none
        self.response_model_exclude_unset = response_model_exclude_unset
        self.response_model_exclude_defaults = response_model_exclude_defaults
        self.response_model_exclude = response_model_exclude
        self.response_model_include = response_model_include
        self.name = name

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """
        调用装饰器

        Args:
            func: 被装饰的方法

        Returns:
            Callable[..., Any]: 装饰后的方法
        """
        func._route_info = self  # type: ignore
        return func


def api_route(
    path: str, **kwargs: Any
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    API路由装饰器函数

    route类的函数形式，功能相同但语法更简洁。

    参数：
        path: str
            路由路径
        **kwargs: Any
            传递给route类的其他参数

    返回：
        函数装饰器

    示例：
    ::

        from fautil.web import APIView, api_route

        class UserView(APIView):
            path = "/users"

            @api_route("/", methods=["GET"])
            async def list_users(self):
                return {"users": [...]}
    """
    return route(path, **kwargs)


class APIView:
    """
    基于类的视图基类

    提供基于类的视图注册与方法分组功能，支持依赖注入和路由注册。

    属性：
        path: str
            视图基础路径，默认为空字符串
        tags: List[str]
            API标签列表，用于文档分组，默认为空列表
        dependencies: List[params.Depends]
            视图级依赖项列表，默认为空列表
        router_kwargs: Dict[str, Any]
            传递给APIRouter的额外参数，默认为空字典
        is_registered: bool
            是否已注册到FastAPI应用，类属性

    类方法：
        setup(cls, app, injector, prefix):
            创建视图实例并注册到FastAPI应用

    实例方法：
        register(self, app, prefix):
            注册视图到FastAPI应用

    示例：
    ::

        # 定义视图类
        class UserView(APIView):
            path = "/users"
            tags = ["用户管理"]

            @route("/", methods=["GET"])
            async def list_users(self):
                return {"users": [...]}

            @route("/{user_id}", methods=["GET"])
            async def get_user(self, user_id: int):
                return {"user": {...}}

        # 方式1：通过setup类方法注册（自动依赖注入）
        UserView.setup(app, injector)

        # 方式2：手动创建实例并注册
        view = UserView()
        view.register(app)
    """

    # 类属性
    path: str = ""
    tags: List[str] = []
    dependencies: List[params.Depends] = []
    router_kwargs: Dict[str, Any] = {}
    is_registered: bool = False  # 注册状态作为类属性

    def __init__(self):
        """初始化视图实例"""
        self.router = APIRouter()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        子类初始化钩子

        当创建APIView的子类时自动调用，用于设置类属性默认值
        并处理路由装饰器。

        参数：
            **kwargs: Any
                传递给父类__init_subclass__的参数
        """
        super().__init_subclass__(**kwargs)

        # 处理路由方法
        cls._routes: List[Dict[str, Any]] = []

        for name, method in inspect.getmembers(cls, inspect.isfunction):
            route_info = getattr(method, "_route_info", None)
            if route_info:
                cls._routes.append(
                    {
                        "path": route_info.path,
                        "response_model": route_info.response_model,
                        "status_code": route_info.status_code,
                        "tags": route_info.tags or cls.tags,
                        "dependencies": route_info.dependencies + cls.dependencies,
                        "summary": route_info.summary,
                        "description": route_info.description,
                        "response_description": route_info.response_description,
                        "responses": route_info.responses,
                        "deprecated": route_info.deprecated,
                        "methods": route_info.methods,
                        "operation_id": route_info.operation_id,
                        "include_in_schema": route_info.include_in_schema,
                        "response_model_exclude_none": (
                            route_info.response_model_exclude_none
                        ),
                        "response_model_exclude_unset": (
                            route_info.response_model_exclude_unset
                        ),
                        "response_model_exclude_defaults": (
                            route_info.response_model_exclude_defaults
                        ),
                        "response_model_exclude": route_info.response_model_exclude,
                        "response_model_include": route_info.response_model_include,
                        "name": route_info.name,
                        "endpoint": method,
                    }
                )

    def register(self, app: FastAPI, prefix: str = "") -> None:
        """
        注册视图到FastAPI应用

        创建APIRouter并将视图的路由方法注册到FastAPI应用。

        参数：
            app: FastAPI
                FastAPI应用实例
            prefix: str
                路由前缀，将与视图的path属性组合，默认为空字符串

        示例：
        ::

            from fastapi import FastAPI
            from my_app.views import UserView

            app = FastAPI()
            view = UserView()
            view.register(app, prefix="/api/v1")
        """
        # 使用类路径和前缀
        full_prefix = prefix + self.path

        # 创建路由器
        router_kwargs = dict(prefix=full_prefix)
        router_kwargs.update(self.router_kwargs)
        router = APIRouter(**router_kwargs)

        # 注册路由
        self._register_routes(router)

        # 将路由器添加到应用中
        app.include_router(router)
        self.__class__.is_registered = True  # 使用类引用设置类属性

        logger.debug(f"已注册视图 {self.__class__.__name__} 到路径前缀 '{full_prefix}'")

    def _register_routes(self, router: APIRouter) -> None:
        """
        注册路由到路由器

        Args:
            router: APIRouter实例
        """
        for route_info in self.__class__._routes:
            # 创建路由处理函数
            def create_endpoint(
                route_info: Dict[str, Any], instance: Any
            ) -> Callable[..., Any]:
                async def endpoint(*args: Any, **kwargs: Any) -> Any:
                    # 调用对应的方法
                    return await route_info["endpoint"](instance, *args, **kwargs)

                # 更新签名
                old_sig = inspect.signature(route_info["endpoint"])

                # 保留原始函数的类型注解
                endpoint.__annotations__ = route_info["endpoint"].__annotations__.copy()

                # 移除self参数
                parameters = list(old_sig.parameters.values())[1:]  # 跳过self参数
                new_sig = old_sig.replace(parameters=parameters)
                endpoint.__signature__ = new_sig  # type: ignore

                return endpoint

            endpoint = create_endpoint(route_info, self)

            # 添加路由
            router.add_api_route(
                path=route_info["path"],
                endpoint=endpoint,
                response_model=route_info["response_model"],
                status_code=route_info["status_code"],
                tags=route_info["tags"],
                dependencies=route_info["dependencies"],
                summary=route_info["summary"],
                description=route_info["description"],
                response_description=route_info["response_description"],
                responses=route_info["responses"],
                deprecated=route_info["deprecated"],
                methods=route_info["methods"],
                operation_id=route_info["operation_id"],
                include_in_schema=route_info["include_in_schema"],
                response_model_exclude_none=route_info["response_model_exclude_none"],
                response_model_exclude_unset=route_info["response_model_exclude_unset"],
                response_model_exclude_defaults=route_info[
                    "response_model_exclude_defaults"
                ],
                response_model_exclude=route_info["response_model_exclude"],
                response_model_include=route_info["response_model_include"],
                name=route_info["name"],
            )

            route_path = route_info["path"]
            logger.debug(
                f"已注册路由 {route_path} -> {route_info['endpoint'].__name__}"
            )

    @classmethod
    def setup(
        cls: Type[T],
        app: FastAPI,
        injector: Optional[Injector] = None,
        prefix: str = "",
    ) -> T:
        """
        创建视图实例并注册到FastAPI应用

        通过依赖注入创建视图实例（如果提供了injector），
        并调用register方法注册到FastAPI应用。

        参数：
            app: FastAPI
                FastAPI应用实例
            injector: Optional[Injector]
                依赖注入器实例，默认为None
            prefix: str
                路由前缀，默认为空字符串

        返回：
            T: 创建的视图实例

        示例：
        ::

            from fastapi import FastAPI
            from injector import Injector
            from my_app.views import UserView

            app = FastAPI()
            injector = Injector()
            view = UserView.setup(app, injector, prefix="/api/v1")
        """
        if injector:
            # 使用依赖注入创建实例
            instance = injector.get(cls)
        else:
            # 直接创建实例
            instance = cls()

        # 注册视图
        instance.register(app, prefix)

        return instance
