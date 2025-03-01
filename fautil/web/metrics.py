"""
服务指标收集模块

提供服务运行时指标的收集、存储和导出功能。
支持Prometheus格式指标导出。
"""

import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    Summary,
    multiprocess,
)
from prometheus_client.exposition import generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse
from starlette.types import ASGIApp


class MetricType(str, Enum):
    """指标类型枚举"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    指标中间件

    收集请求和响应的指标，包括：
    - 请求计数
    - 请求持续时间
    - 响应状态码计数
    """

    def __init__(
        self,
        app: ASGIApp,
        app_name: str = "fastapi",
        exclude_paths: Optional[Set[str]] = None,
        buckets: Optional[List[float]] = None,
    ):
        """
        初始化指标中间件

        Args:
            app: ASGI应用
            app_name: 应用名称（用于指标标签）
            exclude_paths: 排除指标收集的路径集合
            buckets: 请求持续时间直方图的桶定义
        """
        super().__init__(app)
        self.app_name = app_name
        self.exclude_paths = exclude_paths or {"/metrics", "/health"}
        self.buckets = buckets or [
            0.01,
            0.025,
            0.05,
            0.075,
            0.1,
            0.25,
            0.5,
            0.75,
            1.0,
            2.5,
            5.0,
            7.5,
            10.0,
            30.0,
            60.0,
            float("inf"),
        ]

        # 创建指标
        self.requests_total = Counter(
            f"{app_name}_requests_total",
            f"{app_name} total requests",
            ["method", "path", "app_name"],
        )

        self.responses_total = Counter(
            f"{app_name}_responses_total",
            f"{app_name} total responses",
            ["method", "path", "status_code", "app_name"],
        )

        self.requests_duration = Histogram(
            f"{app_name}_request_duration_seconds",
            f"{app_name} request duration in seconds",
            ["method", "path", "app_name"],
            buckets=self.buckets,
        )

        self.requests_in_progress = Gauge(
            f"{app_name}_requests_in_progress",
            f"{app_name} requests in progress",
            ["method", "path", "app_name"],
        )

        self.request_size = Histogram(
            f"{app_name}_request_size_bytes",
            f"{app_name} request size in bytes",
            ["method", "path", "app_name"],
            buckets=[
                100,
                1_000,
                10_000,
                100_000,
                1_000_000,
                float("inf"),
            ],
        )

        self.response_size = Histogram(
            f"{app_name}_response_size_bytes",
            f"{app_name} response size in bytes",
            ["method", "path", "app_name"],
            buckets=[
                100,
                1_000,
                10_000,
                100_000,
                1_000_000,
                float("inf"),
            ],
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 如果路径在排除列表中，直接处理请求
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # 提取标签
        method = request.method
        path = request.scope.get("path_params", {}).get("path", request.url.path)

        # 记录请求开始
        self.requests_total.labels(method=method, path=path, app_name=self.app_name).inc()

        # 增加处理中请求计数
        in_progress = self.requests_in_progress.labels(
            method=method, path=path, app_name=self.app_name
        )
        in_progress.inc()

        # 记录请求大小（如果可能）
        try:
            content_length = request.headers.get("content-length")
            if content_length:
                self.request_size.labels(method=method, path=path, app_name=self.app_name).observe(
                    int(content_length)
                )
        except Exception:
            pass

        # 记录开始时间
        start_time = time.time()

        try:
            # 处理请求
            response = await call_next(request)

            # 记录响应状态码
            self.responses_total.labels(
                method=method,
                path=path,
                status_code=response.status_code,
                app_name=self.app_name,
            ).inc()

            # 记录响应大小（如果可能）
            try:
                content_length = response.headers.get("content-length")
                if content_length:
                    self.response_size.labels(
                        method=method, path=path, app_name=self.app_name
                    ).observe(int(content_length))
            except Exception:
                pass

            return response
        except Exception as e:
            # 记录异常响应
            self.responses_total.labels(
                method=method, path=path, status_code=500, app_name=self.app_name
            ).inc()

            # 重新抛出异常，让其他异常处理器处理
            raise e
        finally:
            # 记录请求持续时间
            request_duration = time.time() - start_time
            self.requests_duration.labels(method=method, path=path, app_name=self.app_name).observe(
                request_duration
            )

            # 减少处理中请求计数
            in_progress.dec()


class MetricsManager:
    """
    指标管理器

    提供创建和管理指标的接口，包括：
    - 计数器
    - 仪表盘
    - 直方图
    - 概要图
    """

    def __init__(self, app_name: str = "app"):
        """
        初始化指标管理器

        Args:
            app_name: 应用名称（用于指标前缀）
        """
        self.app_name = app_name
        self.metrics: Dict[str, Any] = {}

    def create_counter(
        self, name: str, description: str, labels: Optional[List[str]] = None
    ) -> Counter:
        """
        创建计数器

        Args:
            name: 指标名称
            description: 指标描述
            labels: 标签列表

        Returns:
            创建的计数器
        """
        metric_name = f"{self.app_name}_{name}"
        counter = Counter(metric_name, description, labels or [])
        self.metrics[name] = counter
        return counter

    def create_gauge(
        self, name: str, description: str, labels: Optional[List[str]] = None
    ) -> Gauge:
        """
        创建仪表盘

        Args:
            name: 指标名称
            description: 指标描述
            labels: 标签列表

        Returns:
            创建的仪表盘
        """
        metric_name = f"{self.app_name}_{name}"
        gauge = Gauge(metric_name, description, labels or [])
        self.metrics[name] = gauge
        return gauge

    def create_histogram(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Histogram:
        """
        创建直方图

        Args:
            name: 指标名称
            description: 指标描述
            labels: 标签列表
            buckets: 直方图桶定义

        Returns:
            创建的直方图
        """
        metric_name = f"{self.app_name}_{name}"
        histogram = Histogram(metric_name, description, labels or [], buckets=buckets)
        self.metrics[name] = histogram
        return histogram

    def create_summary(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        quantiles: Optional[List[float]] = None,
    ) -> Summary:
        """
        创建概要图

        Args:
            name: 指标名称
            description: 指标描述
            labels: 标签列表
            quantiles: 分位数定义

        Returns:
            创建的概要图
        """
        metric_name = f"{self.app_name}_{name}"
        summary = Summary(metric_name, description, labels or [])
        self.metrics[name] = summary
        return summary

    def get_metric(self, name: str) -> Any:
        """
        获取指标

        Args:
            name: 指标名称

        Returns:
            指标对象

        Raises:
            KeyError: 如果指标不存在
        """
        if name not in self.metrics:
            raise KeyError(f"指标 '{name}' 不存在")
        return self.metrics[name]

    def inc_counter(
        self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        增加计数器值

        Args:
            name: 指标名称
            value: 增加值
            labels: 标签字典
        """
        counter = self.get_metric(name)
        if labels:
            counter.labels(**labels).inc(value)
        else:
            counter.inc(value)

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        设置仪表盘值

        Args:
            name: 指标名称
            value: 设置值
            labels: 标签字典
        """
        gauge = self.get_metric(name)
        if labels:
            gauge.labels(**labels).set(value)
        else:
            gauge.set(value)

    def observe_histogram(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        观察直方图值

        Args:
            name: 指标名称
            value: 观察值
            labels: 标签字典
        """
        histogram = self.get_metric(name)
        if labels:
            histogram.labels(**labels).observe(value)
        else:
            histogram.observe(value)

    def observe_summary(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        观察概要图值

        Args:
            name: 指标名称
            value: 观察值
            labels: 标签字典
        """
        summary = self.get_metric(name)
        if labels:
            summary.labels(**labels).observe(value)
        else:
            summary.observe(value)


async def metrics_endpoint() -> StarletteResponse:
    """
    指标导出端点

    返回Prometheus格式的指标数据。

    Returns:
        指标响应
    """
    content = generate_latest(REGISTRY)
    return StarletteResponse(
        content=content,
        media_type="text/plain",
    )


def setup_metrics(
    app: FastAPI,
    app_name: str,
    enable_middleware: bool = True,
    enable_endpoint: bool = True,
    endpoint_path: str = "/metrics",
    exclude_paths: Optional[Set[str]] = None,
    multiprocess_mode: bool = False,
) -> MetricsManager:
    """
    设置指标

    为FastAPI应用设置指标收集和导出。

    Args:
        app: FastAPI应用实例
        app_name: 应用名称
        enable_middleware: 是否启用指标中间件
        enable_endpoint: 是否启用指标导出端点
        endpoint_path: 指标导出端点路径
        exclude_paths: 排除指标收集的路径集合
        multiprocess_mode: 是否启用多进程模式

    Returns:
        指标管理器
    """
    # 创建指标管理器
    metrics_manager = MetricsManager(app_name)

    # 设置多进程模式
    if multiprocess_mode:
        multiprocess.MultiProcessCollector(REGISTRY)

    # 添加指标中间件
    if enable_middleware:
        app.add_middleware(
            MetricsMiddleware,
            app_name=app_name,
            exclude_paths=exclude_paths,
        )

    # 添加指标导出端点
    if enable_endpoint:
        app.add_route(endpoint_path, metrics_endpoint, methods=["GET"])

    return metrics_manager
