BEGIN;

-- ============================================================
-- 013 PAYMENT ↔ PURCHASE ORDER STATUS CONTRACT HARDENING
-- ============================================================
--
-- Payment may only be created for, or reassigned to:
--   APPROVED
--   RECEIVED
--
-- Rejected Purchase Order states:
--   DRAFT
--   SUBMITTED
--   CANCELLED
--
-- This migration:
--   * does NOT modify existing payment data
--   * does NOT modify 010 payment status validation
--   * does NOT modify 005/006 constraints
--   * enforces company isolation at DB level
--   * protects both INSERT and purchase_order_id/company_id UPDATE
-- ============================================================


-- ============================================================
-- 1. PAYMENT ↔ PURCHASE ORDER VALIDATION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION fn_validate_payment_purchase_order()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    po_company_id UUID;
    po_status VARCHAR(20);
BEGIN

    -- Purchase order must exist.
    SELECT
        po.company_id,
        po.status
    INTO
        po_company_id,
        po_status
    FROM purchase_orders po
    WHERE po.id = NEW.purchase_order_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Invalid payment purchase order: purchase order % does not exist',
            NEW.purchase_order_id
            USING ERRCODE = '23503';
    END IF;


    -- Payment and Purchase Order must belong to the same company.
    IF NEW.company_id IS DISTINCT FROM po_company_id THEN
        RAISE EXCEPTION
            'Invalid payment purchase order: payment company % does not match purchase order company %',
            NEW.company_id,
            po_company_id
            USING ERRCODE = '23514';
    END IF;


    -- Payment is permitted only for APPROVED or RECEIVED Purchase Orders.
    IF po_status NOT IN ('APPROVED', 'RECEIVED') THEN
        RAISE EXCEPTION
            'Payment is not allowed for purchase order % in status %',
            NEW.purchase_order_id,
            po_status
            USING ERRCODE = '23514';
    END IF;


    RETURN NEW;
END;
$$;


-- ============================================================
-- 2. PAYMENT ↔ PURCHASE ORDER VALIDATION TRIGGER
-- ============================================================

DROP TRIGGER IF EXISTS trg_validate_payment_purchase_order
ON payments;

CREATE TRIGGER trg_validate_payment_purchase_order
BEFORE INSERT OR UPDATE OF purchase_order_id, company_id
ON payments
FOR EACH ROW
EXECUTE FUNCTION fn_validate_payment_purchase_order();


-- ============================================================
-- 3. POST-MIGRATION CONTRACT ASSERTIONS
-- ============================================================

DO $$
BEGIN

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc
        WHERE proname = 'fn_validate_payment_purchase_order'
    ) THEN
        RAISE EXCEPTION
            '013 hardening failed: fn_validate_payment_purchase_order is missing.';
    END IF;


    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_validate_payment_purchase_order'
          AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION
            '013 hardening failed: trg_validate_payment_purchase_order is missing.';
    END IF;

END;
$$;


COMMIT;