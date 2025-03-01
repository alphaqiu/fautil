"""
生命周期事件管理模块

提供框架和组件的生命周期事件管理功能，支持事件注册、触发和优先级控制。
"""

import asyncio
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from injector import inject, singleton
from loguru import logger


class LifecycleEventType(str, Enum):
    """生命周期事件类型"""

    # 服务启动前
    PRE_STARTUP = "pre_startup"
    # 服务启动后
    POST_STARTUP = "post_startup"
    # 服务停止前
    PRE_SHUTDOWN = "pre_shutdown"
    # 服务停止后
    POST_SHUTDOWN = "post_shutdown"
    # HTTP服务器启动前
    PRE_HTTP_START = "pre_http_start"
    # HTTP服务器启动后
    POST_HTTP_START = "post_http_start"
    # HTTP服务器停止前
    PRE_HTTP_STOP = "pre_http_stop"
    # HTTP服务器停止后
    POST_HTTP_STOP = "post_http_stop"
    # 服务停止前
    PRE_SERVICES_STOP = "pre_services_stop"
    # 服务停止后
    POST_SERVICES_STOP = "post_services_stop"
    # 资源清理前
    PRE_CLEANUP = "pre_cleanup"
    # 资源清理后
    POST_CLEANUP = "post_cleanup"
    # 依赖注入器创建前
    PRE_INJECTOR_CREATION = "pre_injector_creation"
    # 依赖注入器创建后
    POST_INJECTOR_CREATION = "post_injector_creation"


class ComponentType(str, Enum):
    """组件类型枚举"""

    API = "api"  # API相关组件
    DATABASE = "db"  # 数据库相关组件
    CACHE = "cache"  # 缓存相关组件
    QUEUE = "queue"  # 队列相关组件
    SCHEDULER = "scheduler"  # 调度器相关组件
    STORAGE = "storage"  # 存储相关组件
    CORE = "core"  # 核心组件
    OTHER = "other"  # 其他组件


class LifecycleEventListener:
    """
    生命周期事件监听器

    表示一个生命周期事件的回调函数。
    """

    def __init__(
        self,
        callback: Callable,
        event_type: LifecycleEventType,
        component_type: ComponentType = ComponentType.OTHER,
        priority: int = 0,
        is_async: Optional[bool] = None,
    ):
        """
        初始化生命周期事件监听器

        Args:
            callback: 回调函数
            event_type: 事件类型
            component_type: 组件类型
            priority: 优先级（数字越大优先级越高）
            is_async: 是否是异步函数，如果为None则自动检测
        """
        self.callback = callback
        self.event_type = event_type
        self.component_type = component_type
        self.priority = priority

        # 自动检测是否是异步函数
        if is_async is None:
            self.is_async = asyncio.iscoroutinefunction(callback)
        else:
            self.is_async = is_async

        # 添加标识符
        self.id = id(callback)

        # 元数据
        self.name = getattr(callback, "__name__", str(callback))
        self.module = getattr(callback, "__module__", "unknown")

    def __str__(self) -> str:
        return (
            f"LifecycleEventListener(event={self.event_type}, "
            f"component={self.component_type}, priority={self.priority}, "
            f"name={self.name}, module={self.module})"
        )


