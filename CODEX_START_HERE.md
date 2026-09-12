# Conformly — Engineering Overview & Operational Guide

Conformly has reached **100% milestone completion** across all 10 phases of `docs/BUILD_PLAN.md`.

Conformly is a production-hardened, multi-tenant compliance operations and pre-audit readiness SaaS platform.

## Architecture & Source of Truth

Read these architectural and product standards before making modifications:
1. `AGENTS.md` — Core invariants, data classifications, mandatory tenant isolation, and security rules.
2. `docs/BUILD_PLAN.md` — Complete verification checklist and completion gates (100% complete).
3. `docs/DECISIONS.md` — Architectural decisions and rationale (D-001 through D-046).
4. `docs/THREAT_MODEL.md` — Comprehensive STRIDE threat model across all platform modules.
5. `docs/runbooks/` — Operational runbooks for deployment, incident response, key compromise, backup/restore, and privacy incidents.

## Key Platform Invariants

- **Product Positioning:** Pre-audit readiness and compliance operations platform, not an accredited certification body.
- **Tenancy:** Server-side isolation via PostgreSQL Row-Level Security (RLS) on every tenant-scoped table.
- **Cryptography:** AES-256-GCM application-layer envelope encryption for all files, Restricted fields, and sensitive whistleblower data. Zero customer plaintext in logs or deletion proofs.
- **Whistleblower Intake:** Genuine anonymous reporting with 100,000-iteration PBKDF2-HMAC-SHA256 return secrets, zero IP logging, and strict handler role boundaries.
- **Data Exit:** Deterministic 30-day export window, 90-day multi-table purge across 33 tenant-scoped tables, and cryptographic `DeletionProof` generation.
- **Deterministic Automation:** No autonomous AI agents making generative compliance decisions in production workflows.

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
