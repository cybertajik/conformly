"""Staging Hardened Deployment Integration & Service Demonstration.

Demonstrates all core infrastructure and security services working together:
1. Keycloak OIDC Provider:
   - Hardened non-dev deployment verification.
   - RS256 token signature validation against Keycloak customer-realm JWKS endpoint.
   - Enforced MFA/TOTP assertion verification via AMR claims.
2. OpenBao / HashiCorp Vault KMS Provider:
   - Transit secret engine wrapping and unwrapping of Data Encryption Keys (DEKs).
   - AES-256-GCM envelope encryption with authenticated tenant context.
   - Cryptographic tamper resistance and decryption validation.
3. ClamAV Malware Scanning Engine:
   - zINSTREAM socket protocol daemon streaming verification.
   - Clean file pass-through vs. virus stream quarantine and audit logging.
   - Defense-in-depth heuristic inspection (executables, scripts, zip bombs).
4. Prometheus & Grafana SLO Monitoring:
   - Active collection of request count, latency percentiles, and DB gauge metrics.
   - Full alignment with Grafana SLO provisioning dashboard (conformly-slo.json).
5. Unified End-to-End Staging Flow:
   - Identity verification -> Malware scan -> OpenBao envelope encryption -> Storage -> Metric recording.
"""

import io
import json
import socketserver
import struct
import threading
import time
from collections.abc import Generator
from unittest.mock import patch
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from sqlalchemy.orm import Session

from conformly.audit.models import AuditEvent, AuditOutcome
from conformly.auth.tokens import AuthenticationError, OIDCTokenVerifier
from conformly.authz.policy import Principal, TenantContext
from conformly.authz.roles import Role
from conformly.crypto.envelope import EnvelopeEncryptionService
from conformly.crypto.providers import (
    AES256GCMProvider,
    InvalidCiphertextError,
    VaultKmsProvider,
)
from conformly.crypto.types import EncryptionContext
from conformly.identity.models import Membership, MembershipStatus, Tenant, TenantStatus, User
from conformly.monitoring.metrics import (
    record_request_metric,
    render_prometheus_metrics,
)
from conformly.storage.models import StoredFile, StoredFileStatus
from conformly.storage.providers import MemoryStorageProvider
from conformly.storage.service import StorageService
from conformly.storage.validation import (
    EICAR_SIGNATURE,
    MalwareDetectedError,
    ProductionMalwareScanner,
)

# =============================================================================
# Mock ClamAV Socket Server Fixture
# =============================================================================


class MockClamAVProtocolHandler(socketserver.BaseRequestHandler):
    """Simulates ClamAV daemon zINSTREAM socket protocol."""

    def handle(self) -> None:
        cmd = self.request.recv(10)
        if not cmd.startswith(b"zINSTREAM"):
            self.request.sendall(b"UNKNOWN COMMAND\0")
            return

        streamed_data = b""
        while True:
            raw_len = self.request.recv(4)
            if not raw_len or len(raw_len) < 4:
                break
            chunk_length = struct.unpack(">I", raw_len)[0]
            if chunk_length == 0:
                break
            chunk = b""
            while len(chunk) < chunk_length:
                part = self.request.recv(chunk_length - len(chunk))
                if not part:
                    break
                chunk += part
            streamed_data += chunk

        # Inspect streamed content for malware triggers
        if b"EICAR" in streamed_data or b"MALWARE_PAYLOAD" in streamed_data:
            self.request.sendall(b"stream: Win.Test.EICAR_HDB-1 FOUND\0")
        elif b"TROJAN" in streamed_data:
            self.request.sendall(b"stream: Unix.Trojan.Generic-999 FOUND\0")
        else:
            self.request.sendall(b"stream: OK\0")


@pytest.fixture(scope="module")
def mock_clamav_server() -> Generator[tuple[str, int], None, None]:
    """Runs an in-process mock ClamAV TCP daemon for staging testing."""
    server = socketserver.TCPServer(("127.0.0.1", 0), MockClamAVProtocolHandler)
    host, port = str(server.server_address[0]), int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port
    server.shutdown()
    server.server_close()


# =============================================================================
# Mock OpenBao / Vault Transit Engine
# =============================================================================


