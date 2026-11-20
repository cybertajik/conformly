"""Strict ClamAV malware scanner for customer control evidence.

Overrides daemon scanning to fail closed on absent host, transport errors,
timeouts or non-OK replies, fulfilling D-V2-028.
"""

from __future__ import annotations

import socket
import struct
import time

from fastapi import HTTPException, status

from conformly.storage.validation import MalwareDetectedError, ProductionMalwareScanner

MAX_SCAN_RESPONSE_BYTES = 4096
CHUNK_SIZE = 64 * 1024  # 64 KiB
SCAN_DEADLINE_SECONDS = 3.0


class StrictScanUnavailableError(HTTPException):
    """Raised when malware scanner is unconfigured, times out, or fails to verify."""

    def __init__(self, detail: str = "Malware scan unavailable") -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, private"},
        )


class StrictEvidenceMalwareScanner(ProductionMalwareScanner):
    """Subclass of ProductionMalwareScanner that fails closed on ClamAV verification."""

    def __init__(
        self,
        *,
        clamav_host: str | None = None,
        clamav_port: int | None = None,
        timeout_seconds: float = SCAN_DEADLINE_SECONDS,
    ) -> None:
        super().__init__(
            clamav_host=clamav_host,
            clamav_port=clamav_port,
            timeout_seconds=timeout_seconds,
        )

    def scan(self, data: bytes, filename: str) -> None:
        """Scan data using inherited heuristics and fail-closed ClamAV daemon streaming."""
        if not self.clamav_host:
            raise StrictScanUnavailableError("Malware scan unavailable: ClamAV host not configured")

        # Runs inherited heuristic checks (EICAR, dangerous headers, scripts, markup, zip)
        # and calls self._scan_with_clamav(data)
        super().scan(data, filename)

    def _scan_with_clamav(self, data: bytes) -> None:
        """Stream decrypted bytes to ClamAV daemon and enforce exact 'stream: OK\0' result."""
        start_time = time.monotonic()
        deadline = start_time + self.timeout_seconds

        def remaining_timeout() -> float:
            rem = deadline - time.monotonic()
            if rem <= 0:
                raise TimeoutError("Scan deadline exceeded")
            return rem

        try:
            with socket.create_connection(
                (self.clamav_host, self.clamav_port),
                timeout=remaining_timeout(),
            ) as s:
                s.settimeout(remaining_timeout())
                s.sendall(b"zINSTREAM\0")

                offset = 0
                data_len = len(data)
                while offset < data_len:
                    s.settimeout(remaining_timeout())
                    chunk = data[offset : offset + CHUNK_SIZE]
                    s.sendall(struct.pack(">I", len(chunk)) + chunk)
                    offset += len(chunk)

                s.settimeout(remaining_timeout())
                s.sendall(struct.pack(">I", 0))

                response = b""
                while True:
                    s.settimeout(remaining_timeout())
                    part = s.recv(1024)
                    if not part:
                        break
                    response += part
                    if len(response) > MAX_SCAN_RESPONSE_BYTES:
                        raise StrictScanUnavailableError(
                            "Malware scan response exceeded maximum length"
                        )
                    if b"\0" in response:
                        break

                if not response:
                    raise StrictScanUnavailableError("Malware scan returned empty response")

                if b"FOUND" in response:
                    raise MalwareDetectedError("Malware detected in uploaded evidence")

                # Exact reply check: must be complete and exact 'stream: OK\0'
                if response != b"stream: OK\0":
                    raise StrictScanUnavailableError("Malware scan returned non-OK status")

        except MalwareDetectedError:
            raise
        except (StrictScanUnavailableError, HTTPException):
            raise
        except Exception:
            # Mask all network, transport, connection, and socket errors into sanitized 503
            raise StrictScanUnavailableError("Malware scan unavailable") from None
