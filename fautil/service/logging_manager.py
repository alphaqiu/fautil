"""
日志管理模块

提供统一的日志配置和管理功能，基于loguru库实现。
支持控制台日志、文件日志、日志级别过滤和格式化。
"""

import logging
import os
import sys
from typing import List, Optional

from injector import singleton
from loguru import logger

from fautil.core.config import LogConfig, Settings


@singleton
class LoggingManager:
    """
    日志管理器

    负责配置和管理应用的日志系统，基于loguru库实现。
    提供统一的日志记录接口，支持多种输出目标和格式化选项。

    属性：
        config: LogConfig
            日志配置对象
        log_path: Optional[str]
            日志文件路径，如果启用文件日志
        handlers: List[int]
            活跃的日志处理器ID列表

    示例：
    ::

        # 基本用法
        from fautil.service import LoggingManager
        from fautil.core.config import LogConfig, LogLevel

        # 使用默认配置
        logging_manager = LoggingManager()
        logging_manager.configure()

        # 自定义配置
        config = LogConfig(
            level=LogLevel.DEBUG,
            file_path="logs/app.log",
            rotation="10 MB",
            retention="1 week"
        )
        logging_manager = LoggingManager()
        logging_manager.configure(config)

        # 使用日志
        from loguru import logger

        logger.info("应用启动")
        logger.debug("详细信息")
        logger.error("发生错误", exc_info=True)
    """

    def __init__(self):
        """
        初始化日志管理器

        初始状态下不配置任何日志处理器，需要调用configure方法进行配置。
        """
        self.config: Optional[LogConfig] = None
        self.log_path: Optional[str] = None
        self.handlers: List[int] = []

    def configure(
        self, config: Optional[LogConfig] = None, settings: Optional[Settings] = None
    ) -> None:
        """
        配置日志系统

        根据提供的配置或从设置中提取的配置，设置日志系统。
        移除所有现有的日志处理器，并根据配置添加新的处理器。

        参数：
            config: Optional[LogConfig]
                日志配置对象，默认为None
            settings: Optional[Settings]
                应用设置对象，如果config为None，则从settings.log提取配置

        示例：
        ::

            # 直接使用LogConfig
            from fautil.core.config import LogConfig, LogLevel

            config = LogConfig(
                level=LogLevel.DEBUG,
                file_path="logs/app.log"
            )
            logging_manager.configure(config)

            # 从Settings中提取
            from fautil.core.config import Settings

            settings = Settings()
            logging_manager.configure(settings=settings)
        """
        # 获取配置
        if config is None and settings is not None:
            config = settings.log
        elif config is None:
            # 使用默认配置
            config = LogConfig()

        self.config = config

        # 移除所有现有处理器
        logger.remove()
        self.handlers.clear()

        # 配置日志格式
        log_format = config.format

        # 添加标准输出处理器
        handler_id = logger.add(
            sys.stderr,
            format=log_format,
            level=config.level.value,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
        self.handlers.append(handler_id)

        # 如果配置了文件路径，添加文件处理器
        if config.file_path:
            self.log_path = self._prepare_log_path(config.file_path)

            handler_id = logger.add(
                self.log_path,
                format=log_format,
                level=config.level.value,
                rotation=config.rotation,
                retention=config.retention,
                compression=config.compression,
                serialize=config.serialize,
                backtrace=True,
                diagnose=True,
            )
            self.handlers.append(handler_id)

        # 配置标准库日志拦截
        self._setup_stdlib_logging_intercept()

        logger.info(f"日志系统已配置，级别: {config.level.value}")
        if self.log_path:
            logger.info(f"日志文件路径: {self.log_path}")

    def _prepare_log_path(self, file_path: str) -> str:
        """
        准备日志文件路径

        确保日志文件的目录存在，如果不存在则创建。

        参数：
            file_path: str
                日志文件路径

        返回：
            str: 处理后的日志文件路径
        """
        # 确保日志目录存在
        log_dir = os.path.dirname(file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        return file_path

    def _setup_stdlib_logging_intercept(self) -> None:
        """
        设置标准库日志拦截

        将Python标准库logging模块的日志重定向到loguru。
        这使得使用标准logging模块的第三方库的日志也能被loguru处理。
        """

        # 配置标准库日志的拦截
        class InterceptHandler(logging.Handler):
            def emit(self, record):
                # 获取对应的loguru级别
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno

                # 查找调用者
                frame, depth = logging.currentframe(), 2
                while frame.f_code.co_filename == logging.__file__:
                    frame = frame.f_back
                    depth += 1

                # 使用loguru记录日志
                logger.opt(depth=depth, exception=record.exc_info).log(
                    level, record.getMessage()
                )

        # 拦截标准库日志
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    def get_logger(self) -> logger:
        """
        获取logger实例

        返回loguru.logger实例，用于记录日志。

        返回：
            logger: loguru.logger实例

        示例：
        ::

            logger = logging_manager.get_logger()
            logger.info("这是一条信息日志")
            logger.error("这是一条错误日志")
        """
        return logger
