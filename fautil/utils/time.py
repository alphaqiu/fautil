"""
时间处理模块

提供时间格式化和解析功能，以及JSON时间编码器。
"""

import datetime
import json
from typing import Any, Dict, Optional, Union


class JSONTimeEncoder(json.JSONEncoder):
    """
    JSON时间编码器

    扩展JSON编码器，支持datetime和date类型的序列化。
    """

    def default(self, obj: Any) -> Any:
        """
        自定义序列化方法

        Args:
            obj: 要序列化的对象

        Returns:
            Any: 序列化后的对象
        """
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return format_datetime(obj)
        return super().default(obj)


def format_datetime(
    dt: Union[datetime.datetime, datetime.date],
    format_str: Optional[str] = None,
) -> str:
    """
    格式化日期时间

    Args:
        dt: 日期时间对象
        format_str: 格式化字符串，默认为ISO 8601格式

    Returns:
        str: 格式化后的字符串
    """
    if format_str:
        return dt.strftime(format_str)

    # 默认使用ISO 8601格式
    if isinstance(dt, datetime.datetime):
        return dt.isoformat()
    elif isinstance(dt, datetime.date):
        return dt.isoformat()
    else:
        raise TypeError(f"不支持的类型: {type(dt)}")


def parse_datetime(
    dt_str: str,
    format_str: Optional[str] = None,
    as_date: bool = False,
) -> Union[datetime.datetime, datetime.date]:
    """
    解析日期时间字符串

    Args:
        dt_str: 日期时间字符串
        format_str: 格式化字符串，如果为None则尝试自动解析
        as_date: 是否返回日期对象而不是日期时间对象

    Returns:
        Union[datetime.datetime, datetime.date]: 解析后的日期时间对象
    """
    if format_str:
        # 使用指定格式解析
        dt = datetime.datetime.strptime(dt_str, format_str)
    else:
        # 尝试自动解析
        try:
            # 尝试ISO格式
            dt = datetime.datetime.fromisoformat(dt_str)
        except ValueError:
            # 尝试常见格式
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y",
            ]
            for fmt in formats:
                try:
                    dt = datetime.datetime.strptime(dt_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"无法解析日期时间字符串: {dt_str}")

    # 根据需要返回日期或日期时间
    if as_date:
        return dt.date()
    return dt


def json_dumps(obj: Any, **kwargs: Any) -> str:
    """
    使用时间编码器将对象序列化为JSON字符串

    Args:
        obj: 要序列化的对象
        **kwargs: 传递给json.dumps的其他参数

    Returns:
        str: JSON字符串
    """
    return json.dumps(obj, cls=JSONTimeEncoder, **kwargs)


def json_loads(s: str, **kwargs: Any) -> Any:
    """
    将JSON字符串反序列化为对象

    Args:
        s: JSON字符串
        **kwargs: 传递给json.loads的其他参数

    Returns:
        Any: 反序列化后的对象
    """
    return json.loads(s, **kwargs)
