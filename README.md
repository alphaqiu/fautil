# FastAPI Utility (fautil)

![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)
![FastAPI Version](https://img.shields.io/badge/fastapi-0.110.0%2B-green)
![License](https://img.shields.io/badge/license-MIT-blue)
![Pylint](https://github.com/alphaqiu/fautil/raw/master/pylint_badge.svg)

基于 FastAPI 和 SQLAlchemy 的企业级应用框架，提供完整的生命周期管理、依赖注入、异步支持和优雅关闭机制。

## 特性

- **API服务生命周期管理**
  - 优雅启动和关闭
  - 信号处理 (SIGINT, SIGTERM)
  - 健康检查
  - 组件优先级排序关闭

- **依赖注入**
  - 基于Injector的IoC容器
  - 自动发现和注册组件
  - 作用域管理

- **Web应用构建**
  - 基于类的视图 (CBV)
  - 中间件管理
  - 异常处理
  - 请求上下文
  - 统一响应模型
  - 指标收集

- **数据访问**
  - SQLAlchemy ORM支持
  - 自动事务管理
  - 连接池管理
  - 模型基类

- **消息队列**
  - Kafka生产者和消费者
  - 本地队列支持
  - 事件总线

- **缓存和存储**
  - Redis缓存
  - Minio/S3对象存储
  - 本地缓存

- **任务调度**
  - 基于asyncio的定时任务
  - 任务优先级和管理

- **通用工具**
  - 配置管理
  - 日志管理
  - 加密工具
  - Excel导入导出
  - Snowflake ID生成

## 安装

```bash
# 使用 pip 安装
pip install fautil

# 或者使用 Poetry 安装
poetry add fautil
```

## 快速开始

### 创建项目

创建一个新项目：

```bash
# 创建新项目
fautil new my_project

# 进入项目目录
cd my_project

# 安装依赖
poetry install

# 启动开发服务器
poetry run uvicorn my_project.main:app --reload
```

### 手动创建项目

如果您想手动创建项目，可以按照以下步骤进行：

```python
# main.py
from fautil.service import APIService

# 创建API服务
service = APIService(
    app_name="my_app",
    discovery_packages=["my_app"]
)

# 定义入口函数
async def start():
    await service.start(
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(start())
```

### 创建API视图

```python
# views.py
from fautil.web import APIView, route
from pydantic import BaseModel

class UserModel(BaseModel):
    id: int
    name: str
    email: str

class UserView(APIView):
    path = "/users"
    tags = ["用户管理"]

    @route("/", methods=["GET"])
    async def list_users(self):
        """获取所有用户"""
        return {"users": [
            {"id": 1, "name": "张三", "email": "zhangsan@example.com"},
            {"id": 2, "name": "李四", "email": "lisi@example.com"}
        ]}

    @route("/{user_id}", methods=["GET"])
    async def get_user(self, user_id: int):
        """获取指定用户"""
        return {"id": user_id, "name": "张三", "email": "zhangsan@example.com"}
```

## 项目结构

创建的项目具有以下结构：

```
my_project/
├── alembic.ini
├── migrations/
│   └── env.py
├── pyproject.toml
├── README.md
├── main.py
└── my_project/
    ├── __init__.py
    ├── api/
    │   ├── __init__.py
    │   └── views/
    │       ├── __init__.py
    │       └── user.py
    ├── core/
    │   ├── __init__.py
    │   ├── config.py
    │   └── exceptions.py
    ├── db/
    │   ├── __init__.py
    │   ├── models/
    │   │   ├── __init__.py
    │   │   └── user.py
    │   └── repositories/
    │       ├── __init__.py
    │       └── user.py
    ├── services/
    │   ├── __init__.py
    │   └── user.py
    └── utils/
        ├── __init__.py
        └── common.py
```

## 核心模块使用示例

### API服务

```python
from fautil.service import APIService

# 创建API服务
service = APIService(
    app_name="my_app",
    discovery_packages=["my_app.api", "my_app.services"]
)

# 启动服务
await service.start(host="0.0.0.0", port=8000)

# 注册视图
from my_app.api.views.user import UserView
service.register_view(UserView)

# 停止服务
await service.stop()
```

### 基于类的视图(CBV)

```python
from fautil.web import APIView, route
from pydantic import BaseModel

# 定义请求和响应模型
class UserCreate(BaseModel):
    name: str
    email: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

# 定义视图类
class UserView(APIView):
    path = "/users"
    tags = ["用户管理"]

    @route("/", methods=["GET"])
    async def list_users(self):
        """获取所有用户"""
        return {"users": [...]}

    @route("/{user_id}", methods=["GET"])
    async def get_user(self, user_id: int):
        """获取指定用户"""
        return {"user": {...}}

    @route("/", methods=["POST"], response_model=UserResponse)
    async def create_user(self, user: UserCreate):
        """创建新用户"""
        # 创建用户逻辑
        return {"id": 1, "name": user.name, "email": user.email}
```

### 依赖注入

```python
from fautil.service import APIService
from injector import Module, provider, singleton

# 定义服务接口和实现
class UserService:
    async def get_users(self):
        return [{"id": 1, "name": "张三"}]

# 定义依赖注入模块
class AppModule(Module):
    @singleton
    @provider
    def provide_user_service(self) -> UserService:
        return UserService()

# 使用服务
class UserView(APIView):
    path = "/users"

    def __init__(self, user_service: UserService):
        super().__init__()
        self.user_service = user_service

    @route("/", methods=["GET"])
    async def list_users(self):
        return {"users": await self.user_service.get_users()}

# 创建API服务并注册模块
service = APIService(
    app_name="my_app",
    modules=[AppModule()]
)
```

### 请求上下文

```python
from fautil.web import get_request_context, RequestContext

async def some_function():
    # 获取当前请求上下文
    context = get_request_context()
    request_id = context.request_id

    # 存储上下文数据
    context.set("user_id", 123)

    # 从上下文获取数据
    user_id = context.get("user_id")
```

### 异常处理

```python
from fautil.web import APIException, NotFoundError

# 抛出内置异常
raise NotFoundError(message="用户不存在")

# 自定义异常
raise APIException(
    status_code=400,
    error_code="INVALID_FORMAT",
    message="无效的数据格式"
)
```

## 跨平台开发指南

本项目支持在Windows、macOS和Linux上开发。为确保代码在不同平台上的一致性，请遵循以下指南：

### 行结束符处理

- 项目使用`.gitattributes`文件统一管理行结束符
- 提交到Git仓库的代码统一使用LF(`\n`)作为行结束符
- 在Windows上检出后会自动转换为CRLF(`\r\n`)
- 在提交前会自动转换回LF

### Git配置

首次克隆项目后，请按照`GIT_CONFIG.md`文件中的指南设置Git：

- Windows用户: `git config --global core.autocrlf true`
- macOS/Linux用户: `git config --global core.autocrlf input`

### 代码风格与格式化

项目使用pre-commit钩子自动处理代码风格和行结束符问题：

```bash
# 安装pre-commit
poetry install

# 安装Git钩子
poetry run pre-commit install
```

## 贡献

欢迎贡献代码或提出建议！请参阅[贡献指南](CONTRIBUTING.md)了解更多信息。

## 许可证

本项目采用MIT许可证。详情请参阅[LICENSE](LICENSE)文件。
