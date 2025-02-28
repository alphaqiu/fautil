"""
定时任务调度器模块

提供基于APScheduler的定时任务调度功能，支持异步执行。
"""

import asyncio
import enum
import inspect
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Union

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from fautil.core.events import AppStartEvent, AppStopEvent, subscribe
from fautil.core.logging import get_logger

logger = get_logger(__name__)


class TaskStatus(enum.Enum):
    """任务状态枚举"""

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 正在执行
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 执行失败
    CANCELLED = "cancelled"  # 已取消


class Task:
    """
    任务类

    表示一个定时任务，包含任务ID、名称、状态等信息。
    """

    def __init__(
        self,
        id: str,
        name: str,
        func: Callable,
        trigger: Union[CronTrigger, IntervalTrigger, DateTrigger],
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        next_run_time: Optional[datetime] = None,
    ):
        """
        初始化任务

        Args:
            id: 任务ID
            name: 任务名称
            func: 任务函数
            trigger: 触发器
            args: 位置参数
            kwargs: 关键字参数
            next_run_time: 下次运行时间
        """
        self.id = id
        self.name = name
        self.func = func
        self.trigger = trigger
        self.args = args or []
        self.kwargs = kwargs or {}
        self.next_run_time = next_run_time
        self.status = TaskStatus.PENDING
        self.last_run_time: Optional[datetime] = None
        self.last_result: Any = None
        self.last_error: Optional[Exception] = None

    def __str__(self) -> str:
        return f"Task(id={self.id}, name={self.name}, status={self.status})"


