BEGIN;

-- ============================================================
-- 012 PURCHASE ORDER STATUS CONTRACT HARDENING
--
-- Enforce the Purchase Order API transition contract at the
-- database level.
--
-- Existing PO rows are not modified.
-- INSERT is intentionally not guarded by this transition trigger.
-- Legacy APPROVED -> RECEIVED remains valid when no deliveries
-- are linked to the purchase order.
-- ============================================================

CREATE OR REPLACE FUNCTION fn_validate_purchase_order_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    transition_allowed BOOLEAN := FALSE;
    deliveries_exist BOOLEAN := FALSE;
    active_deliveries INTEGER := 0;
    purchase_order_item_count INTEGER := 0;
    incomplete_items INTEGER := 0;
BEGIN
    -- Same-status updates are intentionally rejected.
    IF OLD.status = NEW.status THEN
        RAISE EXCEPTION
            'Invalid purchase order status transition: % -> %',
            OLD.status,
            NEW.status
            USING ERRCODE = '23514';
    END IF;

    -- Preserve the Purchase Order API transition matrix.
    IF OLD.status = 'DRAFT'
       AND NEW.status IN ('SUBMITTED', 'CANCELLED') THEN
        transition_allowed := TRUE;

    ELSIF OLD.status = 'SUBMITTED'
       AND NEW.status IN ('APPROVED', 'CANCELLED') THEN
        transition_allowed := TRUE;

    ELSIF OLD.status = 'APPROVED'
       AND NEW.status = 'RECEIVED' THEN
        transition_allowed := TRUE;
    END IF;

    IF NOT transition_allowed THEN
        RAISE EXCEPTION
            'Invalid purchase order status transition: % -> %',
            OLD.status,
            NEW.status
            USING ERRCODE = '23514';
    END IF;

    -- Receiving a PO without Delivery records remains supported
    -- for existing legacy procurement workflows.
    IF OLD.status = 'APPROVED'
       AND NEW.status = 'RECEIVED' THEN

        SELECT EXISTS (
            SELECT 1
            FROM deliveries d
            WHERE d.purchase_order_id = NEW.id
        )
        INTO deliveries_exist;

        IF deliveries_exist THEN

            -- All linked deliveries must be terminal before the
            -- purchase order can be marked RECEIVED.
            SELECT COUNT(*)
            INTO active_deliveries
            FROM deliveries d
            WHERE d.purchase_order_id = NEW.id
              AND d.status NOT IN ('DELIVERED', 'CANCELLED');

            IF active_deliveries > 0 THEN
                RAISE EXCEPTION
                    'Purchase order cannot become RECEIVED while linked deliveries are active.'
                    USING ERRCODE = '23514';
            END IF;

            SELECT COUNT(*)
            INTO purchase_order_item_count
            FROM purchase_order_items poi
            WHERE poi.purchase_order_id = NEW.id;

            IF purchase_order_item_count = 0 THEN
                RAISE EXCEPTION
                    'Purchase order cannot become RECEIVED with linked deliveries but no purchase order items.'
                    USING ERRCODE = '23514';
            END IF;

            -- Count all recorded physical quantities, including
            -- quantities on CANCELLED deliveries, consistently
            -- with migration 011.
            SELECT COUNT(*)
            INTO incomplete_items
            FROM purchase_order_items poi
            WHERE poi.purchase_order_id = NEW.id
              AND (
                  SELECT COALESCE(SUM(di.quantity_delivered), 0)
                  FROM delivery_items di
                  WHERE di.purchase_order_id = NEW.id
                    AND di.purchase_order_item_id = poi.id
              ) < poi.quantity;

            IF incomplete_items > 0 THEN
                RAISE EXCEPTION
                    'Purchase order cannot become RECEIVED before all ordered item quantities are accounted for.'
                    USING ERRCODE = '23514';
            END IF;

        END IF;
    END IF;

    RETURN NEW;
END;
$$;


-- Apply transition validation only to status updates.
DROP TRIGGER IF EXISTS trg_validate_purchase_order_state
ON purchase_orders;

CREATE TRIGGER trg_validate_purchase_order_state
BEFORE UPDATE OF status
ON purchase_orders
FOR EACH ROW
EXECUTE FUNCTION fn_validate_purchase_order_state();


-- ============================================================
-- POST-MIGRATION CONTRACT ASSERTION
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc
        WHERE proname = 'fn_validate_purchase_order_state'
          AND pronamespace = 'public'::regnamespace
    ) THEN
        RAISE EXCEPTION
            '012 hardening failed: fn_validate_purchase_order_state is missing.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE t.tgname = 'trg_validate_purchase_order_state'
          AND c.relname = 'purchase_orders'
          AND n.nspname = 'public'
          AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION
            '012 hardening failed: trg_validate_purchase_order_state is missing.';
    END IF;
END;
$$;

COMMIT;
