# 用户指南

欢迎使用Fautil框架用户指南。本指南将详细介绍如何使用Fautil框架的各项功能。

## 依赖注入

Fautil框架使用Injector实现依赖注入，支持组件的自动发现和注册。

### 示例

```python
from fautil import Injector, ServiceModule

class MyService:
    def __init__(self, config):
        self.config = config

injector = Injector([ServiceModule()])
my_service = injector.get(MyService)
```

## 配置管理

Fautil提供了ConfigManager类，用于加载和管理应用配置。

### 示例

```python
from fautil import ConfigManager

config_manager = ConfigManager(config_path="config.yaml")
settings = config_manager.get_settings()
```

## 日志管理

Fautil使用loguru库提供统一的日志管理。

### 示例

```python
from fautil import LoggingManager

logging_manager = LoggingManager()
logging_manager.configure()
logger = logging_manager.get_logger()
logger.info("日志已配置完成")
```

## 组件自动发现

Fautil支持自动发现并注册APIView、Model、DAO等组件。

### 示例

```python
from fautil import DiscoveryManager

discovery_manager = DiscoveryManager()
discovery_manager.discover_components()
```

## 请求上下文管理

Fautil提供RequestContext类，用于管理请求级别的上下文数据。

### 示例

```python
from fautil import RequestContext

request_context = RequestContext()
request_context.set("user_id", 123)
user_id = request_context.get("user_id")
```

## 健康检查和监控

Fautil内置健康检查接口和指标收集功能，支持Prometheus集成。

### 示例

```python
from fautil import HealthCheckView

class MyHealthCheckView(HealthCheckView):
    async def get(self, request):
        return {"status": "ok"}
```

## 统一异常处理

Fautil提供标准化的异常处理和响应格式。

### 示例

```python
from fautil import APIException

class MyCustomException(APIException):
    status_code = 400
    detail = "自定义异常信息"
```

更多详细信息，请参阅各模块的API文档。 