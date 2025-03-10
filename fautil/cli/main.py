"""
命令行工具主入口模块

提供命令行工具的主入口，处理命令行参数。
"""

import sys
from pathlib import Path

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
@click.option(
    "--template", default="standard", help="项目模板，可选: standard, minimal"
)
@click.option(
    "--db", default="sqlite", help="数据库类型，可选: sqlite, mysql, postgresql"
)
@click.option("--cache", default="local", help="缓存类型，可选: local, redis")
@click.option("--auth/--no-auth", default=True, help="是否包含认证功能")
@click.option("--messaging/--no-messaging", default=True, help="是否包含消息队列功能")
@click.option("--scheduler/--no-scheduler", default=True, help="是否包含定时任务功能")
@click.option("--storage/--no-storage", default=True, help="是否包含对象存储功能")
def new(
    name: str,
    directory: str,
    template: str,
    db: str,
    cache: str,
    auth: bool,
    messaging: bool,
    scheduler: bool,
    storage: bool,
) -> None:
    """
    创建新项目

    NAME: 项目名称
    """
    # 创建项目目录
    project_dir = Path(directory) / name
    if project_dir.exists():
        click.echo(f"错误: 目录 {project_dir} 已存在")
        sys.exit(1)

    # 创建项目
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
        create_project(
            name,
            project_dir,
            template=template,
            db_type=db,
            cache_type=cache,
            with_auth=auth,
            with_messaging=messaging,
            with_scheduler=scheduler,
            with_storage=storage,
        )
        click.echo(f"项目 {name} 已创建成功！")
        click.echo(f"项目路径: {project_dir}")
        click.echo("使用以下命令启动项目:")
        click.echo(f"  cd {project_dir}")
        click.echo("  poetry install")
        click.echo(f"  poetry run uvicorn {name}.wsgi:app --reload")
    except Exception as e:
        click.echo(f"创建项目失败: {str(e)}")
        sys.exit(1)


@main.command()
@click.option(
    "--type",
    type=click.Choice(["model", "view", "service", "schema", "dao", "all"]),
    default="all",
    help="生成的组件类型",
)
@click.argument("name")
def generate(component_type: str, name: str) -> None:
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
            generate_dao,
            generate_model,
            generate_schema,
            generate_service,
            generate_view,
        )

        # 根据类型生成组件
        if component_type == "all" or component_type == "model":
            generate_model(project_name, name)
            click.echo(f"模型 {name} 已生成")

        if component_type == "all" or component_type == "view":
            generate_view(project_name, name)
            click.echo(f"视图 {name} 已生成")

        if component_type == "all" or component_type == "service":
            generate_service(project_name, name)
            click.echo(f"服务 {name} 已生成")

        if component_type == "all" or component_type == "schema":
            generate_schema(project_name, name)
            click.echo(f"模式 {name} 已生成")

        if component_type == "all" or component_type == "dao":
            generate_dao(project_name, name)
            click.echo(f"DAO {name} 已生成")

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


@main.command()
@click.option("--revision", default="-1", help="要降级到的版本，默认为上一个版本")
def downgrade(revision: str) -> None:
    """降级数据库"""
    # 检查是否在项目目录中
    if not Path("pyproject.toml").exists():
        click.echo("错误: 请在项目根目录下运行此命令")
        sys.exit(1)

    try:
        # 执行 Alembic 命令
        import subprocess

        cmd = [sys.executable, "-m", "alembic", "downgrade", revision]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            click.echo("数据库降级成功！")
            click.echo(result.stdout)
        else:
            click.echo(f"数据库降级失败: {result.stderr}")
            sys.exit(1)
    except Exception as e:
        click.echo(f"数据库降级失败: {str(e)}")
        sys.exit(1)


@main.command()
def history() -> None:
    """查看数据库迁移历史"""
    # 检查是否在项目目录中
    if not Path("pyproject.toml").exists():
        click.echo("错误: 请在项目根目录下运行此命令")
        sys.exit(1)

    try:
        # 执行 Alembic 命令
        import subprocess

        cmd = [sys.executable, "-m", "alembic", "history"]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            click.echo(result.stdout)
        else:
            click.echo(f"查看迁移历史失败: {result.stderr}")
            sys.exit(1)
    except Exception as e:
        click.echo(f"查看迁移历史失败: {str(e)}")
        sys.exit(1)


@main.command()
@click.option("--host", default="127.0.0.1", help="主机地址")
@click.option("--port", default=8000, help="端口号")
@click.option("--reload/--no-reload", default=True, help="是否启用热重载")
def run(host: str, port: int, reload: bool) -> None:
    """运行开发服务器"""
    # 检查是否在项目目录中
    if not Path("pyproject.toml").exists():
        click.echo("错误: 请在项目根目录下运行此命令")
        sys.exit(1)

    try:
        # 获取项目名称
        from fautil.cli.utils import get_project_name

        project_name = get_project_name()

        if not project_name:
            click.echo("错误: 无法确定项目名称，请检查 pyproject.toml 文件")
            sys.exit(1)

        # 执行 uvicorn 命令
        import subprocess

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            f"{project_name}.wsgi:app",
            "--host",
            host,
            "--port",
            str(port),
        ]

        if reload:
            cmd.append("--reload")

        click.echo(f"启动服务器: {' '.join(cmd)}")
        subprocess.run(cmd)
    except Exception as e:
        click.echo(f"启动服务器失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
