"""
加密工具模块

提供密码加密和验证功能，使用argon2算法。
"""

from typing import Optional

import argon2


class PasswordHasher:
    """
    密码加密工具类

    使用argon2算法进行密码加密和验证，这是目前推荐的密码哈希算法。
    """

    def __init__(
        self,
        time_cost: int = 2,
        memory_cost: int = 102400,
        parallelism: int = 8,
        hash_len: int = 16,
        salt_len: int = 16,
        encoding: str = "utf-8",
    ):
        """
        初始化密码加密器

        Args:
            time_cost: 时间成本参数，越高越安全但越慢
            memory_cost: 内存成本参数，越高越安全但消耗内存越多
            parallelism: 并行度参数
            hash_len: 哈希长度
            salt_len: 盐长度
            encoding: 字符编码
        """
        self.hasher = argon2.PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=hash_len,
            salt_len=salt_len,
            encoding=encoding,
        )

    def hash(self, password: str) -> str:
        """
        对密码进行加密

        Args:
            password: 原始密码

        Returns:
            str: 加密后的密码哈希
        """
        return self.hasher.hash(password)

    def verify(self, hash_value: str, password: str) -> bool:
        """
        验证密码是否匹配

        Args:
            hash_value: 存储的密码哈希
            password: 待验证的密码

        Returns:
            bool: 如果密码匹配返回True，否则返回False
        """
        try:
            self.hasher.verify(hash_value, password)
            return True
        except argon2.exceptions.VerifyMismatchError:
            return False

    def check_needs_rehash(self, hash_value: str) -> bool:
        """
        检查密码哈希是否需要重新计算

        当哈希参数变更时，可以使用此方法检查是否需要更新存储的哈希值

        Args:
            hash_value: 存储的密码哈希

        Returns:
            bool: 如果需要重新计算返回True，否则返回False
        """
        return self.hasher.check_needs_rehash(hash_value)