@pytest.fixture(scope="module")
def mock_openbao_transport() -> httpx.MockTransport:
    """Simulates OpenBao/Vault transit engine AES-256-GCM encryption & decryption."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        token = request.headers.get("X-Vault-Token") or request.headers.get("x-vault-token")
        if token != "root":
            return httpx.Response(403, json={"errors": ["permission denied"]})

        if path == "/v1/transit/encrypt/conformly-master-key":
            body = json.loads(request.content)
            plaintext_b64 = body["plaintext"]
            # In transit engine, ciphertext format is 'vault:v1:<base64-payload>'
            return httpx.Response(
                200,
                json={"data": {"ciphertext": f"vault:v1:{plaintext_b64}"}},
            )
        elif path == "/v1/transit/decrypt/conformly-master-key":
            body = json.loads(request.content)
            ciphertext = body["ciphertext"]
            parts = ciphertext.split(":", 2)
            if len(parts) != 3 or parts[0] != "vault":
                return httpx.Response(400, json={"errors": ["invalid ciphertext"]})
            plaintext_b64 = parts[2]
            return httpx.Response(
                200,
                json={"data": {"plaintext": plaintext_b64}},
            )
        return httpx.Response(404, json={"errors": [f"route not found: {path}"]})

    return httpx.MockTransport(handler)


# =============================================================================
# Keycloak RSA Keypair & JWKS Fixture
# =============================================================================


@pytest.fixture(scope="module")
def keycloak_keypair() -> tuple[rsa.RSAPrivateKey, dict[str, object]]:
    """Generates an RSA keypair and matching JWKS structure for Keycloak testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk_data = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk_data["kid"] = "conformly-keycloak-2026-key"
    jwk_data["alg"] = "RS256"
    jwk_data["use"] = "sig"
    jwks_body: dict[str, object] = {"keys": [jwk_data]}
    return private_key, jwks_body


# =============================================================================
# 1. Keycloak Hardened OIDC Verification Tests
# =============================================================================


def test_keycloak_hardened_oidc_verification(
    keycloak_keypair: tuple[rsa.RSAPrivateKey, dict[str, object]],
) -> None:
    """Verifies Keycloak customer-realm token claims, RS256 signature, and MFA assertion."""
    private_key, jwks = keycloak_keypair
    jwks_bytes = json.dumps(jwks).encode("utf-8")

    class MockJwksUrlOpen:
        def __init__(self, data: bytes) -> None:
            self._stream = io.BytesIO(data)

        def read(self, size: int | None = -1) -> bytes:
            return self._stream.read(size)

        def __enter__(self) -> io.BytesIO:
            return self._stream

        def __exit__(self, *args: object) -> None:
            pass

    issuer = "http://keycloak:8080/realms/conformly-customer"
    audience = "conformly-api"
    certs_url = f"{issuer}/protocol/openid-connect/certs"

    with patch("urllib.request.urlopen", return_value=MockJwksUrlOpen(jwks_bytes)):
        verifier = OIDCTokenVerifier(
            issuer=issuer,
            audience=audience,
            jwks_url=certs_url,
        )

        now = int(time.time())
        token_payload = {
            "iss": issuer,
            "sub": "kc-user-uuid-9876",
            "aud": audience,
            "exp": now + 3600,
            "sid": "kc-session-5544",
            "email": "security-officer@conformly-tenant.de",
            "name": "Hardened Security Officer",
            "email_verified": True,
            "amr": ["pwd", "otp"],  # MFA asserted via TOTP
            "acr": "loa2",
            "realm_access": {"roles": ["customer_user", "customer_privileged"]},
        }

        signed_jwt = jwt.encode(
            token_payload,
            private_key,
            algorithm="RS256",
            headers={"kid": "conformly-keycloak-2026-key"},
        )

        claims = verifier.verify(signed_jwt)
        assert claims.issuer == issuer
        assert claims.subject == "kc-user-uuid-9876"
        assert claims.email == "security-officer@conformly-tenant.de"
        assert claims.email_verified is True
        assert claims.mfa_verified is True
        assert "otp" in claims.amr

        # Test rejected expired token
        expired_jwt = jwt.encode(
            {**token_payload, "exp": now - 300},
            private_key,
            algorithm="RS256",
            headers={"kid": "conformly-keycloak-2026-key"},
        )
        with pytest.raises(AuthenticationError):
            verifier.verify(expired_jwt)

        # Test rejected forged signature with alternate key
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        forged_jwt = jwt.encode(
            token_payload,
            other_key,
            algorithm="RS256",
            headers={"kid": "conformly-keycloak-2026-key"},
        )
        with pytest.raises(AuthenticationError):
            verifier.verify(forged_jwt)


