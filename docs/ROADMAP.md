# BIZAZ Roadmap

## Document control

- Current synchronization: 2026-09-26
- Confirmed version-control baseline: `23d0c80` — `chore: establish BIZAZ v0.1 production baseline`
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

Goal: deliver the missing buyer-to-supplier acquisition flow ahead of additional order features.

Acceptance gates:

- An authorized buyer can create, list, view, and update a purchase request within its company boundary.
- An eligible supplier can submit and revise an offer only for a visible request.
- Offer comparison and explicit supplier selection are available to the buyer.
- Authorization, company isolation, validation errors, and audit events have automated coverage.
- An integration test proves: buyer request → supplier offer → comparison → selection → purchase-order creation.

### 4.23.4 — Frontend integration for the delivered vertical slice

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
