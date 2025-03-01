"""
关闭管理模块

提供服务的分阶段优雅关闭功能，支持按组件类型和优先级排序的关闭顺序。
"""

import asyncio
import signal
import time
from enum import Enum
from typing import Dict, Optional

from injector import inject, singleton
from loguru import logger

from fautil.service.http_server_manager import HTTPServerManager
from fautil.service.lifecycle_manager import (
    ComponentType,
    LifecycleEventType,
    LifecycleManager,
)


class ShutdownPhase(str, Enum):
    """关闭阶段枚举"""

    NOT_STARTED = "not_started"  # 未开始关闭
    API_STOPPING = "api_stopping"  # 停止API服务
    SERVICES_STOPPING = "services_stopping"  # 停止上层服务
    INFRASTRUCTURE_STOPPING = "infrastructure_stopping"  # 停止基础设施
    COMPLETED = "completed"  # 关闭完成
    FAILED = "failed"  # 关闭失败


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
            ShutdownPhase.INFRASTRUCTURE_STOPPING: 10,  # 基础设施关闭超时时间（秒）
        }

        # 组件映射
        self._component_phase_mapping = {
            # API相关组件在第一阶段关闭
            ComponentType.API: ShutdownPhase.API_STOPPING,
            # 上层服务在第二阶段关闭
            ComponentType.SCHEDULER: ShutdownPhase.SERVICES_STOPPING,
            ComponentType.QUEUE: ShutdownPhase.SERVICES_STOPPING,
            ComponentType.OTHER: ShutdownPhase.SERVICES_STOPPING,
            # 基础设施在第三阶段关闭
            ComponentType.CACHE: ShutdownPhase.INFRASTRUCTURE_STOPPING,
            ComponentType.STORAGE: ShutdownPhase.INFRASTRUCTURE_STOPPING,
            ComponentType.DATABASE: ShutdownPhase.INFRASTRUCTURE_STOPPING,
            ComponentType.CORE: ShutdownPhase.INFRASTRUCTURE_STOPPING,
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

        为SIGINT和SIGTERM信号设置处理器，确保优雅关闭。
        根据不同操作系统选择适当的信号处理方法。
        """
        # 跨平台信号处理
        try:
            # 尝试使用asyncio事件循环方式（适用于Unix系统）
            loop = asyncio.get_running_loop()

            # 设置SIGINT处理器（通常是Ctrl+C）
            loop.add_signal_handler(
                signal.SIGINT,
                lambda: asyncio.create_task(
                    self.trigger_shutdown(reason=ShutdownReason.SIGNAL, message="收到SIGINT信号")
                ),
            )

            # 设置SIGTERM处理器（通常是终止信号）
            loop.add_signal_handler(
                signal.SIGTERM,
                lambda: asyncio.create_task(
                    self.trigger_shutdown(reason=ShutdownReason.SIGNAL, message="收到SIGTERM信号")
                ),
            )

            logger.debug("已使用事件循环方式注册信号处理器")
        except (RuntimeError, NotImplementedError, AttributeError):
            # 如果不在事件循环中或不支持（如Windows），使用传统方式
            # Windows可能不支持某些信号，所以我们需要捕获可能的错误
            try:
                # 定义信号处理函数
                def signal_handler(sig, frame):
                    # 在同步上下文中，我们不能直接调用异步函数
                    # 但我们可以设置一个标志，让主循环检测到它
                    logger.info(f"收到信号 {sig}，触发关闭流程")
                    # 尝试使用非阻塞方式创建任务
                    try:
                        loop = asyncio.get_event_loop()
                        loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(
                                self.trigger_shutdown(
                                    reason=ShutdownReason.SIGNAL,
                                    message=f"收到信号 {sig}",
                                )
                            )
                        )
                    except Exception as e:
                        logger.error(f"处理信号时出错: {str(e)}")
                        self._is_shutting_down = True  # 至少设置标志

                # 尝试注册SIGINT
                signal.signal(signal.SIGINT, signal_handler)

                # 尝试注册SIGTERM（Windows可能不支持）
                try:
                    signal.signal(signal.SIGTERM, signal_handler)
                except (AttributeError, ValueError):
                    logger.warning("当前平台不支持SIGTERM信号")

                logger.debug("已使用传统方式注册信号处理器")
            except Exception as e:
                logger.error(f"注册信号处理器失败: {str(e)}")
                logger.warning("无法注册信号处理器，服务将无法响应中断信号")

    async def trigger_shutdown(
        self,
        reason: ShutdownReason = ShutdownReason.MANUAL,
        message: Optional[str] = None,
        exit_code: Optional[int] = None,
    ) -> None:
        """
        触发关闭过程

        Args:
            reason: 关闭原因
            message: 关闭消息
            exit_code: 退出码
        """
        # 检查是否已经在关闭中
        if self._is_shutting_down:
            logger.warning(f"服务已经在关闭中，忽略重复的关闭请求: {reason}")
            return

        # 设置关闭状态
        self._is_shutting_down = True
        self._shutdown_reason = reason
        self._shutdown_message = message
        if exit_code is not None:
            self._exit_code = exit_code

        # 设置关闭事件
        self._shutdown_event.set()

        # 触发关闭流程
        logger.info(f"正在触发服务关闭: 原因={reason}, 消息={message}")

        # 创建关闭任务并保存引用
        self._shutdown_task = asyncio.create_task(self._graceful_shutdown())

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

    async def _graceful_shutdown(self) -> None:
        """
        优雅关闭流程

        按照以下步骤进行关闭：
        1. 停止API服务
        2. 停止上层服务
        3. 停止基础设施
        """
        # 记录开始时间
        self._shutdown_start_time = time.time()

        try:
            # 设置总超时
            try:
                await asyncio.wait_for(self._execute_shutdown_phases(), timeout=self._timeout)
            except asyncio.TimeoutError:
                logger.error(f"服务关闭超时（{self._timeout}秒），继续后续处理")
                self._phase = ShutdownPhase.FAILED
        except asyncio.CancelledError:
            # 捕获取消异常，优雅处理
            logger.warning("关闭任务被取消")
            self._phase = ShutdownPhase.FAILED
        except Exception as e:
            logger.error(f"服务关闭过程中出错: {str(e)}")
            self._phase = ShutdownPhase.FAILED

        # 记录结束时间
        self._shutdown_end_time = time.time()

        # 设置关闭完成事件
        self._shutdown_complete.set()

        # 输出关闭状态
        if self._phase == ShutdownPhase.COMPLETED:
            logger.info(f"服务关闭完成，总耗时: {self.shutdown_time:.2f}秒")
        else:
            logger.warning(f"服务关闭异常，状态: {self._phase}, 耗时: {self.shutdown_time:.2f}秒")

    async def _execute_shutdown_phases(self) -> None:
        """
        执行分阶段关闭流程
        """
        # 1. 停止API服务
        await self._execute_phase(ShutdownPhase.API_STOPPING)

        # 2. 停止上层服务
        await self._execute_phase(ShutdownPhase.SERVICES_STOPPING)

        # 3. 停止基础设施
        await self._execute_phase(ShutdownPhase.INFRASTRUCTURE_STOPPING)

        # 标记为完成
        self._phase = ShutdownPhase.COMPLETED
        logger.info("服务关闭完成")

    async def _execute_phase(self, phase: ShutdownPhase) -> None:
        """
        执行单个关闭阶段

        Args:
            phase: 关闭阶段
        """
        # 更新当前阶段
        self._phase = phase
        logger.info(f"开始执行关闭阶段: {phase}")

        # 获取阶段超时时间
        timeout = self._phase_timeouts.get(phase, 30)  # 默认30秒

        # 特殊处理API关闭阶段
        if phase == ShutdownPhase.API_STOPPING:
            await self._stop_api_server(timeout)

            # 触发HTTP服务器停止后事件
            await self.lifecycle_manager.trigger_event(LifecycleEventType.POST_HTTP_STOP)

        # 触发对应的关闭事件
        await self._trigger_phase_events(phase)

        logger.info(f"关闭阶段完成: {phase}")

    async def _stop_api_server(self, timeout: int) -> None:
        """
        停止API服务器

        Args:
            timeout: 超时时间（秒）
        """
        if self.http_server_manager is None:
            logger.warning("HTTP服务器管理器未配置，跳过API服务器关闭")
            return

        # 触发HTTP服务器停止前事件
        await self.lifecycle_manager.trigger_event(LifecycleEventType.PRE_HTTP_STOP)

        # 停止HTTP服务器
        logger.info("正在停止HTTP服务器...")
        try:
            # 创建一个保护的停止任务
            stop_task = asyncio.create_task(asyncio.shield(self.http_server_manager.stop()))

            # 等待停止任务完成，带超时控制
            await asyncio.wait_for(stop_task, timeout=timeout)
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