class Scheduler:
    """
    定时任务调度器

    基于APScheduler的定时任务调度器，支持异步执行。
    """

    def __init__(self):
        """初始化调度器"""
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={"default": AsyncIOExecutor()},
            job_defaults={"coalesce": True, "max_instances": 1},
        )
        self._tasks: Dict[str, Task] = {}
        self._running = False

        # 订阅应用启动和停止事件
        subscribe(AppStartEvent, self._on_app_start)
        subscribe(AppStopEvent, self._on_app_stop)

    async def _on_app_start(self, event: AppStartEvent) -> None:
        """
        应用启动事件处理

        Args:
            event: 应用启动事件
        """
        await self.start()

    async def _on_app_stop(self, event: AppStopEvent) -> None:
        """
        应用停止事件处理

        Args:
            event: 应用停止事件
        """
        await self.shutdown()

    async def start(self) -> None:
        """启动调度器"""
        if not self._running:
            self._scheduler.start()
            self._running = True
            logger.info("定时任务调度器已启动")

    async def shutdown(self, wait: bool = True) -> None:
        """
        关闭调度器

        Args:
            wait: 是否等待所有任务完成
        """
        if self._running:
            self._scheduler.shutdown(wait=wait)
            self._running = False
            logger.info("定时任务调度器已关闭")

    def _wrap_job(self, task: Task) -> Callable:
        """
        包装任务函数

        Args:
            task: 任务对象

        Returns:
            Callable: 包装后的函数
        """
        original_func = task.func
        is_async = inspect.iscoroutinefunction(original_func)

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            task.status = TaskStatus.RUNNING
            task.last_run_time = datetime.now()
            try:
                if is_async:
                    result = await original_func(*args, **kwargs)
                else:
                    result = original_func(*args, **kwargs)
                task.last_result = result
                task.status = TaskStatus.COMPLETED
                return result
            except Exception as e:
                task.last_error = e
                task.status = TaskStatus.FAILED
                logger.exception(f"任务 {task.name} 执行失败: {str(e)}")
                raise

        return wrapper

    def add_cron_job(
        self,
        func: Callable,
        name: Optional[str] = None,
        year: Optional[Union[int, str]] = None,
        month: Optional[Union[int, str]] = None,
        day: Optional[Union[int, str]] = None,
        week: Optional[Union[int, str]] = None,
        day_of_week: Optional[Union[int, str]] = None,
        hour: Optional[Union[int, str]] = None,
        minute: Optional[Union[int, str]] = None,
        second: Optional[Union[int, str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        添加Cron定时任务

        Args:
            func: 任务函数
            name: 任务名称，如果为None则使用函数名
            year: 年，支持cron表达式
            month: 月，支持cron表达式
            day: 日，支持cron表达式
            week: 周，支持cron表达式
            day_of_week: 周几，支持cron表达式
            hour: 小时，支持cron表达式
            minute: 分钟，支持cron表达式
            second: 秒，支持cron表达式
            start_date: 开始日期
            end_date: 结束日期
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            Task: 任务对象
        """
        task_id = str(uuid.uuid4())
        task_name = name or func.__name__

        trigger = CronTrigger(
            year=year,
            month=month,
            day=day,
            week=week,
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            second=second,
            start_date=start_date,
            end_date=end_date,
        )

        task = Task(
            id=task_id,
            name=task_name,
            func=func,
            trigger=trigger,
            args=args,
            kwargs=kwargs,
        )

        wrapped_func = self._wrap_job(task)
        job = self._scheduler.add_job(
            wrapped_func,
            trigger=trigger,
            args=args,
            kwargs=kwargs,
            id=task_id,
            name=task_name,
        )

        task.next_run_time = job.next_run_time
        self._tasks[task_id] = task

        logger.info(f"已添加Cron任务: {task_name}, 下次运行时间: {job.next_run_time}")
        return task

    def add_interval_job(
        self,
        func: Callable,
        name: Optional[str] = None,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        days: Optional[int] = None,
        weeks: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        添加间隔定时任务

        Args:
            func: 任务函数
            name: 任务名称，如果为None则使用函数名
            seconds: 秒数
            minutes: 分钟数
            hours: 小时数
            days: 天数
            weeks: 周数
            start_date: 开始日期
            end_date: 结束日期
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            Task: 任务对象
        """
        task_id = str(uuid.uuid4())
        task_name = name or func.__name__

        trigger = IntervalTrigger(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            days=days,
            weeks=weeks,
            start_date=start_date,
            end_date=end_date,
        )

        task = Task(
            id=task_id,
            name=task_name,
            func=func,
            trigger=trigger,
            args=args,
            kwargs=kwargs,
        )

        wrapped_func = self._wrap_job(task)
        job = self._scheduler.add_job(
            wrapped_func,
            trigger=trigger,
            args=args,
            kwargs=kwargs,
            id=task_id,
            name=task_name,
        )

        task.next_run_time = job.next_run_time
        self._tasks[task_id] = task

        logger.info(f"已添加间隔任务: {task_name}, 下次运行时间: {job.next_run_time}")
        return task

    def add_date_job(
        self,
        func: Callable,
        run_date: datetime,
        name: Optional[str] = None,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        添加一次性定时任务

        Args:
            func: 任务函数
            run_date: 运行日期
            name: 任务名称，如果为None则使用函数名
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            Task: 任务对象
        """
        task_id = str(uuid.uuid4())
        task_name = name or func.__name__

        trigger = DateTrigger(run_date=run_date)

        task = Task(
            id=task_id,
            name=task_name,
            func=func,
            trigger=trigger,
            args=args,
            kwargs=kwargs,
            next_run_time=run_date,
        )

        wrapped_func = self._wrap_job(task)
        job = self._scheduler.add_job(
            wrapped_func,
            trigger=trigger,
            args=args,
            kwargs=kwargs,
            id=task_id,
            name=task_name,
        )

        self._tasks[task_id] = task

        logger.info(f"已添加一次性任务: {task_name}, 运行时间: {run_date}")
        return task

    def remove_job(self, task_id: str) -> bool:
        """
        移除任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功移除
        """
        if task_id in self._tasks:
            try:
                self._scheduler.remove_job(task_id)
                task = self._tasks.pop(task_id)
                task.status = TaskStatus.CANCELLED
                logger.info(f"已移除任务: {task.name}")
                return True
            except Exception as e:
                logger.error(f"移除任务失败: {str(e)}")
                return False
        return False

    def get_task(self, task_id: str) -> Optional[Task]:
        """
        获取任务

        Args:
            task_id: 任务ID

        Returns:
            Optional[Task]: 任务对象，如果不存在则返回None
        """
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        """
        获取所有任务

        Returns:
            List[Task]: 任务列表
        """
        return list(self._tasks.values())

    def pause_job(self, task_id: str) -> bool:
        """
        暂停任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功暂停
        """
        if task_id in self._tasks:
            try:
                self._scheduler.pause_job(task_id)
                logger.info(f"已暂停任务: {self._tasks[task_id].name}")
                return True
            except Exception as e:
                logger.error(f"暂停任务失败: {str(e)}")
                return False
        return False

    def resume_job(self, task_id: str) -> bool:
        """
        恢复任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功恢复
        """
        if task_id in self._tasks:
            try:
                self._scheduler.resume_job(task_id)
                logger.info(f"已恢复任务: {self._tasks[task_id].name}")
                return True
            except Exception as e:
                logger.error(f"恢复任务失败: {str(e)}")
                return False
        return False

    def modify_job(
        self,
        task_id: str,
        **changes: Any,
    ) -> Optional[Task]:
        """
        修改任务

        Args:
            task_id: 任务ID
            **changes: 要修改的属性

        Returns:
            Optional[Task]: 修改后的任务对象，如果不存在则返回None
        """
        if task_id in self._tasks:
            try:
                self._scheduler.modify_job(task_id, **changes)
                task = self._tasks[task_id]
                job = self._scheduler.get_job(task_id)
                if job:
                    task.next_run_time = job.next_run_time
                logger.info(f"已修改任务: {task.name}")
                return task
            except Exception as e:
                logger.error(f"修改任务失败: {str(e)}")
                return None
        return None


# 创建全局调度器实例
scheduler = Scheduler()
