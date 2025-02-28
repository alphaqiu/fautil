# 项目打包指南

## 前置条件

- Python >= 3.9
- Poetry >= 1.7.0

## 测试

首先运行测试，确保项目能够正常工作：

```bash
poetry run pytest
```

本项目使用 `setuptools-scm` 进行版本管理，版本号由 Git 标签（tag）决定。同时支持使用 Poetry 和 Twine 进行打包和发布。

## 版本管理

本项目的版本遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/) 规范，版本号格式为：`主版本号.次版本号.修订号`，例如 `1.0.0`。

版本号由 Git 标签控制，当在 Git 仓库中打上新标签时，项目的版本号会自动更新。

### 版本同步

项目使用了自定义脚本 `fautil/update_version.py` 来实现版本号的同步。此脚本从 Git 标签获取版本号，并更新到：

```powershell
poetry run python -m fautil.update_version
```

或者使用定义在 `.cursor/.cursorrules` 中的命令：

```powershell
cursor run sync_version
```

## 打包和发布

### 使用 Poetry

Poetry 是一个 Python 依赖管理和打包工具，本项目主要使用 Poetry 进行依赖管理和打包。

#### 构建

```powershell
# 使用 Poetry 构建
poetry build

# 或者使用定义在 .cursor/.cursorrules 中的命令
cursor run build_package

# 构建前先同步版本
cursor run build_with_git_version
```

构建后的文件位于 `dist/` 目录下。

#### 发布

```powershell
# 使用 Poetry 发布到 PyPI
poetry publish

# 或者使用定义在 .cursor/.cursorrules 中的命令
cursor run publish_package
```

### 使用 Twine

Twine 是一个用于发布 Python 包到 PyPI 的工具。

#### 构建

本项目集成了 `build` 包，可以使用以下命令构建：

```powershell
# 使用 build 包构建
poetry run python -m build

# 或者使用定义在 .cursor/.cursorrules 中的命令
cursor run build_package_setuptools
```

#### 发布

```powershell
# 使用 Twine 发布到 PyPI
poetry run twine upload dist/*

# 或者使用定义在 .cursor/.cursorrules 中的命令
cursor run publish_with_twine
```

## Git 标签与版本

### 创建新版本

要创建新版本，可以使用以下命令：

```powershell
# 创建标签
git tag -a v1.0.0 -m "Release 1.0.0"

# 或者使用定义在 .cursor/.cursorrules 中的命令创建与当前版本匹配的标签
cursor run create_version_tag

# 推送标签到远程仓库
git push origin v1.0.0
```

创建新标签后，可以通过 `sync_version` 命令更新项目中的版本号。

## 常见问题

### 版本号不一致

如果你发现项目的版本号与 Git 标签不一致，可以运行 `sync_version` 命令进行同步。

### 没有 Git 标签

如果仓库中没有 Git 标签，项目会使用默认版本号 `0.0.0.dev0`。你需要创建一个有效的 Git 标签来设置正确的版本号。 