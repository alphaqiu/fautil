"""
本地消息队列模块

提供基于内存的本地消息队列实现，支持消息缓冲和异步处理。
"""

import asyncio
import time
import uuid
from collections import deque
from enum import Enum
from threading import RLock
from typing import Any, Callable, Deque, Dict, List, Optional, Set

from pydantic import BaseModel

from fautil.core.logging import get_logger

logger = get_logger(__name__)


class QueueStatus(str, Enum):
    """队列状态枚举"""

    IDLE = "idle"  # 空闲
    RUNNING = "running"  # 运行中
    PAUSED = "paused"  # 暂停
    STOPPED = "stopped"  # 停止


class LocalMessage(BaseModel):
    """本地消息模型"""

    id: str
    topic: str
    data: Dict[str, Any]
    created_at: float

    model_config = {"arbitrary_types_allowed": True}


class LocalQueue:
    """本地消息队列

    基于内存的消息队列实现，支持多生产者多消费者模型。
    """

    def __init__(self, max_size: int = 1000):
        """初始化本地队列

        Args:
            max_size: 队列最大大小
        """
        # 队列字典，按主题分类
        self._queues: Dict[str, Deque[LocalMessage]] = {}

        # 处理器字典，按主题分类
        self._handlers: Dict[str, List[Callable]] = {}

        # 最大队列大小
        self.max_size = max_size

        # 运行状态
        self._status = QueueStatus.IDLE

        # 锁
        self._lock = RLock()

        # 任务集合
        self._tasks: Set[asyncio.Task] = set()

        # 条件变量（用于通知消费者）
        self._condition = asyncio.Condition()

        logger.debug(f"创建本地队列，最大大小: {max_size}")

    def put(self, topic: str, data: Dict[str, Any]) -> LocalMessage:
        """放入消息（同步）

        Args:
            topic: 主题
            data: 消息数据

        Returns:
            LocalMessage: 消息对象
        """
        with self._lock:
            # 初始化队列（如果不存在）
            if topic not in self._queues:
                self._queues[topic] = deque(maxlen=self.max_size)

            # 创建消息
            message = LocalMessage(
                id=str(uuid.uuid4()),
                topic=topic,
                data=data,
                created_at=time.time(),
            )

            # 添加到队列
            self._queues[topic].append(message)

            logger.debug(f"消息已添加到队列，主题: {topic}, ID: {message.id}")

            # 通知消费者
            asyncio.create_task(self._notify_consumers())

            return message

    async def put_async(self, topic: str, data: Dict[str, Any]) -> LocalMessage:
        """放入消息（异步）

        Args:
            topic: 主题
            data: 消息数据

        Returns:
            LocalMessage: 消息对象
        """
        async with self._condition:
            # 初始化队列（如果不存在）
            if topic not in self._queues:
                self._queues[topic] = deque(maxlen=self.max_size)

            # 创建消息
            message = LocalMessage(
                id=str(uuid.uuid4()),
                topic=topic,
                data=data,
                created_at=asyncio.get_event_loop().time(),
            )

            # 添加到队列
            self._queues[topic].append(message)

            logger.debug(f"消息已添加到队列，主题: {topic}, ID: {message.id}")

            # 通知消费者
            self._condition.notify_all()

            return message

    def get(self, topic: str) -> Optional[LocalMessage]:
        """获取消息（同步）

        Args:
            topic: 主题

        Returns:
            Optional[LocalMessage]: 消息对象，如果队列为空则返回None
        """
        with self._lock:
            if topic not in self._queues or not self._queues[topic]:
                return None

            # 获取消息
            message = self._queues[topic].popleft()

            logger.debug(f"消息已从队列获取，主题: {topic}, ID: {message.id}")

            return message

    async def get_async(
        self, topic: str, timeout: Optional[float] = None
    ) -> Optional[LocalMessage]:
        """获取消息（异步）

        Args:
            topic: 主题
            timeout: 超时时间（秒），如果未指定则一直等待

        Returns:
            Optional[LocalMessage]: 消息对象，如果队列为空则返回None
        """
        async with self._condition:
            # 等待消息
            if topic not in self._queues or not self._queues[topic]:
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout)
                except asyncio.TimeoutError:
                    return None

            # 再次检查队列
            if topic not in self._queues or not self._queues[topic]:
                return None

            # 获取消息
            message = self._queues[topic].popleft()

            logger.debug(f"消息已从队列获取，主题: {topic}, ID: {message.id}")

            return message

    def clear(self, topic: Optional[str] = None) -> None:
        """清空队列

        Args:
            topic: 要清空的主题，如果未指定则清空所有队列
        """
        with self._lock:
            if topic is None:
                # 清空所有队列
                self._queues.clear()
                logger.debug("所有队列已清空")
            elif topic in self._queues:
                # 清空指定队列
                self._queues[topic].clear()
                logger.debug(f"队列已清空，主题: {topic}")

    def size(self, topic: Optional[str] = None) -> int:
        """获取队列大小

        Args:
            topic: 要获取大小的主题，如果未指定则返回所有队列的大小之和

        Returns:
            int: 队列大小
        """
        with self._lock:
            if topic is None:
                # 计算所有队列大小之和
                return sum(len(queue) for queue in self._queues.values())

            if topic in self._queues:
                # 返回指定队列大小
                return len(self._queues[topic])
            else:
                return 0

    def register_handler(self, topic: str, handler: Callable) -> None:
        """注册消息处理器

        Args:
            topic: 主题
            handler: 消息处理函数
        """
        with self._lock:
            if topic not in self._handlers:
                self._handlers[topic] = []

            if handler not in self._handlers[topic]:
                self._handlers[topic].append(handler)
                logger.debug(f"已注册处理器 {handler.__name__} 用于主题 {topic}")

    def unregister_handler(self, topic: str, handler: Callable) -> bool:
        """取消注册消息处理器

        Args:
            topic: 主题
            handler: 消息处理函数

        Returns:
            bool: 如果成功取消注册则返回True，否则返回False
        """
        with self._lock:
            if topic in self._handlers and handler in self._handlers[topic]:
                self._handlers[topic].remove(handler)
                logger.debug(f"已取消注册处理器 {handler.__name__} 用于主题 {topic}")

                # 如果处理器列表为空，则移除主题
                if not self._handlers[topic]:
                    del self._handlers[topic]

                return True
            return False

    async def start_processing(self) -> None:
        """开始处理消息"""
        if self._status == QueueStatus.RUNNING:
            return

        self._status = QueueStatus.RUNNING

        # 为每个主题创建消费任务
        for topic in list(self._handlers.keys()):
            task = asyncio.create_task(self._process_topic(topic))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        logger.info("消息处理已启动")

    async def stop_processing(self) -> None:
        """停止处理消息"""
        if self._status != QueueStatus.RUNNING:
            return

        self._status = QueueStatus.STOPPED

        # 等待所有任务完成
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        logger.info("消息处理已停止")

    async def pause_processing(self) -> None:
        """暂停处理消息"""
        if self._status != QueueStatus.RUNNING:
            return

        self._status = QueueStatus.PAUSED
        logger.info("消息处理已暂停")

    async def resume_processing(self) -> None:
        """恢复处理消息"""
        if self._status != QueueStatus.PAUSED:
            return

        self._status = QueueStatus.RUNNING

        # 通知消费者
        async with self._condition:
            self._condition.notify_all()

        logger.info("消息处理已恢复")

    async def _process_topic(self, topic: str) -> None:
        """处理指定主题的消息

        Args:
            topic: 主题
        """
        while self._status == QueueStatus.RUNNING:
            # 获取消息
            message = await self.get_async(topic, timeout=1.0)
            if message is None:
                # 队列为空，继续等待
                continue

            # 处理消息
            if topic in self._handlers:
                # 并行处理所有处理器
                tasks = []
                for handler in self._handlers[topic]:
                    task = asyncio.create_task(self._process_message(handler, message))
                    tasks.append(task)

                # 等待所有处理器完成
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_message(self, handler: Callable, message: LocalMessage) -> None:
        """处理单条消息

        Args:
            handler: 消息处理函数
            message: 消息对象
        """
        try:
            # 处理消息
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, message)

            logger.debug(f"消息处理成功，ID: {message.id}")
        except Exception as e:
            logger.error(f"消息处理失败: {e}, ID: {message.id}")

    async def _notify_consumers(self) -> None:
        """通知消费者有新消息"""
        async with self._condition:
            self._condition.notify_all()

    def subscribe(self, topic: str) -> Callable:
        """装饰器：订阅主题

        Args:
            topic: 主题

        Returns:
            Callable: 装饰器函数
        """

        def decorator(func: Callable) -> Callable:
            self.register_handler(topic, func)
            return func

        return decorator
