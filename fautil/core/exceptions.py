"""
异常处理模块

定义应用中使用的自定义异常类，以及异常处理器。
"""

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """应用基础异常类"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化异常

        Args:
            code: 错误代码
            message: 错误消息
            status_code: HTTP状态码
            details: 错误详情
        """
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    """资源不存在异常"""

    def __init__(
        self,
        message: str = "资源不存在",
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            details: 错误详情
        """
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ValidationError(AppException):
    """参数验证错误异常"""

    def __init__(
        self,
        message: str = "参数验证错误",
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            details: 错误详情
        """
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class UnauthorizedError(AppException):
    """未授权异常"""

    def __init__(
        self,
        message: str = "未授权访问",
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            details: 错误详情
        """
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class ForbiddenError(AppException):
    """禁止访问异常"""

    def __init__(
        self,
        message: str = "禁止访问",
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            details: 错误详情
        """
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ServerError(AppException):
    """服务器内部错误异常"""

    def __init__(
        self,
        message: str = "服务器内部错误",
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            details: 错误详情
        """
        super().__init__(
            code="SERVER_ERROR",
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    设置异常处理器

    Args:
        app: FastAPI应用实例
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """
        处理应用异常

        Args:
            request: 请求对象
            exc: 异常对象

        Returns:
            JSONResponse: JSON响应
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        处理未捕获的异常

        Args:
            request: 请求对象
            exc: 异常对象

        Returns:
            JSONResponse: JSON响应
        """
        logger.exception("未捕获的异常")

        # 构造500错误响应
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "SERVER_ERROR",
                "message": "服务器内部错误",
                "details": {"error": str(exc)},
            },
        )
