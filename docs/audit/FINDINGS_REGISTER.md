# BIZAZ Findings Register

Protocol: [BIZAZ Permanent Audit Control Protocol](BIZAZ_AUDIT_CONTROL.md)  
Registry version: 0.1 (initial structure)  
Status: INITIAL / ORIGINAL FINDING RECORDS REQUIRE RECONCILIATION

> Preserve existing finding IDs. Entries below are index-level descriptions based on available audit history. Where exact original wording, severity, evidence, or disposition is unavailable, it is explicitly marked for reconciliation.

## 1. Audit-log protection findings

| Finding ID | Scope / observation | Status | Confidence | Evidence / disposition |
|---|---|---|---|---|
| AL-01 | No audit_log database trigger identified in prior review | OPEN | Source observation | Preserve original finding; remediation not authorized |
| AL-02 | No audit_log RLS/policies identified in prior review | OPEN | Source observation | Preserve original finding; remediation not authorized |
| AL-03 | Test DB role bizaz_test_runner was reported able to UPDATE/DELETE audit_log | OPEN | Prior audit observation; exact evidence pending | Preserve original finding; remediation not authorized |
| AL-04 | Active local API may use bizaz_test_runner; mapping was strong inference, not conclusive | OPEN / UNKNOWN | Unverified mapping | Do not upgrade inference to confirmed fact |
| AL-05 | Test suite contains direct audit_log DELETE cleanup | OPEN | Source observation | Preserve original finding; remediation not authorized |
| AL-06 | Additional audit_log protection gap from prior assessment | OPEN / DETAILS TO RECONCILE | Unverified in this initial index | Recover exact original wording; do not infer |

## 2. Production deployment findings (RP-02B)

