# BIZAZ Permanent Audit Control Protocol

**Document ID:** BIZAZ-AUDIT-CONTROL-001  
**Version:** 1.1  
**Protocol status:** APPROVED BY PROJECT OWNER  
**Repository integration status:** MERGED INTO MASTER  
**Audit authority:** Project Owner  
**Audit lead:** ChatGPT (architecture, security review, QA and audit coordination)  
**Language:** Azerbaijani for user-facing audit instructions; technical identifiers may remain English.

---

## 1. Purpose and authority

This protocol is the single control point for BIZAZ audit planning, evidence tracking, findings, audit status, and prevention of duplicate work.

The register is authoritative for audit workflow only after its contents have been reconciled with original audit records and accepted into the project baseline. Historical summaries are preserved as historical records; they are not silently upgraded into independently verified evidence.

No audit result, finding, approval, or historical record may be deleted or rewritten merely to make the register appear complete.

## 2. Non-negotiable rules

1. **Check the register before every audit action.** No new audit command, test, search, or inspection is proposed until the relevant audit ID, prior result, evidence, and last-known baseline have been checked.
2. **No duplicate audit without a trigger.** If the same scope, source baseline, configuration, and acceptance criteria were already checked, reuse the prior result and skip the repeat.
3. **Delta first.** When relevant files or behavior changed, inspect only the changed area and its demonstrable dependencies. Expand scope only when evidence shows a dependency or regression risk.
4. **Preserve historical results.** Prior PASS/CLOSED results remain historical results. They are not invalidated by a new audit merely because the same topic is being discussed.
5. **No unsupported PASS.** Source inspection is not runtime proof. Test inventory is not test execution. CI success is not production runtime evidence. A deployment plan is not a live deployment.
6. **Unknown remains UNKNOWN.** Missing evidence is never inferred, guessed, or filled with invented timestamps, commit IDs, agent IDs, test results, or environment values.
7. **Findings remain open until verified.** A finding is closed only after the defined remediation or disposition is supported by evidence and the authorized reviewer accepts closure.
8. **No silent scope expansion.** New audit areas and acceptance criteria must be recorded before work starts.
9. **No implicit remediation authority.** Audit permission does not authorize code edits, migrations, DB writes, test execution, Git operations, deployment, agent activation, or secret rotation.
10. **One next step at a time.** User-facing execution instructions are incremental and must state whether they are READ-ONLY, test execution, or a change operation.
11. **Sensitive values stay out of evidence.** Never print or copy passwords, tokens, JWT secrets, private keys, full connection strings, or sensitive environment values into the register.
12. **Session closure is mandatory.** Each audit session ends with updated status, evidence references, unresolved questions, and one next authorized action.

## 3. Audit decision gate

Before proposing work, the audit lead must answer:

- Is this scope already in the Audit Registry?
- What was the last recorded result and its evidence?
- What exact source baseline (commit/ref and file state) was checked?
- Have relevant files, dependencies, configuration, data contracts, or acceptance criteria changed?
- Is there a new threat, incident, defect, or user requirement?
- Is the requested action within the current authorization boundary?

| Condition | Required action |
|---|---|
| Same scope, same baseline, same criteria, no new trigger | **SKIP**; reuse previous evidence |
| Relevant source/config changed | **DELTA AUDIT** |
| Historical result exists but source evidence is missing or ambiguous | **EVIDENCE RECONCILIATION**; do not repeat full audit by default |
| New feature, control, or threat surface | **NEW AUDIT** |
| Runtime/production evidence is required but unavailable | **UNKNOWN / BLOCKED**; request the smallest safe evidence |
| Change operation not explicitly authorized | **BLOCKED**; do not execute |

A repeat is permitted only when at least one trigger is recorded: relevant change, new threat/incident, failed or contradictory evidence, expired/invalidated control, changed acceptance criteria, or explicit owner request for revalidation.

## 4. Status vocabulary

| Status | Meaning |
|---|---|
| NOT STARTED | Registered, work has not begun |
| IN PROGRESS | Audit work is active |
| CLOSED / PASS | Acceptance criteria met with recorded evidence |
| OPEN | Finding or required work remains unresolved |
| UNKNOWN | Evidence is insufficient or inconclusive |
| BLOCKED | Required permission, access, or evidence is unavailable |
| NOT RUN | Test/check was identified but not executed |
| DEFERRED | Explicitly postponed with owner disposition |
| REOPENED | New evidence or change invalidates the previous closure |
| NOT APPLICABLE | Out of scope, with a recorded rationale |

A parent audit may be “source review complete” while production readiness remains UNKNOWN. Do not collapse different assurance levels into one PASS.

## 5. Required registers

### 5.1 Audit Registry

