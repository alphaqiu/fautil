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
    cast,
)

from fastapi import APIRouter, Depends, FastAPI, params
from fastapi.routing import APIRoute
from pydantic import BaseModel

T = TypeVar("T", bound="APIView")


class route:
    """
    路由装饰器类

    用于装饰 APIView 类的方法，将方法注册为路由处理函数
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

        Args:
            path: 路由路径
            response_model: 响应模型
            status_code: 状态码
            tags: 标签列表
            dependencies: 依赖列表
            summary: 摘要
            description: 描述
            response_description: 响应描述
            responses: 响应字典
            deprecated: 是否已废弃
            methods: 请求方法列表
            operation_id: 操作ID
            include_in_schema: 是否包含在文档中
            response_model_exclude_none: 响应模型是否排除None值
            response_model_exclude_unset: 响应模型是否排除未设置的值
            response_model_exclude_defaults: 响应模型是否排除默认值
            response_model_exclude: 响应模型要排除的字段集合
            response_model_include: 响应模型要包含的字段集合
            name: 路由名称
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
    路由装饰器

    简化版的路由装饰器，用于装饰 APIView 类的方法

    Args:
        path: 路由路径
        **kwargs: 路由参数

    Returns:
        Callable[[Callable[..., Any]], Callable[..., Any]]: 装饰器
    """
    return route(path, **kwargs)


class APIView:
    """
    API视图基类

    用于实现基于类的视图（CBV），支持路由、依赖注入、认证等功能
    """

    # 类属性
    path: str = ""
    tags: List[str] = []
    dependencies: List[params.Depends] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        子类初始化

        处理子类的路由注册

        Args:
            **kwargs: 参数
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
                        "response_model_exclude_none": route_info.response_model_exclude_none,
                        "response_model_exclude_unset": route_info.response_model_exclude_unset,
                        "response_model_exclude_defaults": route_info.response_model_exclude_defaults,
                        "response_model_exclude": route_info.response_model_exclude,
                        "response_model_include": route_info.response_model_include,
                        "name": route_info.name,
                        "endpoint": method,
                    }
                )

    @classmethod
    def register_routes(cls, router: APIRouter) -> None:
        """
        注册路由

        将视图类的路由方法注册到指定的路由器中

        Args:
            router: 路由器
        """
        for route_info in cls._routes:
            # 创建路由处理函数
            def create_endpoint(route_info: Dict[str, Any]) -> Callable[..., Any]:
                async def endpoint(*args: Any, **kwargs: Any) -> Any:
                    # 创建实例
                    instance = cls()

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

            endpoint = create_endpoint(route_info)

            # 添加路由
            router.add_api_route(
                path=cls.path + route_info["path"],
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

    @classmethod
    def setup(cls: Type[T], app: FastAPI, prefix: str = "") -> None:
        """
        设置视图类

        将视图类注册到 FastAPI 应用中

        Args:
            app: FastAPI 应用
            prefix: 路由前缀
        """
        # 创建路由器
        router = APIRouter(prefix=prefix + cls.path)

        # 注册路由
        cls.register_routes(router)

        # 将路由器添加到应用中
        app.include_router(router)
