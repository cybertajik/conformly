import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from conformly.config import Settings
from conformly.storage.providers import (
    FilesystemStorageProvider,
    MemoryStorageProvider,
    ObjectNotFoundError,
    S3StorageProvider,
    StorageError,
    get_storage_provider,
)


def test_memory_storage_provider_crud() -> None:
    provider = MemoryStorageProvider()

    assert not provider.object_exists("file1")

    provider.put_object("file1", b"hello world", "text/plain")
    assert provider.object_exists("file1")
    assert provider.get_object("file1") == b"hello world"

    # Overwrite
    provider.put_object("file1", b"updated content", "text/plain")
    assert provider.get_object("file1") == b"updated content"

    # Delete
    provider.delete_object("file1")
    assert not provider.object_exists("file1")
    with pytest.raises(ObjectNotFoundError):
        provider.get_object("file1")

    # Idempotent delete
    provider.delete_object("file1")


def test_filesystem_storage_provider_crud() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = FilesystemStorageProvider(tmpdir)

        key = "tenants/tenant-1/evidence/doc.enc"
        assert not provider.object_exists(key)

        provider.put_object(key, b"encrypted-blob", "application/octet-stream")
        assert provider.object_exists(key)
        assert provider.get_object(key) == b"encrypted-blob"

        # Verify file is stored in directory
        disk_path = Path(tmpdir) / "tenants" / "tenant-1" / "evidence" / "doc.enc"
        assert disk_path.is_file()
        assert disk_path.read_bytes() == b"encrypted-blob"

        # Delete
        provider.delete_object(key)
        assert not provider.object_exists(key)
        assert not disk_path.exists()
        with pytest.raises(ObjectNotFoundError):
            provider.get_object(key)

        # Idempotent delete
        provider.delete_object(key)


def test_filesystem_storage_provider_path_traversal_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = FilesystemStorageProvider(tmpdir)

        with pytest.raises(StorageError, match="path traversal"):
            provider.put_object("../../etc/passwd", b"bad", "text/plain")

        with pytest.raises(StorageError, match="path traversal"):
            provider.get_object("../outside.txt")


def test_s3_storage_provider_signing_and_requests() -> None:
    provider = S3StorageProvider(
        endpoint_url="http://localhost:9000",
        bucket_name="test-bucket",
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
    )

    # Test put_object
    mock_put_response = MagicMock(spec=httpx.Response)
    mock_put_response.status_code = 200

    with patch.object(provider._client, "put", return_value=mock_put_response) as mock_put:
        provider.put_object("path/to/key.enc", b"data", "application/octet-stream")
        assert mock_put.called
        args, kwargs = mock_put.call_args
        assert args[0] == "http://localhost:9000/test-bucket/path/to/key.enc"
        assert "Authorization" in kwargs["headers"]
        assert "AWS4-HMAC-SHA256" in kwargs["headers"]["Authorization"]
        assert kwargs["content"] == b"data"

    # Test get_object
    mock_get_response = MagicMock(spec=httpx.Response)
    mock_get_response.status_code = 200
    mock_get_response.content = b"retrieved-data"

    with patch.object(provider._client, "get", return_value=mock_get_response) as mock_get:
        retrieved = provider.get_object("path/to/key.enc")
        assert retrieved == b"retrieved-data"
        assert mock_get.called

    # Test get_object 404
    mock_404_response = MagicMock(spec=httpx.Response)
    mock_404_response.status_code = 404

    with patch.object(provider._client, "get", return_value=mock_404_response):
        with pytest.raises(ObjectNotFoundError):
            provider.get_object("missing.enc")

    # Test delete_object
    mock_delete_response = MagicMock(spec=httpx.Response)
    mock_delete_response.status_code = 204

    with patch.object(provider._client, "delete", return_value=mock_delete_response) as mock_del:
        provider.delete_object("path/to/key.enc")
        assert mock_del.called

    # Test object_exists
    mock_head_200 = MagicMock(spec=httpx.Response)
    mock_head_200.status_code = 200
    with patch.object(provider._client, "head", return_value=mock_head_200):
        assert provider.object_exists("key.enc")

    mock_head_404 = MagicMock(spec=httpx.Response)
    mock_head_404.status_code = 404
    with patch.object(provider._client, "head", return_value=mock_head_404):
        assert not provider.object_exists("key.enc")


def test_get_storage_provider_factory() -> None:
    from conformly.storage.providers import create_storage_provider

    mem_settings = Settings(storage_backend="memory")
    provider = create_storage_provider(mem_settings)
    assert isinstance(provider, MemoryStorageProvider)

    fs_settings = Settings(storage_backend="filesystem", storage_local_dir="/tmp/test_storage")
    fs_provider = create_storage_provider(fs_settings)
    assert isinstance(fs_provider, FilesystemStorageProvider)

    bad_settings = Settings(storage_backend="invalid_backend")
    with pytest.raises(StorageError, match="unknown storage backend"):
        create_storage_provider(bad_settings)

    default_provider = get_storage_provider()
    assert default_provider is not None
