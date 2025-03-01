"""
服务模块

提供API服务的生命周期管理、依赖注入和信号处理。
包含优雅启动和停止、组件发现和自动注册等功能。
"""

from fautil.service.api_service import APIService, ServiceModule
from fautil.service.config_manager import ConfigManager
from fautil.service.discovery_manager import DiscoveryManager
from fautil.service.http_server_manager import HTTPServerManager, ServerStatus
from fautil.service.injector_manager import DiscoveryModule, InjectorManager
from fautil.service.lifecycle_manager import (
    ComponentType,
    LifecycleEventListener,
    LifecycleEventType,
    LifecycleManager,
    on_event,
    on_shutdown,
    on_startup,
    post_shutdown,
    pre_startup,
)
from fautil.service.logging_manager import LoggingManager
from fautil.service.service_manager import ServiceManager, ServiceStatus
from fautil.service.shutdown_manager import (
    ShutdownManager,
    ShutdownPhase,
    ShutdownReason,
)

__all__ = [
    # API服务
    "APIService",
    "ServiceModule",
    # 配置管理
    "ConfigManager",
    # 服务管理
    "ServiceManager",
    "ServiceStatus",
    # HTTP服务器管理
    "HTTPServerManager",
    "ServerStatus",
    # 生命周期管理
    "LifecycleManager",
    "LifecycleEventType",
    "LifecycleEventListener",
    "ComponentType",
    "on_event",
    "on_startup",
    "on_shutdown",
    "pre_startup",
    "post_shutdown",
    # 关闭管理
    "ShutdownManager",
    "ShutdownPhase",
    "ShutdownReason",
    # 依赖注入管理
    "InjectorManager",
    "DiscoveryModule",
    # 组件发现
    "DiscoveryManager",
    # 日志管理
    "LoggingManager",
]
