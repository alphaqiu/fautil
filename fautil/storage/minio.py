"""
MinIO对象存储模块

提供与MinIO和Amazon S3兼容的对象存储功能。
"""

import asyncio
import io
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, BinaryIO, Dict, List, Optional, Union

from minio import Minio
from minio.commonconfig import CopySource
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

from fautil.core.config import MinioConfig
from fautil.core.logging import get_logger

logger = get_logger(__name__)


class MinioStorage:
    """MinIO对象存储

    提供对象的上传、下载、复制、删除等功能。
    """

    def __init__(self, config: MinioConfig):
        """初始化MinIO存储

        Args:
            config: MinIO配置
        """
        self.config = config
        self.client: Optional[Minio] = None
        self._executor = ThreadPoolExecutor(max_workers=4)

        logger.debug(f"创建MinIO存储，端点: {config.endpoint}")

    def connect(self) -> Minio:
        """连接到MinIO服务器

        Returns:
            Minio: MinIO客户端
        """
        if self.client is None:
            self.client = Minio(
                endpoint=self.config.endpoint,
                access_key=self.config.access_key,
                secret_key=self.config.secret_key,
                secure=self.config.secure,
                region=self.config.region,
            )
            logger.debug("已连接到MinIO服务器")
        return self.client

    def close(self) -> None:
        """关闭连接（占位，Minio客户端无需显式关闭）"""
        self.client = None
        logger.debug("已关闭MinIO连接")

    def ensure_bucket(self, bucket_name: Optional[str] = None) -> bool:
        """确保存储桶存在

        Args:
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            bool: 如果存储桶已存在或创建成功则返回True，否则返回False
        """
        client = self.connect()
        bucket = bucket_name or self.config.default_bucket

        try:
            # 检查桶是否存在
            if not client.bucket_exists(bucket):
                # 创建桶
                client.make_bucket(bucket, self.config.region)
                logger.info(f"创建存储桶: {bucket}")
            return True
        except S3Error as e:
            logger.error(f"确保存储桶存在失败: {e}")
            return False

    async def ensure_bucket_async(self, bucket_name: Optional[str] = None) -> bool:
        """确保存储桶存在（异步）

        Args:
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            bool: 如果存储桶已存在或创建成功则返回True，否则返回False
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.ensure_bucket, bucket_name)

    def put_object(
        self,
        object_name: str,
        data: Union[bytes, BinaryIO, str],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """上传对象

        Args:
            object_name: 对象名称
            data: 对象数据，可以是字节、文件对象或文件路径
            content_type: 内容类型，如果未指定则自动检测
            metadata: 元数据
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            bool: 如果上传成功则返回True，否则返回False
        """
        client = self.connect()
        bucket = bucket_name or self.config.default_bucket

        # 确保存储桶存在
        if not self.ensure_bucket(bucket):
            return False

        try:
            # 处理不同类型的数据
            if isinstance(data, str):
                # 字符串可能是文件路径
                if os.path.isfile(data):
                    # 打开文件
                    with open(data, "rb") as f:
                        file_data = f
                        file_size = os.path.getsize(data)
                        # 自动检测内容类型
                        content_type = content_type or self._guess_content_type(data)
                        # 上传文件
                        client.put_object(
                            bucket_name=bucket,
                            object_name=object_name,
                            data=f,
                            length=file_size,
                            content_type=content_type,
                            metadata=metadata,
                        )
                else:
                    # 字符串数据
                    data_bytes = data.encode("utf-8")
                    file_data = io.BytesIO(data_bytes)
                    file_size = len(data_bytes)
                    # 默认文本类型
                    content_type = content_type or "text/plain"
                    # 上传数据
                    client.put_object(
                        bucket_name=bucket,
                        object_name=object_name,
                        data=file_data,
                        length=file_size,
                        content_type=content_type,
                        metadata=metadata,
                    )
            elif isinstance(data, bytes):
                # 字节数据
                file_data = io.BytesIO(data)
                file_size = len(data)
                # 默认二进制类型
                content_type = content_type or "application/octet-stream"
                # 上传数据
                client.put_object(
                    bucket_name=bucket,
                    object_name=object_name,
                    data=file_data,
                    length=file_size,
                    content_type=content_type,
                    metadata=metadata,
                )
            else:
                # 文件对象
                # 注意：调用者需要负责关闭文件对象
                file_data = data
                # 尝试获取文件大小
                try:
                    file_size = data.seek(0, os.SEEK_END)
                    data.seek(0)
                except (AttributeError, io.UnsupportedOperation):
                    # 如果无法获取大小，则抛出异常
                    raise ValueError("无法确定文件大小，请提供bytes或文件路径")

                # 默认二进制类型
                content_type = content_type or "application/octet-stream"
                # 上传数据
                client.put_object(
                    bucket_name=bucket,
                    object_name=object_name,
                    data=file_data,
                    length=file_size,
                    content_type=content_type,
                    metadata=metadata,
                )

            logger.debug(f"已上传对象: {object_name} 到存储桶: {bucket}")
            return True
        except S3Error as e:
            logger.error(f"上传对象失败: {e}")
            return False

    async def put_object_async(
        self,
        object_name: str,
        data: Union[bytes, BinaryIO, str],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """上传对象（异步）

        Args:
            object_name: 对象名称
            data: 对象数据，可以是字节、文件对象或文件路径
            content_type: 内容类型，如果未指定则自动检测
            metadata: 元数据
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            bool: 如果上传成功则返回True，否则返回False
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.put_object,
            object_name,
            data,
            content_type,
            metadata,
            bucket_name,
        )

    def get_object(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
    ) -> Optional[bytes]:
        """获取对象数据

        Args:
            object_name: 对象名称
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            Optional[bytes]: 对象数据，如果对象不存在或获取失败则返回None
        """
        client = self.connect()
        bucket = bucket_name or self.config.default_bucket

        try:
            # 获取对象
            response = client.get_object(bucket, object_name)
            # 读取所有数据
            data = response.read()
            # 关闭响应
            response.close()
            response.release_conn()

            logger.debug(f"已获取对象: {object_name} 从存储桶: {bucket}")
            return data
        except S3Error as e:
            logger.error(f"获取对象失败: {e}")
            return None

    async def get_object_async(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
    ) -> Optional[bytes]:
        """获取对象数据（异步）

        Args:
            object_name: 对象名称
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            Optional[bytes]: 对象数据，如果对象不存在或获取失败则返回None
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_object, object_name, bucket_name)

    def download_object(
        self,
        object_name: str,
        file_path: str,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """下载对象到文件

        Args:
            object_name: 对象名称
            file_path: 保存文件的路径
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            bool: 如果下载成功则返回True，否则返回False
        """
        client = self.connect()
        bucket = bucket_name or self.config.default_bucket

        try:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

            # 下载对象
            client.fget_object(bucket, object_name, file_path)

            logger.debug(f"已下载对象: {object_name} 到文件: {file_path}")
            return True
        except S3Error as e:
            logger.error(f"下载对象失败: {e}")
            return False

    async def download_object_async(
        self,
        object_name: str,
        file_path: str,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """下载对象到文件（异步）

        Args:
            object_name: 对象名称
            file_path: 保存文件的路径
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            bool: 如果下载成功则返回True，否则返回False
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.download_object, object_name, file_path, bucket_name
        )

    def list_objects(
        self,
        prefix: str = "",
        recursive: bool = True,
        bucket_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出对象

        Args:
            prefix: 前缀
            recursive: 是否递归列出子目录中的对象
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            List[Dict[str, Any]]: 对象列表，每个对象包含名称、大小、最后修改时间等信息
        """
        client = self.connect()
        bucket = bucket_name or self.config.default_bucket

        try:
            # 列出对象
            objects = client.list_objects(bucket, prefix=prefix, recursive=recursive)

            # 转换为字典列表
            result = [
                {
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag,
                    "content_type": obj.content_type,
                }
                for obj in objects
            ]

            logger.debug(f"已列出 {len(result)} 个对象，前缀: {prefix}")
            return result
        except S3Error as e:
            logger.error(f"列出对象失败: {e}")
            return []

    async def list_objects_async(
        self,
        prefix: str = "",
        recursive: bool = True,
        bucket_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出对象（异步）

        Args:
            prefix: 前缀
            recursive: 是否递归列出子目录中的对象
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            List[Dict[str, Any]]: 对象列表，每个对象包含名称、大小、最后修改时间等信息
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.list_objects, prefix, recursive, bucket_name
        )

    def delete_object(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """删除对象

        Args:
            object_name: 对象名称
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            bool: 如果删除成功则返回True，否则返回False
        """
        client = self.connect()
        bucket = bucket_name or self.config.default_bucket

        try:
            # 删除对象
            client.remove_object(bucket, object_name)

            logger.debug(f"已删除对象: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"删除对象失败: {e}")
            return False

    async def delete_object_async(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """删除对象（异步）

        Args:
            object_name: 对象名称
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            bool: 如果删除成功则返回True，否则返回False
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.delete_object, object_name, bucket_name
        )

    def delete_objects(
        self,
        object_names: List[str],
        bucket_name: Optional[str] = None,
    ) -> bool:
        """批量删除对象

        Args:
            object_names: 对象名称列表
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            bool: 如果删除成功则返回True，否则返回False
        """
        client = self.connect()
        bucket = bucket_name or self.config.default_bucket

        try:
            # 创建删除对象列表
            objects = [DeleteObject(name) for name in object_names]

            # 删除对象
            errors = client.remove_objects(bucket, objects)

            # 检查是否有错误
            error_count = 0
            for error in errors:
                logger.error(f"删除对象失败: {error}")
                error_count += 1

            if error_count:
                logger.warning(f"批量删除对象失败: {error_count}/{len(object_names)}")
                return False

            logger.debug(f"已批量删除 {len(object_names)} 个对象")
            return True
        except S3Error as e:
            logger.error(f"批量删除对象失败: {e}")
            return False

    async def delete_objects_async(
        self,
        object_names: List[str],
        bucket_name: Optional[str] = None,
    ) -> bool:
        """批量删除对象（异步）

        Args:
            object_names: 对象名称列表
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            bool: 如果删除成功则返回True，否则返回False
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.delete_objects, object_names, bucket_name
        )

    def copy_object(
        self,
        source_object_name: str,
        target_object_name: str,
        source_bucket_name: Optional[str] = None,
        target_bucket_name: Optional[str] = None,
    ) -> bool:
        """复制对象

        Args:
            source_object_name: 源对象名称
            target_object_name: 目标对象名称
            source_bucket_name: 源存储桶名称，如果未指定则使用默认存储桶
            target_bucket_name: 目标存储桶名称，如果未指定则使用源存储桶

        Returns:
            bool: 如果复制成功则返回True，否则返回False
        """
        client = self.connect()
        source_bucket = source_bucket_name or self.config.default_bucket
        target_bucket = target_bucket_name or source_bucket

        try:
            # 确保目标存储桶存在
            if not self.ensure_bucket(target_bucket):
                return False

            # 复制对象
            client.copy_object(
                target_bucket,
                target_object_name,
                CopySource(source_bucket, source_object_name),
            )

            logger.debug(f"已复制对象: {source_object_name} -> {target_object_name}")
            return True
        except S3Error as e:
            logger.error(f"复制对象失败: {e}")
            return False

    async def copy_object_async(
        self,
        source_object_name: str,
        target_object_name: str,
        source_bucket_name: Optional[str] = None,
        target_bucket_name: Optional[str] = None,
    ) -> bool:
        """复制对象（异步）

        Args:
            source_object_name: 源对象名称
            target_object_name: 目标对象名称
            source_bucket_name: 源存储桶名称，如果未指定则使用默认存储桶
            target_bucket_name: 目标存储桶名称，如果未指定则使用源存储桶

        Returns:
            bool: 如果复制成功则返回True，否则返回False
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.copy_object,
            source_object_name,
            target_object_name,
            source_bucket_name,
            target_bucket_name,
        )

    def get_presigned_url(
        self,
        object_name: str,
        expires: int = 3600,
        bucket_name: Optional[str] = None,
    ) -> Optional[str]:
        """获取预签名URL

        Args:
            object_name: 对象名称
            expires: 过期时间（秒）
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            Optional[str]: 预签名URL，如果生成失败则返回None
        """
        client = self.connect()
        bucket = bucket_name or self.config.default_bucket

        try:
            # 获取预签名URL
            url = client.presigned_get_object(bucket, object_name, expires=expires)

            logger.debug(f"已生成预签名URL: {url}")
            return url
        except S3Error as e:
            logger.error(f"生成预签名URL失败: {e}")
            return None

    async def get_presigned_url_async(
        self,
        object_name: str,
        expires: int = 3600,
        bucket_name: Optional[str] = None,
    ) -> Optional[str]:
        """获取预签名URL（异步）

        Args:
            object_name: 对象名称
            expires: 过期时间（秒）
            bucket_name: 存储桶名称，如果未指定则使用默认存储桶

        Returns:
            Optional[str]: 预签名URL，如果生成失败则返回None
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.get_presigned_url, object_name, expires, bucket_name
        )

    def _guess_content_type(self, file_path: str) -> str:
        """猜测文件的内容类型

        Args:
            file_path: 文件路径

        Returns:
            str: 内容类型
        """
        import mimetypes

        # 初始化类型检测
        mimetypes.init()

        # 获取文件扩展名
        _, ext = os.path.splitext(file_path)

        # 查找对应的MIME类型
        content_type, _ = mimetypes.guess_type(file_path)

        # 如果无法确定类型，则返回默认类型
        return content_type or "application/octet-stream"
