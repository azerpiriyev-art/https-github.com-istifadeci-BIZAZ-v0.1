# BIZAZ Status — 2026-08-31

| MODUL | STATUS | TEST | PROBLEM | NÖVBƏTİ ADDIM |
|---|---|---|---|---|
| Project Foundation | 🟢 Hazır | Static QA + Python compile pass | Runtime dependency install unavailable in sandbox network | Continue v0.2 |
| Business Model | 🟡 İşlənir | Scope/assumption review pass | Pricing, commission, disputes and legal terms require owner decisions before commercialization | Technicalize model without hard-coded rates |
| MVP Scope | 🟢 Hazır | Scope consistency review pass | Provider/payment details remain adapter-based | Database expansion |
| Technical Architecture | 🟢 Hazır | Boundary/stack consistency review pass | Production observability later | Database |
| Database | 🟢 Hazır | SQL/static structure review pass | Live PostgreSQL migration not executed in this sandbox | Backend domain models |
| Backend/API | 🟡 İşlənir | Static compile pass; unit runtime blocked by missing installed deps | Environment cannot download packages | Implement domain endpoints |
| Authentication | 🔴 Başlanmayıb | — | — | JWT + Argon2 + RBAC |
| Company Management | 🔴 Başlanmayıb | — | — | After Auth |
| Product & Service Catalog | 🔴 Başlanmayıb | — | — | After Company |
| Procurement/Tender/Offers | 🔴 Başlanmayıb | — | — | Vertical slice |
| Orders/Payments/Delivery | 🔴 Başlanmayıb | — | — | Vertical slice |
| Messaging/Notifications/Reviews | 🔴 Başlanmayıb | — | — | After transaction flow |
| KPI/Dashboard | 🔴 Başlanmayıb | — | — | After transaction schema |
| Security | 🟡 İşlənir | Baseline controls embedded | Full threat model/pentest later | Security stage |
| Automated Testing | 🟡 İşlənir | Static + compile pass | Runtime test suite awaits dependencies/DB | Expand continuously |
| Deployment | 🔴 Başlanmayıb | — | — | After pilot readiness |
