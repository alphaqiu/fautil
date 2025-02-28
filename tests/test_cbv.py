from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Query
from fastapi.testclient import TestClient
from injector import Binder, Injector, Module, singleton
from pydantic import BaseModel

from fautil.web.cbv import APIView, api_route
from fautil.web.middleware import RequestLoggingMiddleware


# 定义数据模型
class ItemRequest(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tags: List[str] = []


class ItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    tags: List[str] = []


# 定义服务类用于依赖注入
class ItemService:
    def __init__(self):
        self.items: Dict[int, Dict[str, Any]] = {}
        self.counter = 0

    def get_items(self, skip: int = 0, limit: int = 10):
        return list(self.items.values())[skip : skip + limit]

    def get_item(self, item_id: int):
        return self.items.get(item_id)

    def create_item(self, item: ItemRequest):
        self.counter += 1
        item_dict = item.model_dump()
        item_dict["id"] = self.counter
        self.items[self.counter] = item_dict
        return item_dict


# 配置依赖注入
class AppModule(Module):
    def configure(self, binder: Binder) -> None:
        # 使用单例模式绑定ItemService
        binder.bind(ItemService, to=ItemService(), scope=singleton)


# 创建依赖注入器
injector = Injector([AppModule()])


# 创建依赖注入函数
def get_item_service() -> ItemService:
    return injector.get(ItemService)


# 定义基于类的视图
class ItemView(APIView):
    path = "/items"
    tags = ["items"]

    @api_route("", response_model=List[ItemResponse])
    async def get_items(
        self,
        service: ItemService = Depends(get_item_service),
        skip: int = Query(0, ge=0),
        limit: int = Query(10, ge=1, le=100),
    ):
        """获取所有商品"""
        return service.get_items(skip, limit)

    @api_route("/{item_id}", response_model=ItemResponse)
    async def get_item(
        self, item_id: int, service: ItemService = Depends(get_item_service)
    ):
        """获取单个商品"""
        item = service.get_item(item_id)
        if not item:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Item not found")
        return item

    @api_route("", methods=["POST"], response_model=ItemResponse, status_code=201)
    async def create_item(
        self, item: ItemRequest, service: ItemService = Depends(get_item_service)
    ):
        """创建新商品"""
        return service.create_item(item)


# 创建FastAPI应用
def create_app():
    app = FastAPI(title="Item API", description="使用CBV和依赖注入的API示例")

    # 添加中间件
    app.add_middleware(RequestLoggingMiddleware)

    # 注册路由
    ItemView.setup(app)

    return app


# 创建测试客户端
app = create_app()
client = TestClient(app)


# 测试用例
def test_create_item():
    """测试创建商品"""
    response = client.post(
        "/items",
        json={
            "name": "测试商品",
            "description": "这是一个测试商品",
            "price": 99.9,
            "tags": ["test", "sample"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "测试商品"
    assert data["price"] == 99.9


def test_get_items():
    """测试获取商品列表"""
    # 先创建一个商品
    client.post("/items", json={"name": "商品2", "price": 199.9, "tags": ["premium"]})

    response = client.get("/items")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert any(item["name"] == "商品2" for item in data)


def test_get_item():
    """测试获取单个商品"""
    response = client.get("/items/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "测试商品"


def test_get_nonexistent_item():
    """测试获取不存在的商品"""
    response = client.get("/items/999")
    assert response.status_code == 404


# if __name__ == "__main__":
#     # 使用TestClient模拟服务端而不是启动实际服务器
#     print("模拟API请求...")

#     # 创建一个商品
#     response = client.post(
#         "/items", json={"name": "示例商品", "price": 88.8, "description": "测试用例"}
#     )
#     print(f"POST /items 状态码: {response.status_code}")
#     print(f"响应数据: {response.json()}")

#     # 获取商品列表
#     response = client.get("/items")
#     print(f"GET /items 状态码: {response.status_code}")
#     print(f"响应数据: {response.json()}")

#     # 获取单个商品
#     response = client.get("/items/1")
#     print(f"GET /items/1 状态码: {response.status_code}")
#     print(f"响应数据: {response.json()}")

#     # 测试获取不存在的商品
#     response = client.get("/items/999")
#     print(f"GET /items/999 状态码: {response.status_code}")
#     print(f"响应数据: {response.json()}")

#     print("测试完成！")
