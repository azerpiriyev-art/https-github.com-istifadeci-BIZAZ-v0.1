# API Documentation — v0.1 Foundation

OpenAPI is generated automatically by FastAPI at `/docs` and `/openapi.json`.

## Public system endpoints
- `GET /health` — service health.
- `GET /api/v1/meta` — localization/domain constants.

All business endpoints will use `/api/v1/...` and require explicit authorization once Authentication is enabled.
