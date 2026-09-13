# Conformly — Engineering Overview & Operational Guide

Conformly has reached **100% milestone completion** across all 10 phases of `docs/BUILD_PLAN.md`.

Conformly is a production-hardened, multi-tenant compliance operations and pre-audit readiness SaaS platform.

## Architecture & Source of Truth

Read these architectural and product standards before making modifications:
1. `AGENTS.md` — Core invariants, data classifications, mandatory tenant isolation, and security rules.
2. `docs/BUILD_PLAN.md` — Complete verification checklist and completion gates (100% complete).
3. `docs/DECISIONS.md` — Architectural decisions and rationale (D-001 through D-053).
4. `docs/THREAT_MODEL.md` — Comprehensive STRIDE threat model across all platform modules.
5. `docs/runbooks/` — Operational runbooks for deployment, incident response, key compromise, backup/restore, and privacy incidents.

## Key Platform Invariants

- **Product Positioning:** Pre-audit readiness and compliance operations platform, not an accredited certification body.
- **Tenancy:** Server-side isolation via PostgreSQL Row-Level Security (RLS) on every tenant-scoped table.
- **Cryptography:** AES-256-GCM application-layer envelope encryption for all files and Restricted fields. Pluggable production Key Management Service (`VaultKmsProvider` for HashiCorp Vault / OpenBao transit engine).
- **Audit Immutability:** SHA-256 hash chaining (`sequence_number`, `prev_hash`, `event_hash`), Merkle tree roots, and immutable `AuditSeal` records with ORM mutation prevention.
- **Identity & MFA:** Keycloak customer and workforce dual-realm topology with mandatory multi-factor authentication enforcement on privileged roles (`Owner`, `Administrator`, `Compliance Manager`).
- **Whistleblower Add-on:** Preserved as a standalone decoupled add-on, excluded from Core Tier A entry points and navigation. Genuine anonymous reporting with 100,000-iteration PBKDF2-HMAC-SHA256 return secrets, zero IP logging, and strict handler role boundaries.
- **Data Exit & DR:** Deterministic 30-day export window, 90-day multi-table purge across 33 tenant-scoped tables, cryptographic `DeletionProof` generation, and measured disaster recovery rehearsal (RTO <= 4h, RPO <= 1h).
- **Deterministic Automation:** No autonomous AI agents making generative compliance decisions in production workflows.
- **Module A Beta Framework Packs:** 5 core framework packs (`iso-27001`, `gdpr-bdsg`, `nist-csf`, `cis-controls-ig1`, `mvsp`) with 100% technical implementation, coverage ledgers, declarative applicability evaluation, structured evidence generation, and acceptance tests (`ENGINEERING_COMPLETE`). Formal release status is `CONTENT_REVIEW_PENDING` awaiting human legal/compliance review and Product Owner release sign-off (see `docs/MODULE_A_BETA_RELEASE_EVIDENCE.md`).
- **Broader Module A Catalog Status:** The broader planned Module A catalog is **not delivered**. Five expansion candidates (`iso-9001`, `us-ca-ccpa-cpra`, `sa-pdpl`, `jp-appi`, `au-privacy-act`) exist as initial draft packs awaiting explicit Product Owner scope decisions (`OWNER_DECISION_REQUIRED`). All remaining regional coverage (26 EU member states, 49 US states + DC, 21 Arab League nations, and other international jurisdictions) remains classified as post-beta `LATER_A` backlog (see `docs/MODULE_A_BETA_SCOPE.md`). The five beta packs do not represent completion of the whole module.

## Running Verification Checks

### Backend (Python 3.12 / FastAPI)
From `apps/api`:
```bash
ruff check .
ruff format --check .
mypy src tests
pytest -q
alembic upgrade head --sql
```

### Frontend & Shared Workspace (React / TypeScript / Vite)
From repository root:
```bash
npm run lint
npm run typecheck
npm test --workspace @conformly/web -- --run
npm run build
```

## Running the Application Locally

```bash
# 1. Start dependencies & application via Docker Compose
docker compose up --build

# 2. Apply migrations to live PostgreSQL
docker compose exec api alembic upgrade head

# 3. Seed demo tenant and compliance data (development only)
docker compose exec api python -m conformly.dev.seed
```

- API: `http://localhost:8000` (Docs: `/docs`, Readiness: `/health/ready`)
- Web: `http://localhost:3000` (Trust Center: `/?trust-center=<slug>`, Whistleblower: `/?portal=<slug>`)
