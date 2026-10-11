# BIZAZ Roadmap

## Document control

- Current synchronization: 2026-10-11
- Historical product-development baseline: `25d1bc8` — `test: add true e2e need to payment vertical slice`.
- Current delivery integration merge baseline: `0ca7a9b` — PR #1 merged into `master`; the delivery frontend, company-scoped receiver selection, terminal-state guard, purchase-order unit normalization, and uncapped API-reported pagination are included.
- Post-merge GitHub Actions Run #74 passed all four quality gates on `0ca7a9b`; backend regression: 211 passed, 51 dependency deprecation warnings, no failures.
- Local Windows checkout was fast-forwarded to `master`; the working tree was clean after synchronization. Local health and full backend regression were verified.
- Rule: a stage is complete only with recorded acceptance evidence; a planned capability is not represented as delivered.

## Product roadmap

1. Project Foundation — v0.1
2. Business Model — v0.2
3. MVP Scope — v0.3
4. Technical Architecture — v0.4
5. Database — v0.5
6. Backend — v0.6
7. API — v0.7
8. Authentication — v0.8
9. Company Management — v0.9
10. Product & Service Catalog — v0.10
11. Procurement — v0.11
12. Tender — v0.12
13. Supplier Offers — v0.13
14. Orders — v0.14
15. Payments — v0.15
16. Messaging — v0.16
17. Notifications — v0.17
18. Reviews — v0.18
19. KPI — v0.19
20. Dashboard — v0.20
21. Security — v0.21
22. Automated Testing — v0.22
23. Deployment — v0.23
24. Pilot — v0.24
25. Commercial MVP — v1.0
26. Post-MVP development — v1.x+

## Completed operational milestones

| Stage | Status | Confirmed outcome |
|---|---|---|
| 4.18 | Complete | PostgreSQL backup operations, archive validation, SHA256 evidence, and three backup locations are defined and operationally tested. |
| 4.19 | Complete | Daily backup scheduling and retention controls are defined in the production runbook. |
| 4.20 | Complete | Backup monitoring, alert conditions, and a 15-minute monitoring interval are defined and operationally tested. |
| 4.21 | Complete | Controlled database recovery, isolated DR restore, incident response, RPO, and RTO procedures are documented and tested. |
| 4.22 | Complete | Production change control, security governance, audit-evidence requirements, and repository hygiene are established. |
| 4.22.9 | Complete / PASS | Production Operations & Governance final audit closed with version-controlled baseline `23d0c80`. The last recorded operational state is healthy; current live checks remain required before any production change. |

## Next stage — 4.23 Product development

### 4.23.1 — Roadmap & Status Synchronization

Status: Complete / PASS (this document set).

Acceptance gates:

- `ROADMAP.md`, `STATUS.md`, `MVP-SCOPE.md`, `PRODUCTION-RUNBOOK.md`, and `INCIDENT-RESPONSE.md` identify the same production baseline and governance status.
- The obsolete claim that Git/version control is uninitialized is removed from operational documents.
- Completed operational stages 4.18–4.22.9 and their evidence boundary are recorded without inventing unverified live results.
- The next delivery slice and its measurable acceptance gates are defined.
- Documentation diff passes `git diff --check` and is committed from a clean working tree.

### 4.23.2 — CI/CD quality gate

Status: Complete / PASS. GitHub Actions verified all quality-gate jobs for commit `e2e10f8`.

Goal: make the existing backend test job a release gate and add checks for Python syntax, frontend build, migration safety, and secret/security hygiene.

Acceptance gates:

- Pull requests and pushes run all required checks automatically.
- Backend tests, frontend production build, and migration validation pass in CI.
- A failed check blocks the documented release path.
- No credentials or generated backup artifacts are committed.

### 4.23.3 — Procurement request to supplier offer

Status: Complete / PASS (backend vertical slice implemented and regression-verified).

Goal: deliver the buyer-to-supplier acquisition flow ahead of additional order features.

Acceptance gates:

