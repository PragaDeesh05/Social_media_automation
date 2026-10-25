import pytest
import uuid
from app.services.storage.minio_service import storage_service


def test_minio_health():
    health = storage_service.health_check()
    assert health["connected"] is True
    assert health["status"] == "healthy"


def test_minio_upload_and_download_bytes():
    test_key = f"tests/temp_{uuid.uuid4().hex}.txt"
    test_data = b"IncuBrix automated MinIO verification payload"

    # Upload
    storage_service.upload_bytes(test_key, test_data, content_type="text/plain")

    # Download
    downloaded = storage_service.download_bytes(test_key)
    assert downloaded == test_data

    # Presigned URL
    url = storage_service.get_presigned_url(test_key)
    assert "http" in url

    # Cleanup
    assert storage_service.delete_object(test_key) is True
