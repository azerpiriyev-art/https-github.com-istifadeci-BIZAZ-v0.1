# Database Documentation

PostgreSQL 16. UUID primary keys are used for externally exposed entities. `citext` provides case-insensitive email uniqueness. Financial values use NUMERIC rather than floating point. Audit events are append-oriented.

Migration: `db/migrations/001_foundation.sql`.