| Finding ID | Topic | Historical status | Current treatment |
|---|---|---|---|
| RP-02B-F06 | External/off-host backup target not configured | OPEN | Preserve |
| RP-02B-F07 | Isolated restore test execution evidence absent | OPEN | Preserve |
| RP-02B-F08 | Monitoring, alerting and log rotation not installed/verified | OPEN | Preserve |
| RP-02B-F09 | Daily backup and 180-day notification purge tasks not confirmed | OPEN | Preserve |
| RP-02B-F10 | OCI pilot documentation is a plan, not a live deployment | CONFIRMED | Historical observation; no live deployment claim |
| RP-02B-F11 | backend/token.tmp not explicitly excluded from backend Docker build context | OPEN | File content not inspected; Dockerfile did not directly COPY it |
| RP-02B-F12 | .venv_depcheck_* directories not explicitly excluded from backend Docker context | OPEN | Build-context exposure, not proof of final-image inclusion |
| RP-02B-F13 | Git ignore rules do not substitute for Docker ignore rules | CONFIRMED | Preserve |
| RP-02B-F14 | Production environment secrets are passed as environment variables, not Docker Secrets | CONFIRMED | Design observation; risk assessment remains |
| RP-02B-F15 | No DB/JWT secret ARG found in Dockerfiles | POSITIVE CONTROL | Preserve as positive observation, not an open defect |
| RP-02B-F16 | Real host permissions, secret strength and rotation not evidenced; rotation procedure absent | OPEN | Preserve |
| RP-02B-F17 | Secret generation and protection instructions documented | POSITIVE CONTROL | Preserve |
| RP-02B-F18 | Backend/frontend containers use non-root users | POSITIVE CONTROL | Preserve |
| RP-02B-F19 | Compose read-only filesystem, capability drop and no-new-privileges controls not visible | OPEN | Source observation |
| RP-02B-F20 | Compose CPU/RAM/PID resource limits not visible | OPEN | Source observation |
| RP-02B-F21 | DB and Caddy runtime users/security not verified | OPEN / UNKNOWN | Runtime evidence required |
| RP-02B-F22 | PostgreSQL/backend ports not directly published to host in Compose | POSITIVE CONTROL | Preserve |
| RP-02B-F23 | Data network is configured internal | POSITIVE CONTROL | Runtime not verified |
| RP-02B-F24 | Runtime firewall, subnet conflict and network isolation not verified | OPEN / UNKNOWN | Runtime evidence required |
| RP-02B-F25 | Docker json-file log rotation configured at 10 MB / 3 files | POSITIVE CONTROL | Preserve |
| RP-02B-F26 | Centralized monitoring/alerting not confirmed | OPEN / UNKNOWN | Preserve |
| RP-02B-F27 | Sensitive log redaction not verified | OPEN / UNKNOWN | Preserve |
| RP-02B-F28 | Scheduled-task failure notification not confirmed | OPEN / UNKNOWN | Preserve |
| RP-02B-F29 | Production image references are not digest-pinned | OPEN | Preserve |
| RP-02B-F30 | CI vulnerability scanning, signing, SBOM/provenance not found | OPEN | Preserve |
| RP-02B-F31 | CI builds OCI archives; no registry push visible | OBSERVATION | Preserve; not automatically a defect |
| RP-02B-F32 | GitHub Actions references are not pinned to full commit SHAs | OPEN | Preserve |
| RP-02B-F33 | Workflow token permission contents: read | POSITIVE CONTROL | Preserve |
| RP-02B-F34 | pull_request_target trigger not found | POSITIVE CONTROL | Preserve |
| RP-02B-F35 | Backend CVE dependency audit not found | OPEN | Preserve |
| RP-02B-F36 | Frontend production dependency audit exists | POSITIVE CONTROL | Preserve |
| RP-02B-F37 | npm audit exception expired 2026-11-14 and code fails closed after expiry | EXPIRED / CLEANUP REQUIRED | Not an active bypass based on reviewed code |
| RP-02B-F38 | pip check is dependency consistency, not vulnerability scanning | CONFIRMED | Preserve |
| RP-02B-F39 | Separate production and CI backend requirements files | POSITIVE CONTROL | Preserve |
| RP-02B-F40 | Test packages excluded from production requirements | POSITIVE CONTROL | Preserve |
| RP-02B-F41 | Backend production dependencies include version ranges | OPEN | Preserve |
| RP-02B-F42 | Backend hash-based dependency verification absent | OPEN | Preserve |
| RP-02B-F43 | Backend lockfile absent | OPEN | Preserve |
| RP-02B-F44 | Dependabot configuration not found in repository | OPEN / REPOSITORY CONFIG ONLY | Does not establish GitHub server setting |
| RP-02B-F45 | CodeQL workflow not found in repository | OPEN / REPOSITORY CONFIG ONLY | Does not establish GitHub server setting |
| RP-02B-F46 | Local repository secret-scanning configuration not found | OPEN / REPOSITORY CONFIG ONLY | Does not establish GitHub secret scanning disabled |
| RP-02B-F47 | Gitleaks/Trufflehog configuration not found | OPEN / REPOSITORY CONFIG ONLY | Preserve |
| RP-02B-F48 | Semgrep/Bandit configuration not found | OPEN / REPOSITORY CONFIG ONLY | Preserve |
| RP-02B-F49 | Explicit TLS version/cipher policy not defined in Caddyfile | OPEN / SOURCE OBSERVATION | Caddy may still automatically manage HTTPS |
| RP-02B-F50 | Explicit HSTS header not found | OPEN / SOURCE OBSERVATION | Runtime headers not checked |
| RP-02B-F51 | CSP and other browser security headers not found | OPEN / SOURCE OBSERVATION | Runtime headers not checked |
| RP-02B-F52 | Explicit HTTP-to-HTTPS redirect not shown in Caddyfile | OPEN / SOURCE OBSERVATION | Runtime redirect behavior not checked |
| RP-02B-F53 | CORS allows wildcard methods and headers with credentials enabled | OPEN / SOURCE OBSERVATION | Production origin value and runtime behavior not verified |

## 3. Authentication and authorization delta findings

| Finding ID | Topic | Status | Confidence | Required verification |
|---|---|---|---|---|
| AUTH-F02 | Multi-company membership context may be ambiguous: get_current_membership() selects by user_id only, without explicit company selector, active-state filter or ordering; CompanyMember key permits a user to have multiple company memberships | OPEN | Source-level risk; not proof of cross-tenant exposure | Reconcile historical 4.19 evidence; establish intended company context model; inspect only changed code/tests; runtime test only with separate authorization |
| AUTH-F03 | Role-based approval path may permit requester self-approval: direct approver_user_id self-assignment is rejected, but role-based decision path reviewed did not compare current user with ApprovalRequest.requested_by | OPEN / PROVISIONAL | Source-level potential gap | Reconcile historical approval audit; confirm request creator and test fixture role; inspect all relevant decision logic; obtain authorized isolated test evidence |

## 4. Closure requirements

A finding may be closed only when:
1. the exact acceptance criteria are recorded;
2. remediation or accepted disposition is explicit;
3. source evidence is linked to a known baseline;
4. required tests/runtime evidence are recorded separately;
5. no contradictory evidence remains;
6. Project Owner accepts closure.

Positive controls are retained for traceability and must not be counted as open defects. Risk acceptance or deferral does not equal technical remediation.
