"""
事件系统模块

提供事件注册和触发机制，支持同步和异步事件处理。
"""

import asyncio
import inspect
import threading
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union, cast

from loguru import logger


class EventPriority(Enum):
    """事件处理优先级"""

    LOWEST = auto()
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    HIGHEST = auto()
    MONITOR = auto()  # 用于监控，总是最后执行


class Event:
    """事件基类，所有自定义事件都应继承此类"""

    # 类级别属性，标识是否可以取消
    cancellable = False

    def __init__(self) -> None:
        self._cancelled = False
        self._event_name = self.__class__.__name__

    @property
    def event_name(self) -> str:
        """获取事件名称"""
        return self._event_name

    @property
    def is_cancelled(self) -> bool:
        """检查事件是否已被取消"""
        return self._cancelled

    def cancel(self) -> None:
        """取消事件

        如果事件不可取消，则抛出异常
        """
        if not self.cancellable:
            raise ValueError(f"事件 {self.event_name} 不可取消")
        self._cancelled = True


class EventHandler:
    """事件处理器，包含处理函数和优先级信息"""

    def __init__(
        self,
        func: Callable,
        priority: EventPriority,
        event_type: Type[Event],
        is_async: bool,
    ) -> None:
        self.func = func
        self.priority = priority
        self.event_type = event_type
        self.is_async = is_async

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EventHandler):
            return False
        return self.func == other.func

    def __hash__(self) -> int:
        return hash(self.func)


class EventBus:
    """事件总线，管理事件的注册和分发"""

    def __init__(self) -> None:
        self._handlers: Dict[Type[Event], Set[EventHandler]] = {}
        self._lock = threading.RLock()

    def register(
        self,
        event_type: Type[Event],
        handler: Callable[[Event], Any],
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """注册事件处理器

        Args:
            event_type: 事件类型
            handler: 事件处理函数
            priority: 处理优先级
        """
        with self._lock:
            # 检查是否为协程函数
            is_async = asyncio.iscoroutinefunction(handler)

            # 如果是第一次注册此类型的事件，则创建集合
            if event_type not in self._handlers:
                self._handlers[event_type] = set()

            # 创建并添加处理器
            event_handler = EventHandler(handler, priority, event_type, is_async)
            self._handlers[event_type].add(event_handler)

            logger.debug(
                f"已注册 {handler.__name__} 处理器用于事件 {event_type.__name__}"
            )

    def unregister(
        self,
        event_type: Type[Event],
        handler: Callable[[Event], Any],
    ) -> None:
        """取消注册事件处理器

        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        with self._lock:
            if event_type not in self._handlers:
                return

            # 查找并移除处理器
            for h in list(self._handlers[event_type]):
                if h.func == handler:
                    self._handlers[event_type].remove(h)
                    logger.debug(
                        f"已取消注册 {handler.__name__} 处理器用于事件 {event_type.__name__}"
                    )
                    break

            # 如果没有处理器了，则移除该事件类型
            if not self._handlers[event_type]:
                del self._handlers[event_type]

    def post(self, event: Event) -> bool:
        """发布事件（同步处理）

        Args:
            event: 事件实例

        Returns:
            bool: 如果事件未被取消则返回True，否则返回False
        """
        event_type = type(event)

        # 如果没有处理器，直接返回
        if event_type not in self._handlers:
            logger.debug(f"没有处理器注册用于事件 {event.event_name}")
            return True

        # 获取所有处理器并按优先级排序
        handlers = sorted(self._handlers[event_type], key=lambda h: h.priority.value)

        # 按优先级调用每个处理器
        for handler in handlers:
            # 如果事件已被取消，则停止处理
            if event.is_cancelled:
                return False

            try:
                if handler.is_async:
                    # 对于异步处理器，使用事件循环同步运行
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(handler.func(event))
                else:
                    # 调用同步处理器
                    handler.func(event)
            except Exception as e:
                logger.error(f"处理事件 {event.event_name} 时发生错误: {e}")
                logger.exception(e)

        return not event.is_cancelled

    async def post_async(self, event: Event) -> bool:
        """异步发布事件

        Args:
            event: 事件实例

        Returns:
            bool: 如果事件未被取消则返回True，否则返回False
        """
        event_type = type(event)

        # 如果没有处理器，直接返回
        if event_type not in self._handlers:
            logger.debug(f"没有处理器注册用于事件 {event.event_name}")
            return True

        # 获取所有处理器并按优先级排序
        handlers = sorted(self._handlers[event_type], key=lambda h: h.priority.value)

        # 按优先级调用每个处理器
        for handler in handlers:
            # 如果事件已被取消，则停止处理
            if event.is_cancelled:
                return False

            try:
                if handler.is_async:
                    # 对于异步处理器，直接await
                    await handler.func(event)
                else:
                    # 对于同步处理器，使用线程池运行
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, handler.func, event)
            except Exception as e:
                logger.error(f"处理事件 {event.event_name} 时发生错误: {e}")
                logger.exception(e)

        return not event.is_cancelled

    def has_handlers(self, event_type: Type[Event]) -> bool:
        """检查是否有处理器注册了指定的事件类型

        Args:
            event_type: 事件类型

        Returns:
            bool: 如果有处理器则返回True，否则返回False
        """
        return event_type in self._handlers and bool(self._handlers[event_type])


# 创建全局事件总线实例
event_bus = EventBus()


def register(
    event_type: Type[Event],
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable:
    """装饰器：注册事件处理函数

    Args:
        event_type: 事件类型
        priority: 处理优先级

    Returns:
        Callable: 装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        event_bus.register(event_type, func, priority)
        return func

    return decorator


def post(event: Event) -> bool:
    """发布事件

    Args:
        event: 事件实例

    Returns:
        bool: 如果事件未被取消则返回True，否则返回False
    """
    return event_bus.post(event)


async def post_async(event: Event) -> bool:
    """异步发布事件

    Args:
        event: 事件实例

    Returns:
        bool: 如果事件未被取消则返回True，否则返回False
    """
    return await event_bus.post_async(event)


# 预定义事件类型


class AppStartEvent(Event):
    """应用启动事件"""

    def __init__(self, app: Any) -> None:
        super().__init__()
        self.app = app


class AppStopEvent(Event):
    """应用停止事件"""

    def __init__(self, app: Any) -> None:
        super().__init__()
        self.app = app


class RequestStartEvent(Event):
    """请求开始事件"""

    def __init__(self, request: Any) -> None:
        super().__init__()
        self.request = request


class RequestEndEvent(Event):
    """请求结束事件"""

    def __init__(self, request: Any, response: Any) -> None:
        super().__init__()
        self.request = request
        self.response = response