@singleton
class LifecycleManager:
    """
    生命周期事件管理器

    管理框架和组件的生命周期事件，支持事件注册、触发和优先级控制。
    """

    @inject
    def __init__(self):
        """初始化生命周期事件管理器"""
        # 事件监听器注册表
        # 按事件类型分组
        self._listeners: Dict[LifecycleEventType, List[LifecycleEventListener]] = {
            event_type: [] for event_type in LifecycleEventType
        }

        # 组件关闭优先级
        self._component_shutdown_priority = {
            ComponentType.API: 100,  # 优先关闭API
            ComponentType.SCHEDULER: 80,  # 然后是调度器
            ComponentType.QUEUE: 60,  # 然后是队列
            ComponentType.CACHE: 40,  # 然后是缓存
            ComponentType.STORAGE: 20,  # 然后是存储
            ComponentType.DATABASE: 10,  # 最后是数据库
            ComponentType.CORE: 0,  # 核心组件最后关闭
            ComponentType.OTHER: 50,  # 其他组件处于中间位置
        }

    def register_event_listener(
        self,
        event_type: LifecycleEventType,
        callback: Callable,
        component_type: Optional[ComponentType] = None,
        priority: Optional[int] = None,
    ) -> None:
        """
        注册事件监听器

        Args:
            event_type: 事件类型
            callback: 回调函数
            component_type: 组件类型，如果未指定，则使用默认的OTHER
            priority: 优先级，如果未指定，则使用基于组件类型的默认优先级
        """
        # 使用默认组件类型
        if component_type is None:
            component_type = ComponentType.OTHER

        # 使用基于组件类型的默认优先级
        if priority is None:
            # 对于启动事件，使用组件优先级的反序
            if event_type in (
                LifecycleEventType.PRE_STARTUP,
                LifecycleEventType.POST_STARTUP,
                LifecycleEventType.PRE_HTTP_START,
                LifecycleEventType.POST_HTTP_START,
            ):
                priority = 100 - self._component_shutdown_priority.get(component_type, 50)
            # 对于关闭事件，使用组件优先级
            else:
                priority = self._component_shutdown_priority.get(component_type, 50)

        # 创建监听器
        listener = LifecycleEventListener(
            callback=callback,
            event_type=event_type,
            component_type=component_type,
            priority=priority,
        )

        # 注册监听器
        self._listeners[event_type].append(listener)

        # 按优先级排序
        self._sort_listeners(event_type)

        logger.debug(
            f"已注册生命周期事件监听器: {listener.name} -> {event_type.value} "
            f"[组件类型: {component_type.value}, 优先级: {priority}]"
        )

    def register_listener_for_multiple_events(
        self,
        event_types: List[LifecycleEventType],
        callback: Callable,
        component_type: Optional[ComponentType] = None,
        priority: Optional[int] = None,
    ) -> None:
        """
        为多个事件类型注册同一个监听器

        Args:
            event_types: 事件类型列表
            callback: 回调函数
            component_type: 组件类型
            priority: 优先级
        """
        for event_type in event_types:
            self.register_event_listener(
                event_type=event_type,
                callback=callback,
                component_type=component_type,
                priority=priority,
            )

    def unregister_event_listener(self, event_type: LifecycleEventType, callback: Callable) -> bool:
        """
        取消注册事件监听器

        Args:
            event_type: 事件类型
            callback: 回调函数

        Returns:
            是否成功取消注册
        """
        # 获取监听器列表
        listeners = self._listeners[event_type]

        # 查找回调的ID
        callback_id = id(callback)

        # 过滤掉要删除的监听器
        new_listeners = [listener for listener in listeners if listener.id != callback_id]

        # 检查是否有变化
        if len(new_listeners) == len(listeners):
            return False

        # 更新监听器列表
        self._listeners[event_type] = new_listeners
        return True

    def unregister_all_for_callback(self, callback: Callable) -> int:
        """
        取消注册所有使用指定回调函数的监听器

        Args:
            callback: 回调函数

        Returns:
            取消注册的监听器数量
        """
        # 查找回调的ID
        callback_id = id(callback)
        count = 0

        # 遍历所有事件类型
        for event_type in LifecycleEventType:
            # 过滤掉要删除的监听器
            listeners = self._listeners[event_type]
            new_listeners = [listener for listener in listeners if listener.id != callback_id]

            # 检查是否有变化
            if len(new_listeners) != len(listeners):
                count += len(listeners) - len(new_listeners)
                self._listeners[event_type] = new_listeners

        return count

    async def trigger_event(self, event_type: LifecycleEventType, context: Any = None) -> None:
        """
        触发事件

        按优先级顺序依次调用监听器。

        Args:
            event_type: 事件类型
            context: 事件上下文数据，将传递给监听器
        """
        # 获取已排序的监听器
        listeners = self._listeners[event_type]

        # 检查是否有监听器
        if not listeners:
            logger.debug(f"事件 {event_type.value} 没有监听器")
            return

        logger.info(f"触发事件: {event_type.value} [监听器数量: {len(listeners)}]")

        # 触发事件
        for listener in listeners:
            try:
                # 异步调用
                if listener.is_async:
                    if context is not None:
                        await listener.callback(context)
                    else:
                        await listener.callback()
                # 同步调用
                else:
                    if context is not None:
                        listener.callback(context)
                    else:
                        listener.callback()
            except Exception as e:
                logger.error(
                    f"执行生命周期事件监听器时出错: {listener.name} -> {event_type.value} "
                    f"[组件类型: {listener.component_type.value}, 错误: {str(e)}]"
                )
                # 对于启动事件，抛出异常，防止启动过程继续
                if event_type in (
                    LifecycleEventType.PRE_STARTUP,
                    LifecycleEventType.POST_STARTUP,
                    LifecycleEventType.PRE_HTTP_START,
                    LifecycleEventType.POST_HTTP_START,
                ):
                    raise

    def get_listeners_for_event(
        self, event_type: LifecycleEventType
    ) -> List[LifecycleEventListener]:
        """
        获取指定事件类型的所有监听器

        Args:
            event_type: 事件类型

        Returns:
            监听器列表
        """
        return self._listeners[event_type].copy()

    def _sort_listeners(self, event_type: LifecycleEventType) -> None:
        """
        按优先级对监听器排序

        Args:
            event_type: 事件类型
        """
        # 获取监听器列表
        listeners = self._listeners[event_type]

        # 对于启动事件，高优先级在前
        if event_type in (
            LifecycleEventType.PRE_STARTUP,
            LifecycleEventType.POST_STARTUP,
            LifecycleEventType.PRE_HTTP_START,
            LifecycleEventType.POST_HTTP_START,
            LifecycleEventType.PRE_INJECTOR_CREATION,
            LifecycleEventType.POST_INJECTOR_CREATION,
        ):
            listeners.sort(key=lambda x: (-x.priority, x.name))
        # 对于关闭事件，高优先级在前
        else:
            listeners.sort(key=lambda x: (-x.priority, x.name))


