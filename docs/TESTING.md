# Testing Documentation

Quality gates:
1. Static/syntax checks.
2. Unit tests.
3. API contract tests.
4. Database migration/integration tests.
5. End-to-end buyer/supplier workflow tests.
6. Security tests.
7. Regression suite before release.

A module moves to 🟢 Hazır only when its applicable gates pass.

## CI quality gate — 4.23.2

The GitHub Actions workflow runs on every push and pull request:

1. Python dependency installation, backend source compilation, and isolated health/metadata tests.
2. A clean PostgreSQL 16 service with `001_foundation.sql` applied and its four foundation tables verified.
3. Deterministic frontend dependency installation (`npm ci`) and production build (`npm run build`).
4. Repository hygiene checks that reject tracked runtime `.env` files, generated backup/log artifacts, and private-key material.

The purchase-order acceptance suite is intentionally not included in this isolated CI job yet: it makes stateful requests to a running API and relies on seeded business records. It remains an integration-environment gate until its fixtures are made self-contained.
