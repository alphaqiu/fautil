"""
服务核心视图模块

包含服务基础视图，如健康检查、状态监控等。
"""

from typing import Any, Dict

from fastapi import HTTPException
from injector import inject

from fautil.service.service_manager import ServiceManager
from fautil.web.cbv import APIView, api_route


class HealthCheckView(APIView):
    """
    健康检查视图

    提供服务健康状态检查接口，包括整体状态和各组件状态。
    """

    path = "/api/system"
    tags = ["系统"]

    @inject
    def __init__(self, service_manager: ServiceManager):
        """
        初始化健康检查视图

        Args:
            service_manager: 服务管理器
        """
        self.service_manager = service_manager

    @api_route("/health", summary="健康状态检查")
    async def health_check(self) -> Dict[str, Any]:
        """
        获取服务健康状态

        返回服务整体状态和各组件的详细状态。

        Returns:
            健康状态信息
        """
        return self.service_manager.get_health_status()

    @api_route("/status", summary="服务状态检查")
    async def status_check(self) -> Dict[str, Any]:
        """
        获取服务运行状态

        返回服务当前运行状态和版本信息。

        Returns:
            服务状态信息

        Raises:
            HTTPException: 如果服务状态不正常
        """
        health_status = self.service_manager.get_health_status()

        # 检查状态
        if health_status["status"] != "ok":
            raise HTTPException(
                status_code=503,
                detail="服务状态异常",
            )

        return {
            "status": self.service_manager.status,
            "version": health_status["version"],
            "components": len(health_status.get("components", {})),
        }