# 装饰器函数


def on_event(
    event_type: LifecycleEventType,
    component_type: ComponentType = ComponentType.OTHER,
    priority: Optional[int] = None,
):
    """
    生命周期事件装饰器

    用于标记函数为特定生命周期事件的监听器。

    使用示例:
    ```python
    @on_event(LifecycleEventType.PRE_STARTUP)
    async def my_startup_handler():
        print("Service is starting...")
    ```

    Args:
        event_type: 事件类型
        component_type: 组件类型
        priority: 优先级
    """

    def decorator(func):
        # 添加事件元数据
        setattr(func, "__lifecycle_event__", True)
        setattr(func, "__event_type__", event_type)
        setattr(func, "__component_type__", component_type)
        setattr(func, "__priority__", priority)

        return func

    return decorator


def on_startup(
    component_type: ComponentType = ComponentType.OTHER,
    priority: Optional[int] = None,
):
    """
    服务启动后事件装饰器

    Args:
        component_type: 组件类型
        priority: 优先级
    """
    return on_event(
        LifecycleEventType.POST_STARTUP,
        component_type=component_type,
        priority=priority,
    )


def on_shutdown(
    component_type: ComponentType = ComponentType.OTHER,
    priority: Optional[int] = None,
):
    """
    服务关闭前事件装饰器

    Args:
        component_type: 组件类型
        priority: 优先级
    """
    return on_event(
        LifecycleEventType.PRE_SHUTDOWN,
        component_type=component_type,
        priority=priority,
    )


def pre_startup(
    component_type: ComponentType = ComponentType.OTHER,
    priority: Optional[int] = None,
):
    """
    服务启动前事件装饰器

    Args:
        component_type: 组件类型
        priority: 优先级
    """
    return on_event(
        LifecycleEventType.PRE_STARTUP,
        component_type=component_type,
        priority=priority,
    )


def post_shutdown(
    component_type: ComponentType = ComponentType.OTHER,
    priority: Optional[int] = None,
):
    """
    服务关闭后事件装饰器

    Args:
        component_type: 组件类型
        priority: 优先级
    """
    return on_event(
        LifecycleEventType.POST_SHUTDOWN,
        component_type=component_type,
        priority=priority,
    )
