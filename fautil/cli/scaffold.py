"""
项目脚手架模块

提供项目脚手架功能，用于生成项目模板和组件。
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union

from fautil.cli.utils import snake_to_camel, snake_to_pascal


# 项目模板文件内容
TEMPLATES = {
    "pyproject.toml": """[tool.poetry]
name = "{project_name}"
version = "0.1.0"
description = "使用FastAPI Utility框架创建的项目"
authors = ["Your Name <your.email@example.com>"]
readme = "README.md"

[tool.poetry.dependencies]
python = ">=3.9,<4.0"
fautil = ">=0.2.0,<0.3.0"
uvicorn = ">=0.23.0,<0.24.0"

[tool.poetry.group.dev.dependencies]
pytest = ">=7.0.0,<8.0.0"
pytest-asyncio = ">=0.20.0,<0.21.0"
black = ">=23.0.0,<24.0.0"
isort = ">=5.0.0,<6.0.0"
mypy = ">=1.0.0,<2.0.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.black]
line-length = 88
target-version = ["py39"]

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
""",
    "README.md": """# {project_name_title}

使用六坊框架创建的项目

## 安装

```bash
pip install -r requirements.txt
```

## 开发

```bash
# 启动开发服务器
uvicorn {project_name}.wsgi:app --reload

# 创建数据库迁移
alembic revision --autogenerate -m "备注信息"

# 应用数据库迁移
alembic upgrade head
```

## 部署

```bash
# 安装生产依赖
pip install -r requirements.txt

# 启动生产服务器
uvicorn {project_name}.wsgi:app --host 0.0.0.0 --port 8000
```
""",
    "alembic.ini": """# Alembic 配置

[alembic]
# 脚本位置
script_location = migrations

# 模板使用 jinja2
# jinja2.extensions = jinja2.ext.loopcontrols

# 数据库连接 URL，将在 env.py 中设置
sqlalchemy.url = driver://user:pass@localhost/dbname

# 日志输出模板
# file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d%%(second).2d_%%(slug)s

# 设置为'true'以允许 .pyc 和 .pyo 文件
# set to 'true' to allow .pyc and .pyo files without
# corresponding .py file to be detected as revisions
# sourceless = false

# 在日志中回显 SQL
# output_encoding = utf-8

# 将 SQL 脚本编码设置为 'utf8'
sqlalchemy.url = sqlite:///./app.db

# 仅输出 SQL Schema
# schema_only = true

[post_write_hooks]
# post_write_hooks defines scripts or Python functions that are run
# on newly generated revision scripts.  See the documentation for further
# detail and examples

# format using "black" - use the console_scripts runner, against the "black" entrypoint
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
""",
    ".env": """# 环境变量配置文件
LFUN_APP_NAME="{project_name}"
LFUN_APP_VERSION="0.1.0"
LFUN_DEBUG=true

# 数据库配置
LFUN_DB_URL="sqlite:///./app.db"
LFUN_DB_ECHO=true

# Redis 配置
LFUN_REDIS_HOST="localhost"
LFUN_REDIS_PORT=6379
LFUN_REDIS_DB=0

# Kafka 配置
LFUN_KAFKA_BOOTSTRAP_SERVERS=["localhost:9092"]
LFUN_KAFKA_GROUP_ID="{project_name}-consumer-group"
""",
    "wsgi.py": """#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from lfun_framework.core.app import Application
from lfun_framework.core.config import load_settings
from lfun_framework.core.exceptions import setup_exception_handlers
from lfun_framework.db import init_db
from lfun_framework.web.middleware import setup_middlewares

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("{project_name}")

# 加载配置
config_path = os.environ.get("CONFIG_FILE")
settings = load_settings(config_path)

# 创建应用
app = FastAPI(
    title=settings.app.app_name,
    version=settings.app.app_version,
    debug=settings.app.debug,
    docs_url=settings.app.docs_url,
    redoc_url=settings.app.redoc_url,
    openapi_url=settings.app.openapi_url,
)

# 设置异常处理器
setup_exception_handlers(app)

# 设置中间件
setup_middlewares(app, settings.app)

# 初始化数据库
init_db(settings.db)

# 添加静态文件
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 引入视图
from {project_name}.views import router as api_router

# 注册路由
app.include_router(api_router, prefix=settings.app.api_prefix)

# 创建应用实例
application = Application(settings=settings)
application.app = app

