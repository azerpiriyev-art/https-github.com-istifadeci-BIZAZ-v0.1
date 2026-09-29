# Database Documentation

PostgreSQL 16. UUID primary keys are used for externally exposed entities. `citext` provides case-insensitive email uniqueness. Financial values use NUMERIC rather than floating point. Audit events are append-oriented.

Migration sequence: `001_foundation.sql` -> `001_foundation_catalog.sql` -> `001_foundation_procurement.sql` -> `002_procurement.sql` -> `003_need_engine_v2.sql` -> `004_approval_engine.sql` -> `005_payment_engine.sql` -> `006_payment_state_machine.sql` -> `007_supplier_offer_item_uniqueness.sql`.
