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
2. A clean PostgreSQL 16 service with the complete migration sequence applied (`001_foundation.sql` through `007_supplier_offer_item_uniqueness.sql`), followed by verification of the required schema and key constraints.
3. Deterministic frontend dependency installation (`npm ci`) and production build (`npm run build`).
4. Repository hygiene checks that reject tracked runtime `.env` files, generated backup/log artifacts, and private-key material.

Stateful purchase-order and true E2E tests are included in the backend full-regression CI job. CI seeds acceptance data, starts the backend API, applies the complete migration sequence, and then runs `python -m pytest -q tests` against the seeded integration environment.

## True E2E acceptance — 4.23.12H

The true E2E acceptance test is:

`backend/tests/test_true_e2e_vertical_slice.py::test_true_e2e_need_to_payment`

Verified business chain:

Need
→ Need lifecycle
→ Need → Purchase Request
→ Supplier Offer
→ Comparison
→ Purchase Request Approval
→ Supplier Selection
→ Selection Approval
→ Purchase Order
→ Purchase Order Approval
→ Payment

Acceptance evidence:

- Targeted test: **1/1 PASS**.
- Full backend regression after the addition: **198/198 PASS**.
- GitHub Actions Run #28: **SUCCESS**.
- The E2E test performs cleanup of all created entities after execution.
- Payment settlement is not asserted by this continuity test; payment state-transition behavior remains covered by the dedicated payment acceptance tests.
