#!/usr/bin/env python3
"""
API应用示例

展示fautil服务框架第三阶段功能的使用，包括：
- 统一响应格式
- 请求上下文和跟踪ID
- 异常处理
- 指标监控
- 视图自动发现
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Query
from injector import inject, singleton
from loguru import logger
from pydantic import BaseModel, Field

# 确保能导入fautil包
sys.path.insert(0, str(Path(__file__).parent.parent))

from fautil.service.api_service import APIService
from fautil.service.injector_manager import Module
from fautil.web.cbv import APIView
from fautil.web.context import RequestContext
from fautil.web.exception_handlers import (
    BadRequestException,
    NotFoundException,
    ValidationException,
)
from fautil.web.metrics import MetricsManager
from fautil.web.models import (
    PaginatedData,
    create_paginated_response_model,
    create_response_model,
)


# 数据模型
class Item(BaseModel):
    """示例项目模型"""

    id: int = Field(description="项目ID")
    name: str = Field(description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    price: float = Field(description="项目价格")
    tags: List[str] = Field(default_factory=list, description="项目标签")


# 生成响应模型
ItemResponse = create_response_model(Item)
ItemListResponse = create_paginated_response_model(Item)


# 服务
@singleton
class ItemService:
    """项目服务"""

    def __init__(self):
        """初始化项目服务"""
        # 模拟数据
        self.items = {
            1: Item(
                id=1,
                name="示例项目1",
                description="这是一个示例项目",
                price=100.0,
                tags=["标签1", "标签2"],
            ),
            2: Item(
                id=2,
                name="示例项目2",
                description="这是另一个示例项目",
                price=200.0,
                tags=["标签2", "标签3"],
            ),
            3: Item(id=3, name="示例项目3", price=300.0, tags=["标签1", "标签3"]),
        }
        self._next_id = 4

    async def get_item(self, item_id: int) -> Item:
        """
        获取项目

        Args:
            item_id: 项目ID

        Returns:
            项目

        Raises:
            NotFoundException: 如果项目不存在
        """
        if item_id not in self.items:
            logger.warning(
                f"项目不存在: {item_id} - 请求ID: {RequestContext.get_request_id()}"
            )
            raise NotFoundException(f"项目 {item_id} 不存在")

        logger.info(f"获取项目: {item_id} - 请求ID: {RequestContext.get_request_id()}")
        return self.items[item_id]

    async def list_items(
        self, page: int = 1, size: int = 10, tag: Optional[str] = None
    ) -> PaginatedData[Item]:
        """
        列出项目

        Args:
            page: 页码
            size: 页大小
            tag: 标签筛选

        Returns:
            分页项目列表
        """
        # 筛选项目
        filtered_items = list(self.items.values())
        if tag:
            filtered_items = [item for item in filtered_items if tag in item.tags]

        # 计算分页
        total = len(filtered_items)
        start = (page - 1) * size
        end = min(start + size, total)
        items = filtered_items[start:end]

        logger.info(
            f"列出项目: page={page}, size={size}, tag={tag}, total={total} - 请求ID: {RequestContext.get_request_id()}"
        )

        # 返回分页数据
        return PaginatedData.create(items, total, page, size)

    async def create_item(self, item: Item) -> Item:
        """
        创建项目

        Args:
            item: 项目

        Returns:
            创建的项目
        """
        # 验证数据
        if item.price < 0:
            raise ValidationException("价格不能为负数")

        # 设置ID
        item.id = self._next_id
        self._next_id += 1

        # 保存项目
        self.items[item.id] = item

        logger.info(f"创建项目: {item.id} - 请求ID: {RequestContext.get_request_id()}")

        return item

    async def update_item(self, item_id: int, item: Item) -> Item:
        """
        更新项目

        Args:
            item_id: 项目ID
            item: 项目

        Returns:
            更新后的项目

        Raises:
            NotFoundException: 如果项目不存在
        """
        # 检查项目是否存在
        if item_id not in self.items:
            raise NotFoundException(f"项目 {item_id} 不存在")

        # 验证数据
        if item.price < 0:
            raise ValidationException("价格不能为负数")

        # 保证ID一致
        item.id = item_id

        # 保存项目
        self.items[item_id] = item

        logger.info(f"更新项目: {item_id} - 请求ID: {RequestContext.get_request_id()}")

        return item

    async def delete_item(self, item_id: int) -> None:
        """
        删除项目

        Args:
            item_id: 项目ID

        Raises:
            NotFoundException: 如果项目不存在
        """
        # 检查项目是否存在
        if item_id not in self.items:
            raise NotFoundException(f"项目 {item_id} 不存在")

        # 删除项目
        del self.items[item_id]

        logger.info(f"删除项目: {item_id} - 请求ID: {RequestContext.get_request_id()}")


# 视图
class ItemView(APIView):
    """项目视图"""

    path = "/api/items"
    tags = ["项目"]

    @inject
    def __init__(self, item_service: ItemService, metrics: MetricsManager):
        """
        初始化项目视图

        Args:
            item_service: 项目服务
            metrics: 指标管理器
        """
        self.item_service = item_service
        self.metrics = metrics

        # 创建指标
        self.metrics.create_counter(
            "item_views_total", "项目视图访问次数", ["method", "path"]
        )

    @classmethod
    def register_routes(cls, app: FastAPI, view_instance: "ItemView") -> None:
        """
        注册路由

        Args:
            app: FastAPI应用
            view_instance: 视图实例
        """
        super().register_routes(app, view_instance)

        # 注册附加路由
        app.get(
            f"{cls.path}/search",
            response_model=ItemListResponse,
            tags=cls.tags,
            summary="搜索项目",
        )(view_instance.search_items)

    async def get(self, item_id: int) -> Item:
        """
        获取单个项目

        Args:
            item_id: 项目ID

        Returns:
            项目
        """
        # 记录指标
        self.metrics.inc_counter(
            "item_views_total",
            labels={"method": "get", "path": f"{self.path}/{item_id}"},
        )

        return await self.item_service.get_item(item_id)

    async def list(
        self,
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
        tag: Optional[str] = None,
    ) -> PaginatedData[Item]:
        """
        获取项目列表

        Args:
            page: 页码
            size: 页大小
            tag: 标签筛选

        Returns:
            分页项目列表
        """
        # 记录指标
        self.metrics.inc_counter(
            "item_views_total",
            labels={"method": "list", "path": self.path},
        )

        return await self.item_service.list_items(page, size, tag)

    async def search_items(
        self,
        q: str = Query(..., description="搜索关键词"),
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
    ) -> PaginatedData[Item]:
        """
        搜索项目

        Args:
            q: 搜索关键词
            page: 页码
            size: 页大小

        Returns:
            分页项目列表
        """
        # 记录指标
        self.metrics.inc_counter(
            "item_views_total",
            labels={"method": "search", "path": f"{self.path}/search"},
        )

        # 筛选项目
        filtered_items = []
        for item in self.item_service.items.values():
            if (
                q.lower() in item.name.lower()
                or (item.description and q.lower() in item.description.lower())
                or any(q.lower() in tag.lower() for tag in item.tags)
            ):
                filtered_items.append(item)

        # 计算分页
        total = len(filtered_items)
        start = (page - 1) * size
        end = min(start + size, total)
        items = filtered_items[start:end]

        logger.info(
            f"搜索项目: q={q}, page={page}, size={size}, total={total} - 请求ID: {RequestContext.get_request_id()}"
        )

        # 返回分页数据
        return PaginatedData.create(items, total, page, size)

    async def post(self, item: Item) -> Item:
        """
        创建项目

        Args:
            item: 项目数据

        Returns:
            创建的项目
        """
        # 记录指标
        self.metrics.inc_counter(
            "item_views_total",
            labels={"method": "post", "path": self.path},
        )

        return await self.item_service.create_item(item)

    async def put(self, item_id: int, item: Item) -> Item:
        """
        更新项目

        Args:
            item_id: 项目ID
            item: 项目数据

        Returns:
            更新后的项目
        """
        # 记录指标
        self.metrics.inc_counter(
            "item_views_total",
            labels={"method": "put", "path": f"{self.path}/{item_id}"},
        )

        return await self.item_service.update_item(item_id, item)

    async def delete(self, item_id: int) -> Dict[str, Any]:
        """
        删除项目

        Args:
            item_id: 项目ID

        Returns:
            删除结果
        """
        # 记录指标
        self.metrics.inc_counter(
            "item_views_total",
            labels={"method": "delete", "path": f"{self.path}/{item_id}"},
        )

        await self.item_service.delete_item(item_id)
        return {"message": f"项目 {item_id} 已删除"}


# 依赖注入模块
class DemoModule(Module):
    """示例模块"""

    def configure(self, binder):
        """配置绑定"""
        # 服务绑定
        binder.bind(ItemService, to=ItemService, scope=singleton)


async def main():
    """主函数"""
    # 创建API服务
    service = APIService(
        app_name="demo-api",
        version="1.0.0",
        title="示例API",
        description="展示fautil服务框架第三阶段功能的API示例",
        modules=[DemoModule()],
        discovery_packages=["__main__"],
        enable_metrics=True,
        enable_request_context=True,
        enable_request_logging=True,
    )

    try:
        # 启动服务
        await service.start()
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
