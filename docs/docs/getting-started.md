# 快速开始

本章节将指导您如何使用Fautil框架快速构建一个API服务。

## 安装

首先，确保您已安装Python 3.9或更高版本，并使用Poetry管理项目依赖。

```bash
# 安装Poetry
pip install poetry

# 安装项目依赖
poetry install
```

## 创建项目

使用Fautil框架创建一个新项目：

```bash
# 创建项目目录
mkdir my_fautil_project
cd my_fautil_project

# 初始化Poetry项目
poetry init

# 添加Fautil依赖
poetry add fautil
```

## 编写代码

在项目中创建一个简单的API服务：

```python
from fautil import APIService, APIView

class HelloWorldView(APIView):
    path = "/hello"

    async def get(self, request):
        return {"message": "Hello, World!"}

service = APIService()
service.register_view(HelloWorldView)

if __name__ == "__main__":
    service.start()
```

## 运行服务

使用以下命令启动服务：

```bash
poetry run python my_fautil_project.py
```

服务启动后，您可以在浏览器中访问`http://localhost:8000/hello`，查看API响应。