- An authorized buyer can create, list, view, and update a purchase request within its company boundary.
- An eligible supplier can submit and revise an offer only for a visible request.
- Offer comparison and explicit supplier selection are available to the buyer.
- Authorization, company isolation, validation errors, and audit events have automated coverage.
- An integration test proves: buyer request → supplier offer → comparison → selection → purchase-order creation.

### 4.23.4 — Frontend integration for the delivered vertical slice

Status: Complete / PASS (frontend flow implemented, production build passed, and integration acceptance recorded in the current baseline).

Acceptance gates:

- Authenticated users can complete the 4.23.3 flow in the UI without direct API calls.
- API errors, loading states, and forbidden actions have usable UI handling.
- The production frontend build passes and the flow is verified against an integration environment.

## 4.23.5 - Need & Approval Engine and control hardening

Status: Complete / PASS (delivered and regression-verified).

Delivered scope:

- Need creation, lifecycle, and Need -> Purchase Request conversion.
- Approval engine database/models, request API, decision API, and response schemas.
- Approval gates integrated for Purchase Request, Supplier Offer, Offer Selection, Purchase Order, and Need.
- Cross-company isolation and unsupported-entity handling covered by automated tests.
- Approval audit integrity and unauthorized-action behavior covered by automated tests.
- Domain-state consistency covered: approval decisions do not implicitly mutate controlled business state.
- Terminal-status and stale/re-approval precedence behavior covered for integrated approval gates.
- Approval request detail read endpoint and cross-company detail isolation covered.

Acceptance evidence:

- Current full backend regression: 91 passed.
- Current regression warning count: 84 dependency deprecation warnings; no test failures.
- Development checkpoint before this documentation update: dad115d.

### 4.23.6 - Need & Approval Frontend Integration

Status: Complete / PASS (implemented and manually verified).

Delivered scope:

- Need creation frontend is available at `/needs/new`.
- Dashboard provides navigation to the Need creation flow.
- Frontend API references are unified to port 8001.
- Need lifecycle is usable through the frontend: DRAFT -> SUBMITTED -> UNDER_REVIEW -> APPROVED.
- Need approval request creation, approval detail retrieval, and approval decision are available in the frontend.
- Approval completion does not implicitly change the Need domain status.
- Explicit Need approval action changes the Need from UNDER_REVIEW to APPROVED.
- Terminal approval UI hides approve/reject actions after the approval is completed.

Acceptance evidence:

- Manual browser verification of Need creation and lifecycle: PASS.
- Manual verification of Approval creation and approval decision: PASS.
- Manual verification of explicit Need approval after approval decision: PASS.
- Terminal approval UI behavior: PASS.
- Next.js production build: PASS (13/13 routes).
- Backend full regression: 91/91 PASS.
- Development code checkpoint: 9ff508a.

### 4.23.7 - Frontend Localization

Status: Complete / PASS (implemented and regression-verified).

Delivered scope:

- User-visible frontend action and navigation texts localized to Azerbaijani.
- Home, Dashboard, Login, Company, Products, Purchase Requests, Need/Approval, and Supplier Offers frontend texts were reviewed and localized.
- Approval and Purchase Order display labels were localized without changing backend/API enum values or code identifiers.
- Frontend localization changes were kept isolated from business logic and API contracts.

Acceptance evidence:

- Next.js production build: PASS (13/13 routes).
- Full backend regression: 91/91 PASS.
- Regression warnings: 84 dependency deprecation warnings; no test failures.
- Clean Git working tree after checkpoint.
- Development code checkpoint: 921d2d3.

### 4.23.8 - Python Backend Code Audit & UTF-8 Hardening

Status: Complete / PASS (audited and regression-verified).

Delivered scope:

- Python backend application and test files passed compile-time syntax validation.
- AST syntax audit passed after removal of an unexpected UTF-8 BOM from `backend/app/models.py`.
- Duplicate top-level definitions audit found no duplicates.
- API route audit found no duplicate application routes across the audited backend.
- Backend behavior remained regression-safe after the encoding cleanup.

Acceptance evidence:

