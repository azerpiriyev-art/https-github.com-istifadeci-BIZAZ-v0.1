# BIZAZ Evidence Register

Protocol: [BIZAZ Permanent Audit Control Protocol](BIZAZ_AUDIT_CONTROL.md)  
Registry version: 0.1 (initial structure)  
Status: INITIAL / PRIMARY ARTIFACT INDEXING PENDING

> This file intentionally does not fabricate evidence IDs, collection timestamps, commit SHAs, line numbers, command outputs, or test outcomes. Historical findings and summaries are not primary evidence by themselves.

## 1. Evidence inventory status

| Evidence family | Known material | Evidence IDs | Current limitation |
|---|---|---|---|
| RP-02A migration runner and candidate | Source-review notes; 18-file manifest hash comparison; validator source inventory | NOT YET ASSIGNED | Exact commit SHA and original command output not indexed here |
| RP-02B deployment configuration | Compose, Dockerfiles, Caddy, runbooks, CI and backend source review notes | NOT YET ASSIGNED | Source baseline SHA and original line-range citations not reconciled |
| RP-02B.15 authentication/authorization | Backend source excerpts and test-source excerpts supplied during audit | NOT YET ASSIGNED | Historical 4.19 overlap not reconciled; no runtime tests executed in this audit |
| AL-01–AL-06 | Prior audit findings and partial descriptions | NOT YET ASSIGNED | Original evidence and exact finding AL-06 wording must be recovered |
| PGEMS WP-00/WP-01 | Owner dispositions and audit notes in historical context | NOT YET ASSIGNED | Original Journal, manifest, authorization evidence and Source Map must be recovered |

## 2. Evidence record template

Use one row per evidence item.

| Evidence ID | Audit ID | Finding ID | Repository path / artifact | Line range / locator | Source ref + commit SHA | Collected at (timezone) | Method | Result | Limitations | Integrity hash | Reviewer |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | UNKNOWN | NOT RECORDED | TBD | TBD | TBD | NOT RECORDED | TBD |

## 3. Evidence quality labels

- PRIMARY: exact file, test output, CI result, runtime observation or signed artifact with traceable locator.
- SECONDARY: contemporaneous audit note or summary that points to primary evidence.
- HISTORICAL SUMMARY: reconstructed description from prior conversation/context; useful for navigation, not enough by itself to claim a current PASS.
- INFERENCE: conclusion derived from evidence; confidence and assumptions must be explicit.
- MISSING: evidence expected but not recovered.
- CONTRADICTED: evidence conflicts with another record; preserve both and investigate.

## 4. Evidence collection rules

- Record the exact source ref and commit SHA when available.
- Record local dirty-state limitations; do not assume working tree matches a remote branch.
- For test evidence, record exact command, environment, exit code, test count and output artifact. If not run, mark NOT RUN.
- For runtime evidence, record target environment and observation time; redact secrets and personal data.
- For SQL evidence, record whether it was SELECT-only or changed data/schema.
- For generated evidence, record the exact artifact path and verified hash.
- Do not treat GitHub branch creation or document creation as proof that local project files were changed.
