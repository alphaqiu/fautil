"""
配置管理模块

提供从多种来源加载配置的功能，支持配置文件（YAML/JSON）、环境变量和.env文件，
并按照优先级加载配置。
"""

import json
import logging
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# 定义类型变量用于泛型函数
T = TypeVar("T", bound="BaseSettings")


def locate_config_file(
    file_name: str, explicit_path: Optional[str] = None
) -> Optional[Path]:
    """
    按照优先级定位配置文件路径

    Args:
        file_name: 配置文件名
        explicit_path: 显式指定的配置文件路径

    Returns:
        Optional[Path]: 配置文件路径，如果未找到则返回None
    """
    paths_to_check = []

    # 1. 显式指定的路径
    if explicit_path:
        paths_to_check.append(Path(explicit_path))

    # 2. 当前工作目录
    paths_to_check.append(Path.cwd() / file_name)

    # 3. 应用程序运行目录
    app_dir = Path(sys.argv[0]).parent.absolute()
    paths_to_check.append(app_dir / file_name)

    # 4. 用户主目录下的.fautil目录
    home_dir = Path.home()
    paths_to_check.append(home_dir / ".fautil" / file_name)

    # 检查路径
    for path in paths_to_check:
        if path.exists() and path.is_file():
            return path

    return None


def load_yaml_config(file_path: Path) -> Dict[str, Any]:
    """
    加载YAML配置文件

    Args:
        file_path: 配置文件路径

    Returns:
        Dict[str, Any]: 配置字典
    """
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"解析YAML配置文件失败: {e}")
            return {}


def load_json_config(file_path: Path) -> Dict[str, Any]:
    """
    加载JSON配置文件

    Args:
        file_path: 配置文件路径

    Returns:
        Dict[str, Any]: 配置字典
    """
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"解析JSON配置文件失败: {e}")
            return {}


def load_config_from_file(
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    从配置文件加载配置

    Args:
        config_path: 配置文件路径，如果未指定则按优先级自动查找

    Returns:
        Dict[str, Any]: 配置字典
    """
    config_dict: Dict[str, Any] = {}

    # 尝试查找yaml配置文件
    yaml_path = locate_config_file("config.yaml", config_path)
    if yaml_path:
        config_dict.update(load_yaml_config(yaml_path))
        logger.info(f"已从 {yaml_path} 加载YAML配置")
        return config_dict

    # 尝试查找json配置文件
    json_path = locate_config_file("config.json", config_path)
    if json_path:
        config_dict.update(load_json_config(json_path))
        logger.info(f"已从 {json_path} 加载JSON配置")
        return config_dict

    logger.warning("未找到配置文件，将使用环境变量和默认值")
    return config_dict


def load_settings(
    settings_class: Type[T],
    config_path: Optional[str] = None,
    env_file: Optional[str] = None,
) -> T:
    """
    加载应用设置，按照优先级从配置文件、.env文件和环境变量加载

    Args:
        settings_class: 设置类型，必须继承自BaseSettings
        config_path: 配置文件路径，如果未指定则按优先级自动查找
        env_file: .env文件路径，如果未指定则按优先级自动查找

    Returns:
        T: 设置实例
    """
    # 加载.env文件
    if env_file:
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"已加载环境变量文件: {env_path}")
    else:
        env_path = locate_config_file(".env")
        if env_path:
            load_dotenv(env_path)
            logger.info(f"已加载环境变量文件: {env_path}")

    # 从配置文件加载
    config_dict = load_config_from_file(config_path)

    # 创建设置实例（包含环境变量和.env中的配置）
    settings = settings_class()

    # 配置文件具有最高优先级，覆盖已加载的设置
    for key, value in config_dict.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    return settings


class LogLevel(str, Enum):
    """日志级别枚举"""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogConfig(BaseModel):
    """日志配置"""

    level: LogLevel = LogLevel.INFO
    format: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    file_path: Optional[str] = None
    rotation: str = "20 MB"
    retention: str = "1 week"
    compression: str = "zip"
    serialize: bool = False


class DBConfig(BaseModel):
    """数据库配置"""

    url: str
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    table_prefix: str = ""


class RedisConfig(BaseModel):
    """Redis配置"""

    url: str
    password: Optional[str] = None
    db: int = 0
    encoding: str = "utf-8"
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    max_connections: int = 10


class KafkaConfig(BaseModel):
    """Kafka配置"""

    bootstrap_servers: str
    client_id: Optional[str] = None
    group_id: str
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = True
    max_poll_records: int = 500
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 10000
    consumer_timeout_ms: int = 1000
    api_version: Optional[str] = None


class MinioConfig(BaseModel):
    """Minio配置"""

    endpoint: str
    access_key: str
    secret_key: str
    secure: bool = True
    region: Optional[str] = None
    default_bucket: str = "default"

    def get_endpoint_url(self) -> str:
        """获取完整的端点URL"""
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.endpoint}"


class AppConfig(BaseModel):
    """应用配置"""

    title: str = "FastAPI Application"
    description: str = "FastAPI Application"
    version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    jwt_secret: str = "your-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_expires_seconds: int = 3600
    log_level: LogLevel = LogLevel.INFO


class Settings(BaseSettings):
    """应用设置"""

    app: AppConfig = Field(default_factory=AppConfig)
    db: Optional[DBConfig] = None
    redis: Optional[RedisConfig] = None
    kafka: Optional[KafkaConfig] = None
    minio: Optional[MinioConfig] = None
    log: LogConfig = Field(default_factory=LogConfig)

    model_config = {"env_nested_delimiter": "__", "case_sensitive": False}

    @property
    def is_debug(self) -> bool:
        """是否为调试模式"""
        return self.app.debug
