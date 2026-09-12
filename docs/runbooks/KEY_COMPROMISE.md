# Conformly — Key Compromise & Cryptographic Rotation Runbook

## 1. Overview & Architecture
Conformly uses **server-side envelope encryption** with AES-256-GCM for all `Restricted` fields, whistleblower message payloads, and stored files:
- **Key Encryption Key (KEK):** Master key managed in a KMS or versioned local keystore (`CONFORMLY_LOCAL_KEKS`).
- **Data Encryption Key (DEK):** Generated uniquely per field or per file, used to encrypt plaintext with AES-256-GCM, then wrapped with the active KEK and stored alongside the ciphertext.
- **Token Pepper:** Kept exclusively in memory/environment (`CONFORMLY_INVITATION_TOKEN_PEPPER`), never written to database tables.

This architecture ensures that a KEK rotation does **not** require re-encrypting all underlying files or databases simultaneously, but rather allows phased re-wrapping of DEKs or phased dual-key decryption.

---

## 2. Key Compromise Severity Assessment

| Compromise Scope | Threat Level | Immediate Impact | Mitigation Priority |
| :--- | :--- | :--- | :--- |
| **KEK Compromise** | Critical (SEV-1) | Attacker possessing database access could unwrap DEKs. | Immediate KEK deprecation & re-wrapping. |
| **DEK Compromise** | High (SEV-2) | Affects only a single field or stored file. | Immediate re-encryption of the affected entity. |
| **Token Pepper Compromise** | High (SEV-2) | Weakens brute-force protection of pending invite tokens. | Invalidate all pending invitations & rotate pepper. |

---

## 3. KEK Rotation & Retirement Procedure

Conformly's crypto providers support **versioned KEKs** (e.g. `v1`, `v2`, `v3`).

```
[1. Provision New KEK v(N+1)] -> [2. Deploy with Dual-Read Config] -> [3. Promote to Active Write Key] -> [4. Background DEK Re-Wrap] -> [5. Deprecate v(N)]
```

### Step 1: Generate & Provision New KEK
Generate a cryptographically secure 256-bit key:
```bash
# Example generating high-entropy base64 key
openssl rand -base64 32
```
Provision the new key in KMS or environment:
```env
CONFORMLY_LOCAL_KEKS={"v1": "<old_b64>", "v2": "<new_b64>"}
CONFORMLY_ACTIVE_KEK_VERSION=v2
```

### Step 2: Deploy Dual-Key Configuration
Deploy the application with both keys configured. The `LocalKeyManagementProvider` (or KMS provider) automatically:
- Uses `active_kek_version` (`v2`) for all **new encryption operations**.
- Decrypts existing encrypted DEKs using the version indicated in the payload metadata (`v1` or `v2`).

### Step 3: Execute Phased Re-wrapping
To re-wrap existing DEKs with the new KEK:
1. Query records with `encrypted_dek` wrapped with `v1`.
2. Unwrap DEK using `v1`.
3. Wrap DEK using `v2`.
4. Update record transactionally without decrypting the underlying data payload.

### Step 4: Deprecate Compromised KEK
Once all records indicate `v2` wrapping:
1. Remove `v1` from `CONFORMLY_LOCAL_KEKS`.
2. Any subsequent decryption request referencing `v1` will fail immediately with `KeyVersionNotFoundError`.

---

## 4. Token Pepper Rotation Procedure

If `CONFORMLY_INVITATION_TOKEN_PEPPER` is exposed:
1. Invalidate all pending tenant invitations in database:
   ```sql
   UPDATE membership_invitations
   SET status = 'REVOKED'
   WHERE status = 'PENDING';
   ```
2. Generate a new high-entropy random pepper (at least 32 characters).
3. Update `CONFORMLY_INVITATION_TOKEN_PEPPER` in secret manager / environment.
4. Restart API instances.
5. Notify tenant administrators to re-issue pending member invitations.
