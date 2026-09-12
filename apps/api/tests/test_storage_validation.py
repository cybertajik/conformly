import pytest

from conformly.storage.validation import (
    EICAR_SIGNATURE,
    BuiltinMalwareScanner,
    FileValidationError,
    MalwareDetectedError,
    normalize_content_type,
    normalize_filename,
    validate_classification,
    validate_file_size,
)


@pytest.mark.parametrize(
    ("input_name", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("path/to/evidence.docx", "evidence.docx"),
        ("..\\..\\windows\\system32\\calc.txt", "calc.txt"),
        ("safe_file_123.csv", "safe_file_123.csv"),
        ("audit-résumé.pdf", "audit-résumé.pdf"),
    ],
)
def test_normalize_filename_success(input_name: str, expected: str) -> None:
    assert normalize_filename(input_name) == expected


@pytest.mark.parametrize(
    "bad_name",
    [
        "",
        "   ",
        ".",
        "..",
        "\x00",
        "\x00bad.txt",
    ],
)
def test_normalize_filename_invalid(bad_name: str) -> None:
    with pytest.raises(FileValidationError):
        normalize_filename(bad_name)


@pytest.mark.parametrize(
    "forbidden_file",
    [
        "malware.exe",
        "script.bat",
        "run.cmd",
        "exploit.dll",
        "setup.msi",
        "deploy.sh",
        "macro.vbs",
        "power.ps1",
        "trojan.scr",
        "bad.js",
    ],
)
def test_disallowed_extensions_rejected(forbidden_file: str) -> None:
    with pytest.raises(FileValidationError, match="prohibited"):
        normalize_filename(forbidden_file)


def test_normalize_filename_truncates_long_name() -> None:
    long_name = "a" * 300 + ".pdf"
    normalized = normalize_filename(long_name)
    assert len(normalized) == 255
    assert normalized.endswith(".pdf")


def test_validate_file_size() -> None:
    # 0 bytes rejected
    with pytest.raises(FileValidationError, match="cannot be empty"):
        validate_file_size(0, max_bytes=1000)

    # Negative bytes rejected
    with pytest.raises(FileValidationError, match="cannot be empty"):
        validate_file_size(-1, max_bytes=1000)

    # Within limit accepted
    validate_file_size(500, max_bytes=1000)

    # Exceeding limit rejected
    with pytest.raises(FileValidationError, match="exceeds maximum"):
        validate_file_size(1001, max_bytes=1000)


def test_validate_classification() -> None:
    for classification in ["Public", "Internal", "Confidential", "Restricted"]:
        assert validate_classification(classification) == classification

    with pytest.raises(FileValidationError, match="invalid data classification"):
        validate_classification("TopSecret")


def test_normalize_content_type() -> None:
    assert normalize_content_type("application/pdf") == "application/pdf"
    assert normalize_content_type("  IMAGE/PNG  ") == "image/png"
    assert normalize_content_type(None) == "application/octet-stream"
    assert normalize_content_type("") == "application/octet-stream"
    assert normalize_content_type("invalid_mime") == "application/octet-stream"


def test_malware_scanner() -> None:
    scanner = BuiltinMalwareScanner()

    # Clean data passes
    scanner.scan(b"this is clean compliance document content", "doc.txt")

    # EICAR signature triggers MalwareDetectedError
    with pytest.raises(MalwareDetectedError, match="malicious signature"):
        scanner.scan(b"header " + EICAR_SIGNATURE + b" footer", "eicar.txt")
