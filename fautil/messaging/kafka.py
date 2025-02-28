"""
Kafka消息队列模块

提供基于Kafka的消息队列实现，支持生产者和消费者的异步操作。
"""

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import BaseModel

from fautil.core.config import KafkaConfig
from fautil.core.logging import get_logger

logger = get_logger(__name__)


class MessageStatus(str, Enum):
    """消息状态枚举"""

    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 处理完成
    FAILED = "failed"  # 处理失败
    RETRYING = "retrying"  # 重试中


class Message(BaseModel):
    """消息模型"""

    id: str  # 消息ID
    topic: str  # 主题
    key: Optional[str] = None  # 消息键
    data: Dict[str, Any]  # 消息数据
    status: MessageStatus = MessageStatus.PENDING  # 消息状态
    retry_count: int = 0  # 重试次数
    max_retries: int = 3  # 最大重试次数
    created_at: Optional[float] = None  # 创建时间

    model_config = {"arbitrary_types_allowed": True}


class KafkaProducer:
    """Kafka生产者

    提供异步消息发布功能
    """

    def __init__(self, config: KafkaConfig):
        """初始化Kafka生产者

        Args:
            config: Kafka配置
        """
        self.config = config

        # 异步生产者
        self._producer: Optional[AIOKafkaProducer] = None

        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=4)

        logger.debug(f"创建Kafka生产者，服务器: {config.bootstrap_servers}")

    async def connect(self) -> AIOKafkaProducer:
        """连接到Kafka

        Returns:
            AIOKafkaProducer: Kafka生产者
        """
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                client_id=self.config.client_id or f"fautil-producer-{uuid.uuid4()}",
                enable_idempotence=True,
                compression_type="gzip",
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
            )
            await self._producer.start()
            logger.debug("已连接到Kafka服务器")
        return self._producer

    async def close(self) -> None:
        """关闭Kafka连接"""
        if self._producer:
            await self._producer.stop()
            self._producer = None
            logger.debug("已关闭Kafka连接")

    async def send(
        self, topic: str, value: Dict[str, Any], key: Optional[str] = None
    ) -> Message:
        """发送消息

        Args:
            topic: 主题
            value: 消息值
            key: 消息键

        Returns:
            Message: 消息对象
        """
        # 创建消息对象
        message = Message(
            id=str(uuid.uuid4()),
            topic=topic,
            key=key,
            data=value,
            created_at=asyncio.get_event_loop().time(),
        )

        # 连接到Kafka
        producer = await self.connect()

        # 发送消息
        try:
            await producer.send_and_wait(
                topic=topic,
                value=message.dict(),
                key=key,
            )
            message.status = MessageStatus.COMPLETED
            logger.debug(f"已发送消息到主题 {topic}, ID: {message.id}")
        except Exception as e:
            message.status = MessageStatus.FAILED
            logger.error(f"发送消息失败: {e}")
            raise

        return message

    async def send_sync(
        self, topic: str, value: Dict[str, Any], key: Optional[str] = None
    ) -> Message:
        """同步方式发送消息（在asyncio环境中调用异步方法）

        Args:
            topic: 主题
            value: 消息值
            key: 消息键

        Returns:
            Message: 消息对象
        """
        return await self.send(topic, value, key)


class KafkaConsumer:
    """Kafka消费者

    提供异步消息消费功能
    """

    def __init__(self, config: KafkaConfig):
        """初始化Kafka消费者

        Args:
            config: Kafka配置
        """
        self.config = config

        # 异步消费者
        self._consumer: Optional[AIOKafkaConsumer] = None

        # 消息处理器
        self._handlers: Dict[str, List[Callable]] = {}

        # 运行标志
        self._running = False

        # 任务集合
        self._tasks: Set[asyncio.Task] = set()

        logger.debug(
            f"创建Kafka消费者，服务器: {config.bootstrap_servers}, 组ID: {config.group_id}"
        )

    async def connect(self, topics: List[str]) -> AIOKafkaConsumer:
        """连接到Kafka

        Args:
            topics: 要订阅的主题列表

        Returns:
            AIOKafkaConsumer: Kafka消费者
        """
        if self._consumer is None:
            self._consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.config.bootstrap_servers,
                group_id=self.config.group_id,
                auto_offset_reset=self.config.auto_offset_reset,
                enable_auto_commit=self.config.enable_auto_commit,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                session_timeout_ms=self.config.session_timeout_ms,
                heartbeat_interval_ms=self.config.heartbeat_interval_ms,
            )
            await self._consumer.start()
            logger.debug(f"已连接到Kafka服务器，订阅主题: {topics}")
        return self._consumer

    async def close(self) -> None:
        """关闭Kafka连接"""
        self._running = False

        # 等待所有任务完成
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        # 关闭消费者
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
            logger.debug("已关闭Kafka连接")

    def register_handler(self, topic: str, handler: Callable) -> None:
        """注册消息处理器

        Args:
            topic: 主题
            handler: 消息处理函数
        """
        if topic not in self._handlers:
            self._handlers[topic] = []

        if handler not in self._handlers[topic]:
            self._handlers[topic].append(handler)
            logger.debug(f"已注册处理器 {handler.__name__} 用于主题 {topic}")

    async def start(self) -> None:
        """启动消费者"""
        if self._running:
            return

        self._running = True

        # 获取所有订阅的主题
        topics = list(self._handlers.keys())
        if not topics:
            logger.warning("没有注册处理器，消费者不会启动")
            return

        # 连接到Kafka
        consumer = await self.connect(topics)

        # 创建消费任务
        task = asyncio.create_task(self._consume_loop())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        logger.info(f"消费者已启动，订阅主题: {topics}")

    async def _consume_loop(self) -> None:
        """消息消费循环"""
        try:
            # 异步迭代消息
            async for msg in self._consumer:
                if not self._running:
                    break

                # 获取主题和消息
                topic = msg.topic
                try:
                    value = msg.value
                    message = Message(**value)
                except Exception as e:
                    logger.error(f"解析消息失败: {e}, 原始消息: {msg.value}")
                    continue

                # 处理消息
                if topic in self._handlers:
                    # 并行处理所有处理器
                    tasks = []
                    for handler in self._handlers[topic]:
                        task = asyncio.create_task(
                            self._handle_message(handler, message)
                        )
                        tasks.append(task)

                    # 等待所有处理器完成
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"消费循环异常: {e}")
            if self._running:
                # 重新启动消费循环
                logger.info("尝试重新启动消费循环...")
                await asyncio.sleep(1)
                task = asyncio.create_task(self._consume_loop())
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

    async def _handle_message(self, handler: Callable, message: Message) -> None:
        """处理单条消息

        Args:
            handler: 消息处理函数
            message: 消息对象
        """
        try:
            # 更新消息状态
            message.status = MessageStatus.PROCESSING

            # 处理消息
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, message)

            # 更新消息状态
            message.status = MessageStatus.COMPLETED
            logger.debug(f"消息处理成功，ID: {message.id}")
        except Exception as e:
            # 更新消息状态
            message.status = MessageStatus.FAILED
            message.retry_count += 1

            logger.error(f"消息处理失败: {e}, ID: {message.id}")

            # 尝试重试
            if message.retry_count < message.max_retries:
                message.status = MessageStatus.RETRYING
                logger.info(
                    f"消息将重试，ID: {message.id}, 重试次数: {message.retry_count}/{message.max_retries}"
                )

                # 延迟重试
                await asyncio.sleep(2**message.retry_count)
                await self._handle_message(handler, message)

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