if __name__ == "__main__":
    import uvicorn

    # 运行应用
    uvicorn.run(
        "wsgi:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app.debug,
    )
""",
    "{project_name}/__init__.py": """# -*- coding: utf-8 -*-
"""标准化目录结构的六坊项目"""

__version__ = "0.1.0"
""",
    "{project_name}/views/__init__.py": """# -*- coding: utf-8 -*-
"""视图层模块

处理HTTP请求，调用业务规则，返回HTTP响应。
"""

from fastapi import APIRouter

# 创建API路由器
router = APIRouter()

# 导入视图模块
from {project_name}.views.hello import router as hello_router

# 注册子路由器
router.include_router(hello_router, tags=["Hello"])
""",
    "{project_name}/views/hello.py": """# -*- coding: utf-8 -*-
"""Hello视图模块

示例视图模块
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from {project_name}.rules.hello import HelloRule

router = APIRouter()


class HelloResponse(BaseModel):
    """Hello响应模型"""

    message: str


@router.get("/hello", response_model=HelloResponse)
async def hello(name: str = "world"):
    """
    Hello API

    一个简单的示例API，返回问候消息。

    参数:
        name: 名称，默认为"world"

    返回:
        HelloResponse: 问候消息
    """
    # 调用业务规则
    rule = HelloRule()
    message = await rule.get_hello_message(name)

    # 返回响应
    return HelloResponse(message=message)
""",
    "{project_name}/rules/__init__.py": """# -*- coding: utf-8 -*-
"""业务规则层模块

包含业务规则、逻辑处理和服务协调。
"""
""",
    "{project_name}/rules/hello.py": """# -*- coding: utf-8 -*-
"""Hello业务规则模块

示例业务规则模块
"""

from {project_name}.dao.hello import HelloDAO


class HelloRule:
    """Hello业务规则类"""

    def __init__(self):
        """初始化Hello业务规则"""
        self.dao = HelloDAO()

    async def get_hello_message(self, name: str) -> str:
        """
        获取问候消息

        参数:
            name: 名称

        返回:
            str: 问候消息
        """
        # 调用DAO获取问候模板
        template = await self.dao.get_greeting_template()

        # 格式化模板
        return template.format(name=name)
""",
    "{project_name}/dao/__init__.py": """# -*- coding: utf-8 -*-
"""数据访问层模块

处理数据库访问、缓存访问和外部服务调用。
"""
""",
    "{project_name}/dao/hello.py": """# -*- coding: utf-8 -*-
"""Hello数据访问模块

示例数据访问模块
"""


class HelloDAO:
    """Hello数据访问类"""

    async def get_greeting_template(self) -> str:
        """
        获取问候模板

        返回:
            str: 问候模板
        """
        # 这里可以从数据库或缓存中获取模板
        # 示例中直接返回固定模板
        return "Hello, {name}!"
""",
    "{project_name}/models/__init__.py": """# -*- coding: utf-8 -*-
"""数据模型层模块

定义数据库模型和数据结构。
"""

from {project_name}.models.hello import Hello

__all__ = ["Hello"]
""",
    "{project_name}/models/hello.py": """# -*- coding: utf-8 -*-
"""Hello数据模型模块

示例数据模型模块
"""

from lfun_framework.db import Base
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class Hello(Base):
    """Hello数据模型"""

    __tablename__ = "hello"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<Hello(name={self.name}, message={self.message})>"
""",
    "{project_name}/common/__init__.py": """# -*- coding: utf-8 -*-
"""公共模块

包含工具函数、常量和通用功能。
"""
""",
    "{project_name}/common/utils.py": """# -*- coding: utf-8 -*-
"""工具函数模块

包含各种工具函数。
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def timer(func: Callable[..., T]) -> Callable[..., T]:
    """
    计时器装饰器

    记录函数执行时间

    参数:
        func: 被装饰的函数

    返回:
        Callable[..., T]: 装饰后的函数
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"函数 {func.__name__} 执行时间: {end_time - start_time:.4f}秒")
        return result

    return wrapper
""",
    "migrations/env.py": """# -*- coding: utf-8 -*-
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from lfun_framework.core.config import DBConfig, Settings, load_settings
from lfun_framework.db import Base
from {project_name}.models import *  # 导入所有模型

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# 加载配置
settings = load_settings()

# 设置数据库URL
config.set_main_option("sqlalchemy.url", settings.db.url)

# 设置元数据
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
""",
    "migrations/README": """# 数据库迁移

此目录包含数据库迁移文件。

## 创建迁移

```bash
alembic revision --autogenerate -m "描述迁移内容"
```

## 应用迁移

```bash
alembic upgrade head
```

## 回滚迁移

```bash
alembic downgrade -1
```
""",
    "migrations/script.py.mako": """\"\"\"${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

\"\"\"
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
""",
    "migrations/versions/.gitkeep": "",
    "requirements.txt": """# 项目依赖
fautil>=0.2.0,<0.3.0
uvicorn>=0.23.0,<0.24.0
"""
}


