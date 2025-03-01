# 示例

本章节提供Fautil框架的使用示例，帮助开发者快速上手。

## 快速入门示例

`quickstart.py`文件展示了如何使用Fautil框架创建一个简单的API服务。

### 代码片段

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

## API服务完整示例

`api_demo.py`文件展示了一个完整的API服务示例，包括视图、模型、异常处理和中间件。

## 服务生命周期演示

`service_lifecycle_demo.py`文件展示了服务的启动和停止过程。

## 组件发现示例

`discovery_demo.py`文件展示了如何自动发现和注册组件。

更多示例代码，请参阅`examples`目录下的其他文件。
