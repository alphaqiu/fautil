"""
数据库模块包括数据库连接管理、事务管理、模型基类等功能。
"""

# 导出公共API
from fautil.db.base import Base, PrefixBase
from fautil.db.engine import create_engine, get_session, session_factory
from fautil.db.transaction import transactional

__all__ = [
    "Base",
    "PrefixBase",
    "create_engine",
    "get_session",
    "session_factory",
    "transactional",
]
