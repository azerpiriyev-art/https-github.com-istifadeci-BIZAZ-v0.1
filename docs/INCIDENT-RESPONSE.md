# BIZAZ Incident Response Runbook

## 1. Purpose

This document defines the standard response procedure for BIZAZ production incidents.

Primary objectives:
- Detect the incident
- Protect data
- Restore service
- Verify database integrity
- Verify backup integrity
- Confirm monitoring recovery
- Preserve audit evidence

## 2. Incident Severity

### SEV-1 — Critical

Examples:
- Production database unavailable
- Data loss suspected
- Production service unavailable
- Recovery cannot be completed within the RTO target

Immediate action:
- Protect existing backups
- Start recovery procedure
- Preserve logs and evidence
- Escalate immediately

### SEV-2 — Major

Examples:
- Backup failure
- Monitoring alert
- API unavailable while database remains healthy
- Repeated operational failure

Action:
- Investigate
- Restore normal operation
- Verify backup and monitoring
- Record incident

### SEV-3 — Minor

Examples:
- Non-critical operational warning
- Documentation/configuration issue
- Single transient failure with successful automatic recovery

Action:
- Investigate
- Correct if required
- Record the event

## 3. First Response

1. Record the time of detection.
2. Identify the affected component.
3. Do not delete production data.
4. Do not remove the PostgreSQL volume.
5. Protect the most recent valid backup.
6. Check Docker status:
   docker compose ps
7. Check PostgreSQL:
   docker compose exec -T db pg_isready -U bizaz -d bizaz
8. Check API:
   Invoke-RestMethod http://127.0.0.1:8000/health

## 4. Database Incident

If PostgreSQL is unavailable:

1. Check:
   docker compose ps

2. Attempt controlled recovery:
   docker compose start db

3. Wait for health:
   Start-Sleep -Seconds 8

4. Verify:
   docker compose ps

5. Verify connectivity:
   docker compose exec -T db pg_isready -U bizaz -d bizaz

6. Verify business data counts.

7. Create a recovery backup.

8. Verify backup archive and SHA256.

## 5. Backup Incident

If a backup fails:

1. Check database availability.
2. Review the backup log.
3. Do not treat the failed backup as valid.
4. Recover the database if required.
5. Re-run the backup.
6. Validate the CUSTOM archive.
7. Verify SHA256.
8. Verify Local, D: and OneDrive copies.
9. Confirm monitoring returns to OK.

## 6. Monitoring Incident

If monitoring reports ALERT:

1. Identify the alert condition.
2. Check database status.
3. Check the latest backup.
4. Check the latest backup log.
5. Correct the underlying problem.
6. Run a verification check.
7. Confirm:
   MONITORING_STATUS: OK
8. Preserve evidence of the incident and recovery.

## 7. Disaster Recovery

If production recovery is not possible:

1. Identify the latest valid backup.
2. Verify SHA256.
3. Verify archive integrity using pg_restore --list.
4. Restore into an isolated recovery database first where practical.
5. Validate:
   - tables
   - data
   - primary keys
   - foreign keys
   - indexes
   - expected row counts
6. Only proceed to production recovery after validation.

Routine DR tests must not overwrite the production database.

## 8. RPO / RTO

RPO target:
<= 24 hours

RTO target:
<= 2 hours

Every major recovery incident must record:
- incident start time
- recovery start time
- service restoration time
- data verification time
- backup verification time

## 9. Evidence Preservation

Preserve:
- Docker status
- PostgreSQL connectivity result
- API health result
- backup filename
- backup size
- SHA256
- backup log
- monitoring status
- incident time
- recovery time
- final health check

Do not overwrite or delete evidence before the incident is closed.

## 10. Incident Closure

An incident may be closed only when:

- PostgreSQL is healthy
- PostgreSQL accepts connections
- API health is OK
- Business data integrity is verified
- A valid backup exists
- Backup integrity is verified
- Monitoring status is OK
- Required evidence is recorded
- Root cause or known limitation is documented

## 11. Post-Incident Review

For SEV-1 and SEV-2 incidents record:

- What happened?
- When did it happen?
- What was affected?
- What caused it?
- What action restored service?
- Was RPO maintained?
- Was RTO maintained?
- Was any data lost?
- What preventive action is required?

## 12. Current Tested Recovery Capabilities

The following capabilities have been operationally tested:

- PostgreSQL stop/recovery
- Backup failure handling
- Monitoring alert detection
- Monitoring recovery
- Recovery backup
- Three-way backup verification
- Disaster recovery restore
- RPO validation
- RTO validation

## 13. Version-Controlled Incident and Change History

Git repository/version control is initialized. The approved v0.1 production baseline is:

`23d0c80` — `chore: establish BIZAZ v0.1 production baseline`

For every SEV-1 or SEV-2 incident, preserve the incident evidence listed in section 9 and record the resulting corrective change in version control when a code, configuration, script, or documentation change is required. Do not treat the baseline commit as evidence of a fresh live health check.

## 14. Incident Status

Current known production state:
HEALTHY

Operational resilience:
PASS

Backup:
PASS

Monitoring:
PASS

Disaster recovery:
PASS
