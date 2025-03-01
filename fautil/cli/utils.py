"""
命令行工具工具函数模块

提供命令行工具使用的工具函数。
"""

from pathlib import Path
from typing import Dict, Optional

import toml
import yaml


def load_config(file_path: Path) -> Dict:
    """
    加载配置文件

    Args:
        file_path: 配置文件路径

    Returns:
        Dict: 配置字典
    """
    if not file_path.exists():
        return {}

    if file_path.suffix.lower() in (".yaml", ".yml"):
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    elif file_path.suffix.lower() == ".toml":
        with open(file_path, "r", encoding="utf-8") as f:
            return toml.load(f)
    else:
        raise ValueError(f"不支持的配置文件格式: {file_path.suffix}")


def get_project_name() -> Optional[str]:
    """
    获取项目名称

    从 pyproject.toml 文件中获取项目名称

    Returns:
        Optional[str]: 项目名称，如果未找到则返回 None
    """
    try:
        # 尝试从 pyproject.toml 获取项目名称
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            data = load_config(pyproject_path)

            # 从不同的配置部分获取项目名称
            project_name = None
            if "project" in data:
                project_name = data["project"].get("name")
            elif "tool" in data and "poetry" in data["tool"]:
                project_name = data["tool"]["poetry"].get("name")

            # 格式化项目名称
            if project_name:
                # 移除版本信息
                project_name = project_name.split("-")[0]
                # 转换为小写，并替换中划线为下划线
                project_name = project_name.lower().replace("-", "_")
                return project_name
    except Exception:
        pass

    return None


def snake_to_camel(snake_str: str) -> str:
    """
    将下划线命名转换为驼峰命名

    Args:
        snake_str: 下划线命名字符串

    Returns:
        str: 驼峰命名字符串
    """
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def snake_to_pascal(snake_str: str) -> str:
    """
    将下划线命名转换为帕斯卡命名

    Args:
        snake_str: 下划线命名字符串

    Returns:
        str: 帕斯卡命名字符串
    """
    return "".join(x.title() for x in snake_str.split("_"))
