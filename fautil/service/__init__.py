"""
服务模块 (Service Module)
========================

提供API服务的生命周期管理、依赖注入和信号处理。
包含优雅启动和停止、组件发现和自动注册等功能。

主要组件：
---------
* APIService: API服务核心类，管理服务生命周期
* ConfigManager: 配置加载和管理
* LoggingManager: 日志配置和管理
* InjectorManager: 依赖注入容器管理
* DiscoveryManager: 组件自动发现
* LifecycleManager: 生命周期事件管理
* HTTPServerManager: HTTP服务器管理
* ShutdownManager: 优雅关闭流程管理
* ServiceManager: 服务状态管理

使用方法：
---------
::

    from fautil.service import APIService

    # 创建API服务
    service = APIService(
        app_name="my_app",
        discovery_packages=["my_app"]
    )

    # 启动服务
    await service.start(
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

    # 停止服务
    await service.stop()
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
