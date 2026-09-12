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


class FileValidationError(ValueError):
    """Raised when uploaded file violates validation rules."""


class MalwareDetectedError(FileValidationError):
    """Raised when malware scanner identifies malicious content."""


class MalwareScanner(Protocol):
    """Protocol for pluggable malware detection engines."""

    def scan(self, data: bytes, filename: str) -> None: ...


class BuiltinMalwareScanner:
    """Builtin scanner verifying test signatures (e.g. EICAR)."""

    def scan(self, data: bytes, filename: str) -> None:
        if EICAR_SIGNATURE in data:
            raise MalwareDetectedError("malicious signature detected in uploaded file")


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
