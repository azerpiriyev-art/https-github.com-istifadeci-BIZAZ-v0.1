BEGIN;

CREATE TABLE IF NOT EXISTS approval_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,

    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (
            status IN (
                'PENDING',
                'IN_PROGRESS',
                'APPROVED',
                'REJECTED',
                'CANCELLED',
                'EXPIRED'
            )
        ),

    execution_mode VARCHAR(20) NOT NULL DEFAULT 'SEQUENTIAL'
        CHECK (execution_mode IN ('SEQUENTIAL','PARALLEL')),

    decision_mode VARCHAR(10) NOT NULL DEFAULT 'ALL'
        CHECK (decision_mode IN ('ALL','ANY')),

    priority VARCHAR(20) NOT NULL DEFAULT 'NORMAL'
        CHECK (priority IN ('LOW','NORMAL','HIGH','URGENT')),

    policy_key VARCHAR(100),
    policy_version VARCHAR(50),

    requested_by UUID NOT NULL
        REFERENCES users(id) ON DELETE RESTRICT,

    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approval_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    approval_request_id UUID NOT NULL
        REFERENCES approval_requests(id) ON DELETE CASCADE,

    step_order INTEGER NOT NULL
        CHECK (step_order > 0),

    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (
            status IN (
                'PENDING',
                'APPROVED',
                'REJECTED',
                'SKIPPED',
                'CANCELLED'
            )
        ),

    approver_user_id UUID
        REFERENCES users(id) ON DELETE RESTRICT,

    approver_role VARCHAR(50),

    acted_by UUID
        REFERENCES users(id) ON DELETE RESTRICT,

    acted_at TIMESTAMPTZ,

    comment TEXT,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_approval_steps_request_order
        UNIQUE (approval_request_id, step_order)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_approval_requests_active_entity
    ON approval_requests(company_id, entity_type, entity_id)
    WHERE status IN ('PENDING','IN_PROGRESS');

CREATE INDEX IF NOT EXISTS idx_approval_requests_company_status
    ON approval_requests(company_id, status);

CREATE INDEX IF NOT EXISTS idx_approval_requests_entity
    ON approval_requests(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_approval_requests_requested_by
    ON approval_requests(requested_by);

CREATE INDEX IF NOT EXISTS idx_approval_steps_request
    ON approval_steps(approval_request_id);

CREATE INDEX IF NOT EXISTS idx_approval_steps_status
    ON approval_steps(status);

CREATE INDEX IF NOT EXISTS idx_approval_steps_approver
    ON approval_steps(approver_user_id);

COMMIT;