- Python compileall: PASS.
- AST syntax audit: PASS.
- Audited Python files: 5.
- Registered application routes audited: 42.
- Duplicate top-level definitions: none.
- Duplicate application routes: none.
- Full backend regression: 91/91 PASS.
- Regression warnings: 84 dependency deprecation warnings; no test failures.
- Development code checkpoint: 2daf1d5.

### 4.23.9 - UTF-8 Encoding Hardening

Status: Complete / PASS (implemented and regression-verified).

Delivered scope:

- Corrupted Azerbaijani characters in backend user-facing messages were restored to valid UTF-8 text.
- UTF-8 BOM markers were removed from the affected Python test files and frontend comparison page.
- Product default unit text was restored from corrupted `?d?d` to `?d?d`.
- Static corrupted-string audit reported no remaining affected Python string literals.
- No business logic or API contract changes were introduced.

Acceptance evidence:

- Final corrupted-string audit: PASS (NONE).
- UTF-8 BOM audit: PASS (NONE).
- Unicode replacement-character audit: PASS (NONE).
- Python compileall: PASS.
- Full backend regression: 91/91 PASS.
- Regression warnings: 84 dependency deprecation warnings; no test failures.
- Development code checkpoint: c7a8997.

### 4.23.10 - Payment Engine Hardening

Status: Complete / PASS (implemented and regression-verified).

Delivered scope:

- Duplicate payment reference handling at API level with HTTP 409.
- Transaction rollback on duplicate reference conflicts before returning the business-level error.
- Payment creation role enforcement for `OWNER`, `ADMIN`, and `PROCUREMENT`.
- Payment status operation role enforcement.
- Preservation of cross-company isolation and payment state-machine controls.
- Regression coverage for payment reference conflicts and payment RBAC.

Acceptance evidence:

- Targeted duplicate-reference test: PASS.
- Payment creation RBAC: PASS.
- Payment status RBAC: PASS.
- Payment acceptance suite: 38/38 PASS.
- Full backend regression: 193/193 PASS.
- `git diff --check`: PASS.
- GitHub Actions Run #18 for commit `2ae1cb9`: SUCCESS.
- All four CI jobs passed.
- Regression warnings: 44 dependency deprecation warnings; no test failures.

### 4.23.11 - Residual UTF-8 Model/Test Hardening

Status: Complete / PASS (implemented and regression-verified).

Delivered scope:

- Corrected residual mojibake model defaults for `Product.unit` and `PurchaseOrderItem.unit`.
- Added regression coverage for both model defaults.
- Removed UTF-8 BOM from the new regression test file.
- Verified the corrected model values independently of shell encoding.

Acceptance evidence:

- Targeted tests: **2/2 PASS**.
- Full backend regression: **195/195 PASS**.
- BOM audit: PASS.
- Python compileall: PASS.
- `git diff --check`: PASS.
- GitHub Actions Run #21: **SUCCESS**.
- All four CI jobs passed.
- Regression warnings: 44 dependency deprecation warnings; no test failures.
- Code checkpoint: `f38a572`.

### 4.23.12F — Frontend Dependency Security Hardening

Status: Complete / PASS.

Acceptance evidence:

- Next.js `15.5.27`.
- PostCSS override `8.5.28`.
- Sharp override `0.35.5`.
- `npm audit --audit-level=low`: **0 vulnerabilities**.
- Clean `npm ci`: PASS.
- Next.js production build: **13/13 routes PASS**.
- Full backend regression: **197/197 PASS**.
- GitHub Actions Run #24: **SUCCESS** for commit `d17739a`.

### 4.23.12G — CI Security Enforcement

Status: Complete / PASS.

Acceptance evidence:

- Explicit frontend `npm audit --audit-level=low` CI gate added before production build.
- Local security-gate verification: PASS.
- GitHub Actions Run #25: **SUCCESS** for commit `b6d3698`.
- Frontend Security audit: **SUCCESS**.
- Frontend production build: **SUCCESS**.
- Backend syntax and full regression: **SUCCESS**.
- PostgreSQL migration smoke check: **SUCCESS**.
- Repository hygiene: **SUCCESS**.

