"""
数据库模型基类模块

提供SQLAlchemy模型的基类，支持表前缀功能。
"""

import uuid
from datetime import datetime
from typing import Any, ClassVar, Dict, Optional, cast

from sqlalchemy import MetaData, DateTime, String, Table
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """
    SQLAlchemy模型基类
    提供默认的ID和时间戳列
    """

    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class CustomMeta(DeclarativeMeta):
    """
    自定义元类，用于支持表前缀功能
    """

    def __new__(
        mcs: type[DeclarativeMeta],
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
    ) -> DeclarativeMeta:
        # 获取表名
        tablename = namespace.get("__tablename__")

        if tablename is not None:
            # 获取表前缀
            registry = namespace.get("registry", None)

            if registry is not None and hasattr(registry, "metadata"):
                metadata = cast(MetaData, registry.metadata)
                prefix = getattr(metadata, "prefix", "")

                if prefix and not tablename.startswith(prefix):
                    namespace["__tablename__"] = f"{prefix}{tablename}"

        return super().__new__(mcs, name, bases, namespace)


class BaseMeta(Base.__class__, CustomMeta):
    """
    结合Base的元类和自定义元类
    """

    pass


class PrefixBase(Base, metaclass=BaseMeta):
    """
    支持表前缀的模型基类
    """

    __abstract__ = True

    @classmethod
    def set_table_prefix(cls, prefix: str) -> None:
        """
        设置表前缀

        Args:
            prefix: 表前缀
        """
        if hasattr(cls.metadata, "prefix"):
            cls.metadata.prefix = prefix
        else:
            setattr(cls.metadata, "prefix", prefix)
