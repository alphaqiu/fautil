"""
关闭管理模块

提供服务的分阶段优雅关闭功能，支持按组件类型和优先级排序的关闭顺序。
"""

import asyncio
import os
import signal
import time
from enum import Enum
from typing import Dict, Optional

from injector import inject, singleton
from loguru import logger

from fautil.service.http_server_manager import HTTPServerManager
from fautil.service.lifecycle_manager import ComponentType, LifecycleEventType, LifecycleManager


class ShutdownPhase(str, Enum):
    """关闭阶段"""

    NOT_STARTED = "not_started"  # 未开始关闭
    STARTING = "starting"  # 开始关闭
    API_STOPPING = "api_stopping"  # API服务关闭中
    SERVICES_STOPPING = "services_stopping"  # 服务关闭中
    CLEANUP = "cleanup"  # 清理资源
    COMPLETED = "completed"  # 关闭完成
    FAILED = "failed"  # 关闭失败
    CANCELLED = "cancelled"  # 取消关闭


class ShutdownReason(str, Enum):
    """关闭原因枚举"""

    SIGNAL = "signal"  # 信号触发
    API_CALL = "api_call"  # API调用
    EXCEPTION = "exception"  # 异常
    MANUAL = "manual"  # 手动调用
    TIMEOUT = "timeout"  # 超时
    OTHER = "other"  # 其他原因


