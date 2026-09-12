import hashlib
import hmac
import os
import tempfile
import threading
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urljoin, urlparse

import httpx

from conformly.config import Settings, get_settings


class StorageError(Exception):
    """Base class for storage failures."""


class ObjectNotFoundError(StorageError):
    """Raised when an object does not exist in storage."""


class StorageProvider(Protocol):
    """Protocol for pluggable object storage backends."""

    def put_object(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None: ...

    def get_object(self, key: str) -> bytes: ...

    def delete_object(self, key: str) -> None: ...

    def object_exists(self, key: str) -> bool: ...


class MemoryStorageProvider:
    """Thread-safe in-memory storage provider for tests and ephemeral environments."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[bytes, str]] = {}
        self._lock = threading.Lock()

    def put_object(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        with self._lock:
            self._store[key] = (bytes(data), content_type)

    def get_object(self, key: str) -> bytes:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                raise ObjectNotFoundError(f"object not found: {key}")
            return item[0]

    def delete_object(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def object_exists(self, key: str) -> bool:
        with self._lock:
            return key in self._store

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class FilesystemStorageProvider:
    """Local filesystem storage provider with atomic writes and directory confinement."""

    def __init__(self, base_directory: str | Path) -> None:
        self.base_path = Path(base_directory).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        normalized = key.replace("\\", "/").strip("/")
        resolved = (self.base_path / normalized).resolve()
        if not str(resolved).startswith(str(self.base_path)):
            raise StorageError("path traversal detected in storage key")
        return resolved

    def put_object(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        target_path = self._resolve_path(key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write via temp file in the same directory
        temp_dir = target_path.parent
        fd, temp_file_path = tempfile.mkstemp(dir=temp_dir, prefix=".tmp_upload_")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(temp_file_path, target_path)
        except Exception as err:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            raise StorageError(f"failed to write object {key}: {err}") from err

    def get_object(self, key: str) -> bytes:
        target_path = self._resolve_path(key)
        if not target_path.is_file():
            raise ObjectNotFoundError(f"object not found: {key}")
        try:
            return target_path.read_bytes()
        except Exception as err:
            raise StorageError(f"failed to read object {key}: {err}") from err

    def delete_object(self, key: str) -> None:
        target_path = self._resolve_path(key)
        target_path.unlink(missing_ok=True)

    def object_exists(self, key: str) -> bool:
        target_path = self._resolve_path(key)
        return target_path.is_file()


class S3StorageProvider:
    """S3-compatible storage provider (MinIO / AWS S3) using AWS SigV4 authorization."""

    def __init__(
        self,
        endpoint_url: str,
        bucket_name: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.bucket_name = bucket_name
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.timeout = timeout_seconds
        self._client = httpx.Client(timeout=self.timeout)

    def _sign_request(
        self, method: str, path: str, query: str, headers: dict[str, str], payload: bytes
    ) -> dict[str, str]:
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        datestamp = now.strftime("%Y%m%d")

        headers["x-amz-date"] = amz_date
        payload_hash = hashlib.sha256(payload).hexdigest()
        headers["x-amz-content-sha256"] = payload_hash

        parsed = urlparse(self.endpoint_url)
        headers["host"] = parsed.netloc

        canonical_headers_list = sorted(
            [(k.lower().strip(), v.strip()) for k, v in headers.items()]
        )
        canonical_headers = "".join(f"{k}:{v}\n" for k, v in canonical_headers_list)
        signed_headers = ";".join(k for k, _ in canonical_headers_list)

        canonical_request = (
            f"{method.upper()}\n"
            f"{quote(path, safe='/')}\n"
            f"{query}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )

        credential_scope = f"{datestamp}/{self.region}/s3/aws4_request"
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        # Compute signature
        k_date = hmac.new(
            ("AWS4" + self.secret_key).encode("utf-8"),
            datestamp.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        k_region = hmac.new(k_date, self.region.encode("utf-8"), hashlib.sha256).digest()
        k_service = hmac.new(k_region, b"s3", hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        headers["Authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return headers

    def _object_url_and_path(self, key: str) -> tuple[str, str]:
        encoded_key = quote(key.lstrip("/"), safe="/")
        path = f"/{self.bucket_name}/{encoded_key}"
        url = urljoin(self.endpoint_url, path)
        return url, path

    def put_object(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        url, path = self._object_url_and_path(key)
        headers = {"content-type": content_type}
        signed_headers = self._sign_request("PUT", path, "", headers, data)
        try:
            response = self._client.put(url, headers=signed_headers, content=data)
            if response.status_code not in (200, 201, 204):
                raise StorageError(
                    f"S3 put_object failed with status {response.status_code}: {response.text}"
                )
        except httpx.RequestError as err:
            raise StorageError(f"S3 request error during put_object: {err}") from err

    def get_object(self, key: str) -> bytes:
        url, path = self._object_url_and_path(key)
        headers: dict[str, str] = {}
        signed_headers = self._sign_request("GET", path, "", headers, b"")
        try:
            response = self._client.get(url, headers=signed_headers)
            if response.status_code == 404:
                raise ObjectNotFoundError(f"object not found in S3: {key}")
            if response.status_code != 200:
                raise StorageError(
                    f"S3 get_object failed with status {response.status_code}: {response.text}"
                )
            return response.content
        except httpx.RequestError as err:
            raise StorageError(f"S3 request error during get_object: {err}") from err

    def delete_object(self, key: str) -> None:
        url, path = self._object_url_and_path(key)
        headers: dict[str, str] = {}
        signed_headers = self._sign_request("DELETE", path, "", headers, b"")
        try:
            response = self._client.delete(url, headers=signed_headers)
            # S3 DELETE is idempotent; 204 or 200 or 404 are all considered deleted
            if response.status_code not in (200, 204, 404):
                raise StorageError(
                    f"S3 delete_object failed with status {response.status_code}: {response.text}"
                )
        except httpx.RequestError as err:
            raise StorageError(f"S3 request error during delete_object: {err}") from err

    def object_exists(self, key: str) -> bool:
        url, path = self._object_url_and_path(key)
        headers: dict[str, str] = {}
        signed_headers = self._sign_request("HEAD", path, "", headers, b"")
        try:
            response = self._client.head(url, headers=signed_headers)
            if response.status_code == 200:
                return True
            if response.status_code == 404:
                return False
            raise StorageError(f"S3 object_exists returned status {response.status_code}")
        except httpx.RequestError as err:
            raise StorageError(f"S3 request error during object_exists: {err}") from err


def create_storage_provider(settings: Settings) -> StorageProvider:
    backend = settings.storage_backend.lower().strip()

    if backend == "memory":
        return MemoryStorageProvider()

    if backend == "filesystem":
        return FilesystemStorageProvider(settings.storage_local_dir)

    if backend == "s3":
        if not settings.storage_endpoint:
            raise StorageError("storage_endpoint is required for S3 backend")
        if not settings.storage_access_key or not settings.storage_secret_key:
            raise StorageError("storage credentials are required for S3 backend")
        return S3StorageProvider(
            endpoint_url=settings.storage_endpoint,
            bucket_name=settings.storage_bucket,
            access_key=settings.storage_access_key,
            secret_key=settings.storage_secret_key,
            region=settings.storage_region,
        )

    raise StorageError(f"unknown storage backend: {settings.storage_backend}")


@lru_cache
def get_storage_provider() -> StorageProvider:
    """Factory returning the configured storage provider singleton."""
    return create_storage_provider(get_settings())
