"""
更新版本号脚本

此脚本使用setuptools-scm从git标签中获取版本号，
并更新pyproject.toml文件中的版本号。
同时也生成_version.py文件。
"""

import subprocess
import sys
from pathlib import Path

import toml


def get_git_version():
    """使用setuptools-scm从git标签获取版本号"""
    try:
        # 使用setuptools_scm API获取版本
        from setuptools_scm import get_version

        version = get_version(root=".", relative_to=__file__)
        return version
    except Exception as e:
        print(f"Error getting version from git: {e}")
        # 如果获取失败，使用git命令行获取最新标签
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                check=True,
            )
            version = result.stdout.strip()
            # 移除版本号前的"v"
            if version.startswith("v"):
                version = version[1:]
            return version
        except subprocess.CalledProcessError:
            print("Error getting version from git command. Using default version.")
            return "0.0.0.dev0"


def update_pyproject_toml(version):
    """更新pyproject.toml文件中的版本号"""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

    try:
        # 读取并解析TOML文件
        pyproject_data = toml.load(pyproject_path)

        # 更新版本号
        if "tool" in pyproject_data and "poetry" in pyproject_data["tool"]:
            pyproject_data["tool"]["poetry"]["version"] = version

        # 写回TOML文件
        with open(pyproject_path, "w", encoding="utf-8") as f:
            toml.dump(pyproject_data, f)

        print(f"Updated pyproject.toml with version: {version}")
        return True
    except Exception as e:
        print(f"Error updating pyproject.toml: {e}")
        return False


def generate_version_file(version):
    """生成_version.py文件"""
    version_file_path = Path(__file__).parent / "_version.py"

    try:
        with open(version_file_path, "w", encoding="utf-8") as f:
            f.write(
                f"""# 版本信息由setuptools-scm自动生成，请勿手动修改
__version__ = "{version}"
"""
            )
        print(f"Generated _version.py with version: {version}")
        return True
    except Exception as e:
        print(f"Error generating _version.py: {e}")
        return False


def main():
    """主函数"""
    # 获取版本号
    version = get_git_version()
    print(f"Current version from git: {version}")

    # 更新pyproject.toml
    updated_pyproject = update_pyproject_toml(version)

    # 生成_version.py
    generated_version_file = generate_version_file(version)

    if updated_pyproject and generated_version_file:
        print("Version update completed successfully.")
        return 0
    else:
        print("Version update failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
