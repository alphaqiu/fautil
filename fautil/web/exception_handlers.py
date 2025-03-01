"""
异常处理器模块

提供统一的异常处理逻辑，将各种异常转换为标准的API响应格式。
支持自定义异常类型和HTTP状态码映射。
"""

import logging
import traceback
from typing import List, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from fautil.web.context import RequestContext
from fautil.web.models import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class APIException(Exception):
    """
    API异常基类

    所有自定义API异常应继承此类。
    提供统一的异常码、消息和细节信息。
    """

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_ERROR",
        message: str = "服务器内部错误",
        details: Optional[List[ErrorDetail]] = None,
    ):
        """
        初始化API异常

        Args:
            status_code: HTTP状态码
            code: 错误码
            message: 错误消息
            details: 错误详情列表
        """
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        super().__init__(self.message)


class BadRequestException(APIException):
    """请求参数错误异常"""

    def __init__(
        self,
        message: str = "请求参数错误",
        details: Optional[List[ErrorDetail]] = None,
        code: str = "BAD_REQUEST",
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=code,
            message=message,
            details=details,
        )


class NotFoundException(APIException):
    """资源不存在异常"""

    def __init__(
        self,
        message: str = "请求的资源不存在",
        details: Optional[List[ErrorDetail]] = None,
        code: str = "NOT_FOUND",
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code=code,
            message=message,
            details=details,
        )


class UnauthorizedException(APIException):
    """未授权异常"""

    def __init__(
        self,
        message: str = "请求未授权",
        details: Optional[List[ErrorDetail]] = None,
        code: str = "UNAUTHORIZED",
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=code,
            message=message,
            details=details,
        )


class ForbiddenException(APIException):
    """禁止访问异常"""

    def __init__(
        self,
        message: str = "禁止访问请求的资源",
        details: Optional[List[ErrorDetail]] = None,
        code: str = "FORBIDDEN",
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=code,
            message=message,
            details=details,
        )


class InternalServerErrorException(APIException):
    """服务器内部错误异常"""

    def __init__(
        self,
        message: str = "服务器内部错误",
        details: Optional[List[ErrorDetail]] = None,
        code: str = "INTERNAL_SERVER_ERROR",
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=code,
            message=message,
            details=details,
        )


class ValidationException(BadRequestException):
    """数据验证错误异常"""

    def __init__(
        self,
        message: str = "数据验证错误",
        details: Optional[List[ErrorDetail]] = None,
    ):
        super().__init__(message=message, details=details, code="VALIDATION_ERROR")


class ServiceUnavailableException(APIException):
    """服务不可用异常"""

    def __init__(
        self,
        message: str = "服务暂时不可用",
        details: Optional[List[ErrorDetail]] = None,
        code: str = "SERVICE_UNAVAILABLE",
    ):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=code,
            message=message,
            details=details,
        )


class ConflictException(APIException):
    """资源冲突异常"""

    def __init__(
        self,
        message: str = "资源冲突",
        details: Optional[List[ErrorDetail]] = None,
        code: str = "CONFLICT",
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code=code,
            message=message,
            details=details,
        )


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """
    API异常处理器

    将APIException及其子类转换为标准的错误响应格式。

    Args:
        request: 请求对象
        exc: API异常

    Returns:
        标准格式的JSON错误响应
    """
    # 获取请求ID
    request_id = RequestContext.get_request_id()

    # 记录错误日志
    logger.error(
        f"API异常: {exc.code} - {exc.message} - 请求ID: {request_id}",
        exc_info=True,
    )

    # 创建错误响应
    error_response = ErrorResponse(
        success=False,
        error=dict(
            code=exc.code,
            message=exc.message,
            details=exc.details or [],
            request_id=request_id,
        ),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    请求验证异常处理器

    将FastAPI的RequestValidationError转换为标准的错误响应格式。

    Args:
        request: 请求对象
        exc: 验证异常

    Returns:
        标准格式的JSON错误响应
    """
    # 获取请求ID
    request_id = RequestContext.get_request_id()

    # 记录错误日志
    logger.error(
        f"请求验证错误 - 请求ID: {request_id}",
        exc_info=True,
    )

    # 从验证错误中提取错误详情
    details = []
    for error in exc.errors():
        field = ".".join([str(loc) for loc in error.get("loc", []) if loc != "body"])
        details.append(
            ErrorDetail(
                field=field,
                message=error.get("msg", "验证错误"),
                code=error.get("type", "validation_error"),
            )
        )

    # 创建错误响应
    error_response = ErrorResponse(
        success=False,
        error=dict(
            code="VALIDATION_ERROR",
            message="请求参数验证失败",
            details=details,
            request_id=request_id,
        ),
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.dict(),
    )


async def pydantic_validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """
    Pydantic验证异常处理器

    将Pydantic的ValidationError转换为标准的错误响应格式。

    Args:
        request: 请求对象
        exc: 验证异常

    Returns:
        标准格式的JSON错误响应
    """
    # 获取请求ID
    request_id = RequestContext.get_request_id()

    # 记录错误日志
    logger.error(
        f"Pydantic验证错误 - 请求ID: {request_id}",
        exc_info=True,
    )

    # 从验证错误中提取错误详情
    details = []
    for error in exc.errors():
        field = ".".join([str(loc) for loc in error.get("loc", [])])
        details.append(
            ErrorDetail(
                field=field,
                message=error.get("msg", "验证错误"),
                code=error.get("type", "validation_error"),
            )
        )

    # 创建错误响应
    error_response = ErrorResponse(
        success=False,
        error=dict(
            code="VALIDATION_ERROR",
            message="数据验证失败",
            details=details,
            request_id=request_id,
        ),
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.dict(),
    )


async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """
    SQLAlchemy异常处理器

    将SQLAlchemy异常转换为标准的错误响应格式。

    Args:
        request: 请求对象
        exc: SQLAlchemy异常

    Returns:
        标准格式的JSON错误响应
    """
    # 获取请求ID
    request_id = RequestContext.get_request_id()

    # 记录错误日志
    logger.error(
        f"数据库错误 - 请求ID: {request_id}",
        exc_info=True,
    )

    # 创建错误响应
    error_response = ErrorResponse(
        success=False,
        error=dict(
            code="DATABASE_ERROR",
            message="数据库操作失败",
            details=[],
            request_id=request_id,
        ),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.dict(),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    通用异常处理器

    将未处理的异常转换为标准的错误响应格式。

    Args:
        request: 请求对象
        exc: 异常对象

    Returns:
        标准格式的JSON错误响应
    """
    # 获取请求ID
    request_id = RequestContext.get_request_id()

    # 记录错误日志
    logger.error(
        f"未处理的异常: {str(exc)} - 请求ID: {request_id}",
        exc_info=True,
    )

    # 获取堆栈跟踪信息（仅在开发环境下包含）
    traceback_str = traceback.format_exc()
    logger.debug(f"异常堆栈: {traceback_str}")

    # 创建错误响应
    error_response = ErrorResponse(
        success=False,
        error=dict(
            code="INTERNAL_ERROR",
            message="服务器内部错误",
            details=[],
            request_id=request_id,
        ),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.dict(),
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    设置异常处理器

    为FastAPI应用配置和添加异常处理器。

    Args:
        app: FastAPI应用实例
    """
    # 注册API异常处理器
    app.add_exception_handler(APIException, api_exception_handler)

    # 注册FastAPI验证异常处理器
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # 注册Pydantic验证异常处理器
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)

    # 注册SQLAlchemy异常处理器
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)

    # 注册通用异常处理器（必须最后注册）
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("异常处理器设置完成")
