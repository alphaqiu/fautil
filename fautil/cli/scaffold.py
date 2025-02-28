"""
脚手架模块

提供项目脚手架功能，用于创建新项目和生成组件。
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from jinja2 import Environment, FileSystemLoader

from fautil.cli.utils import snake_to_camel, snake_to_pascal


def create_project(
    name: str,
    project_dir: Path,
    template: str = "standard",
    db_type: str = "sqlite",
    cache_type: str = "local",
    with_auth: bool = True,
    with_messaging: bool = True,
    with_scheduler: bool = True,
    with_storage: bool = True,
) -> None:
    """
    创建新项目

    Args:
        name: 项目名称
        project_dir: 项目目录
        template: 项目模板，可选: standard, minimal
        db_type: 数据库类型，可选: sqlite, mysql, postgresql
        cache_type: 缓存类型，可选: local, redis
        with_auth: 是否包含认证功能
        with_messaging: 是否包含消息队列功能
        with_scheduler: 是否包含定时任务功能
        with_storage: 是否包含对象存储功能
    """
    # 获取模板目录
    templates_dir = Path(__file__).parent.parent / "templates"

    # 创建项目基础结构
    create_project_structure(name, project_dir, template)

    # 创建项目文件
    create_project_files(
        name,
        project_dir,
        template,
        db_type,
        cache_type,
        with_auth,
        with_messaging,
        with_scheduler,
        with_storage,
    )


def create_project_structure(
    name: str, project_dir: Path, template: str = "standard"
) -> None:
    """
    创建项目目录结构

    Args:
        name: 项目名称
        project_dir: 项目目录
        template: 项目模板
    """
    # 创建项目根目录
    project_dir.mkdir(parents=True, exist_ok=True)

    # 创建项目包目录
    package_dir = project_dir / name
    package_dir.mkdir(exist_ok=True)

    # 创建标准目录结构
    dirs = [
        package_dir / "api",
        package_dir / "api" / "v1",
        package_dir / "core",
        package_dir / "db",
        package_dir / "models",
        package_dir / "schemas",
        package_dir / "services",
        package_dir / "utils",
        project_dir / "tests",
        project_dir / "alembic",
        project_dir / "alembic" / "versions",
    ]

    # 如果是标准模板，添加更多目录
    if template == "standard":
        dirs.extend(
            [
                package_dir / "dao",
                package_dir / "middlewares",
                package_dir / "tasks",
                package_dir / "static",
                package_dir / "templates",
            ]
        )

    # 创建目录
    for d in dirs:
        d.mkdir(exist_ok=True)

    # 创建空的 __init__.py 文件
    for d in dirs:
        init_file = d / "__init__.py"
        if not init_file.exists():
            init_file.touch()


def create_project_files(
    name: str,
    project_dir: Path,
    template: str = "standard",
    db_type: str = "sqlite",
    cache_type: str = "local",
    with_auth: bool = True,
    with_messaging: bool = True,
    with_scheduler: bool = True,
    with_storage: bool = True,
) -> None:
    """
    创建项目文件

        Args:
        name: 项目名称
        project_dir: 项目目录
        template: 项目模板
        db_type: 数据库类型
        cache_type: 缓存类型
        with_auth: 是否包含认证功能
        with_messaging: 是否包含消息队列功能
        with_scheduler: 是否包含定时任务功能
        with_storage: 是否包含对象存储功能
    """
    # 获取模板环境
    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))

    # 准备模板变量
    context = {
        "project_name": name,
        "project_name_pascal": snake_to_pascal(name),
        "project_name_camel": snake_to_camel(name),
        "db_type": db_type,
        "cache_type": cache_type,
        "with_auth": with_auth,
        "with_messaging": with_messaging,
        "with_scheduler": with_scheduler,
        "with_storage": with_storage,
    }

    # 创建 pyproject.toml
    create_file_from_template(
        env, "pyproject.toml.jinja2", project_dir / "pyproject.toml", context
    )

    # 创建 README.md
    create_file_from_template(
        env, "README.md.jinja2", project_dir / "README.md", context
    )

    # 创建 .gitignore
    create_file_from_template(
        env, "gitignore.jinja2", project_dir / ".gitignore", context
    )

    # 创建 .env 和 .env.example
    create_file_from_template(env, "env.jinja2", project_dir / ".env", context)
    create_file_from_template(
        env, "env.example.jinja2", project_dir / ".env.example", context
    )

    # 创建 alembic.ini
    create_file_from_template(
        env, "alembic.ini.jinja2", project_dir / "alembic.ini", context
    )

    # 创建 alembic/env.py
    create_file_from_template(
        env, "alembic_env.py.jinja2", project_dir / "alembic" / "env.py", context
    )

    # 创建 wsgi.py
    create_file_from_template(
        env, "wsgi.py.jinja2", project_dir / name / "wsgi.py", context
    )

    # 创建 config.py
    create_file_from_template(
        env, "config.py.jinja2", project_dir / name / "core" / "config.py", context
    )

    # 创建 db.py
    create_file_from_template(
        env, "db.py.jinja2", project_dir / name / "db" / "db.py", context
    )

    # 创建 base.py
    create_file_from_template(
        env, "base.py.jinja2", project_dir / name / "models" / "base.py", context
    )

    # 创建 dependencies.py
    create_file_from_template(
        env,
        "dependencies.py.jinja2",
        project_dir / name / "core" / "dependencies.py",
        context,
    )

    # 创建 exceptions.py
    create_file_from_template(
        env,
        "exceptions.py.jinja2",
        project_dir / name / "core" / "exceptions.py",
        context,
    )

    # 创建 middleware.py
    create_file_from_template(
        env,
        "middleware.py.jinja2",
        project_dir / name / "core" / "middleware.py",
        context,
    )

    # 创建 utils.py
    create_file_from_template(
        env, "utils.py.jinja2", project_dir / name / "utils" / "utils.py", context
    )

    # 创建 api/__init__.py
    create_file_from_template(
        env, "api_init.py.jinja2", project_dir / name / "api" / "__init__.py", context
    )

    # 创建 api/v1/__init__.py
    create_file_from_template(
        env,
        "api_v1_init.py.jinja2",
        project_dir / name / "api" / "v1" / "__init__.py",
        context,
    )

    # 创建 api/v1/endpoints.py
    create_file_from_template(
        env,
        "endpoints.py.jinja2",
        project_dir / name / "api" / "v1" / "endpoints.py",
        context,
    )

    # 创建 __init__.py
    create_file_from_template(
        env, "init.py.jinja2", project_dir / name / "__init__.py", context
    )

    # 如果包含认证功能，创建认证相关文件
    if with_auth:
        create_file_from_template(
            env, "auth.py.jinja2", project_dir / name / "core" / "auth.py", context
        )
        create_file_from_template(
            env,
            "user_model.py.jinja2",
            project_dir / name / "models" / "user.py",
            context,
        )
        create_file_from_template(
            env,
            "user_schema.py.jinja2",
            project_dir / name / "schemas" / "user.py",
            context,
        )
        create_file_from_template(
            env,
            "auth_service.py.jinja2",
            project_dir / name / "services" / "auth.py",
            context,
        )
        create_file_from_template(
            env,
            "auth_api.py.jinja2",
            project_dir / name / "api" / "v1" / "auth.py",
            context,
        )

    # 如果包含消息队列功能，创建消息队列相关文件
    if with_messaging:
        create_file_from_template(
            env,
            "messaging.py.jinja2",
            project_dir / name / "core" / "messaging.py",
            context,
        )

    # 如果包含定时任务功能，创建定时任务相关文件
    if with_scheduler:
        create_file_from_template(
            env,
            "scheduler.py.jinja2",
            project_dir / name / "core" / "scheduler.py",
            context,
        )
        create_file_from_template(
            env, "tasks.py.jinja2", project_dir / name / "tasks" / "tasks.py", context
        )

    # 如果包含对象存储功能，创建对象存储相关文件
    if with_storage:
        create_file_from_template(
            env,
            "storage.py.jinja2",
            project_dir / name / "core" / "storage.py",
            context,
        )


def create_file_from_template(
    env: Environment, template_name: str, output_path: Path, context: Dict
) -> None:
    """
    从模板创建文件

        Args:
        env: Jinja2 环境
        template_name: 模板名称
        output_path: 输出路径
        context: 模板上下文
    """
    try:
        template = env.get_template(template_name)
        content = template.render(**context)

        with open(output_path, "w") as f:
            f.write(content)
    except Exception as e:
        print(f"创建文件 {output_path} 失败: {str(e)}")


def generate_model(project_name: str, name: str) -> None:
    """
    生成模型

    Args:
        project_name: 项目名称
        name: 模型名称
    """
    # 获取模板环境
    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))

    # 准备模板变量
    context = {
        "project_name": project_name,
        "model_name": name,
        "model_name_pascal": snake_to_pascal(name),
        "model_name_camel": snake_to_camel(name),
    }

    # 创建模型文件
    output_path = Path(f"{project_name}/models/{name}.py")
    create_file_from_template(env, "model.py.jinja2", output_path, context)


def generate_view(project_name: str, name: str) -> None:
    """
    生成视图

    Args:
        project_name: 项目名称
        name: 视图名称
    """
    # 获取模板环境
    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))

    # 准备模板变量
    context = {
        "project_name": project_name,
        "view_name": name,
        "view_name_pascal": snake_to_pascal(name),
        "view_name_camel": snake_to_camel(name),
    }

    # 创建视图文件
    output_path = Path(f"{project_name}/api/v1/{name}.py")
    create_file_from_template(env, "view.py.jinja2", output_path, context)


def generate_service(project_name: str, name: str) -> None:
    """
    生成服务

    Args:
        project_name: 项目名称
        name: 服务名称
    """
    # 获取模板环境
    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))

    # 准备模板变量
    context = {
        "project_name": project_name,
        "service_name": name,
        "service_name_pascal": snake_to_pascal(name),
        "service_name_camel": snake_to_camel(name),
    }

    # 创建服务文件
    output_path = Path(f"{project_name}/services/{name}.py")
    create_file_from_template(env, "service.py.jinja2", output_path, context)


def generate_schema(project_name: str, name: str) -> None:
    """
    生成模式

    Args:
        project_name: 项目名称
        name: 模式名称
    """
    # 获取模板环境
    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))

    # 准备模板变量
    context = {
        "project_name": project_name,
        "schema_name": name,
        "schema_name_pascal": snake_to_pascal(name),
        "schema_name_camel": snake_to_camel(name),
    }

    # 创建模式文件
    output_path = Path(f"{project_name}/schemas/{name}.py")
    create_file_from_template(env, "schema.py.jinja2", output_path, context)


def generate_dao(project_name: str, name: str) -> None:
    """
    生成DAO

    Args:
        project_name: 项目名称
        name: DAO名称
    """
    # 获取模板环境
    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))

    # 准备模板变量
    context = {
        "project_name": project_name,
        "dao_name": name,
        "dao_name_pascal": snake_to_pascal(name),
        "dao_name_camel": snake_to_camel(name),
    }

    # 创建DAO文件
    output_path = Path(f"{project_name}/dao/{name}.py")
    create_file_from_template(env, "dao.py.jinja2", output_path, context)
