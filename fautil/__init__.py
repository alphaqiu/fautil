"""
FastAPI Utility 基础框架库

此框架提供了构建FastAPI应用的通用组件和工具。

主要功能：
----------
* API服务生命周期管理：优雅启动和关闭
* 依赖注入：基于Injector的IoC容器
* 配置管理：多源配置加载与管理
* 数据库集成：SQLAlchemy ORM支持
* 消息队列：Kafka生产者和消费者
* 任务调度：基于asyncio的定时任务
* 缓存支持：Redis缓存集成
* 对象存储：Minio/S3客户端
* 统一日志：基于loguru的日志管理
* 请求上下文：请求级别的上下文传递
* 异常处理：统一的异常处理机制
* 指标监控：Prometheus集成

使用方法：
----------
1. 创建API服务实例
   ::

       from fautil.service import APIService

       service = APIService("my_app")
       await service.start(host="0.0.0.0", port=8000)

2. 定义API视图
   ::

       from fautil.web import APIView, route

       class UserView(APIView):
           path = "/users"
           tags = ["用户管理"]

           @route("/", methods=["GET"])
           async def list_users(self):
               return {"users": []}
"""

import importlib.util

# 使用importlib.util.find_spec检查_version模块是否存在
if importlib.util.find_spec("fautil._version") is not None:
    # 当模块确实存在时才导入
    from ._version import __version__  # type: ignore
else:
    # 如果_version.py不存在（例如在开发环境中初次克隆后），使用默认版本
    __version__ = "0.0.0.dev0"

# 导出主要模块
from fautil import (
    cache,
    cli,
    core,
    db,
    messaging,
    scheduler,
    service,
    storage,
    utils,
    web,
)

__all__ = [
    "cache",
    "cli",
    "core",
    "db",
    "messaging",
    "scheduler",
    "service",
    "storage",
    "utils",
    "web",
]
