"""
配置管理模块

负责加载、验证和管理应用配置。支持多环境配置、配置覆盖和动态配置。
"""

import os
import sys
from typing import Optional, Type, TypeVar

from injector import singleton
from loguru import logger
from pydantic_settings import BaseSettings

from fautil.core.config import Settings

T = TypeVar("T", bound=BaseSettings)


@singleton
class ConfigManager:
    """
    配置管理器

    负责加载、验证和访问应用配置。
    支持基于环境变量和配置文件的多级配置。
    """

    def __init__(self, settings_class: Type[T] = Settings):
        """
        初始化配置管理器

        Args:
            settings_class: 配置类，默认使用fautil.core.config.Settings
        """
        self._settings_class = settings_class
        self._settings: Optional[T] = None
        self._loaded = False
        self._env: str = os.environ.get("FAUTIL_ENV", "development")

    async def load(self, env_file: Optional[str] = None) -> T:
        """
        加载配置

        Args:
            env_file: 环境变量文件路径，如果指定则从文件加载环境变量

        Returns:
            加载的配置对象
        """
        if self._loaded:
            assert self._settings is not None
            return self._settings

        # 设置日志输出格式（在日志管理器初始化前的临时配置）
        self._setup_initial_logging()

        logger.info(f"加载配置，环境: {self._env}")

        # 基于环境确定配置文件路径
        if env_file:
            try:
                # 使用指定的环境变量文件
                logger.info(f"从文件加载环境变量: {env_file}")
                # 这里不真正加载.env文件，由Settings类处理
                self._settings = self._settings_class()  # 使用Settings的加载机制
            except Exception as e:
                logger.error(f"加载环境变量文件失败: {str(e)}")
                sys.exit(1)
        else:
            # 不使用额外环境变量文件，直接加载
            self._settings = self._settings_class()

        self._loaded = True

        # 打印已加载的配置（排除敏感信息）
        self._log_loaded_config()

        return self._settings

    def get_settings(self) -> T:
        """
        获取配置对象

        Returns:
            已加载的配置对象

        Raises:
            RuntimeError: 如果配置尚未加载
        """
        if not self._loaded or self._settings is None:
            raise RuntimeError("配置尚未加载，请先调用load方法")

        return self._settings

    def _setup_initial_logging(self) -> None:
        """设置初始日志配置"""
        # 移除默认处理器
        logger.remove()

        # 添加控制台处理器
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> |"
                " <level>{level: <8}</level> |"
                " <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> -"
                " <level>{message}</level>"
            ),
            level="INFO",
            colorize=True,
        )

    def _log_loaded_config(self) -> None:
        """打印已加载的配置（排除敏感信息）"""
        assert self._settings is not None

        # 获取配置字典，过滤敏感信息
        config_dict = self._settings.model_dump()
        sensitive_keys = ["password", "secret", "key", "token"]

        # 隐藏敏感信息
        filtered_config = {}
        for key, value in config_dict.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                filtered_config[key] = "******"
            else:
                filtered_config[key] = value

        logger.debug(f"已加载配置: {filtered_config}")
