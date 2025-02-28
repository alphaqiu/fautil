# 基础框架

这是一个基于 FastAPI 和 SQLAlchemy 的 Web 应用框架，旨在简化企业级应用的开发。

## 特性

- 项目脚手架生成
- 数据库集成 (SQLAlchemy)
- 依赖注入
- 配置管理
- 事件系统
- JWT 认证
- 基于类的视图 (CBV)
- 异常处理
- 数据库自动事务
- Kafka 支持
- 中间件
- 通用工具
- Redis 缓存支持
- Minio 对象存储支持

## 安装

```bash
# 使用 pip 安装
pip install fautil

# 或者使用 Poetry 安装
poetry add fautil
```

## 快速开始

创建一个新项目：

```bash
# 创建新项目
fautil new my_project

# 进入项目目录
cd my_project

# 安装依赖
poetry install

# 启动开发服务器
poetry run uvicorn my_project.wsgi:app --reload
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
├── requirements.txt
├── wsgi.py
└── my_project/
    ├── __init__.py
    ├── common/
    │   └── utils.py
    ├── dao/
    │   └── hello.py
    ├── models/
    │   └── hello.py
    ├── rules/
    │   └── hello.py
    └── views/
        └── hello.py
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

更多详细信息，请参阅`GIT_CONFIG.md`和`.pre-commit-config.yaml`文件。

## 开发指南

查看 [文档](https://github.com/alphaqiu/fautil/docs) 获取更多信息。

## 许可证

MIT