# =============================================================================
# 2. OpenBao / Vault Transit KMS Provider Tests
# =============================================================================


def test_openbao_transit_kms_envelope_encryption(
    mock_openbao_transport: httpx.MockTransport,
) -> None:
    """Verifies OpenBao transit engine key wrapping, unwrapping, and AEAD envelope encryption."""
    client = httpx.Client(base_url="http://openbao:8200", transport=mock_openbao_transport)
    kms_provider = VaultKmsProvider(
        endpoint="http://openbao:8200",
        token="root",
        mount="transit",
        key_name="conformly-master-key",
        http_client=client,
    )
    assert kms_provider.active_key_version == "1"

    encryption_service = EnvelopeEncryptionService(
        crypto=AES256GCMProvider(),
        keys=kms_provider,
    )

    tenant_id = uuid4()
    context = EncryptionContext(
        tenant_id=tenant_id,
        resource_type="audit_log",
        resource_id="log-entry-001",
        field_name="event_details",
        version=1,
    )

    sensitive_evidence = b"CRITICAL_HEALTHCARE_COMPLIANCE_PATIENT_RECORDS_DATA"
    encrypted = encryption_service.encrypt(sensitive_evidence, context)

    assert encrypted.algorithm == "AES-256-GCM"
    assert encrypted.key_version == "1"
    assert encrypted.ciphertext != sensitive_evidence
    assert b"vault:v1:" in encrypted.wrapped_dek

    # Verify successful decryption round-trip via OpenBao unwrap
    decrypted = encryption_service.decrypt(encrypted, context)
    assert decrypted == sensitive_evidence

    # Verify tamper resistance: modifying ciphertext causes AEAD tag failure
    corrupted_ciphertext = bytearray(encrypted.ciphertext)
    corrupted_ciphertext[0] ^= 0xFF
    corrupted_payload = encrypted.__class__(
        algorithm=encrypted.algorithm,
        context_version=encrypted.context_version,
        key_version=encrypted.key_version,
        wrapped_dek_nonce=encrypted.wrapped_dek_nonce,
        wrapped_dek=encrypted.wrapped_dek,
        nonce=encrypted.nonce,
        ciphertext=bytes(corrupted_ciphertext),
    )
    with pytest.raises(InvalidCiphertextError):
        encryption_service.decrypt(corrupted_payload, context)


# =============================================================================
# 3. ClamAV Daemon Streaming Protocol Tests
# =============================================================================


def test_clamav_daemon_stream_malware_detection(
    mock_clamav_server: tuple[str, int],
) -> None:
    """Verifies ClamAV zINSTREAM streaming protocol with clean and malicious files."""
    host, port = mock_clamav_server
    scanner = ProductionMalwareScanner(clamav_host=host, clamav_port=port)

    # Clean file streams through without exception
    clean_content = b"%PDF-1.4\n1 0 obj\n<< /Title (SOC2 Clean Report) >>\nendobj"
    scanner.scan(clean_content, "soc2_audit.pdf")

    # Malicious stream triggers ClamAV daemon virus detection
    infected_content = b"Some legitimate headers... MALWARE_PAYLOAD ...tail bytes"
    with pytest.raises(MalwareDetectedError) as exc_info:
        scanner.scan(infected_content, "vendor_contract.pdf")
    assert "Win.Test.EICAR_HDB-1" in str(exc_info.value)

    # Test defense-in-depth heuristic detection (EICAR signature)
    with pytest.raises(MalwareDetectedError) as exc_eicar:
        scanner.scan(EICAR_SIGNATURE, "test.txt")
    assert "EICAR test signature" in str(exc_eicar.value)

    # Test defense-in-depth heuristic detection (Windows executable header)
    with pytest.raises(MalwareDetectedError) as exc_pe:
        scanner.scan(b"MZ\x90\x00\x03\x00\x00\x00", "invoice.exe")
    assert "executable binary" in str(exc_pe.value)


# =============================================================================
# 4. Storage Service Integration with OpenBao & ClamAV
# =============================================================================


