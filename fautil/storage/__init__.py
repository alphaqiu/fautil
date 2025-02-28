"""
对象存储模块

提供兼容S3的对象存储功能，支持MinIO和Amazon S3。
"""

from fautil.storage.minio import MinioStorage

__all__ = ["MinioStorage"]
