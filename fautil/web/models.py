"""
API模型模块

定义API接口使用的通用模型，包括：
- API响应模型
- 分页数据模型
- 错误详情模型
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union, get_args

from pydantic import BaseModel, ConfigDict, Field, create_model

# 定义泛型类型变量
T = TypeVar("T")
DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    """错误详情模型"""

    field: str = Field(description="错误字段名")
    message: str = Field(description="错误信息")
    code: str = Field(description="错误码")


class ApiResponse(BaseModel, Generic[T]):
    """
    API响应基础模型

    所有API响应的基础模型，包括成功和错误状态。
    泛型参数T表示响应数据的类型。
    """

    model_config = ConfigDict(populate_by_name=True)

    success: bool = Field(default=True, description="请求是否成功")
    data: Optional[T] = Field(
        default=None, description="响应数据，仅在success=True时存在"
    )
    error: Optional[Dict[str, Any]] = Field(
        default=None, description="错误信息，仅在success=False时存在"
    )

    @classmethod
    def success_response(cls, data: Optional[T] = None) -> "ApiResponse[T]":
        """
        创建成功响应

        Args:
            data: 响应数据

        Returns:
            成功响应实例
        """
        return cls(success=True, data=data)

    @classmethod
    def error_response(
        cls,
        code: str,
        message: str,
        details: Optional[List[ErrorDetail]] = None,
        request_id: Optional[str] = None,
    ) -> "ApiResponse[T]":
        """
        创建错误响应

        Args:
            code: 错误码
            message: 错误消息
            details: 错误详情列表
            request_id: 请求ID

        Returns:
            错误响应实例
        """
        return cls(
            success=False,
            error=dict(
                code=code,
                message=message,
                details=details or [],
                request_id=request_id,
            ),
        )


class PaginatedData(BaseModel, Generic[DataT]):
    """
    分页数据模型

    用于返回分页查询结果。
    泛型参数DataT表示列表项的类型。
    """

    items: List[DataT] = Field(description="数据项列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    size: int = Field(description="每页大小")
    pages: int = Field(description="总页数")

    @classmethod
    def create(
        cls, items: List[DataT], total: int, page: int, size: int
    ) -> "PaginatedData[DataT]":
        """
        创建分页数据实例

        Args:
            items: 数据项列表
            total: 总记录数
            page: 当前页码
            size: 每页大小

        Returns:
            分页数据实例
        """
        pages = (total + size - 1) // size if size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
        )


class ErrorResponse(ApiResponse[None]):
    """
    错误响应模型

    专用于返回错误响应的模型。
    """

    success: bool = Field(default=False, description="请求是否成功")
    data: None = Field(default=None, description="响应数据")
    error: Dict[str, Any] = Field(description="错误信息")


def create_response_model(data_model: Type[BaseModel]) -> Type[ApiResponse]:
    """
    创建响应模型

    根据数据模型创建对应的响应模型。

    Args:
        data_model: 数据模型类

    Returns:
        创建的响应模型类
    """
    model_name = f"{data_model.__name__}Response"
    return create_model(
        model_name,
        __base__=ApiResponse[data_model],
    )


def create_paginated_response_model(
    data_model: Type[BaseModel],
) -> Type[ApiResponse]:
    """
    创建分页响应模型

    根据数据模型创建对应的分页响应模型。

    Args:
        data_model: 数据模型类

    Returns:
        创建的分页响应模型类
    """
    paginated_model = PaginatedData[data_model]
    model_name = f"{data_model.__name__}PaginatedResponse"
    return create_model(
        model_name,
        __base__=ApiResponse[paginated_model],
    )
