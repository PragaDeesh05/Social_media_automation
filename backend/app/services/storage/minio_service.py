import io
import os
from datetime import timedelta
from typing import Optional, BinaryIO, Dict, Any, List
from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.logging import logger


class MinioStorageService:
    def __init__(self):
        self.endpoint = settings.MINIO_ENDPOINT
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.bucket = settings.MINIO_BUCKET
        self.secure = settings.MINIO_SECURE

        self.client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket '{self.bucket}'")
            else:
                logger.debug(f"MinIO bucket '{self.bucket}' verified")
        except Exception as e:
            logger.warning(f"Failed to verify/create MinIO bucket '{self.bucket}': {e}")

    def upload_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Upload in-memory bytes directly to MinIO."""
        stream = io.BytesIO(data)
        length = len(data)
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_key,
            data=stream,
            length=length,
            content_type=content_type,
            metadata=metadata
        )
        logger.info(f"Uploaded {length} bytes to MinIO key: {object_key}")
        return object_key

    def upload_file(
        self,
        object_key: str,
        file_path: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Upload file from local path to MinIO."""
        file_size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_key,
                data=f,
                length=file_size,
                content_type=content_type,
                metadata=metadata
            )
        logger.info(f"Uploaded file {file_path} ({file_size} bytes) to MinIO key: {object_key}")
        return object_key

    def get_presigned_url(self, object_key: str, expires_seconds: int = 3600) -> str:
        """Generate presigned GET URL for authenticated downloading/rendering."""
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=object_key,
                expires=timedelta(seconds=expires_seconds)
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for key {object_key}: {e}")
            # Fallback direct proxy path
            return f"{settings.BACKEND_URL}/api/v1/media/stream?key={object_key}"

    def download_bytes(self, object_key: str) -> bytes:
        """Download raw bytes from MinIO."""
        response = None
        try:
            response = self.client.get_object(self.bucket, object_key)
            return response.read()
        finally:
            if response:
                response.close()
                response.release_conn()

    def download_to_file(self, object_key: str, dest_path: str) -> str:
        """Download MinIO object to destination local temporary path."""
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        data = self.download_bytes(object_key)
        with open(dest_path, "wb") as f:
            f.write(data)
        return dest_path

    def delete_object(self, object_key: str) -> bool:
        """Safely delete object from MinIO."""
        try:
            self.client.remove_object(self.bucket, object_key)
            logger.info(f"Deleted MinIO object: {object_key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting MinIO object {object_key}: {e}")
            return False

    def list_objects(self, prefix: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """List objects in bucket with optional prefix."""
        items = []
        try:
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
            for i, obj in enumerate(objects):
                if i >= limit:
                    break
                items.append({
                    "object_key": obj.object_name,
                    "size_bytes": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "etag": obj.etag
                })
        except Exception as e:
            logger.error(f"Error listing MinIO objects for prefix {prefix}: {e}")
        return items

    def health_check(self) -> Dict[str, Any]:
        """Verify MinIO connectivity and bucket readiness."""
        try:
            exists = self.client.bucket_exists(self.bucket)
            return {
                "status": "healthy" if exists else "bucket_missing",
                "endpoint": self.endpoint,
                "bucket": self.bucket,
                "connected": True
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.endpoint,
                "bucket": self.bucket,
                "connected": False,
                "error": str(e)
            }


storage_service = MinioStorageService()