Each audit entry must contain:
- Audit ID and title
- Scope and explicit exclusions
- Status and assurance level
- Historical predecessor(s)
- Source baseline (branch/ref and commit SHA, if known)
- Start/finish timestamps with timezone, if captured
- Acceptance criteria
- Evidence IDs
- Findings created or affected
- Duplicate-audit decision and rationale
- Next action and authorization boundary

### 5.2 Findings Register

Each finding must contain:
- Finding ID
- Title and affected component
- Risk statement and plausible impact
- Evidence and exact source references
- Confidence: confirmed / probable / unverified
- Status and owner disposition
- Remediation or verification criteria
- Dependencies and affected audit IDs
- Closure evidence and reviewer

A source-level concern must not be described as a confirmed runtime exploit unless runtime evidence supports that claim.

### 5.3 Evidence Register

Each evidence item must contain:
- Evidence ID and linked Audit/Finding IDs
- Repository path and line range, or test/runtime artifact reference
- Source ref/commit SHA when available
- Collection timestamp and timezone when actually captured
- Method: source review, READ-ONLY inventory, test execution, CI, runtime, production observation
- Result and limitations
- Collector and reviewer, if known
- Integrity hash when generated and verified

Do not invent missing metadata. Use UNKNOWN or NOT RECORDED.

### 5.4 Baseline and Change Registers

Record:
- Last accepted baseline per audit area
- Relevant files and dependencies
- Git diff/commit evidence used to establish change
- New or removed routes, schemas, migrations, roles, policies, secrets handling, deployment controls, or tests
- Whether the change reopens a prior finding

A clean Git status is not assumed. Existing dirty work must be preserved; never reset, clean, stash, or overwrite it as part of audit bookkeeping.

### 5.5 Duplicate Audit / Skip Register

Every proposed repeat must record:
- Requested scope
- Previous Audit ID
- Previous result/evidence
- Change/incident/criteria trigger, if any
- Decision: SKIP, DELTA, RECONCILE, or REOPEN
- Reason and approver

## 6. Finding lifecycle and closure

1. Record the observation without overstating certainty.
2. Link exact evidence and identify what it proves and does not prove.
3. Assign a finding ID and OPEN/UNKNOWN status.
4. Record owner disposition: accept, remediate, defer, or reject with rationale.
5. For remediation, define a separate authorized change task.
6. Verify the change against explicit acceptance criteria.
7. Record test/runtime evidence separately from source review.
8. Close only after evidence review and owner acceptance.

An owner acceptance of risk is not the same as technical remediation. A deferred finding remains visible and open/deferred; it is not deleted.

## 7. Execution and safety boundaries

Default audit mode is **READ-ONLY**.

Unless the Project Owner separately authorizes the exact operation, do not:
- modify project files or generated configuration;
- execute database INSERT/UPDATE/DELETE/DDL or migrations;
- run tests or scripts that mutate data;
- create, delete, reset, clean, stash, commit, or push Git changes;
- start, stop, rebuild, or remove Docker resources;
- deploy or change production infrastructure;
- enable local agents or grant new permissions;
- expose or rotate secrets.

Commands must be labeled with their effect. Prefer bounded, targeted commands over recursive broad scans. Exclude virtual environments, node_modules, build outputs, and generated artifacts unless they are the specific audit target.

## 8. Session start protocol

At the start of each BIZAZ audit session:

1. Identify the active Audit ID and requested scope.
2. Read this protocol and the latest audit register.
3. Read relevant prior evidence and findings.
4. Establish the current source baseline without changing it.
5. Compare relevant changes with the prior baseline.
6. Decide SKIP / DELTA AUDIT / EVIDENCE RECONCILIATION / NEW AUDIT.
7. State the decision and the next smallest authorized action.

If the current register or evidence cannot be accessed, say so. Do not silently reconstruct missing records from memory and present them as authoritative.

## 9. Session close protocol

At the end of each session:
- update the audit status and assurance level;
- add or update evidence references;
- add new findings without overwriting historical ones;
- record finding disposition and its authority;
- record checks not run and reasons;
- record source baseline and changed files, if known;
- identify duplicate scopes to skip next time;
- set one next action and its authorization boundary.

The session summary must be concise and suitable for direct transfer to the register.

## 10. Initial BIZAZ audit baseline

This section is an initial index, not a claim that every historical artifact has already been recovered and independently verified.

### 10.1 Historical audit families

| Audit family | Current register treatment |
|---|---|
| 4.17.x structural, transaction, concurrency, security, tenant isolation, RBAC and audit integrity checks | Historical results reported as PASS; preserve and reconcile original evidence before treating as current baseline |
| 4.19.4.1–4.19.4.10 Security / Authorization / RBAC | Historical CLOSED/PASS reported; do not repeat wholesale; reconcile source baseline and evidence |
| PGEMS WP-00 | UNKNOWN pending its separately required read-only verification |
| PGEMS WP-01 | Owner dispositions recorded; preserve and reconcile evidence and Journal metadata |
| RP-02A | Migration/deployment mechanism source review complete; production readiness not established |
| RP-02B.1–.14 | Production deployment configuration source review completed; runtime/production readiness not established |
| RP-02B.15 | Authentication/authorization source review in progress; compare with historical 4.19 evidence before further overlapping checks |

