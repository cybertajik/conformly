# Conformly

Conformly is a multi-tenant compliance operations and pre-audit SaaS platform.

The first paid MVP focuses on deterministic compliance workflows, evidence management, framework/control tracking, pre-audit readiness, anonymous whistleblower reporting, public compliance profiles, and exportable audit-ready records.

## Start Here

Codex and developers should read these files in order:

1. `AGENTS.md`
2. `docs/PRODUCT_SPEC.md`
3. `docs/ARCHITECTURE.md`
4. `docs/SECURITY.md`
5. `docs/DATA_MODEL.md`
6. `docs/MVP_SCOPE.md`
7. `docs/DECISIONS.md`
8. `docs/IMPLEMENTATION_PLAN.md`

## Initial Development Goal

The first implementation milestone is the secure repository foundation, not a polished UI.

Expected initial components:

```text
apps/
  api/
  web/

packages/
  shared/

infra/
  docker/

docs/
```

The actual structure may evolve once implementation begins, but tenant isolation, authorization, encryption, auditability, and testability are non-negotiable.

## Initial Technology Direction

The current implementation direction is:

- Backend: Python + FastAPI
- Frontend: React + TypeScript
- Database: PostgreSQL
- Cache / queue: Redis where needed
- Background processing: deterministic jobs
- Object storage: S3-compatible abstraction
- Containers: Docker
- Migrations: Alembic
- CI: automated lint, type-check, tests, migrations check

These are implementation defaults, not permission to weaken documented security requirements.

## Product Status

Conformly begins as a pre-audit/compliance operations platform, not an accredited certification body.

Customer-facing language must avoid implying formal accreditation unless and until that status is independently established.

## Local development

Prerequisites: Docker with Compose, Node.js 22+, and Python 3.12+.

Start the complete stack:

```bash
cp .env.example .env
docker compose up --build
```

The web application is available at `http://localhost:3000`, the API at
`http://localhost:8000`, and API documentation at `http://localhost:8000/docs`.

Interactive sign-in uses a public OIDC Authorization Code + PKCE client. Configure the backend
issuer, audience, and JWKS URL plus the frontend authorization URL, token URL, client ID, redirect
URI, and scopes shown in `.env.example`. The verified access token must contain `iss`, `sub`,
`sid`, `exp`, `email`, and `email_verified=true`; `name` is optional. Conformly derives tenant
access only from its own membership records. The development fixture command creates no password,
token, or session:

```bash
cd apps/api
python -m conformly.dev.seed
```

Run backend checks from `apps/api` after installing `.[dev]`:

```bash
ruff check .
ruff format --check .
mypy src tests
pytest
alembic upgrade head --sql
```

Run frontend checks from the repository root:

```bash
npm install
npm run lint
npm run typecheck
npm test
npm run build
```
