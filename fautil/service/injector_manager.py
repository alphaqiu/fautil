"""
依赖注入管理模块

负责创建和管理依赖注入容器，提供组件绑定和解析功能。
支持动态注册和自动发现的组件绑定。
"""

import inspect
import sys
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
    get_type_hints,
)

from injector import (
    Binder,
    Injector,
    Module,
    Provider,
    Scope,
    ScopeDecorator,
    singleton,
)
from loguru import logger

from fautil.service.discovery_manager import DiscoveryManager

T = TypeVar("T")
ProviderCallable = Callable[[], Any]


@singleton
class InjectorManager:
    """
    依赖注入管理器

    负责创建和管理依赖注入容器，提供统一的组件注册和获取接口。
    支持模块组合、Provider工厂和自动绑定。
    """

    def __init__(self, modules: Optional[List[Module]] = None):
        """
        初始化依赖注入管理器

        Args:
            modules: 初始模块列表
        """
        self._modules = modules or []
        self._injector: Optional[Injector] = None
        self._bound_types: Set[Type] = set()

    def create_injector(self, modules: Optional[List[Module]] = None) -> Injector:
        """
        创建依赖注入器

        Args:
            modules: 额外的模块列表，将与初始模块合并

        Returns:
            创建的依赖注入器
        """
        # 合并模块
        all_modules = self._modules.copy()

        if modules:
            all_modules.extend(modules)

        # 添加自身作为模块
        injector_module = self._create_injector_module()
        all_modules.append(injector_module)

        # 创建注入器
        logger.info(f"创建依赖注入器，模块数量: {len(all_modules)}")
        self._injector = Injector(all_modules)

        return self._injector

    def get_injector(self) -> Injector:
        """
        获取依赖注入器

        Returns:
            依赖注入器

        Raises:
            RuntimeError: 如果注入器尚未创建
        """
        if self._injector is None:
            raise RuntimeError("依赖注入器尚未创建")

        return self._injector

    def bind_instance(
        self,
        interface: Type[T],
        instance: T,
        scope: Optional[ScopeDecorator] = singleton,
    ) -> None:
        """
        绑定实例

        Args:
            interface: 接口类型
            instance: 实例对象
            scope: 作用域装饰器

        Raises:
            RuntimeError: 如果注入器尚未创建
        """
        if self._injector is None:
            raise RuntimeError("依赖注入器尚未创建")

        # 创建覆盖模块
        class OverrideModule(Module):
            def configure(self, binder: Binder) -> None:
                if scope:
                    binder.bind(interface, to=instance, scope=scope)
                else:
                    binder.bind(interface, to=instance)

        # 添加到注入器
        self._injector.binder.install(OverrideModule())
        self._bound_types.add(interface)

        logger.debug(f"已绑定实例: {interface.__name__}")

    def bind_provider(
        self,
        interface: Type[T],
        provider: Callable[[], T],
        scope: Optional[ScopeDecorator] = singleton,
    ) -> None:
        """
        绑定提供者函数

        Args:
            interface: 接口类型
            provider: 提供者函数
            scope: 作用域装饰器

        Raises:
            RuntimeError: 如果注入器尚未创建
        """
        if self._injector is None:
            raise RuntimeError("依赖注入器尚未创建")

        # 创建提供者类
        class CustomProvider(Provider):
            def get(self, _):
                return provider()

        # 创建覆盖模块
        class OverrideModule(Module):
            def configure(self, binder: Binder) -> None:
                if scope:
                    binder.bind(interface, to=CustomProvider(), scope=scope)
                else:
                    binder.bind(interface, to=CustomProvider())

        # 添加到注入器
        self._injector.binder.install(OverrideModule())
        self._bound_types.add(interface)

        logger.debug(f"已绑定提供者: {interface.__name__}")

    def register_discovered_components(self, components: Dict[str, Set[Type]]) -> None:
        """
        注册发现的组件

        Args:
            components: 组件字典，格式为 {组件类型: 组件集合}

        Raises:
            RuntimeError: 如果注入器尚未创建
        """
        if self._injector is None:
            raise RuntimeError("依赖注入器尚未创建")

        # 注册服务
        services = components.get("services", set())
        if services:
            self._register_services(services)

        # 注册模型
        models = components.get("models", set())
        if models:
            self._register_models(models)

        # 模块已在创建注入器时注册

    def _register_services(self, services: Set[Type]) -> None:
        """
        注册服务组件

        Args:
            services: 服务类型集合
        """
        for service_cls in services:
            # 跳过已绑定的类型
            if service_cls in self._bound_types:
                continue

            try:
                # 检查是否有自定义的工厂方法
                factory = getattr(service_cls, "__factory__", None)

                if factory:
                    # 使用工厂方法创建实例
                    self.bind_provider(service_cls, factory)
                else:
                    # 创建实例并注册
                    instance = self._injector.get(service_cls)
                    self.bind_instance(service_cls, instance)

                logger.debug(f"已注册服务: {service_cls.__name__}")

            except Exception as e:
                logger.error(f"注册服务 {service_cls.__name__} 时出错: {str(e)}")

    def _register_models(self, models: Set[Type]) -> None:
        """
        注册模型组件

        Args:
            models: 模型类型集合
        """
        # 目前不需要特殊处理模型
        logger.debug(f"已发现 {len(models)} 个模型类")

    def _create_injector_module(self) -> Module:
        """
        创建注入器模块

        Returns:
            注入器模块实例
        """
        # 获取自身引用
        injector_manager = self

        # 创建模块
        class InjectorModule(Module):
            def configure(self, binder: Binder) -> None:
                # 绑定管理器自身
                binder.bind(InjectorManager, to=injector_manager, scope=singleton)

                # 绑定发现管理器（如果需要）
                if not any(
                    isinstance(mod, DiscoveryModule)
                    for mod in injector_manager._modules
                ):
                    binder.bind(
                        DiscoveryManager, to=DiscoveryManager(), scope=singleton
                    )

        return InjectorModule()


class DiscoveryModule(Module):
    """
    发现模块

    为依赖注入器提供DiscoveryManager实例。
    """

    def __init__(self, discovery_manager: Optional[DiscoveryManager] = None):
        """
        初始化发现模块

        Args:
            discovery_manager: 发现管理器实例
        """
        self.discovery_manager = discovery_manager or DiscoveryManager()

    def configure(self, binder: Binder) -> None:
        """
        配置依赖注入绑定

        Args:
            binder: 绑定器
        """
        binder.bind(DiscoveryManager, to=self.discovery_manager, scope=singleton)