@singleton
class ShutdownManager:
    """
    关闭管理器

    提供服务的分阶段优雅关闭功能，支持按组件类型和优先级排序的关闭顺序。
    """

    @inject
    def __init__(
        self,
        lifecycle_manager: LifecycleManager,
        http_server_manager: Optional[HTTPServerManager] = None,
    ):
        """
        初始化关闭管理器

        Args:
            lifecycle_manager: 生命周期事件管理器
            http_server_manager: HTTP服务器管理器（可选）
        """
        self.lifecycle_manager = lifecycle_manager
        self.http_server_manager = http_server_manager

        # 关闭状态
        self._phase = ShutdownPhase.NOT_STARTED
        self._shutdown_reason: Optional[ShutdownReason] = None
        self._shutdown_message: Optional[str] = None
        self._shutdown_start_time: Optional[float] = None
        self._shutdown_end_time: Optional[float] = None

        # 关闭控制
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False
        self._shutdown_complete = asyncio.Event()  # 新增：关闭完成事件

        # 关闭配置
        self._timeout = 60  # 默认超时时间（秒）
        self._force_exit = False  # 默认不强制退出，改为False
        self._exit_code = 0  # 默认退出码
        self._wait_api_requests = True  # 默认等待API请求完成
        self._api_request_timeout = 30  # 默认API请求等待超时时间（秒）

        # 阶段超时配置
        self._phase_timeouts = {
            ShutdownPhase.API_STOPPING: 30,  # API关闭超时时间（秒）
            ShutdownPhase.SERVICES_STOPPING: 20,  # 上层服务关闭超时时间（秒）
            ShutdownPhase.CLEANUP: 10,  # 清理资源超时时间（秒）
        }

        # 组件映射
        self._component_phase_mapping = {
            # API相关组件在第一阶段关闭
            ComponentType.API: ShutdownPhase.API_STOPPING,
            # 上层服务在第二阶段关闭
            ComponentType.SCHEDULER: ShutdownPhase.SERVICES_STOPPING,
            ComponentType.QUEUE: ShutdownPhase.SERVICES_STOPPING,
            ComponentType.OTHER: ShutdownPhase.SERVICES_STOPPING,
            # 基础设施在清理阶段关闭
            ComponentType.CACHE: ShutdownPhase.CLEANUP,
            ComponentType.STORAGE: ShutdownPhase.CLEANUP,
            ComponentType.DATABASE: ShutdownPhase.CLEANUP,
            ComponentType.CORE: ShutdownPhase.CLEANUP,
        }

        # 关闭任务
        self._shutdown_task = None

    @property
    def is_shutting_down(self) -> bool:
        """是否正在关闭"""
        return self._is_shutting_down

    @property
    def phase(self) -> ShutdownPhase:
        """当前关闭阶段"""
        return self._phase

    @property
    def reason(self) -> Optional[ShutdownReason]:
        """关闭原因"""
        return self._shutdown_reason

    @property
    def message(self) -> Optional[str]:
        """关闭消息"""
        return self._shutdown_message

    @property
    def shutdown_time(self) -> Optional[float]:
        """关闭耗时（秒）"""
        if self._shutdown_start_time is None:
            return None

        end_time = self._shutdown_end_time or time.time()
        return end_time - self._shutdown_start_time

    def configure(
        self,
        timeout: Optional[int] = None,
        force_exit: Optional[bool] = None,
        exit_code: Optional[int] = None,
        wait_api_requests: Optional[bool] = None,
        api_request_timeout: Optional[int] = None,
        phase_timeouts: Optional[Dict[ShutdownPhase, int]] = None,
    ) -> None:
        """
        配置关闭参数

        Args:
            timeout: 总超时时间（秒）
            force_exit: 是否强制退出进程
            exit_code: 退出码
            wait_api_requests: 是否等待API请求完成
            api_request_timeout: API请求等待超时时间（秒）
            phase_timeouts: 阶段超时配置
        """
        if timeout is not None:
            self._timeout = timeout

        if force_exit is not None:
            self._force_exit = force_exit

        if exit_code is not None:
            self._exit_code = exit_code

        if wait_api_requests is not None:
            self._wait_api_requests = wait_api_requests

        if api_request_timeout is not None:
            self._api_request_timeout = api_request_timeout

        if phase_timeouts:
            self._phase_timeouts.update(phase_timeouts)

    def register_signal_handlers(self) -> None:
        """
        注册信号处理器

        注册SIGINT和SIGTERM信号处理器，用于优雅关闭服务。
        """
        try:
            # 获取当前事件循环
            loop = asyncio.get_event_loop()

            # 注册SIGINT处理器（Ctrl+C）
            loop.add_signal_handler(
                signal.SIGINT,
                lambda: self.trigger_shutdown(
                    reason=ShutdownReason.SIGNAL, message="收到SIGINT信号"
                ),
            )

            # 注册SIGTERM处理器（终止信号）
            loop.add_signal_handler(
                signal.SIGTERM,
                lambda: self.trigger_shutdown(
                    reason=ShutdownReason.SIGNAL, message="收到SIGTERM信号"
                ),
            )

            logger.debug("已使用事件循环方式注册信号处理器")
        except (NotImplementedError, RuntimeError) as e:
            # 在不支持add_signal_handler的平台上使用signal模块
            logger.warning(f"无法使用事件循环注册信号处理器: {str(e)}")
            logger.warning("无法注册信号处理器，服务将无法响应中断信号")

    def trigger_shutdown(
        self, reason: ShutdownReason = ShutdownReason.MANUAL, message: str = None
    ) -> None:
        """
        触发服务关闭

        Args:
            reason: 关闭原因
            message: 关闭消息
        """
        # 如果已经在关闭中，直接返回
        if self._is_shutting_down:
            logger.warning("服务已经在关闭中，忽略重复的关闭请求")
            return

        # 记录关闭原因
        logger.info(f"正在触发服务关闭: 原因={reason}, 消息={message}")

        # 创建关闭任务并保存引用
        self._shutdown_task = asyncio.create_task(self._graceful_shutdown(reason, message))

    async def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        等待关闭完成

        Args:
            timeout: 等待超时时间（秒），None表示无限等待

        Returns:
            是否在超时前完成关闭
        """
        if not self._is_shutting_down:
            return True

        try:
            await asyncio.wait_for(self._shutdown_complete.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def _graceful_shutdown(self, reason: ShutdownReason, message: str = None) -> None:
        """
        执行优雅关闭流程

        Args:
            reason: 关闭原因
            message: 关闭消息
        """
        # 如果已经在关闭中，直接返回
        if self._is_shutting_down:
            logger.warning("服务已经在关闭中，忽略重复的关闭请求")
            return

        # 设置关闭标志
        self._is_shutting_down = True
        self._shutdown_reason = reason
        self._shutdown_message = message or "未指定关闭原因"

        # 记录开始时间
        self._shutdown_start_time = time.time()

        # 设置当前关闭阶段
        self._phase = ShutdownPhase.STARTING

        try:
            # 执行API停止阶段
            await self._execute_phase(ShutdownPhase.API_STOPPING)

            # 执行服务停止阶段
            await self._execute_phase(ShutdownPhase.SERVICES_STOPPING)

            # 执行资源清理阶段
            await self._execute_phase(ShutdownPhase.CLEANUP)

            # 设置完成状态
            self._phase = ShutdownPhase.COMPLETED
            logger.info(
                f"服务关闭完成，原因: {self._shutdown_reason}, "
                f"耗时: {time.time() - self._shutdown_start_time:.2f}秒"
            )

            # 如果需要退出进程
            if self._force_exit:
                logger.info("正在退出进程...")
                # 使用os._exit而不是sys.exit，确保不会触发更多的清理操作
                os._exit(0)

        except asyncio.CancelledError:
            logger.warning("关闭任务被取消")
            self._phase = ShutdownPhase.CANCELLED
            raise
        except Exception as e:
            logger.error(f"服务关闭过程中出错: {str(e)}")
            self._phase = ShutdownPhase.FAILED
            logger.warning(
                f"服务关闭异常，状态: {self._phase}, "
                f"耗时: {time.time() - self._shutdown_start_time:.2f}秒"
            )

            # 如果需要退出进程，即使出错也要退出
            if self._force_exit:
                logger.info("尽管出错，仍然退出进程...")
                os._exit(1)

            # 重新抛出异常
            raise

    async def _execute_shutdown_phases(self) -> None:
        """
        执行分阶段关闭流程
        """
        # 1. 停止API服务
        await self._execute_phase(ShutdownPhase.API_STOPPING)

        # 2. 停止上层服务
        await self._execute_phase(ShutdownPhase.SERVICES_STOPPING)

        # 3. 停止基础设施
        await self._execute_phase(ShutdownPhase.CLEANUP)

        # 标记为完成
        self._phase = ShutdownPhase.COMPLETED
        logger.info("服务关闭完成")

    async def _execute_phase(self, phase: ShutdownPhase) -> None:
        """
        执行指定的关闭阶段

        Args:
            phase: 关闭阶段
        """
        # 更新当前阶段
        self._phase = phase
        logger.info(f"开始执行关闭阶段: {phase}")

        # 根据阶段执行不同的操作
        if phase == ShutdownPhase.API_STOPPING:
            # 停止API服务
            await self._stop_api_server(timeout=10.0)
        elif phase == ShutdownPhase.SERVICES_STOPPING:
            # 停止服务
            await self._stop_services(timeout=10.0)
        elif phase == ShutdownPhase.CLEANUP:
            # 清理资源
            await self._cleanup_resources(timeout=5.0)
        else:
            logger.warning(f"未知的关闭阶段: {phase}")

        # 记录阶段完成
        logger.info(f"关闭阶段完成: {phase}")

    async def _stop_api_server(self, timeout: float = 10.0) -> None:
        """
        停止API服务器

        Args:
            timeout: 停止超时时间（秒）
        """
        if self.http_server_manager is None:
            logger.warning("HTTP服务器管理器未配置，跳过API服务器关闭")
            return

        # 触发HTTP服务器停止前事件
        await self.lifecycle_manager.trigger_event(LifecycleEventType.PRE_HTTP_STOP)

        # 停止HTTP服务器
        logger.info("正在停止HTTP服务器...")
        try:
            # 直接等待HTTP服务器停止，不使用asyncio.shield
            await asyncio.wait_for(self.http_server_manager.stop(), timeout=timeout)
            logger.info("HTTP服务器已停止")
        except asyncio.TimeoutError:
            logger.error(f"停止HTTP服务器超时（{timeout}秒），继续后续关闭流程")
        except asyncio.CancelledError:
            logger.warning("停止HTTP服务器的任务被取消")
            # 即使取消也确保HTTP服务器知道需要关闭
            if hasattr(self.http_server_manager, "_server") and self.http_server_manager._server:
                if hasattr(self.http_server_manager._server, "should_exit"):
                    self.http_server_manager._server.should_exit = True
        except Exception as e:
            logger.error(f"停止HTTP服务器时出错: {str(e)}")

        # 等待一小段时间，确保lifespan事件得到处理
        await asyncio.sleep(0.5)

    async def _trigger_phase_events(self, phase: ShutdownPhase) -> None:
        """
        触发阶段对应的事件

        Args:
            phase: 关闭阶段
        """
        # 获取此阶段应关闭的组件类型
        component_types = [ct for ct, ph in self._component_phase_mapping.items() if ph == phase]

        if not component_types:
            logger.warning(f"阶段 {phase} 没有对应的组件类型")
            return

        # 获取关闭前的监听器
        pre_shutdown_listeners = self.lifecycle_manager.get_listeners_for_event(
            LifecycleEventType.PRE_SHUTDOWN
        )

        # 按组件类型和优先级过滤
        phase_listeners = [
            listener
            for listener in pre_shutdown_listeners
            if listener.component_type in component_types
        ]

        if not phase_listeners:
            logger.debug(f"阶段 {phase} 没有对应的关闭监听器")
            return

        # 按优先级排序（已在生命周期管理器中排序）

        # 触发监听器
        logger.info(f"触发阶段 {phase} 的关闭事件 [监听器数量: {len(phase_listeners)}]")

        # 创建阶段上下文数据
        context = {
            "phase": phase,
            "reason": self._shutdown_reason,
            "message": self._shutdown_message,
        }

        # 执行阶段关闭监听器
        for listener in phase_listeners:
            try:
                if listener.is_async:
                    await listener.callback(context)
                else:
                    listener.callback(context)
            except asyncio.CancelledError:
                logger.warning(f"关闭监听器 {listener.name} 执行被取消")
                break
            except Exception as e:
                logger.error(
                    f"执行关闭监听器时出错: {listener.name} "
                    f"[组件类型: {listener.component_type.value}, 错误: {str(e)}]"
                )

    async def _stop_services(self, timeout: float = 10.0) -> None:
        """
        停止服务

        Args:
            timeout: 停止超时时间（秒）
        """
        # 触发服务停止前事件
        if self.lifecycle_manager:
            await self.lifecycle_manager.trigger_event(LifecycleEventType.PRE_SERVICES_STOP)

        # 停止服务
        logger.info("正在停止服务...")
        try:
            # 这里可以添加停止特定服务的逻辑
            # 例如停止数据库连接、缓存连接等

            # 等待一小段时间，确保服务有时间完成关闭
            await asyncio.sleep(0.5)

            logger.info("服务已停止")
        except Exception as e:
            logger.error(f"停止服务时出错: {str(e)}")

        # 触发服务停止后事件
        if self.lifecycle_manager:
            await self.lifecycle_manager.trigger_event(LifecycleEventType.POST_SERVICES_STOP)

    async def _cleanup_resources(self, timeout: float = 5.0) -> None:
        """
        清理资源

        Args:
            timeout: 清理超时时间（秒）
        """
        # 触发资源清理前事件
        if self.lifecycle_manager:
            await self.lifecycle_manager.trigger_event(LifecycleEventType.PRE_CLEANUP)

        # 清理资源
        logger.info("正在清理资源...")
        try:
            # 这里可以添加清理特定资源的逻辑
            # 例如关闭文件句柄、释放内存等

            # 等待一小段时间，确保资源有时间完成清理
            await asyncio.sleep(0.5)

            logger.info("资源已清理")
        except Exception as e:
            logger.error(f"清理资源时出错: {str(e)}")

        # 触发资源清理后事件
        if self.lifecycle_manager:
            await self.lifecycle_manager.trigger_event(LifecycleEventType.POST_CLEANUP)

        # 设置关闭完成事件
        self._shutdown_complete.set()

        # 记录结束时间
        self._shutdown_end_time = time.time()