### 10.2 RP-02A baseline

Known source-review conclusions:
- Active runner is deploy/migrate.sh; it uses filename-based migration journal handling and lacks the candidate’s checksum/advisory-lock/validator controls.
- Hardened candidate v2.4.3 is untracked and explicitly not approved for production.
- Candidate manifest was compared against the 18 current migration files: 18/18 SHA-256 matches at the time of that check.
- Python transaction validator was reviewed at source level; its 43 test cases were inventoried but not executed.
- Candidate was not executed or approved for production.
- Production migration readiness was not established.

Do not repeat manifest hashing or validator source review unless the candidate, migrations, validator, or acceptance criteria change, or evidence reconciliation identifies a gap.

### 10.3 RP-02B baseline

Source review has covered:
- production Compose and service dependencies;
- Dockerfiles, Caddy, DB role bootstrap;
- deployment and Free Tier runbooks;
- backup and restore procedures;
- backend /health and /ready;
- .dockerignore and build-context exposure;
- production environment and secret handling;
- container hardening and network isolation;
- logging and observability;
- image pinning, CI build and GitHub Actions security;
- dependency audit and lockfile controls;
- security automation inventory;
- TLS, HTTP headers and CORS;
- JWT, company membership, tenant scoping, approval logic and test-source inventory.

These are source-review results, not proof of live production behavior.

### 10.4 Known open finding groups

**Audit log protection (AL-01–AL-06):** preserve as OPEN/UNKNOWN according to each original finding. They require a separately authorized remediation phase. Do not conflate audit_log findings with PGEMS execution-audit evidence.

**Production deployment (RP-02B):** previously recorded open areas include off-host backup and restore evidence, monitoring/alerting/log rotation, scheduled purge verification, build-context exclusions, secret rotation evidence, container hardening/resource limits, runtime network/firewall verification, image digest pinning and supply-chain controls, backend dependency security/lockfile/hash verification, repository security automation, TLS policy/security headers, and CORS restrictions. Preserve original finding IDs F06–F53 and their individual dispositions; do not renumber or merge them without reconciliation.

**Authentication / authorization:**
- AUTH-F02: multi-company membership context selection may be ambiguous because get_current_membership() selects by user ID without an explicit company selector, active-state filter, or ordering. This is a source-level risk; not proof of cross-tenant data exposure.
- AUTH-F03: role-based approval may allow the requester to decide their own approval. Direct approver_user_id self-assignment is rejected, but the role-based decision path reviewed did not compare the current user with ApprovalRequest.requested_by. Test source includes same-auth-header create/decision flows; actual fixture role and runtime behavior still require verification.
- Do not repeat general JWT, ordinary RBAC, or cross-company IDOR audits already covered by historical audit families unless a recorded delta trigger exists.

### 10.5 PGEMS owner dispositions

Preserve previously recorded decisions:
- H-01: accepted; complete authorization/manifest evidence.
- M-01: accepted; wording clarification deferred.
- M-02: accepted; missing execution metadata requires a separately authorized Journal append; never invent Agent ID or timestamps.
- M-03: accepted; address through a future Source Map.
- M-04: WP-00 remains UNKNOWN pending read-only verification.
- M-05: preserve the recorded owner disposition; reconcile its full original wording before changing its status.

## 11. Initial no-repeat rules

Unless a valid repeat trigger is recorded, do not restart:
- completed 4.17.x audit scopes;
- completed 4.19.4.x JWT/authentication/RBAC/tenant-isolation scopes;
- RP-02A candidate manifest comparison and validator source review;
- RP-02B.1–.14 source reviews on unchanged files;
- already inspected cross-company delivery/payment/approval test source.

These no-repeat rules do not prohibit delta verification, evidence reconciliation, incident response, or owner-requested revalidation.

## 12. Current handoff

**Current audit:** RP-02B.15 — Authentication and Authorization.  
**Current mode:** READ-ONLY source review.  
**Immediate control action:** reconcile overlapping 4.19 historical evidence before proposing additional generic authentication/RBAC checks.  
**Potential delta findings:** AUTH-F02 and AUTH-F03, subject to evidence reconciliation.  
**No code, DB, test, Docker, or deployment changes are authorized by this protocol.**

---

**Protocol change control:** Changes to this document require a recorded reason, version increment, and Project Owner approval. Historical audit records must be append-only or versioned; never silently overwritten.
