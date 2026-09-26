BEGIN;

CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,

    purchase_order_id UUID NOT NULL
        REFERENCES purchase_orders(id) ON DELETE RESTRICT,

    amount NUMERIC(18,4) NOT NULL
        CHECK (amount > 0),

    currency CHAR(3) NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (
            status IN (
                'PENDING',
                'PAID',
                'FAILED',
                'CANCELLED'
            )
        ),

    reference VARCHAR(100),

    paid_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payments_company
    ON payments(company_id);

CREATE INDEX IF NOT EXISTS idx_payments_purchase_order
    ON payments(purchase_order_id);

CREATE INDEX IF NOT EXISTS idx_payments_company_status
    ON payments(company_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_reference
    ON payments(reference)
    WHERE reference IS NOT NULL;

COMMIT;
