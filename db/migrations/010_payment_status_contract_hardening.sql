BEGIN;

-- ============================================================
-- 010 PAYMENT STATUS CONTRACT HARDENING
-- Align DB payment status transitions with the Payment API
-- contract.
--
-- Allowed transitions:
--   PENDING -> PAID
--   PENDING -> FAILED
--   PENDING -> CANCELLED
--
-- Same-status updates and all terminal-state transitions
-- are rejected.
--
-- Existing 005/006 migrations are intentionally NOT modified.
-- Existing payment data is NOT changed.
-- Existing payment constraints and indexes are preserved.
-- ============================================================


-- ============================================================
-- 1. HARDEN PAYMENT STATUS TRANSITION VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION fn_validate_payment_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    transition_allowed BOOLEAN := FALSE;
BEGIN

    -- Same-status updates are intentionally NOT allowed.
    IF OLD.status = NEW.status THEN
        RAISE EXCEPTION
            'Invalid payment status transition: % -> %',
            OLD.status,
            NEW.status
            USING ERRCODE = '23514';
    END IF;


    -- The Payment API contract allows transitions only
    -- from PENDING to one of the three non-PENDING states.
    IF OLD.status = 'PENDING'
       AND NEW.status IN ('PAID', 'FAILED', 'CANCELLED') THEN
        transition_allowed := TRUE;
    END IF;


    IF NOT transition_allowed THEN
        RAISE EXCEPTION
            'Invalid payment status transition: % -> %',
            OLD.status,
            NEW.status
            USING ERRCODE = '23514';
    END IF;


    RETURN NEW;
END;
$$;


-- ============================================================
-- 2. PAYMENT STATUS VALIDATION TRIGGER
-- ============================================================

DROP TRIGGER IF EXISTS trg_validate_payment_state
ON payments;

CREATE TRIGGER trg_validate_payment_state
BEFORE UPDATE OF status ON payments
FOR EACH ROW
EXECUTE FUNCTION fn_validate_payment_state();


-- ============================================================
-- 3. POST-MIGRATION CONTRACT ASSERTION
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc
        WHERE proname = 'fn_validate_payment_state'
    ) THEN
        RAISE EXCEPTION
            '010 hardening failed: fn_validate_payment_state is missing.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_validate_payment_state'
          AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION
            '010 hardening failed: trg_validate_payment_state is missing.';
    END IF;
END;
$$;


COMMIT;
