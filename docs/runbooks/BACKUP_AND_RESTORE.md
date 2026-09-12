# Conformly — Backup, Disaster Recovery & Restore Rehearsal Runbook

## 1. Overview & Recovery Objectives

Conformly maintains continuous backup and disaster recovery mechanisms to ensure customer data durability and business continuity.

### Operational Recovery Targets (Paid Pilot Baseline)
- **Recovery Point Objective (RPO):** Maximum **1 hour** of potential data loss.
- **Recovery Time Objective (RTO):** Maximum **4 hours** to complete restoration of operational services.
- **Contractual SLA Prerequisite:** Per [`AGENTS.md`](file:///c:/Users/AD/Desktop/conformly/AGENTS.md), contractual availability and recovery SLAs will **only** be offered after a minimum of six (6) months of production operational evidence and two (2) verified full-restore rehearsals.

---

## 2. Backup Architecture & Inventory

Conformly's state is distributed across three decoupled layers, each backed up independently with strict encryption:

```
+--------------------------+----------------------------+-----------------------------+
|   PostgreSQL Database    |    Encrypted S3 Storage    |   KMS Keys & Configuration  |
|  - WAL Archiving (Continuous)| - Cross-Region Replication |  - Versioned Key Store      |
|  - Daily Full Base Backups   | - S3 Object Versioning     |  - Infrastructure as Code   |
|  - AES-256 Storage Encryption| - 90-day retention bucket  |  - Zero Secret Git Policy   |
+--------------------------+----------------------------+-----------------------------+
```

### 1. Database Tier (PostgreSQL)
- **Continuous WAL Archiving:** Write-Ahead Logging (WAL) streamed continuously to an isolated, immutable storage bucket via WAL-G / pgBackRest, enabling Point-in-Time Recovery (PITR).
- **Daily Base Snapshots:** Full compressed database dumps taken daily at 02:00 UTC and retained for 30 days.

### 2. Encrypted Object Storage Tier
- **Stored Files:** Original files are already application-layer encrypted with AES-256-GCM envelope encryption prior to reaching the storage bucket.
- **Bucket Lifecycle:** Storage bucket uses S3 Versioning, Object Lock (Compliance Mode), and cross-region replication.
- **Retention Lifecycle:** Deleted objects enter a 30-day soft-delete transition before permanent expiration, aligning with tenant cancellation workflows.

### 3. Key Management & Configuration Tier
- KMS keys (KEKs) and KMS policies are maintained in terraform/IaC with independent versioning.
- Secret tokens (JWT signing keys, OIDC client secrets, token peppers) are backed up within an enterprise secret manager with automated version history.

---

## 3. Tenant Deletion vs Backup Retention Invariant

> [!NOTE]
> **Data Retention Invariant:** When a tenant executes a cancellation and day-90 deletion:
> - Active systems instantly purge all 33 tenant-scoped tables and physical active storage objects.
> - A cryptographic `DeletionProof` receipt is created.
> - Backups expire naturally at the end of their retention lifecycle (30-day WAL retention). Conformly does not claim or attempt immediate forensic erasure from existing immutable backup archives, but rather guarantees that deleted tenant data cannot and will not be restored to active service.

---

## 4. Full Restore Rehearsal Procedure

Every restore rehearsal must be conducted in an isolated staging environment using production backup snapshots:

### Step 1: Provision Isolated Restore Target
Provision an isolated PostgreSQL instance and target storage bucket:
```bash
docker compose -f compose.test-restore.yaml up -d postgres-restore minio-restore
```

### Step 2: Database Restoration
Restore from base snapshot and replay WAL logs up to the rehearsal recovery point:
```bash
pg_restore --clean --if-exists -h localhost -p 5433 -U conformly -d conformly_restored /backups/db_snapshot.dump
```

### Step 3: Object Storage Sync
Verify encrypted object storage replication and synchronization:
```bash
aws s3 sync s3://conformly-prod-backups/objects/ s3://conformly-restore-test/
```

### Step 4: Verification Smoke Test
1. Boot API pointed at the restored database and storage endpoints.
2. Execute automated verification test (`tests/test_backup_restore_rehearsal.py`):
   - Authenticate with pre-existing tenant credentials.
   - Verify tenant isolation and Row-Level Security (RLS).
   - Decrypt sample `Restricted` fields and stored files using active KEK.
   - Verify cryptographic hash match of pre-audit manifests.
3. Record signed evidence in the release audit log (`docs/rehearsals/RESTORE_TEST_YYYYMMDD.md`).