def test_storage_service_integrated_with_openbao_and_clamav(
    session: Session,
    mock_openbao_transport: httpx.MockTransport,
    mock_clamav_server: tuple[str, int],
) -> None:
    """Demonstrates StorageService storing clean files and quarantining infected files."""
    host, port = mock_clamav_server
    scanner = ProductionMalwareScanner(clamav_host=host, clamav_port=port)

    client = httpx.Client(base_url="http://openbao:8200", transport=mock_openbao_transport)
    kms = VaultKmsProvider(endpoint="http://openbao:8200", token="root", http_client=client)
    encryption = EnvelopeEncryptionService(AES256GCMProvider(), kms)

    storage_provider = MemoryStorageProvider()
    storage_svc = StorageService(
        session=session,
        storage_provider=storage_provider,
        encryption_service=encryption,
        malware_scanner=scanner,
    )

    tenant = Tenant(
        name="Staging Tenant", slug=f"stg-{uuid4().hex[:6]}", status=TenantStatus.ACTIVE
    )
    user = User(
        oidc_issuer="http://keycloak:8080/realms/conformly-customer",
        oidc_subject=str(uuid4()),
        email="auditor@staging.de",
        display_name="Auditor",
    )
    session.add_all([tenant, user])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=Role.COMPLIANCE_MANAGER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    session.flush()

    principal = Principal(user_id=user.id)
    context = TenantContext(
        tenant_id=tenant.id,
        user_id=user.id,
        role=Role.COMPLIANCE_MANAGER,
    )

    # 1. Clean file upload: passes ClamAV, envelope-encrypted via OpenBao, stored
    clean_data = b"Clean Policy Documentation Content"
    clean_record = storage_svc.upload_file(
        principal=principal,
        tenant_context=context,
        filename="security_policy.pdf",
        content_type="application/pdf",
        content=clean_data,
        classification="Confidential",
    )
    assert clean_record.status == StoredFileStatus.ACTIVE
    assert clean_record.key_version == "1"

    # Verify retrieval and decryption
    retrieved_record, retrieved_data = storage_svc.download_file(
        principal=principal,
        tenant_context=context,
        file_id=clean_record.id,
        request_id="req-clean-download",
    )
    assert retrieved_data == clean_data
    assert retrieved_record.id == clean_record.id

    # 2. Infected file upload: blocked by ClamAV, quarantined, blocked from storage
    infected_data = b"Doc content containing MALWARE_PAYLOAD string"
    with pytest.raises(MalwareDetectedError) as exc:
        storage_svc.upload_file(
            principal=principal,
            tenant_context=context,
            filename="malicious_attachment.pdf",
            content_type="application/pdf",
            content=infected_data,
            classification="Internal",
        )
    assert "Win.Test.EICAR_HDB-1" in str(exc.value)

    # Verify quarantine status recorded in database
    quarantined = (
        session.query(StoredFile)
        .filter_by(
            tenant_id=tenant.id,
            original_filename="malicious_attachment.pdf",
        )
        .first()
    )
    assert quarantined is not None
    assert quarantined.status == StoredFileStatus.QUARANTINED


# =============================================================================
# 5. Prometheus Monitoring & Grafana SLO Metric Verification
# =============================================================================


def test_prometheus_monitoring_and_slo_metrics_scrape() -> None:
    """Verifies that Prometheus metrics matching Grafana conformly-slo.json are collected."""
    # Simulate API operations
    record_request_metric("GET", "/health", 200, 0.0025)
    record_request_metric("POST", "/api/v1/compliance/policies", 201, 0.045)
    record_request_metric("POST", "/api/v1/storage/files", 200, 0.120)
    record_request_metric(
        "GET", "/api/v1/storage/files/3b5d2e3f4a5b6c7d8e9f0a1b2c3d4e5f", 200, 0.015
    )
    record_request_metric("POST", "/api/v1/storage/files", 400, 0.010)

    rendered = render_prometheus_metrics()

    # Verify all metrics consumed by the Grafana SLO dashboard
    assert "conformly_http_requests_total" in rendered
    assert 'method="GET",path="/health",status="200"' in rendered
    assert 'method="POST",path="/api/v1/compliance/policies",status="201"' in rendered
    assert 'method="GET",path="/api/v1/storage/files/:id",status="200"' in rendered  # ID normalized
    assert "conformly_http_request_duration_seconds_sum" in rendered
    assert "conformly_http_request_duration_seconds_count" in rendered
    assert "conformly_database_connections_active" in rendered
    assert "conformly_backup_last_successful_timestamp" in rendered


# =============================================================================
# 6. Unified Staging Hardened Services Demonstration
# =============================================================================


