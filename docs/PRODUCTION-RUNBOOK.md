# BIZAZ Production Operations Runbook

## 1. Purpose

This runbook defines the standard operational procedures for the BIZAZ platform.

Scope:
- PostgreSQL
- FastAPI backend
- Docker infrastructure
- PostgreSQL backups
- Backup monitoring
- Failure detection and recovery
- Disaster recovery
- RPO/RTO
- Audit evidence
- Operational governance

## 2. Current Production Baseline

Project:
C:\Projects\BIZAZ-v0.1

Database:
PostgreSQL 16
Database name: bizaz
Container: bizaz-postgres
Port: 5432

Backend:
FastAPI
Health endpoint:
http://127.0.0.1:8000/health

Backup locations:
- C:\Projects\BIZAZ-v0.1\backups
- D:\BIZAZ-Backups
- C:\Users\USER\OneDrive\BIZAZ-Backups

Scheduled tasks:
- BIZAZ - Daily PostgreSQL Backup
- BIZAZ - Backup Monitoring

## 3. Daily Health Check

1. Check Docker/PostgreSQL:
   docker compose ps

2. Check PostgreSQL connectivity:
   docker compose exec -T db pg_isready -U bizaz -d bizaz

3. Check API:
   Invoke-RestMethod http://127.0.0.1:8000/health

Expected:
- PostgreSQL = Up / healthy
- PostgreSQL = accepting connections
- API status = ok

## 4. Database Integrity Check

Expected baseline:

companies = 4
suppliers = 2
products = 2
purchase_orders = 84
purchase_order_items = 85
audit_log = 403

Any unexpected change requires investigation before declaring the system healthy.

## 5. Backup Operations

Daily backup task:

BIZAZ - Daily PostgreSQL Backup

Schedule:
Daily at 02:00

Backup requirements:
- PostgreSQL CUSTOM format
- Archive validation with pg_restore --list
- SHA256 verification
- Local copy
- Secondary D: copy
- OneDrive copy
- Three-way SHA256 match
- 30-day retention

## 6. Backup Monitoring

Monitoring task:

BIZAZ - Backup Monitoring

Monitoring interval:
Every 15 minutes

Alert conditions:
- Database unavailable
- Backup task failure
- Backup failure log
- Missing backup
- Backup older than 24 hours

Healthy state:
MONITORING_STATUS: OK

Failure state:
MONITORING_STATUS: ALERT

## 7. Failure Response

### Database unavailable

1. Check:
   docker compose ps

2. Attempt recovery:
   docker compose start db

3. Wait for health:
   Start-Sleep -Seconds 8

4. Verify:
   docker compose ps

5. Verify connectivity:
   docker compose exec -T db pg_isready -U bizaz -d bizaz

6. Verify data integrity.

7. Run a recovery backup.

Do not delete the PostgreSQL volume during incident recovery.

## 8. Backup Failure

If backup fails:

1. Do not mark the backup as successful.
2. Check database availability.
3. Check the backup log.
4. Recover PostgreSQL if necessary.
5. Re-run the backup.
6. Validate the archive.
7. Verify SHA256.
8. Verify secondary and OneDrive copies.
9. Confirm monitoring returns to OK.

## 9. Disaster Recovery

A valid PostgreSQL CUSTOM backup may be restored into an isolated database for verification.

Required validation:
- Restore completes without errors
- Tables exist
- Foreign keys exist
- Indexes exist
- Expected row counts match
- Application data remains consistent

Do not overwrite the production database during a routine restore test.

## 10. RPO / RTO

RPO target:
<= 24 hours

RTO target:
<= 2 hours

Operational tests completed:
- PostgreSQL failure/recovery
- Backup failure handling
- Monitoring alert
- Recovery backup
- DR restore
- RPO check
- RTO check

## 11. Change Control

Production changes must be:
- intentional
- documented
- tested
- reversible where practical
- followed by health verification

Before significant changes:
1. Confirm current health.
2. Confirm recent backup.
3. Record the intended change.
4. Apply the change.
5. Run health checks.
6. Verify data integrity.
7. Record the result.

## 12. Security Governance

Production security requirements:
- No hardcoded secrets
- Environment secrets must not be committed
- No wildcard CORS
- DEBUG must not be enabled in production
- Authentication and RBAC must remain enforced
- Audit logging must remain operational

## 13. Audit Evidence

Maintain evidence for:
- health checks
- backup success
- backup SHA256
- monitoring results
- incidents
- recovery operations
- DR restore tests
- configuration changes

## 14. Operational Checklist

### Daily
- Docker/PostgreSQL health
- PostgreSQL connectivity
- API health
- Backup task status
- Latest backup existence
- Monitoring status

### Weekly
- Review backup logs
- Review alerts/incidents
- Verify backup copies
- Review operational changes

### Monthly
- Perform DR restore test
- Review RPO/RTO readiness
- Review retention
- Review security controls
- Review documentation

## 15. Emergency Recovery Sequence

1. Identify the incident.
2. Check Docker/PostgreSQL.
3. Check API.
4. Protect existing backups.
5. Recover PostgreSQL if possible.
6. Verify connectivity.
7. Verify data integrity.
8. Create a fresh backup.
9. Verify all backup copies.
10. Confirm monitoring status.
11. Document the incident.
12. Escalate unresolved issues.

## 16. Governance Status

Operational resilience:
PASS

Backup:
PASS

Backup monitoring:
PASS

Disaster recovery:
PASS

RPO:
PASS

RTO:
PASS

Current known governance gap:
Git repository/version control is not initialized for the project.

This gap must be addressed before treating version-controlled change management as complete.
