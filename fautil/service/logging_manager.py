"""
日志管理模块

负责配置和管理应用日志。提供统一的日志格式、级别控制和输出管理。
支持将日志输出到控制台、文件和远程服务。
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from injector import Inject, singleton
from loguru import logger

from fautil.core.config import Settings
from fautil.service.config_manager import ConfigManager


@singleton
class LoggingManager:
    """
    日志管理器

    负责配置和管理应用日志。
    支持多目标输出、日志旋转和格式定制。
    """

    def __init__(self, config_manager: ConfigManager):
        """
        初始化日志管理器

        Args:
            config_manager: 配置管理器
        """
        self._config_manager = config_manager
        self._initialized = False
        self._log_handlers = []

    async def setup(self) -> None:
        """
        设置日志系统

        根据应用配置初始化日志系统。
        """
        if self._initialized:
            return

        settings = self._config_manager.get_settings()

        # 移除所有现有处理器
        logger.remove()

        # 添加控制台日志
        self._setup_console_logging(settings)

        # 添加文件日志（如果配置了日志目录）
        if hasattr(settings, "LOG_DIR") and settings.LOG_DIR:
            self._setup_file_logging(settings)

        # 设置默认日志级别
        if hasattr(settings, "LOG_LEVEL"):
            log_level = settings.LOG_LEVEL
        else:
            log_level = "INFO"

        logger.info(f"日志系统初始化完成，默认级别: {log_level}")

        self._initialized = True

    def _setup_console_logging(self, settings: Settings) -> None:
        """
        设置控制台日志

        Args:
            settings: 应用配置
        """
        # 获取日志级别，如果未配置则使用INFO
        log_level = getattr(settings, "LOG_LEVEL", "INFO")

        # 添加控制台处理器
        handler_id = logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=log_level,
            colorize=True,
        )

        self._log_handlers.append(handler_id)

    def _setup_file_logging(self, settings: Settings) -> None:
        """
        设置文件日志

        Args:
            settings: 应用配置
        """
        # 确保日志目录存在
        log_dir = Path(settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)

        # 获取日志级别和保留天数
        log_level = getattr(settings, "LOG_LEVEL", "INFO")
        log_retention = getattr(settings, "LOG_RETENTION_DAYS", 30)

        # 添加文件处理器（按日期旋转）
        log_file = log_dir / "app_{time:YYYY-MM-DD}.log"
        handler_id = logger.add(
            str(log_file),
            rotation="00:00",  # 每天午夜轮换
            retention=f"{log_retention} days",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level=log_level,
            compression="zip",  # 压缩旧日志
        )

        self._log_handlers.append(handler_id)

        # 添加错误级别单独文件
        error_log_file = log_dir / "error_{time:YYYY-MM-DD}.log"
        handler_id = logger.add(
            str(error_log_file),
            rotation="00:00",
            retention=f"{log_retention} days",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level="ERROR",
            compression="zip",
            filter=lambda record: record["level"].name == "ERROR"
            or record["level"].name == "CRITICAL",
        )

        self._log_handlers.append(handler_id)

    def get_logger(self) -> logger:
        """
        获取日志记录器

        Returns:
            配置好的日志记录器
        """
        if not self._initialized:
            logger.warning("日志系统尚未初始化，使用默认配置")

        return logger

    async def close(self) -> None:
        """关闭日志系统"""
        logger.info("正在关闭日志系统...")

        # 移除所有处理器
        for handler_id in self._log_handlers:
            logger.remove(handler_id)

        logger.info("日志系统已关闭")

        # 最后添加一个临时控制台处理器以便显示关闭信息
        logger.add(sys.stderr, format="{message}", level="INFO")