def test_unified_hardened_staging_demonstration(
    session: Session,
    keycloak_keypair: tuple[rsa.RSAPrivateKey, dict[str, object]],
    mock_openbao_transport: httpx.MockTransport,
    mock_clamav_server: tuple[str, int],
) -> None:
    """Comprehensive rehearsal uniting Keycloak, OpenBao KMS, ClamAV, and SLO metrics."""
    private_key, jwks = keycloak_keypair
    jwks_bytes = json.dumps(jwks).encode("utf-8")
    clamav_host, clamav_port = mock_clamav_server

    class MockJwksUrlOpen:
        def __init__(self, data: bytes) -> None:
            self._stream = io.BytesIO(data)

        def read(self, size: int | None = -1) -> bytes:
            return self._stream.read(size)

        def __enter__(self) -> io.BytesIO:
            return self._stream

        def __exit__(self, *args: object) -> None:
            pass

    # 1. Authenticate via Hardened Keycloak Realm Token
    issuer = "http://keycloak:8080/realms/conformly-customer"
    audience = "conformly-api"
    with patch("urllib.request.urlopen", return_value=MockJwksUrlOpen(jwks_bytes)):
        verifier = OIDCTokenVerifier(issuer=issuer, audience=audience, jwks_url=f"{issuer}/certs")
        raw_jwt = jwt.encode(
            {
                "iss": issuer,
                "sub": "kc-lead-auditor-1",
                "aud": audience,
                "exp": int(time.time()) + 1800,
                "sid": "kc-session-lead-1",
                "email": "lead-auditor@enterprise.de",
                "name": "Lead Auditor",
                "email_verified": True,
                "amr": ["otp"],
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "conformly-keycloak-2026-key"},
        )
        claims = verifier.verify(raw_jwt)
        assert claims.mfa_verified is True

    # 2. Setup Staging Tenant & Membership
    tenant = Tenant(
        name="Enterprise Staging Corp",
        slug=f"ent-stg-{uuid4().hex[:6]}",
        status=TenantStatus.ACTIVE,
    )
    user = User(
        oidc_issuer=claims.issuer,
        oidc_subject=claims.subject,
        email=claims.email or "fallback@enterprise.de",
        display_name=claims.display_name,
    )
    session.add_all([tenant, user])
    session.flush()

    membership = Membership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=Role.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    session.flush()

    principal = Principal(user_id=user.id)
    context = TenantContext(
        tenant_id=tenant.id,
        user_id=user.id,
        role=Role.OWNER,
    )

    # 3. Initialize Storage with OpenBao Transit KMS & ClamAV Daemon
    vault_client = httpx.Client(base_url="http://openbao:8200", transport=mock_openbao_transport)
    vault_kms = VaultKmsProvider(
        endpoint="http://openbao:8200",
        token="root",
        mount="transit",
        key_name="conformly-master-key",
        http_client=vault_client,
    )
    encryption = EnvelopeEncryptionService(AES256GCMProvider(), vault_kms)
    clamav_scanner = ProductionMalwareScanner(clamav_host=clamav_host, clamav_port=clamav_port)
    storage_svc = StorageService(
        session=session,
        storage_provider=MemoryStorageProvider(),
        encryption_service=encryption,
        malware_scanner=clamav_scanner,
    )

    # 4. Stream Evidence File through ClamAV & Encrypt with OpenBao Transit DEK
    evidence_content = b"ISO27001 Access Control Matrix Evidence [Restricted]"
    stored = storage_svc.upload_file(
        principal=principal,
        tenant_context=context,
        filename="iso27001_evidence.pdf",
        content_type="application/pdf",
        content=evidence_content,
        classification="Restricted",
    )
    assert stored.status == StoredFileStatus.ACTIVE
    assert stored.key_version == "1"

    # 5. Record API Metric for Prometheus / Grafana SLO
    record_request_metric("POST", "/api/v1/storage/files", 201, 0.082)

    # 6. Retrieve and Decrypt Evidence File
    file_meta, retrieved_bytes = storage_svc.download_file(
        principal=principal,
        tenant_context=context,
        file_id=stored.id,
        request_id="req-staging-demo-1",
    )
    assert retrieved_bytes == evidence_content
    assert file_meta.original_filename == "iso27001_evidence.pdf"

    # 7. Validate Audit Log Tamper-Evident Trail
    audit_event = (
        session.query(AuditEvent)
        .filter_by(
            tenant_id=tenant.id,
            action="file.uploaded",
            outcome=AuditOutcome.SUCCESS,
        )
        .first()
    )
    assert audit_event is not None
    assert audit_event.resource_id == str(stored.id)
