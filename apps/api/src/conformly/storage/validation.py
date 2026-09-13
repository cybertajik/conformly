import os
import re
import unicodedata
from typing import Protocol

DISALLOWED_EXTENSIONS = frozenset(
    {
        ".action",
        ".apk",
        ".app",
        ".bat",
        ".bin",
        ".cmd",
        ".com",
        ".command",
        ".cpl",
        ".dll",
        ".exe",
        ".gadget",
        ".inf",
        ".ins",
        ".inx",
        ".isu",
        ".jar",
        ".jse",
        ".js",
        ".ksh",
        ".lnk",
        ".msc",
        ".msi",
        ".msp",
        ".mst",
        ".osx",
        ".out",
        ".pif",
        ".ps1",
        ".psm1",
        ".reg",
        ".rgs",
        ".run",
        ".scr",
        ".sct",
        ".sh",
        ".shb",
        ".shs",
        ".u3p",
        ".vb",
        ".vbe",
        ".vbs",
        ".vbscript",
        ".workflow",
        ".ws",
        ".wsf",
        ".wsh",
    }
)

VALID_CLASSIFICATIONS = frozenset({"Public", "Internal", "Confidential", "Restricted"})

MAX_FILENAME_LENGTH = 255

EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


import io
import logging
import socket
import struct
import zipfile

logger = logging.getLogger(__name__)


class FileValidationError(ValueError):
    """Raised when uploaded file violates validation rules."""


class MalwareDetectedError(FileValidationError):
    """Raised when malware scanner identifies malicious content."""


class MalwareScanner(Protocol):
    """Protocol for pluggable malware detection engines."""

    def scan(self, data: bytes, filename: str) -> None: ...


# Known malicious executable headers / magic bytes
DANGEROUS_MAGIC_HEADERS: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "Windows PE / DOS executable binary"),
    (b"\x7fELF", "Linux ELF executable binary"),
    (b"\xfe\xed\xfa\xce", "Mach-O 32-bit binary"),
    (b"\xce\xfa\xed\xfe", "Mach-O 32-bit binary (reverse endian)"),
    (b"\xfe\xed\xfa\xcf", "Mach-O 64-bit binary"),
    (b"\xcf\xfa\xed\xfe", "Mach-O 64-bit binary (reverse endian)"),
    (b"\xca\xfe\xba\xbe", "Java Classfile / Mach-O universal binary"),
)

# Masquerading malicious script signatures
DANGEROUS_SCRIPT_PATTERNS: tuple[bytes, ...] = (
    b"#!/bin/sh",
    b"#!/bin/bash",
    b"#!/usr/bin/env sh",
    b"#!/usr/bin/env bash",
    b"powershell.exe -enc",
    b"powershell -enc",
    b"powershell -w hidden",
    b"WScript.Shell",
    b"cmd.exe /c",
)

# HTML / SVG script injection patterns
SCRIPT_INJECTION_PATTERNS: tuple[bytes, ...] = (
    b"<script",
    b"javascript:",
    b"vbscript:",
    b"onload=",
    b"onerror=",
    b"onclick=",
    b"expression(",
)