### 4.23.12H — True E2E Vertical Slice & Acceptance Hardening

Status: Complete / PASS.

Delivered scope:

- Added a true end-to-end acceptance test for the integrated procurement-to-payment path.
- Verified Need lifecycle and Need → Purchase Request conversion.
- Verified Supplier Offer submission and Offer Comparison.
- Verified Purchase Request approval through the Approval Engine.
- Verified explicit Supplier Offer Selection and its Approval Engine gate.
- Verified Purchase Order creation, submission, and Approval Engine approval.
- Verified Payment record creation and resulting PENDING payment state.
- Added deterministic cleanup for all entities created by the E2E test.

Acceptance evidence:

- Test: `backend/tests/test_true_e2e_vertical_slice.py::test_true_e2e_need_to_payment`.
- Targeted E2E test: **1/1 PASS**.
- Full backend regression: **198/198 PASS**.
- GitHub Actions Run #28 for commit `25d1bc8`: **SUCCESS**.
- All four CI jobs passed.
- No production application code was changed by this slice; the delivered change is the E2E acceptance test.


### 4.23.13 — Delivery Frontend Integration

Status: Complete / PASS — merged to `master` in PR #1 on 2026-10-11 (`0ca7a9b2b3d86a69a38c5ffefc007f739184b4e3`).

Delivered scope:

- Delivery registry UI at `/deliveries` and dashboard navigation.
- Delivery creation from `APPROVED` purchase orders only.
- Delivery-item entry with quantity/remaining-quantity validation hints.
- Status updates limited in the UI to the backend's existing transition contract.
- Company-scoped list of active members for the required `received_by` field.
- API-level guard returns HTTP 409 when attempting to add an item to a `DELIVERED` or `CANCELLED` delivery; regression coverage tests both cases. The database trigger already enforces the underlying terminal-state quantity invariant.
- Regression test for the member endpoint's company scope and active-user filter.

Acceptance evidence:

- GitHub Actions Run #74 for merge commit `0ca7a9b`: **SUCCESS**; all four quality gates passed. PR validation Run #73 attempt 2 also passed all four jobs.
- Backend syntax and full regression: **211 passed**, 51 dependency deprecation warnings and no failures.
- Local Windows regression: **211 passed**, 51 dependency deprecation warnings, no failures; local `/health` returned `status=ok` after starting the normal server.
- Terminal-state item-add regression covers `CANCELLED` and `DELIVERED`.
- Frontend security audit: PASS.
- Frontend production build: PASS.
- Repository hygiene: PASS.
- No database migration changes.
- Local browser acceptance passed on 2026-10-11: delivery creation, item entry, PLANNED → DISPATCHED → IN_TRANSIT → DELIVERED, receiver selection, and `2 ədəd` display.
- Pagination review finding was fixed in commit `853b56d`: `loadAllPages` no longer silently stops at 100 pages.
- PR #1 was merged into `master`; merge commit `0ca7a9b2b3d86a69a38c5ffefc007f739184b4e3`.


### 4.23.14 — Purchase Order Unit Corruption Guard

Status: Complete / PASS — normalization helper and terminal-state regression were verified locally; merge CI passed.

Delivered scope:

- Confirmed the malformed unit originates in an acceptance-test helper that explicitly passed `"?d?d"`; the API previously persisted the received string. The evidence does not establish a general PostgreSQL UTF-8 failure.
- Kept valid caller-supplied units unchanged.
- Added a backend fallback to the associated product's catalogue unit when purchase-order item input contains question-mark corruption or the Unicode replacement character.
- Covered direct Purchase Order creation, item replacement during Purchase Order update, and procurement offer-selection → Purchase Order creation.
- Corrected the reusable acceptance helper to use the Unicode-escaped Azerbaijani default and added a regression test for malformed unit input.

Acceptance evidence:

