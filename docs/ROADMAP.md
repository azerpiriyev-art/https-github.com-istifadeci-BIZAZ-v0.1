# BIZAZ Roadmap

## Document control

- Current synchronization: 2026-09-06
- Confirmed version-control baseline: `23d0c80` вЂ” `chore: establish BIZAZ v0.1 production baseline`
- Rule: a stage is complete only with recorded acceptance evidence; a planned capability is not represented as delivered.

## Product roadmap

1. Project Foundation вЂ” v0.1
2. Business Model вЂ” v0.2
3. MVP Scope вЂ” v0.3
4. Technical Architecture вЂ” v0.4
5. Database вЂ” v0.5
6. Backend вЂ” v0.6
7. API вЂ” v0.7
8. Authentication вЂ” v0.8
9. Company Management вЂ” v0.9
10. Product & Service Catalog вЂ” v0.10
11. Procurement вЂ” v0.11
12. Tender вЂ” v0.12
13. Supplier Offers вЂ” v0.13
14. Orders вЂ” v0.14
15. Payments вЂ” v0.15
16. Messaging вЂ” v0.16
17. Notifications вЂ” v0.17
18. Reviews вЂ” v0.18
19. KPI вЂ” v0.19
20. Dashboard вЂ” v0.20
21. Security вЂ” v0.21
22. Automated Testing вЂ” v0.22
23. Deployment вЂ” v0.23
24. Pilot вЂ” v0.24
25. Commercial MVP вЂ” v1.0
26. Post-MVP development вЂ” v1.x+

## Completed operational milestones

| Stage | Status | Confirmed outcome |
|---|---|---|
| 4.18 | Complete | PostgreSQL backup operations, archive validation, SHA256 evidence, and three backup locations are defined and operationally tested. |
| 4.19 | Complete | Daily backup scheduling and retention controls are defined in the production runbook. |
| 4.20 | Complete | Backup monitoring, alert conditions, and a 15-minute monitoring interval are defined and operationally tested. |
| 4.21 | Complete | Controlled database recovery, isolated DR restore, incident response, RPO, and RTO procedures are documented and tested. |
| 4.22 | Complete | Production change control, security governance, audit-evidence requirements, and repository hygiene are established. |
| 4.22.9 | Complete / PASS | Production Operations & Governance final audit closed with version-controlled baseline `23d0c80`. The last recorded operational state is healthy; current live checks remain required before any production change. |

## Next stage вЂ” 4.23 Product development

### 4.23.1 вЂ” Roadmap & Status Synchronization

Status: Complete / PASS (this document set).

Acceptance gates:

- `ROADMAP.md`, `STATUS.md`, `MVP-SCOPE.md`, `PRODUCTION-RUNBOOK.md`, and `INCIDENT-RESPONSE.md` identify the same production baseline and governance status.
- The obsolete claim that Git/version control is uninitialized is removed from operational documents.
- Completed operational stages 4.18вЂ“4.22.9 and their evidence boundary are recorded without inventing unverified live results.
- The next delivery slice and its measurable acceptance gates are defined.
- Documentation diff passes `git diff --check` and is committed from a clean working tree.

### 4.23.2 вЂ” CI/CD quality gate

Status: Complete / PASS. GitHub Actions verified all quality-gate jobs for commit `e2e10f8`.

Goal: make the existing backend test job a release gate and add checks for Python syntax, frontend build, migration safety, and secret/security hygiene.

Acceptance gates:

- Pull requests and pushes run all required checks automatically.
- Backend tests, frontend production build, and migration validation pass in CI.
- A failed check blocks the documented release path.
- No credentials or generated backup artifacts are committed.

### 4.23.3 вЂ” Procurement request to supplier offer

Goal: deliver the missing buyer-to-supplier acquisition flow ahead of additional order features.

Acceptance gates:

- An authorized buyer can create, list, view, and update a purchase request within its company boundary.
- An eligible supplier can submit and revise an offer only for a visible request.
- Offer comparison and explicit supplier selection are available to the buyer.
- Authorization, company isolation, validation errors, and audit events have automated coverage.
- An integration test proves: buyer request в†’ supplier offer в†’ comparison в†’ selection в†’ purchase-order creation.

### 4.23.4 вЂ” Frontend integration for the delivered vertical slice

Acceptance gates:

- Authenticated users can complete the 4.23.3 flow in the UI without direct API calls.
- API errors, loading states, and forbidden actions have usable UI handling.
- The production frontend build passes and the flow is verified against an integration environment.
