# Conformly — Deployment & Zero-Downtime Rollback Runbook

## 1. Overview & Purpose
This runbook governs the continuous delivery, staged deployment, database migration execution, and rollback procedures for **Conformly** in staging and production environments.

Conformly enforces strict tenant isolation, application-layer envelope encryption, PostgreSQL Row-Level Security (RLS), and zero-downtime operational availability.

---

## 2. Environment Isolation & Profiles

| Environment | Database | Storage | KMS / Secret Provider | Network / Ingress |
| :--- | :--- | :--- | :--- | :--- |
| **Development** | Local Docker PostgreSQL / SQLite (test) | Memory / Local filesystem | `LocalKeyManagementProvider` (env KEKs) | `http://localhost:3000`, `8000` |
| **Staging** | Managed PostgreSQL (Aurora/RDS) with RLS | S3 / MinIO with server-side encryption | AWS KMS / Vault KMS provider | TLS 1.3, internal VPN, test IdP |
| **Production** | Multi-AZ Managed PostgreSQL with RLS & read replicas | S3 Multi-region versioned bucket | Hardware KMS (HSM-backed) envelope keys | TLS 1.3, Cloudflare/WAF, strict CSP |

---

## 3. Pre-Deployment Verification Checklist

Before promoting any build to staging or production:
1. **Clean Test Suite:** All backend unit & integration tests (`pytest`) pass with zero regressions.
2. **Strict Type-Checking:** `mypy src tests` passes with 0 errors.
3. **Lint & Code Format:** `ruff check .` and `ruff format --check .` pass.
4. **Frontend Verification:** Vitest suite, ESLint, TypeScript check (`tsc -b`), and `vite build` pass.
5. **Alembic Offline SQL Review:**
   ```bash
   alembic upgrade head --sql > /tmp/deployment_migration.sql
   ```
   Inspect the generated SQL to verify:
   - No destructive `DROP TABLE` or `DROP COLUMN` on active tenant tables.
   - Backward-compatible column additions (`DEFAULT` values, nullable additions).
   - Tenant RLS policies are enabled and enforced on any new tables.
   - `alembic_version` widening remains intact.

---

## 4. Controlled Deployment Sequence

Conformly uses an **expand-and-contract** migration pattern for zero downtime.

```
[Phase 1: Expand Migration] -> [Phase 2: Canary/Rolling API Deployment] -> [Phase 3: Web App Deploy] -> [Phase 4: Contract Migration]
```

### Step 1: Pre-Deployment Database Migration
Run database migrations from an isolated migration runner container:
```bash
docker compose run --rm migrate alembic upgrade head
```
Verify the current schema revision:
```bash
docker compose run --rm migrate alembic current
```

### Step 2: Rolling API Deployment
Deploy the new API container image with rolling updates (minimum 50% healthy instances maintained):
1. New container instances boot and execute the `/health/ready` probe.
2. Load balancer routes traffic only after `/health/ready` returns HTTP 200:
   ```json
   {
     "status": "ok",
     "service": "conformly-api",
     "database": "connected",
     "storage": "connected"
   }
   ```
3. Old instances receive `SIGTERM`, drain active requests gracefully (within a 30-second window), and terminate.

### Step 3: Web Frontend Deployment
Deploy static assets to CDN / hosting bucket with hashed bundle filenames (`dist/assets/index-[hash].js`), ensuring existing user sessions do not experience broken asset loads.

### Step 4: Post-Deployment Smoke Test
Run automated synthetic health checks:
```bash
curl -f https://api.conformly.com/health/live
curl -f https://api.conformly.com/health/ready
```

---

## 5. Rollback Procedures

If critical defects or telemetry spikes occur during the canary or deployment window:

### Scenario A: API / Frontend Code Defect (No Database Schema Changes)
1. **Revert Frontend CDN:** Point CDN distribution to previous release asset manifest.
2. **Revert API Containers:** Roll back deployment to previous Docker image tag:
   ```bash
   kubectl rollout undo deployment/conformly-api
   # or
   docker compose up -d --no-deps api
   ```
3. Verify `/health/ready` on restored instances.

### Scenario B: Database Migration Requires Downgrade
If a migration was applied and must be rolled back:
1. Confirm the downgrade target migration hash:
   ```bash
   alembic history -n 3
   ```
2. Generate downgrade SQL before executing to inspect risks:
   ```bash
   alembic downgrade <target_hash> --sql
   ```
3. Execute downgrade:
   ```bash
   alembic downgrade <target_hash>
   ```
4. Verify application functionality and review database logs for lock contention.

---

## 6. Worker Draining & Graceful Shutdown
1. API worker processes handle `SIGTERM` gracefully via FastAPI lifespan.
2. In-flight HTTP requests and streaming export ZIP downloads are permitted 30 seconds to finish.
3. Background workers (`run_retention_lifecycle`, notification workers) complete their current batch before stopping.