def create_project(project_name: str, project_dir: Path) -> None:
    """
    创建项目脚手架
    
    Args:
        project_name: 项目名称
        project_dir: 项目目录
    """
    # 创建基本目录
    for subdir in [
        project_name,
        f"{project_name}/views",
        f"{project_name}/rules",
        f"{project_name}/dao",
        f"{project_name}/models",
        f"{project_name}/common",
        "migrations",
        "migrations/versions",
    ]:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    # 格式化项目名称
    project_name_title = project_name.replace("_", " ").title()
    
    # 创建文件
    for filename, content in TEMPLATES.items():
        # 替换文件名中的占位符
        target_filename = filename.format(project_name=project_name)
        # 替换内容中的占位符
        formatted_content = content.format(
            project_name=project_name,
            project_name_title=project_name_title,
        )
        # 写入文件
        with open(project_dir / target_filename, "w", encoding="utf-8") as f:
            f.write(formatted_content)


# 模型模板
MODEL_TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"
{name} 数据模型模块
\"\"\"

from lfun_framework.db import Base
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List


class {class_name}(Base):
    \"\"\"
    {name} 数据模型
    \"\"\"
    
    __tablename__ = "{table_name}"
    
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    def __repr__(self) -> str:
        return f"<{class_name}(id={self.id}, name={self.name})>"
"""


# 视图模板
VIEW_TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"
{name} 视图模块
\"\"\"

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from {project_name}.rules.{module_name} import {class_name}Rule

router = APIRouter(prefix="/{api_prefix}")


class {class_name}Base(BaseModel):
    \"\"\"
    {name} 基础模型
    \"\"\"
    name: str
    description: Optional[str] = None


class {class_name}Create(BaseModel):
    \"\"\"
    {name} 创建模型
    \"\"\"
    name: str
    description: Optional[str] = None


class {class_name}Response(BaseModel):
    \"\"\"
    {name} 响应模型
    \"\"\"
    id: str
    name: str
    description: Optional[str] = None
    created_at: str
    updated_at: str
    
    class Config:
        orm_mode = True


@router.post("", response_model={class_name}Response)
async def create_{module_name}(item: {class_name}Create):
    \"\"\"
    创建 {name}
    \"\"\"
    rule = {class_name}Rule()
    result = await rule.create(item.dict())
    return result


@router.get("", response_model=List[{class_name}Response])
async def list_{module_name}():
    \"\"\"
    列出所有 {name}
    \"\"\"
    rule = {class_name}Rule()
    return await rule.list_all()


@router.get("/{{item_id}}", response_model={class_name}Response)
async def get_{module_name}(item_id: str):
    \"\"\"
    获取 {name} 详情
    \"\"\"
    rule = {class_name}Rule()
    result = await rule.get_by_id(item_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{name}不存在"
        )
    return result


@router.put("/{{item_id}}", response_model={class_name}Response)
async def update_{module_name}(item_id: str, item: {class_name}Base):
    \"\"\"
    更新 {name}
    \"\"\"
    rule = {class_name}Rule()
    result = await rule.update(item_id, item.dict())
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{name}不存在"
        )
    return result


@router.delete("/{{item_id}}", response_model={class_name}Response)
async def delete_{module_name}(item_id: str):
    \"\"\"
    删除 {name}
    \"\"\"
    rule = {class_name}Rule()
    result = await rule.delete(item_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{name}不存在"
        )
    return result
"""


# 规则模板
RULE_TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"
{name} 业务规则模块
\"\"\"

from typing import Dict, List, Optional, Any
from lfun_framework.db import transactional
from sqlalchemy.ext.asyncio import AsyncSession

from {project_name}.dao.{module_name} import {class_name}DAO


