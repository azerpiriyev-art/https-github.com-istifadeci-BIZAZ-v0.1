# Project Foundation — v0.1

## Mission
Build a secure, scalable Azerbaijan-focused B2B marketplace/workflow platform connecting buyers and suppliers.

## Product principles
1. Buyer and supplier workflows are explicit state machines.
2. Company membership and RBAC are first-class security boundaries.
3. Financial amounts use exact decimal semantics; default currency AZN.
4. Auditability is built in from day one.
5. No module is Ready before tests and integration checks pass.

## Non-functional baseline
- API validation via Pydantic.
- Password hashing with Argon2 when authentication is implemented.
- JWT with short-lived access tokens; refresh-token strategy to be finalized in Authentication stage.
- Rate limiting at API edge/application layer.
- Parameterized DB access/ORM to prevent SQL injection.
- Output encoding and content-security controls for XSS mitigation.
- CSRF strategy based on token transport; avoid unsafe cookie-based auth until finalized.
- CORS allowlist, security headers, audit logging, least privilege.
- Secrets only through environment/secret manager.

## Azerbaijan localization
- VÖEN (tax ID) field.
- Legal forms include MMC and fərdi sahibkar.
- AZN default currency.
- VAT default model 18%; final tax/legal behavior requires legal/accounting validation before production.
- Azerbaijani UI as primary language.

## Architecture
Browser → Next.js → REST API → FastAPI service → PostgreSQL.
Future workers: notifications, scheduled KPI aggregation, payment adapters, search, observability.

## Version policy
v0.1 Foundation; v0.2 Business Model; v0.3 MVP Scope; subsequent versions follow roadmap. v1.0 = Commercial MVP.
