# Demo deployment — 2026-09-13

Status: IN PROGRESS; this is not a framework content approval.

Target: authorized development server 192.168.0.5, existing Conformly stack only.
Preserve its environment, encryption keys, data, existing canonical releases and tenant adoptions.
The unrelated scheduler stack must not be modified.

Preflight found schema 0025 and five legacy released packs. The new six-pack content will be
imported as separately versioned DRAFTS. No synthetic reviewer approval or automatic tenant
adoption is authorized by this deployment.

Verification fixes: align three outdated tests with ISO 9001 admission; explicitly return an
approved version to draft before amending its blocked coverage in the lifecycle test.
Migration 0030 closes missing database RLS on tenant_applicability_profiles introduced by 0027;
this implements the existing strict tenant-isolation requirement without changing product scope.

The PostgreSQL clone rehearsal rejected ISO 9001's 282-character rights notice against the
255-character field (SQLite did not enforce this limit). Migration 0031 widens content_rights
to Text without truncating the notice. The first rehearsal draft import rolled back atomically.

Deployment requires a database backup, preserved previous images/configuration, staged migration
verification, matching API/frontend builds, framework-count checks and post-deployment health checks.