class {class_name}Rule:
    \"\"\"
    {name} 业务规则类
    \"\"\"
    
    def __init__(self):
        \"\"\"
        初始化 {name} 业务规则
        \"\"\"
        self.dao = {class_name}DAO()
    
    @transactional
    async def create(self, data: Dict[str, Any], session: Optional[AsyncSession] = None) -> Any:
        \"\"\"
        创建 {name}
        
        Args:
            data: {name} 数据
            session: 数据库会话
            
        Returns:
            Any: 创建的 {name}
        \"\"\"
        return await self.dao.create(data, session=session)
    
    async def list_all(self) -> List[Any]:
        \"\"\"
        列出所有 {name}
        
        Returns:
            List[Any]: {name} 列表
        \"\"\"
        return await self.dao.list_all()
    
    async def get_by_id(self, id: str) -> Optional[Any]:
        \"\"\"
        根据ID获取 {name}
        
        Args:
            id: {name} ID
            
        Returns:
            Optional[Any]: {name} 对象，如果不存在则返回 None
        \"\"\"
        return await self.dao.get_by_id(id)
    
    @transactional
    async def update(self, id: str, data: Dict[str, Any], session: Optional[AsyncSession] = None) -> Optional[Any]:
        \"\"\"
        更新 {name}
        
        Args:
            id: {name} ID
            data: 更新数据
            session: 数据库会话
            
        Returns:
            Optional[Any]: 更新后的 {name}，如果不存在则返回 None
        \"\"\"
        return await self.dao.update(id, data, session=session)
    
    @transactional
    async def delete(self, id: str, session: Optional[AsyncSession] = None) -> Optional[Any]:
        \"\"\"
        删除 {name}
        
        Args:
            id: {name} ID
            session: 数据库会话
            
        Returns:
            Optional[Any]: 删除的 {name}，如果不存在则返回 None
        \"\"\"
        return await self.dao.delete(id, session=session)
"""


# DAO模板
DAO_TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"
{name} 数据访问模块
\"\"\"

from typing import Dict, List, Optional, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lfun_framework.db import get_session
from {project_name}.models.{module_name} import {class_name}


class {class_name}DAO:
    \"\"\"
    {name} 数据访问类
    \"\"\"
    
    async def create(self, data: Dict[str, Any], session: Optional[AsyncSession] = None) -> {class_name}:
        \"\"\"
        创建 {name}
        
        Args:
            data: {name} 数据
            session: 数据库会话
            
        Returns:
            {class_name}: 创建的 {name}
        \"\"\"
        async with get_session() as session_ctx:
            session = session or session_ctx
            obj = {class_name}(**data)
            session.add(obj)
            await session.flush()
            await session.refresh(obj)
            return obj
    
    async def list_all(self) -> List[{class_name}]:
        \"\"\"
        列出所有 {name}
        
        Returns:
            List[{class_name}]: {name} 列表
        \"\"\"
        async with get_session() as session:
            result = await session.execute(select({class_name}))
            return list(result.scalars().all())
    
    async def get_by_id(self, id: str) -> Optional[{class_name}]:
        \"\"\"
        根据ID获取 {name}
        
        Args:
            id: {name} ID
            
        Returns:
            Optional[{class_name}]: {name} 对象，如果不存在则返回 None
        \"\"\"
        async with get_session() as session:
            return await session.get({class_name}, id)
    
    async def update(self, id: str, data: Dict[str, Any], session: Optional[AsyncSession] = None) -> Optional[{class_name}]:
        \"\"\"
        更新 {name}
        
        Args:
            id: {name} ID
            data: 更新数据
            session: 数据库会话
            
        Returns:
            Optional[{class_name}]: 更新后的 {name}，如果不存在则返回 None
        \"\"\"
        async with get_session() as session_ctx:
            session = session or session_ctx
            obj = await session.get({class_name}, id)
            if not obj:
                return None
            
            for key, value in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            
            await session.flush()
            await session.refresh(obj)
            return obj
    
    async def delete(self, id: str, session: Optional[AsyncSession] = None) -> Optional[{class_name}]:
        \"\"\"
        删除 {name}
        
        Args:
            id: {name} ID
            session: 数据库会话
            
        Returns:
            Optional[{class_name}]: 删除的 {name}，如果不存在则返回 None
        \"\"\"
        async with get_session() as session_ctx:
            session = session or session_ctx
            obj = await session.get({class_name}, id)
            if not obj:
                return None
            
            await session.delete(obj)
            return obj
"""


