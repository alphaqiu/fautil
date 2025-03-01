#!/usr/bin/env python3
"""
API服务示例

展示如何使用APIService类启动和管理FastAPI应用。
"""

import asyncio
import sys
from pathlib import Path

# 将项目根目录添加到模块搜索路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from injector import Binder, Module, singleton

from fautil.service import APIService
from fautil.web.cbv import APIView, api_route


# 定义示例视图
class ExampleView(APIView):
    """示例视图"""

    path = "/examples"
    tags = ["示例"]

    @api_route("", methods=["GET"])
    async def get_examples(self) -> dict:
        """获取示例数据"""
        return {"message": "这是一个示例"}

    @api_route("/{example_id}", methods=["GET"])
    async def get_example(self, example_id: int) -> dict:
        """获取指定示例"""
        return {"example_id": example_id, "message": f"示例 {example_id}"}


# 定义自定义模块
class AppModule(Module):
    """应用模块"""

    def configure(self, binder: Binder) -> None:
        """配置依赖注入绑定"""
        # 这里可以绑定自定义服务
        pass


async def main():
    """主函数"""
    # 创建API服务
    service = APIService(
        app_name="Example API",
        modules=[AppModule()],
    )

    # 创建应用并注册视图
    app = service._create_app()
    service.register_view(ExampleView)

    try:
        # 启动服务
        await service.start(host="127.0.0.1", port=8000)
    except KeyboardInterrupt:
        print("\n接收到键盘中断，正在停止服务...")
    finally:
        # 确保服务停止
        await service.stop()


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
