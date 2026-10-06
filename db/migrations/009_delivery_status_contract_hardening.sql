BEGIN;

-- ============================================================
-- 009 DELIVERY STATUS CONTRACT HARDENING
-- Align DB status transitions with the Delivery API contract.
--
-- Changes relative to 008:
--   1. Same-status updates are no longer accepted.
--   2. PARTIALLY_DELIVERED -> PARTIALLY_DELIVERED is rejected.
--
-- Existing 008 migration is intentionally NOT modified.
-- Existing delivery data is NOT changed.
-- Existing trigger is preserved.
-- ============================================================


-- ============================================================
-- 1. HARDEN DELIVERY STATUS TRANSITION VALIDATION
-- ============================================================

CREATE OR REPLACE FUNCTION fn_validate_delivery_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    po_status VARCHAR(20);
    transition_allowed BOOLEAN := FALSE;
    delivered_total NUMERIC(18,4);
    ordered_total NUMERIC(18,4);
    incomplete_items INTEGER;
BEGIN

    SELECT po.status
      INTO po_status
    FROM purchase_orders po
    WHERE po.id = NEW.purchase_order_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Purchase order does not exist.'
            USING ERRCODE = '23503';
    END IF;


    -- Delivery creation is allowed only for APPROVED PO.
    IF TG_OP = 'INSERT' THEN

        IF NEW.status <> 'PLANNED' THEN
            RAISE EXCEPTION
                'New delivery must start in PLANNED status.'
                USING ERRCODE = '23514';
        END IF;

        IF po_status <> 'APPROVED' THEN
            RAISE EXCEPTION
                'Delivery can only be created for an APPROVED purchase order.'
                USING ERRCODE = '23514';
        END IF;

        RETURN NEW;
    END IF;


    -- Same-status updates are intentionally NOT allowed.
    -- The API contract rejects them with HTTP 400.


    IF OLD.status = 'PLANNED'
       AND NEW.status IN ('DISPATCHED', 'CANCELLED') THEN
        transition_allowed := TRUE;

    ELSIF OLD.status = 'DISPATCHED'
       AND NEW.status IN ('IN_TRANSIT', 'CANCELLED') THEN
        transition_allowed := TRUE;

    ELSIF OLD.status = 'IN_TRANSIT'
       AND NEW.status IN (
           'PARTIALLY_DELIVERED',
           'DELIVERED',
           'CANCELLED'
       ) THEN
        transition_allowed := TRUE;

    ELSIF OLD.status = 'PARTIALLY_DELIVERED'
       AND NEW.status IN (
           'DELIVERED',
           'CANCELLED'
       ) THEN
        transition_allowed := TRUE;
    END IF;


    IF NOT transition_allowed THEN
        RAISE EXCEPTION
            'Invalid delivery status transition: % -> %',
            OLD.status,
            NEW.status
            USING ERRCODE = '23514';
    END IF;


    IF NEW.status IN (
        'DISPATCHED',
        'IN_TRANSIT',
        'PARTIALLY_DELIVERED',
        'DELIVERED'
    ) THEN

        IF NEW.dispatched_at IS NULL THEN
            NEW.dispatched_at := COALESCE(OLD.dispatched_at, now());
        END IF;

        IF po_status <> 'APPROVED' THEN
            RAISE EXCEPTION
                'Delivery execution requires the purchase order to remain APPROVED.'
                USING ERRCODE = '23514';
        END IF;

    END IF;


    IF NEW.status = 'PARTIALLY_DELIVERED' THEN

        SELECT
            COALESCE(SUM(di.quantity_delivered), 0)
        INTO delivered_total
        FROM delivery_items di
        JOIN deliveries d
          ON d.id = di.delivery_id
        WHERE d.purchase_order_id = NEW.purchase_order_id
          AND d.status <> 'CANCELLED';

        IF delivered_total <= 0 THEN
            RAISE EXCEPTION
                'PARTIALLY_DELIVERED requires delivered quantity.'
                USING ERRCODE = '23514';
        END IF;

    END IF;


    IF NEW.status = 'DELIVERED' THEN

        IF NEW.delivered_at IS NULL THEN
            NEW.delivered_at := now();
        END IF;

        IF NEW.received_by IS NULL THEN
            RAISE EXCEPTION
                'DELIVERED requires received_by.'
                USING ERRCODE = '23514';
        END IF;


        SELECT COUNT(*)
        INTO incomplete_items
        FROM purchase_order_items poi
        WHERE poi.purchase_order_id = NEW.purchase_order_id
          AND (
              SELECT COALESCE(SUM(di.quantity_delivered), 0)
              FROM delivery_items di
              JOIN deliveries d
                ON d.id = di.delivery_id
              WHERE d.purchase_order_id = NEW.purchase_order_id
                AND d.status <> 'CANCELLED'
                AND di.purchase_order_item_id = poi.id
          ) < poi.quantity;


        IF incomplete_items > 0 THEN
            RAISE EXCEPTION
                'Delivery cannot become DELIVERED before all purchase order item quantities are fully delivered.'
                USING ERRCODE = '23514';
        END IF;

    END IF;


    RETURN NEW;
END;
$$;


-- ============================================================
-- 2. POST-MIGRATION CONTRACT ASSERTION
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc
        WHERE proname = 'fn_validate_delivery_state'
    ) THEN
        RAISE EXCEPTION
            '009 hardening failed: fn_validate_delivery_state is missing.';
    END IF;
END;
$$;


COMMIT;
