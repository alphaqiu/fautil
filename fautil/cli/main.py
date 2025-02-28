"""
命令行工具主入口模块

提供命令行工具的主入口，处理命令行参数。
"""

import os
import sys
from pathlib import Path
from typing import Optional

import click

from fautil import __version__
from fautil.cli.scaffold import create_project


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """FastAPI Utility框架命令行工具"""
    pass


@main.command()
@click.argument("name")
@click.option("--dir", default=".", help="项目创建目录，默认为当前目录")
def new(name: str, dir: str) -> None:
    """
    创建新项目

    NAME: 项目名称
    """
    # 创建项目目录
    project_dir = Path(dir) / name
    if project_dir.exists():
        click.echo(f"错误: 目录 {project_dir} 已存在")
        sys.exit(1)

    # 创建项目
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
        create_project(name, project_dir)
        click.echo(f"项目 {name} 已创建成功！")
        click.echo(f"项目路径: {project_dir}")
        click.echo(f"使用以下命令启动项目:")
        click.echo(f"  cd {project_dir}")
        click.echo(f"  poetry install")
        click.echo(f"  poetry run uvicorn {name}.wsgi:app --reload")
    except Exception as e:
        click.echo(f"创建项目失败: {str(e)}")
        sys.exit(1)


@main.command()
@click.option(
    "--type",
    type=click.Choice(["model", "view", "rule", "all"]),
    default="all",
    help="生成的组件类型",
)
@click.argument("name")
def generate(type: str, name: str) -> None:
    """
    生成组件

    NAME: 组件名称
    """
    # 检查是否在项目目录中
    if not Path("pyproject.toml").exists():
        click.echo("错误: 请在项目根目录下运行此命令")
        sys.exit(1)

    # 生成组件
    try:
        # 获取项目名称
        from fautil.cli.utils import get_project_name

        project_name = get_project_name()

        if not project_name:
            click.echo("错误: 无法确定项目名称，请检查 pyproject.toml 文件")
            sys.exit(1)

        # 导入对应的生成器
        from fautil.cli.scaffold import (
            generate_model,
            generate_view,
            generate_rule,
        )

        # 根据类型生成组件
        if type == "all" or type == "model":
            generate_model(project_name, name)
            click.echo(f"模型 {name} 已生成")

        if type == "all" or type == "view":
            generate_view(project_name, name)
            click.echo(f"视图 {name} 已生成")

        if type == "all" or type == "rule":
            generate_rule(project_name, name)
            click.echo(f"规则 {name} 已生成")

        click.echo("组件生成成功！")
    except Exception as e:
        click.echo(f"生成组件失败: {str(e)}")
        sys.exit(1)


@main.command()
@click.option("--message", "-m", default="", help="迁移说明")
def migrate(message: str) -> None:
    """生成数据库迁移文件"""
    # 检查是否在项目目录中
    if not Path("pyproject.toml").exists():
        click.echo("错误: 请在项目根目录下运行此命令")
        sys.exit(1)

    try:
        # 执行 Alembic 命令
        import subprocess

        cmd = [sys.executable, "-m", "alembic", "revision", "--autogenerate"]
        if message:
            cmd.extend(["-m", message])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            click.echo("数据库迁移文件生成成功！")
            click.echo(result.stdout)
        else:
            click.echo(f"生成迁移文件失败: {result.stderr}")
            sys.exit(1)
    except Exception as e:
        click.echo(f"生成迁移文件失败: {str(e)}")
        sys.exit(1)


@main.command()
@click.option("--revision", default="head", help="要升级到的版本，默认为最新版本")
def upgrade(revision: str) -> None:
    """升级数据库"""
    # 检查是否在项目目录中
    if not Path("pyproject.toml").exists():
        click.echo("错误: 请在项目根目录下运行此命令")
        sys.exit(1)

    try:
        # 执行 Alembic 命令
        import subprocess

        cmd = [sys.executable, "-m", "alembic", "upgrade", revision]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            click.echo("数据库升级成功！")
            click.echo(result.stdout)
        else:
            click.echo(f"数据库升级失败: {result.stderr}")
            sys.exit(1)
    except Exception as e:
        click.echo(f"数据库升级失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
