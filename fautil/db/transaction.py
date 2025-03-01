"""
数据库事务管理模块

提供事务装饰器，自动管理数据库事务。
"""

import functools
import inspect
import logging
from typing import Any, Callable, TypeVar, cast

from fautil.db.engine import get_session

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def transactional(func: F) -> F:
    """
    事务装饰器

    自动管理数据库事务，如果函数执行成功则提交事务，否则回滚事务

    可以装饰普通函数或异步函数，被装饰的函数必须接受 session 参数

    Args:
        func: 被装饰的函数

    Returns:
        F: 装饰后的函数
    """
    is_async = inspect.iscoroutinefunction(func)

    if is_async:

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if "session" in kwargs and kwargs["session"] is not None:
                # 使用传入的会话
                session = kwargs["session"]
                created_session = False
            else:
                # 创建新会话
                async with get_session() as session:
                    kwargs["session"] = session
                    created_session = True

            # 执行函数
            try:
                result = await func(*args, **kwargs)

                # 如果是我们创建的会话，则提交事务
                if created_session:
                    await session.commit()

                return result
            except Exception as e:
                # 如果是我们创建的会话，则回滚事务
                if created_session:
                    await session.rollback()

                # 重新抛出异常
                raise e
            finally:
                # 如果是我们创建的会话，则关闭会话
                if created_session:
                    await session.close()

        return cast(F, async_wrapper)
    else:

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError("不支持同步函数，请使用异步函数")

        return cast(F, sync_wrapper)
