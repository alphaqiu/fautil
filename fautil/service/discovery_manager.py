"""
组件发现管理模块

负责扫描项目结构，发现并注册组件到依赖注入容器和FastAPI应用中。
支持基于约定的自动发现机制，无需手动注册。
"""

import importlib
import inspect
import pkgutil
import sys
from abc import ABCMeta, abstractmethod
from importlib import util as importlib_util
from pathlib import Path
from types import ModuleType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from fastapi import APIRouter, FastAPI
from injector import Inject, Injector, Module, singleton
from loguru import logger
from pydantic import BaseModel

from fautil.web.cbv import APIView

T = TypeVar("T")


@singleton
class DiscoveryManager:
    """
    组件发现管理器

    负责扫描项目结构，发现并注册组件到依赖注入容器和FastAPI应用中。
    实现了基于约定的自动发现机制，可以自动发现视图、模型、服务和模块。
    """

    def __init__(self):
        """
        初始化组件发现管理器
        """
        self._scanned_packages: Set[str] = set()
        self._components: Dict[str, Set[Type]] = {
            "views": set(),
            "models": set(),
            "services": set(),
            "modules": set(),
        }

    def discover(
        self,
        package_name: str,
        include_subpackages: bool = True,
    ) -> Dict[str, Set[Type]]:
        """
        发现组件

        扫描指定包及其子包，发现并返回组件

        Args:
            package_name: 包名称
            include_subpackages: 是否包含子包

        Returns:
            发现的组件字典，格式为 {组件类型: 组件集合}

        Raises:
            ImportError: 如果无法导入指定包
        """
        logger.info(f"开始扫描包 '{package_name}' 以发现组件")

        # 检查是否已扫描过该包
        if package_name in self._scanned_packages:
            logger.debug(f"包 '{package_name}' 已扫描过，跳过")
            return self._components

        try:
            # 导入包
            package = importlib.import_module(package_name)

            # 扫描包
            self._discover_package(package, include_subpackages)

            # 标记为已扫描
            self._scanned_packages.add(package_name)

            # 记录发现的组件数量
            total_components = sum(
                len(components) for components in self._components.values()
            )
            logger.info(f"发现组件总数: {total_components}")

            for component_type, components in self._components.items():
                logger.info(f"发现 {component_type} 组件: {len(components)} 个")

            return self._components

        except ImportError as e:
            logger.error(f"无法导入包 '{package_name}': {str(e)}")
            raise
        except Exception as e:
            logger.error(f"扫描包 '{package_name}' 时出错: {str(e)}")
            return self._components

    def register_components(
        self,
        app: FastAPI,
        injector: Injector,
        components: Optional[Dict[str, Set[Type]]] = None,
    ) -> None:
        """
        注册组件

        将发现的组件注册到FastAPI应用和依赖注入容器中

        Args:
            app: FastAPI应用实例
            injector: 依赖注入容器
            components: 组件字典，格式为 {组件类型: 组件集合}。如果为None，则使用上次发现的组件
        """
        if components is None:
            components = self._components

        # 注册视图
        views = components.get("views", set())
        if views:
            self._register_views(app, injector, views)

        # 注册模块（其他组件由InjectorManager注册）
        modules = components.get("modules", set())
        if modules:
            self._register_modules(injector, modules)

    def _discover_package(
        self, package: ModuleType, include_subpackages: bool = True
    ) -> None:
        """
        发现包中的组件

        递归扫描包及其子包，发现并记录组件

        Args:
            package: 包模块
            include_subpackages: 是否包含子包
        """
        # 扫描当前模块
        self._scan_module(package)

        # 如果不包含子包，则直接返回
        if not include_subpackages:
            return

        # 获取包路径
        package_path = getattr(package, "__path__", None)
        if not package_path:
            return

        # 递归扫描子包
        prefix = package.__name__ + "."
        for _, name, is_pkg in pkgutil.iter_modules(package_path, prefix):
            if is_pkg:
                # 子包
                try:
                    subpkg = importlib.import_module(name)
                    self._discover_package(subpkg, include_subpackages)
                except ImportError as e:
                    logger.warning(f"无法导入子包 '{name}': {str(e)}")
            else:
                # 模块
                try:
                    module = importlib.import_module(name)
                    self._scan_module(module)
                except ImportError as e:
                    logger.warning(f"无法导入模块 '{name}': {str(e)}")

    def _scan_module(self, module: ModuleType) -> None:
        """
        扫描模块中的组件

        检查模块中的所有类，将符合条件的类添加到组件集合中

        Args:
            module: 模块对象
        """
        # 获取模块中的所有成员
        for name, obj in inspect.getmembers(module):
            # 跳过非类对象
            if not inspect.isclass(obj):
                continue

            # 跳过导入的类（除非是显式重新导出的）
            if obj.__module__ != module.__name__ and not name.startswith("__"):
                continue

            # 检查是否为视图类
            if self._is_view_class(obj):
                self._components["views"].add(obj)
                continue

            # 检查是否为模型类
            if self._is_model_class(obj):
                self._components["models"].add(obj)
                continue

            # 检查是否为服务类
            if self._is_service_class(obj):
                self._components["services"].add(obj)
                continue

            # 检查是否为模块类
            if self._is_module_class(obj):
                self._components["modules"].add(obj)
                continue

    def _is_view_class(self, cls: Type) -> bool:
        """
        检查是否为视图类

        Args:
            cls: 要检查的类

        Returns:
            如果是视图类则返回True，否则返回False
        """
        # 检查是否继承自APIView
        return inspect.isclass(cls) and issubclass(cls, APIView) and cls != APIView

    def _is_model_class(self, cls: Type) -> bool:
        """
        检查是否为模型类

        Args:
            cls: 要检查的类

        Returns:
            如果是模型类则返回True，否则返回False
        """
        # 检查是否继承自BaseModel
        return inspect.isclass(cls) and issubclass(cls, BaseModel) and cls != BaseModel

    def _is_service_class(self, cls: Type) -> bool:
        """
        检查是否为服务类

        Args:
            cls: 要检查的类

        Returns:
            如果是服务类则返回True，否则返回False
        """
        # 检查是否有服务标记
        if getattr(cls, "__service__", False):
            return True

        # 检查类名是否以Service结尾
        if cls.__name__.endswith("Service"):
            return True

        # 检查是否有注入器装饰器
        try:
            init_sig = inspect.signature(cls.__init__)
            for param in init_sig.parameters.values():
                if param.name == "self":
                    continue

                if getattr(param, "__inject__", False):
                    return True

                if (
                    param.annotation.__module__ == "injector"
                    and param.annotation.__name__ == "Inject"
                ):
                    return True
        except (AttributeError, ValueError):
            pass

        return False

    def _is_module_class(self, cls: Type) -> bool:
        """
        检查是否为模块类

        Args:
            cls: 要检查的类

        Returns:
            如果是模块类则返回True，否则返回False
        """
        # 检查是否继承自Module
        return inspect.isclass(cls) and issubclass(cls, Module) and cls != Module

    def _register_views(
        self, app: FastAPI, injector: Injector, views: Set[Type[APIView]]
    ) -> None:
        """
        注册视图

        Args:
            app: FastAPI应用实例
            injector: 依赖注入容器
            views: 视图类集合
        """
        for view_cls in views:
            try:
                # 创建视图实例
                view_instance = injector.get(view_cls)

                # 注册到FastAPI
                view_instance.register(app)

                logger.debug(f"已注册视图: {view_cls.__name__}")

            except Exception as e:
                logger.error(f"注册视图 {view_cls.__name__} 时出错: {str(e)}")

    def _register_modules(self, injector: Injector, modules: Set[Type[Module]]) -> None:
        """
        注册模块

        Args:
            injector: 依赖注入容器
            modules: 模块类集合
        """
        for module_cls in modules:
            try:
                # 获取模块实例
                module_instance = injector.get(module_cls)

                # 注册到注入器（由InjectorManager处理）
                logger.debug(f"已发现模块: {module_cls.__name__}")

            except Exception as e:
                logger.error(f"处理模块 {module_cls.__name__} 时出错: {str(e)}")
