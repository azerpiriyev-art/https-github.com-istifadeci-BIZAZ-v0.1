# MVP Scope — v0.3 working scope

## Delivery status at 4.23.1

This section records delivery status; it does not expand the MVP scope.

- Implemented baseline: registration/login, company membership/RBAC, company profile, product/supplier catalog primitives, purchase-order lifecycle, and audit logging.
- Next vertical slice: buyer purchase request → supplier offer → comparison → supplier selection → purchase order.
- Not yet delivered: purchase requests, supplier offers, offer comparison/selection, payment provider integration, delivery, reviews, notifications, and KPI dashboard.

## Must-have
1. Registration/login.
2. Company profile and membership/RBAC.
3. Product/service catalog.
4. Buyer purchase request.
5. Supplier discovery/participation.
6. Supplier offer submission.
7. Offer comparison and supplier selection.
8. Order creation and status lifecycle.
9. Payment record/state (provider adapter later; no unsafe card-data storage).
10. Delivery status.
11. Review/rating.
12. Basic notifications.
13. Audit log.
14. Core KPI dashboard.

## Explicitly out of first MVP
- Full ERP/accounting integration.
- Complex logistics optimization.
- Credit/BNPL underwriting.
- Arbitrary marketplace financial instruments.
- Advanced AI procurement automation.

## Acceptance principle
A vertical slice is accepted only when buyer and supplier can complete the intended flow in an integration environment, authorization and company isolation are verified, audit events are recorded where required, and automated regression tests pass.
