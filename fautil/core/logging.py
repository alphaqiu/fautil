"""
日志管理模块

使用loguru库实现统一的日志管理，支持配置日志级别、格式、输出位置等。
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Optional, Union

from loguru import logger

from fautil.core.config import LogConfig, LogLevel


class InterceptHandler(logging.Handler):
    """
    拦截标准库logging的日志，转发给loguru处理
    """

    def emit(self, record: logging.LogRecord) -> None:
        # 获取对应的loguru级别
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 找到调用发起的位置
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # 使用loguru记录日志
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    config: LogConfig,
    app_name: str = "fautil",
) -> None:
    """
    设置日志系统

    Args:
        config: 日志配置
        app_name: 应用名称，用于日志文件命名
    """
    # 清除所有已存在的处理器
    logger.remove()

    # 将标准库的日志器与loguru集成
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 获取所有常用的库日志器
    loggers = [
        logging.getLogger(name)
        for name in logging.root.manager.loggerDict
        if name.startswith("uvicorn")
        or name.startswith("fastapi")
        or name.startswith("sqlalchemy")
    ]

    # 为所有日志器添加拦截处理器
    for log in loggers:
        log.handlers = [InterceptHandler()]
        log.propagate = False

    # 添加控制台输出
    logger.configure(
        handlers=[
            {
                "sink": sys.stderr,
                "level": config.level.value,
                "format": config.format,
            }
        ]
    )

    # 如果配置了文件输出，则添加文件输出
    if config.file_path:
        log_file_path = Path(config.file_path)

        # 确保日志目录存在
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # 添加文件输出
        logger.add(
            log_file_path,
            level=config.level.value,
            format=config.format,
            rotation=config.rotation,
            retention=config.retention,
            compression=config.compression,
            serialize=config.serialize,
        )

    logger.info(f"日志系统已初始化，级别: {config.level.value}")


def get_logger(name: str = "fautil"):
    """
    获取指定名称的日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        logger: loguru日志记录器
    """
    return logger.bind(name=name)