- New regression test: `backend/tests/test_purchase_orders_acceptance.py::test_18_corrupted_purchase_order_unit_falls_back_to_product_unit`.
- GitHub Actions Run #54 for commit `e6068ca`: **SUCCESS**.
- Backend syntax and full regression, PostgreSQL migration smoke check, frontend production build, and repository hygiene: all PASS.
- No database migration and no mutation of the existing delivered local test record.
- Local helper check passed: corrupted `?d?d` normalizes to the product catalogue unit `ədəd`.
- The terminal-state targeted regression passed locally: **2/2** for `CANCELLED` and `DELIVERED`; the full backend regression passed **211/211**.
- Post-merge GitHub Actions Run #74 and PR validation Run #73 attempt 2 passed all four quality gates.


## 4.23.15 — Reviews & Ratings

**Status: Complete / PASS — merged to `master` in PR #2 on 2026-10-11.**

Merge commit: `4f7369663802bd49296055694b00bf34a7d8bbc9`.

Delivered scope:

- Additive PostgreSQL migration `014_review_ratings.sql` and SQLAlchemy `Review` model.
- Tenant-scoped POST/GET/PATCH review APIs for a Purchase Order and paginated supplier review-list API.
- Batch endpoint `POST /api/v1/reviews/summary` returns reviews for tenant-owned Purchase Orders and per-supplier rating aggregates without one detail request per order.
- Review creation is limited to eligible, fully delivered Purchase Orders, active users, and the `OWNER`, `ADMIN`, and `PROCUREMENT` roles.
- One review per Purchase Order, integer rating 1–5, optional plain-text comment up to 2000 characters, 24-hour author-edit window, and audit events.
- Azerbaijani `/reviews` frontend integrated with the dashboard. Delivery records use server pagination (100 per page) rather than unbounded concurrent page requests.
- Acceptance tests cover eligibility, duplicate prevention, create/read/list/update, audit events, validation, concurrent duplicate submissions, RBAC, edit-window enforcement, batch summary behavior, and tenant isolation.

Acceptance evidence:

- Local browser acceptance: review created, shown in the list, edited from 5/5 to 4/5, and comment updated; the review remained visible after refreshing.
- Local browser Network inspection: `POST /api/v1/reviews/summary` returned HTTP 200.
- Local migration applied to the backend's active `bizaz_procurement_test` database after a validated backup; the `reviews` table and eight constraints were verified.
- Latest pre-merge CI Run #109 (workflow run `38167889764`): all four quality gates passed; backend regression **221 passed**, 56 dependency deprecation warnings, no failures.
- Post-merge GitHub Actions Run #111 (`38169190885`) for merge commit `4f7369663802bd49296055694b00bf34a7d8bbc9`: **SUCCESS**, all four quality gates passed; backend regression **221 passed**, 56 warnings, no failures.
- Codex review of head `0309e80`: “Didn't find any major issues”; the two rate-limit findings were addressed and their review threads resolved.

The review/rating MVP is tenant-scoped. Public/global supplier reputation, review withdrawal, and moderation remain out of scope until supplier identity and product policy are separately designed.

### Next planned slice — 4.23.16 Basic Notifications

Status: **Implementation in progress** on `feature/basic-notifications`; Product Owner approved the MVP policy decisions on 2026-10-11.

Goal: deliver reliable, tenant-scoped notifications for existing procurement workflows before beginning the core KPI dashboard.

Accepted contract: `docs/BASIC-NOTIFICATIONS-SPEC.md`. Scope is in-app-only, tenant-scoped recipient resolution, actionable Approval notifications, request/offer/order/delivery/payment status notifications, inbox/unread-count/mark-as-read APIs, idempotent creation, and 180-day retention with daily purge owned by the BIZAZ system administrator. External supplier-user notifications remain out of scope until canonical supplier identity exists.

Acceptance gates:

- Only authorized users in the relevant company receive workflow notifications.
- Notification creation is transactionally consistent or safely idempotent with its source event.
- List, unread count, and mark-as-read APIs enforce tenant boundaries.
- Frontend shows the notification list, unread count, empty/loading/error states, and mark-as-read actions in Azerbaijani.
- Tests cover recipient resolution, cross-company isolation, duplicate delivery, unread count, and read-state changes.
- All four CI quality gates pass; production frontend build and repository hygiene pass.
