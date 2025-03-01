"""
配置管理模块

提供配置加载、访问和验证的功能。
支持从多种来源加载配置，包括配置文件、环境变量和默认值。
"""

from typing import Optional, Type, TypeVar

from loguru import logger
from pydantic import ValidationError

from fautil.core.config import Settings, load_settings

# 配置类型变量用于泛型函数
T = TypeVar("T", bound=Settings)


class ConfigManager:
    """
    配置管理器

    负责加载、验证和访问应用配置。
    支持从YAML/JSON配置文件、环境变量、.env文件加载配置，
    并根据优先级合并配置。

    属性：
        settings: Settings
            已加载的配置实例
        config_path: Optional[str]
            配置文件路径
        env_file: Optional[str]
            环境变量文件路径
        settings_class: Type[Settings]
            配置类，默认为Settings

    示例：
    ::

        # 基本用法
        from fautil.service import ConfigManager
        from fautil.core.config import Settings

        # 默认配置加载
        config_manager = ConfigManager()
        settings = config_manager.settings

        # 自定义配置文件路径
        config_manager = ConfigManager(
            config_path="config/my_config.yaml",
            env_file=".env.prod"
        )

        # 使用自定义配置类
        class MySettings(Settings):
            # 自定义配置字段...
            pass

        config_manager = ConfigManager(settings_class=MySettings)

        # 访问配置
        db_url = config_manager.settings.db.url if config_manager.settings.db else None
        log_level = config_manager.settings.log.level
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        env_file: Optional[str] = None,
        settings_class: Type[T] = Settings,  # type: ignore
    ):
        """
        初始化配置管理器

        参数：
            config_path: Optional[str]
                配置文件路径，默认为None（自动查找）
            env_file: Optional[str]
                环境变量文件路径，默认为None（自动查找）
            settings_class: Type[Settings]
                配置类，默认为Settings基类

        示例：
        ::

            # 使用默认配置
            config_manager = ConfigManager()

            # 指定配置文件
            config_manager = ConfigManager(
                config_path="configs/app_config.yaml"
            )
        """
        self.config_path = config_path
        self.env_file = env_file
        self.settings_class = settings_class

        try:
            self.settings = self._load_settings()
            logger.debug(f"配置已加载: {self.settings_class.__name__}")
        except ValidationError as e:
            logger.error(f"配置验证失败: {e}")
            raise

    def _load_settings(self) -> T:
        """
        加载配置

        从配置文件和环境变量加载配置，并返回配置实例。

        返回：
            Settings: 加载的配置实例

        异常：
            ValidationError: 配置验证失败时抛出
        """
        return load_settings(
            self.settings_class,
            config_path=self.config_path,
            env_file=self.env_file,
        )

    def reload(self) -> None:
        """
        重新加载配置

        从配置文件和环境变量重新加载配置。
        用于配置文件或环境变量更改后刷新配置。

        示例：
        ::

            # 修改配置文件后重新加载
            config_manager.reload()

            # 在配置更改事件中使用
            def on_config_changed():
                config_manager.reload()
        """
        try:
            self.settings = self._load_settings()
            logger.info(f"配置已重新加载: {self.settings_class.__name__}")
        except ValidationError as e:
            logger.error(f"配置重新加载失败: {e}")
            raise

    def get_settings(self) -> T:
        """
        获取配置实例

        返回当前加载的配置实例。

        返回：
            Settings: 配置实例
        """
        return self.settings

    @property
    def is_debug(self) -> bool:
        """
        是否为调试模式

        返回：
            bool: 是否为调试模式
        """
        return self.settings.is_debug

    def get_app_version(self) -> str:
        """获取应用版本"""
        # 首先尝试从settings.app.version获取
        if hasattr(self.settings, "app") and hasattr(self.settings.app, "version"):
            return self.settings.app.version
        # 然后尝试从settings.APP_VERSION获取
        elif hasattr(self.settings, "APP_VERSION"):
            return getattr(self.settings, "APP_VERSION")
        # 最后返回默认版本
        return "0.1.0"
