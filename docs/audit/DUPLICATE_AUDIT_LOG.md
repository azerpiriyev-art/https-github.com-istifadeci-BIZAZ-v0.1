# BIZAZ Duplicate Audit / Skip Log

Protocol: [BIZAZ Permanent Audit Control Protocol](BIZAZ_AUDIT_CONTROL.md)  
Registry version: 0.1 (initial structure)

> This log records why a repeated audit is skipped, narrowed to a delta, reconciled, or reopened. It is not a substitute for the underlying audit evidence.

## 1. Decisions recorded at initialization

| Decision ID | Requested / recurring scope | Prior audit | Trigger for repeat | Decision | Rationale | Evidence state | Approver |
|---|---|---|---|---|---|---|---|
| DUP-0001 | General JWT/authentication/RBAC/tenant-isolation review | Historical 4.19.4.1–4.19.4.10 | No new trigger established yet | RECONCILE FIRST | Historical CLOSED/PASS is reported; recover exact source baseline and evidence before any repeat | Historical primary evidence not yet mapped | Project Owner protocol approval |
| DUP-0002 | RP-02A migration manifest and validator source review | RP-02A | No known relevant change since review | SKIP unless delta trigger | 18/18 manifest hashes were previously matched; candidate and validator were not executed | Conversation audit history; primary artifacts not indexed | Project Owner protocol approval |
| DUP-0003 | RP-02B.1–.14 deployment source review | RP-02B.1–.14 | No known relevant change established | SKIP unless delta trigger | These areas were already reviewed at source level; production runtime remains UNKNOWN | Conversation audit history; baseline SHA not yet reconciled | Project Owner protocol approval |
| DUP-0004 | Cross-company delivery/payment/approval test-source inspection | RP-02B.15 prior steps | No new source delta established | SKIP unless delta trigger | Relevant tests were already inspected; do not re-open the same files without a code/test change or evidence contradiction | Source excerpts in audit history; exact commit SHA not recorded | Project Owner protocol approval |
| DUP-0005 | Approval self-approval logic | RP-02B.15.64–.69 | Potential role-based self-approval path and historical RBAC overlap | DELTA / RECONCILIATION | Direct-user self-assignment rejection is present; role-based path needs targeted confirmation and historical overlap review, not a full auth audit | Source excerpts; tests not executed; fixture role not yet confirmed | Project Owner protocol approval |

## 2. New decision template

| Decision ID | Date/time | Requested scope | Prior Audit ID | Prior result/evidence | Source delta / incident / criteria trigger | Decision (SKIP/DELTA/RECONCILE/REOPEN) | Reason | Approver | Follow-up Audit ID |
|---|---|---|---|---|---|---|---|---|---|
| TBD | NOT RECORDED | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## 3. Mandatory rule

No new audit command is proposed until this log and the relevant Audit Registry entry have been checked. If no trigger exists, reuse the prior evidence and SKIP the repeat.
