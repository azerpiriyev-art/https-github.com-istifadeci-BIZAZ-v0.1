BEGIN;

ALTER TABLE payments
    DROP CONSTRAINT IF EXISTS chk_payments_paid_at_consistency;

ALTER TABLE payments
    ADD CONSTRAINT chk_payments_paid_at_consistency
    CHECK (
        (status = 'PAID' AND paid_at IS NOT NULL)
        OR
        (status IN ('PENDING', 'FAILED', 'CANCELLED') AND paid_at IS NULL)
    );

COMMIT;
