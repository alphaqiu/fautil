"""
数据库引擎和会话管理模块

提供数据库引擎创建和会话管理功能。
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Union

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from fautil.core.config import DBConfig

logger = logging.getLogger(__name__)


def create_engine(db_config: DBConfig) -> AsyncEngine:
    """
    创建数据库引擎

    Args:
        db_config: 数据库配置

    Returns:
        AsyncEngine: 异步数据库引擎
    """
    engine = create_async_engine(
        db_config.url,
        echo=db_config.echo,
        pool_size=db_config.pool_size,
        max_overflow=db_config.max_overflow,
        pool_recycle=db_config.pool_recycle,
    )

    logger.info(f"已创建数据库引擎: {db_config.url}")

    return engine


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    创建会话工厂

    Args:
        engine: 数据库引擎

    Returns:
        async_sessionmaker[AsyncSession]: 异步会话工厂
    """
    factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    return factory


_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def init_db(db_config: DBConfig) -> None:
    """
    初始化数据库

    Args:
        db_config: 数据库配置
    """
    global _engine, _session_maker

    _engine = create_engine(db_config)
    _session_maker = session_factory(_engine)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话

    Yields:
        AsyncSession: 数据库会话
    """
    if _session_maker is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")

    session = _session_maker()
    try:
        yield session
    finally:
        await session.close()


@asynccontextmanager
async def get_connection() -> AsyncGenerator[AsyncConnection, None]:
    """
    获取数据库连接

    Yields:
        AsyncConnection: 数据库连接
    """
    if _engine is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")

    async with _engine.begin() as conn:
        yield conn
