# Technical Architecture — v0.4 baseline

```text
Next.js / React / TypeScript / Tailwind
             |
          REST/JSON
             |
      FastAPI application
       |      |       |
    Auth/RBAC Domain  Audit
       |      |       |
       +------|-------+
              |
         PostgreSQL 16
```

## Domain boundaries
- Identity & access
- Companies & memberships
- Catalog
- Procurement requests
- Tenders/offers
- Orders
- Payments (provider adapter boundary)
- Delivery
- Messaging/notifications
- Reviews
- KPI/reporting

## Design rules
- `/api/v1` versioned REST surface.
- UUID identifiers for domain entities.
- Decimal/NUMERIC for monetary values.
- Explicit status transitions, not arbitrary writes.
- Tenant boundary enforced by company membership.
- Audit sensitive mutations.
- External payment details never stored directly; use provider tokens/references.