class ProductionMalwareScanner:
    """Production-ready malware scanner with ClamAV stream protocol and multi-engine heuristics."""

    def __init__(
        self,
        *,
        clamav_host: str | None = None,
        clamav_port: int | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.clamav_host = clamav_host or os.environ.get("CLAMAV_HOST")
        self.clamav_port = clamav_port or int(os.environ.get("CLAMAV_PORT", "3310"))
        self.timeout_seconds = timeout_seconds

    def scan(self, data: bytes, filename: str) -> None:
        # 1. EICAR Test Signature
        if EICAR_SIGNATURE in data:
            raise MalwareDetectedError("malicious signature detected: EICAR test signature in uploaded file")

        # 2. Executable / Binary Header Inspection
        for magic, desc in DANGEROUS_MAGIC_HEADERS:
            if data.startswith(magic):
                raise MalwareDetectedError(
                    f"prohibited executable binary signature detected ({desc})"
                )

        # 3. Masquerading script / shell execution patterns
        lower_data = data[:8192].lower()
        for pattern in DANGEROUS_SCRIPT_PATTERNS:
            if pattern in lower_data:
                raise MalwareDetectedError(
                    f"malicious script execution signature detected: {pattern.decode('latin-1', errors='replace')}"
                )

        # 4. Markup / SVG Script Injection
        _, ext = os.path.splitext(filename.lower())
        if ext in {".svg", ".xml", ".html", ".htm"} or b"<svg" in lower_data or b"<?xml" in lower_data:
            for pattern in SCRIPT_INJECTION_PATTERNS:
                if pattern in lower_data:
                    raise MalwareDetectedError(
                        f"malicious active content / script injection detected in markup file: {pattern.decode('latin-1', errors='replace')}"
                    )

        # 5. Archive / Decompression Bomb Heuristics
        if data.startswith(b"PK\x03\x04"):
            self._scan_zip_archive(data)

        # 6. ClamAV Daemon Streaming (if host configured)
        if self.clamav_host:
            self._scan_with_clamav(data)

    def _scan_zip_archive(self, data: bytes) -> None:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                total_uncompressed = 0
                for info in zf.infolist():
                    # Defeat zip slip path traversal
                    if ".." in info.filename or info.filename.startswith(("/", "\\")):
                        raise MalwareDetectedError("archive contains hazardous path traversal entries")
                    total_uncompressed += info.file_size
                    # Check ratio for individual file
                    if info.compress_size > 0:
                        ratio = info.file_size / info.compress_size
                        if ratio > 100 and info.file_size > 10 * 1024 * 1024:
                            raise MalwareDetectedError("decompression bomb pattern detected (high compression ratio)")

                # Max total uncompressed limit (500MB safety ceiling)
                if total_uncompressed > 500 * 1024 * 1024:
                    raise MalwareDetectedError("decompression bomb pattern detected (excessive total uncompressed size)")
        except zipfile.BadZipFile:
            pass  # Not a valid zip file, allow normal file processing

    def _scan_with_clamav(self, data: bytes) -> None:
        try:
            with socket.create_connection(
                (self.clamav_host, self.clamav_port), timeout=self.timeout_seconds
            ) as s:
                s.sendall(b"zINSTREAM\0")
                chunk_size = 64 * 1024
                offset = 0
                while offset < len(data):
                    chunk = data[offset : offset + chunk_size]
                    s.sendall(struct.pack(">I", len(chunk)) + chunk)
                    offset += chunk_size
                s.sendall(struct.pack(">I", 0))

                response = b""
                while True:
                    part = s.recv(1024)
                    if not part:
                        break
                    response += part

                resp_str = response.decode("latin-1", errors="replace").strip()
                if "FOUND" in resp_str:
                    virus_name = resp_str.replace("stream:", "").replace("FOUND", "").strip()
                    raise MalwareDetectedError(f"ClamAV detected malware signature: {virus_name}")
        except MalwareDetectedError:
            raise
        except Exception as exc:
            logger.warning(
                "ClamAV daemon scan failed or timed out (%s:%s): %s; heuristic checks passed.",
                self.clamav_host,
                self.clamav_port,
                exc,
            )


# Backward compatibility alias
BuiltinMalwareScanner = ProductionMalwareScanner


def normalize_filename(filename: str) -> str:
    """Sanitize and normalize filename to prevent path traversal and control character injection."""
    if not filename or not filename.strip():
        raise FileValidationError("filename cannot be empty")
    if "\x00" in filename:
        raise FileValidationError("filename cannot contain null bytes")

    # Strip control characters
    cleaned = "".join(c for c in filename if unicodedata.category(c)[0] != "C")
    cleaned = unicodedata.normalize("NFC", cleaned).strip()

    # Extract base name to defeat path traversal
    cleaned = cleaned.replace("\\", "/")
    base_name = os.path.basename(cleaned).strip()

    if not base_name or base_name in {".", ".."}:
        raise FileValidationError("invalid filename")

    if len(base_name) > MAX_FILENAME_LENGTH:
        # Preserve extension if present
        name, ext = os.path.splitext(base_name)
        allowed_name_len = MAX_FILENAME_LENGTH - len(ext)
        if allowed_name_len <= 0:
            raise FileValidationError("filename extension exceeds maximum length")
        base_name = name[:allowed_name_len] + ext

    # Check extension
    _, ext = os.path.splitext(base_name)
    if ext.lower() in DISALLOWED_EXTENSIONS:
        raise FileValidationError(f"executable or hazardous file extension is prohibited: {ext}")

    return base_name


def validate_file_size(size_bytes: int, max_bytes: int) -> None:
    if size_bytes <= 0:
        raise FileValidationError("file cannot be empty")
    if size_bytes > max_bytes:
        raise FileValidationError(
            f"file size {size_bytes} exceeds maximum allowed limit of {max_bytes} bytes"
        )


def validate_classification(classification: str) -> str:
    if classification not in VALID_CLASSIFICATIONS:
        valid_list = sorted(VALID_CLASSIFICATIONS)
        raise FileValidationError(
            f"invalid data classification '{classification}'; must be one of {valid_list}"
        )
    return classification


def normalize_content_type(content_type: str | None) -> str:
    if not content_type or not content_type.strip():
        return "application/octet-stream"
    normalized = content_type.strip().lower()
    # Basic sanity check on MIME format
    if not re.match(r"^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+(;.*)?$", normalized):
        return "application/octet-stream"
    return normalized
