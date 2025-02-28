"""
ID生成器模块

提供分布式唯一ID生成功能，基于Snowflake算法。
"""

import threading
import time
from typing import Optional


class SnowflakeGenerator:
    """
    Snowflake ID生成器

    基于Twitter的Snowflake算法实现的分布式唯一ID生成器。
    生成的ID是64位整数，由以下部分组成：
    - 1位符号位，始终为0
    - 41位时间戳（毫秒级）
    - 10位工作机器ID（5位数据中心ID + 5位机器ID）
    - 12位序列号

    这样可以在同一毫秒内生成4096个不同的ID。
    """

    def __init__(
        self,
        worker_id: int = 0,
        datacenter_id: int = 0,
        sequence: int = 0,
        twepoch: int = 1288834974657,  # 2010-11-04 01:42:54.657 UTC
    ):
        """
        初始化Snowflake生成器

        Args:
            worker_id: 工作机器ID (0-31)
            datacenter_id: 数据中心ID (0-31)
            sequence: 起始序列号 (0-4095)
            twepoch: 起始时间戳，默认为Twitter的起始时间戳
        """
        # 位长度常量
        self.worker_id_bits = 5
        self.datacenter_id_bits = 5
        self.sequence_bits = 12

        # 最大值
        self.max_worker_id = -1 ^ (-1 << self.worker_id_bits)
        self.max_datacenter_id = -1 ^ (-1 << self.datacenter_id_bits)
        self.max_sequence = -1 ^ (-1 << self.sequence_bits)

        # 位移量
        self.worker_id_shift = self.sequence_bits
        self.datacenter_id_shift = self.sequence_bits + self.worker_id_bits
        self.timestamp_shift = (
            self.sequence_bits + self.worker_id_bits + self.datacenter_id_bits
        )

        # 参数验证
        if worker_id > self.max_worker_id or worker_id < 0:
            raise ValueError(f"worker_id不能大于{self.max_worker_id}或小于0")
        if datacenter_id > self.max_datacenter_id or datacenter_id < 0:
            raise ValueError(f"datacenter_id不能大于{self.max_datacenter_id}或小于0")

        # 初始化属性
        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = sequence
        self.twepoch = twepoch
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _next_millis(self, last_timestamp: int) -> int:
        """
        获取下一毫秒时间戳

        Args:
            last_timestamp: 上一次的时间戳

        Returns:
            int: 下一毫秒的时间戳
        """
        timestamp = self._get_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self._get_timestamp()
        return timestamp

    def _get_timestamp(self) -> int:
        """
        获取当前时间戳（毫秒）

        Returns:
            int: 当前时间戳
        """
        return int(time.time() * 1000)

    def next_id(self) -> int:
        """
        生成下一个ID

        Returns:
            int: 生成的唯一ID
        """
        with self.lock:
            timestamp = self._get_timestamp()

            # 时钟回拨检查
            if timestamp < self.last_timestamp:
                raise RuntimeError(
                    f"时钟回拨，拒绝生成ID，上次时间戳: {self.last_timestamp}，当前时间戳: {timestamp}"
                )

            # 同一毫秒内，序列号递增
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.max_sequence
                # 同一毫秒内序列号用尽，等待下一毫秒
                if self.sequence == 0:
                    timestamp = self._next_millis(self.last_timestamp)
            else:
                # 不同毫秒，序列号重置
                self.sequence = 0

            self.last_timestamp = timestamp

            # 组装ID
            return (
                ((timestamp - self.twepoch) << self.timestamp_shift)
                | (self.datacenter_id << self.datacenter_id_shift)
                | (self.worker_id << self.worker_id_shift)
                | self.sequence
            )
