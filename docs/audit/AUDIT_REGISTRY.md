# BIZAZ Audit Registry

Protocol: [BIZAZ Permanent Audit Control Protocol](BIZAZ_AUDIT_CONTROL.md)  
Registry version: 0.1 (initial structure)  
Status: INITIAL / HISTORICAL RECONCILIATION REQUIRED  
Last update: 2026-11-20 (date of registry setup; exact timezone/time not recorded)

> This registry is a controlled index. Historical statuses below are transcribed from available audit history and are not a substitute for original evidence. Unknown commit SHAs, dates, evidence IDs, and runtime results are deliberately left unfilled.

## 1. Active audit queue

| Audit ID | Scope | Current status | Assurance level | Prior audit / overlap | Evidence mapping | Next permitted action |
|---|---|---|---|---|---|---|
| RP-02B.15 | Authentication and Authorization | IN PROGRESS | Source review only | Overlaps historical 4.19.4.x security/RBAC work | NOT YET RECONCILED | Reconcile 4.19.4.x source/evidence before further generic checks; then assess only documented deltas |
| RP-02B | Production Deployment Configuration | Source review complete for .1–.14; .15 in progress | Source review only; runtime UNKNOWN | Prior deployment and security audits may overlap | Conversation audit history; primary artifact index pending | Do not repeat .1–.14 on unchanged baseline; reconcile findings and establish baseline |
| RP-02A | Migration and Deployment Mechanism | Source review complete | Source review only; production readiness NOT ESTABLISHED | Migration/CI audit history | Conversation audit history; primary artifact index pending | No repeat of manifest/validator review unless relevant changes or evidence gap |

## 2. Historical audit families

| Audit ID / family | Historical status reported | Current treatment | Revalidation trigger |
|---|---|---|---|
| 4.17.x structural, transaction, concurrency, security, tenant isolation, RBAC and audit integrity | PASS reported historically | PRESERVE; primary evidence and exact baseline not yet reconciled | Relevant code/schema/config change, incident, failed evidence, changed criteria, owner request |
| 4.19.4.1–4.19.4.10 Security / Authorization / RBAC | CLOSED/PASS reported historically | PRESERVE; reconcile original artifacts before relying on current baseline | Relevant auth/RBAC/tenant code or tests changed, incident, evidence contradiction |
| PGEMS WP-00 | UNKNOWN | Keep UNKNOWN | Authorized read-only verification |
| PGEMS WP-01 | Owner dispositions recorded | Preserve dispositions; reconcile Journal and Source Map evidence | Authorized evidence append/review |
| AL-01–AL-06 audit_log protection | OPEN / deferred remediation | Keep open; separate remediation authorization required | Explicitly authorized remediation and verification |

## 3. RP-02B work breakdown

| Sub-audit | Scope | Status | Assurance | Notes |
|---|---|---|---|---|
| RP-02B.1–.4 | Compose, Dockerfiles, Caddy, role bootstrap, deployment docs, backup/restore | SOURCE REVIEW COMPLETE | Source only | Live server, backup target and restore execution not verified |
| RP-02B.5 | Backend health/readiness | SOURCE REVIEW COMPLETE | Source only | Runtime behavior not verified |
| RP-02B.6 | Ignore rules and Docker build context | SOURCE REVIEW COMPLETE | Source only | Findings F11–F13 recorded historically |
| RP-02B.7 | Environment and secret handling | SOURCE REVIEW COMPLETE | Source only | Real environment values intentionally not inspected |
| RP-02B.8–.10 | Container hardening, network, logging/observability | SOURCE REVIEW COMPLETE | Source only | Runtime and monitoring not verified |
| RP-02B.11 | Image supply chain and CI security | SOURCE REVIEW COMPLETE | Source only | Registry, signing, SBOM and runtime evidence not established |
| RP-02B.12 | Dependency security and pinning | SOURCE REVIEW COMPLETE | Source only | Backend lock/hash/security scanning gaps remain |
| RP-02B.13 | GitHub security automation inventory | SOURCE REVIEW COMPLETE | Repository config only | GitHub server-side settings not inspected |
| RP-02B.14 | TLS, HTTP headers and CORS | SOURCE REVIEW COMPLETE | Source only | Runtime TLS/headers/origin not verified |
| RP-02B.15 | Authentication, authorization, tenant context, approval | IN PROGRESS | Source review only | Historical overlap reconciliation required |

## 4. Registry rules

- No audit is marked CLOSED/PASS in this registry solely because a prior conversation summary says so; retain the wording “historically reported” until evidence reconciliation.
- “Source review complete” does not imply tests passed or runtime is secure.
- A repeat must have a linked Duplicate Audit Log entry.
- A new finding must have a Findings Register entry and evidence reference, or explicitly state evidence is pending.
- Do not invent commit SHA, execution timestamp, agent identity, test output, environment value, or production state.

## 5. Required fields for future entries

Audit ID | Title | Scope | Exclusions | Status | Assurance level | Prior audit | Baseline ref/SHA | Acceptance criteria | Evidence IDs | Finding IDs | Duplicate decision | Owner authorization | Next action