def generate_model(project_name: str, model_name: str) -> None:
    """
    生成模型
    
    Args:
        project_name: 项目名称
        model_name: 模型名称
    """
    module_name = model_name.lower()
    class_name = snake_to_pascal(module_name)
    table_name = module_name
    
    # 创建模型文件
    model_file = Path(f"{project_name}/models/{module_name}.py")
    with open(model_file, "w", encoding="utf-8") as f:
        f.write(MODEL_TEMPLATE.format(
            name=model_name,
            class_name=class_name,
            table_name=table_name,
        ))
    
    # 更新 __init__.py
    init_file = Path(f"{project_name}/models/__init__.py")
    if init_file.exists():
        with open(init_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查是否已经导入
        import_line = f"from {project_name}.models.{module_name} import {class_name}"
        if import_line not in content:
            # 添加导入语句
            parts = content.split("__all__ =")
            if len(parts) == 2:
                # 更新导入
                imports = parts[0].strip() + f"\n{import_line}\n\n"
                
                # 更新 __all__
                all_part = parts[1].strip()
                if all_part.startswith("[") and all_part.endswith("]"):
                    # 提取列表内容
                    items = all_part[1:-1].strip()
                    if items:
                        all_list = [item.strip(' "\'') for item in items.split(",")]
                        if class_name not in all_list:
                            all_list.append(class_name)
                        
                        # 重建 __all__
                        all_str = ", ".join([f'"{item}"' for item in all_list])
                        all_part = f"[{all_str}]"
                    else:
                        all_part = f'["{class_name}"]'
                
                # 合并内容
                content = f"{imports}__all__ = {all_part}\n"
                
                # 写入文件
                with open(init_file, "w", encoding="utf-8") as f:
                    f.write(content)


def generate_view(project_name: str, view_name: str) -> None:
    """
    生成视图
    
    Args:
        project_name: 项目名称
        view_name: 视图名称
    """
    module_name = view_name.lower()
    class_name = snake_to_pascal(module_name)
    api_prefix = module_name.replace("_", "-")
    
    # 创建视图文件
    view_file = Path(f"{project_name}/views/{module_name}.py")
    with open(view_file, "w", encoding="utf-8") as f:
        f.write(VIEW_TEMPLATE.format(
            name=view_name,
            class_name=class_name,
            module_name=module_name,
            api_prefix=api_prefix,
            project_name=project_name,
        ))
    
    # 更新 __init__.py
    init_file = Path(f"{project_name}/views/__init__.py")
    if init_file.exists():
        with open(init_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查是否已经导入
        import_line = f"from {project_name}.views.{module_name} import router as {module_name}_router"
        if import_line not in content:
            # 更新文件
            lines = content.split("\n")
            import_index = -1
            register_index = -1
            
            # 查找导入位置和注册位置
            for i, line in enumerate(lines):
                if line.startswith("# 导入视图模块"):
                    import_index = i + 1
                elif line.startswith("# 注册子路由器"):
                    register_index = i + 1
            
            # 插入导入
            if import_index >= 0:
                lines.insert(import_index, import_line)
                register_index += 1  # 导入行增加后，注册行的索引也要增加
            
            # 插入注册路由
            if register_index >= 0:
                lines.insert(register_index, f'router.include_router({module_name}_router, tags=["{class_name}"])')
            
            # 合并内容
            content = "\n".join(lines)
            
            # 写入文件
            with open(init_file, "w", encoding="utf-8") as f:
                f.write(content)


def generate_rule(project_name: str, rule_name: str) -> None:
    """
    生成规则
    
    Args:
        project_name: 项目名称
        rule_name: 规则名称
    """
    module_name = rule_name.lower()
    class_name = snake_to_pascal(module_name)
    
    # 创建规则文件
    rule_file = Path(f"{project_name}/rules/{module_name}.py")
    with open(rule_file, "w", encoding="utf-8") as f:
        f.write(RULE_TEMPLATE.format(
            name=rule_name,
            class_name=class_name,
            module_name=module_name,
            project_name=project_name,
        ))
    
    # 创建DAO文件
    dao_file = Path(f"{project_name}/dao/{module_name}.py")
    with open(dao_file, "w", encoding="utf-8") as f:
        f.write(DAO_TEMPLATE.format(
            name=rule_name,
            class_name=class_name,
            module_name=module_name,
            project_name=project_name,
        )) 