# BIZAZ Baseline and Change Register

Protocol: [BIZAZ Permanent Audit Control Protocol](BIZAZ_AUDIT_CONTROL.md)  
Registry version: 0.1 (initial structure)  
Status: INITIAL / REPOSITORY BASELINE NOT YET RECONCILED

## 1. Known audit baseline references

| Audit family | Branch/ref known from history | Commit SHA | Local working-tree state | Baseline status |
|---|---|---|---|---|
| RP-02A | integration/production-readiness-20261016 was active in prior session | NOT RECORDED | NOT RECHECKED | HISTORICAL REFERENCE ONLY |
| RP-02B | integration/production-readiness-20261016 was active in prior session | NOT RECORDED | NOT RECHECKED | HISTORICAL REFERENCE ONLY |
| 4.17.x | NOT RECORDED | NOT RECORDED | NOT RECORDED | HISTORICAL BASELINE TO RECOVER |
| 4.19.4.1–4.19.4.10 | NOT RECORDED | NOT RECORDED | NOT RECORDED | HISTORICAL BASELINE TO RECOVER |
| PGEMS WP-00/WP-01 | NOT RECORDED | NOT RECORDED | NOT RECORDED | HISTORICAL BASELINE TO RECOVER |

## 2. Change record template

| Change ID | Date/time | Audit area | Source ref + SHA before | Source ref + SHA after | Changed paths | Change summary | Findings potentially affected | Delta audit required? | Evidence ID |
|---|---|---|---|---|---|---|---|---|---|
| TBD | NOT RECORDED | TBD | UNKNOWN | UNKNOWN | TBD | TBD | TBD | TBD | TBD |

## 3. Baseline verification checklist

- [ ] Confirm intended active branch and exact commit SHA.
- [ ] Capture Git status without changing the working tree.
- [ ] Preserve all dirty/untracked files.
- [ ] Compare relevant paths against the last accepted audit baseline.
- [ ] Exclude unrelated build outputs and dependency directories unless they are audit targets.
- [ ] Identify changed migrations, models, routes, schemas, role logic, authorization dependencies, tests, deployment configuration and secrets handling.
- [ ] Link each detected delta to affected Audit IDs and Finding IDs.
- [ ] Do not mark a historical baseline current until the owner accepts the reconciliation.

## 4. Safety

This register does not authorize Git checkout, reset, clean, stash, commit, push, branch changes in the local workspace, or any file mutation. Baseline collection is READ-ONLY unless separately authorized.
