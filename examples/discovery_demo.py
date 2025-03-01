#!/usr/bin/env python3
"""
组件自动发现示例

演示使用组件自动发现和依赖注入功能启动服务。
"""

# 导入标准库
import asyncio
import os
import sys
from pathlib import Path

# 导入第三方库
from injector import Module
from loguru import logger


def setup_path_and_import():
    """设置路径并导入项目模块"""
    # 添加项目根目录到路径
    ROOT_DIR = Path(__file__).parent.parent
    sys.path.insert(0, str(ROOT_DIR))

    # 导入项目模块并返回
    from fautil.service import APIService, ServiceManager

    return APIService, ServiceManager


# 导入项目模块
APIService, ServiceManager = setup_path_and_import()


class DemoModule(Module):
    """演示模块"""

    def configure(self, binder):
        """配置绑定"""
        # 这里可以添加自定义的服务绑定
        pass


async def main():
    """
    主函数

    创建并启动服务，演示组件自动发现和依赖注入功能。
    """
    # 初始化服务
    service = APIService(
        app_name="Discovery Demo",
        modules=[DemoModule()],
        discovery_packages=[
            "fautil.service",  # 扫描服务模块
        ],
    )

    # 启动服务
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))

    logger.info(f"启动服务: http://{host}:{port}")

    await service.start(host=host, port=port)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务已停止")
    except Exception as e:
        logger.exception(f"服务异常: {str(e)}")
        sys.exit(1)
