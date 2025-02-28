"""
消息队列模块

提供Kafka消息队列和本地缓冲队列支持。
"""

from fautil.messaging.kafka import KafkaConsumer, KafkaProducer
from fautil.messaging.local import LocalQueue

__all__ = ["KafkaConsumer", "KafkaProducer", "LocalQueue"]
