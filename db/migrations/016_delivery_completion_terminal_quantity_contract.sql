BEGIN;

-- 016: Only quantities from completed, partially delivered,
-- cancelled deliveries, plus the delivery currently transitioning
-- to DELIVERED, may satisfy PO-wide delivery completeness.
--
-- Preserve migration 011 contract: CANCELLED delivery quantities
-- remain included. Do not count unrelated PLANNED, DISPATCHED,
-- or IN_TRANSIT deliveries as completed quantities.

CREATE OR REPLACE FUNCTION public.fn_validate_delivery_state()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $function$
DECLARE
    po_status VARCHAR(20);
    transition_allowed BOOLEAN := FALSE;
    delivered_total NUMERIC(18,4);
    ordered_total NUMERIC(18,4);
    incomplete_items INTEGER;
BEGIN
    SELECT po.status
      INTO po_status
    FROM public.purchase_orders po
    WHERE po.id = NEW.purchase_order_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Purchase order does not exist.'
            USING ERRCODE = '23503';
    END IF;

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

    -- Preserve the existing status transition contract.
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
       AND NEW.status IN ('DELIVERED', 'CANCELLED') THEN
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
        SELECT COALESCE(SUM(di.quantity_delivered), 0)
          INTO delivered_total
        FROM public.delivery_items di
        WHERE di.delivery_id = NEW.id
          AND di.purchase_order_id = NEW.purchase_order_id;

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
        FROM public.purchase_order_items poi
        WHERE poi.purchase_order_id = NEW.purchase_order_id
          AND (
              SELECT COALESCE(SUM(di.quantity_delivered), 0)
              FROM public.delivery_items di
              JOIN public.deliveries d
                ON d.id = di.delivery_id
              WHERE d.purchase_order_id = NEW.purchase_order_id
                AND di.purchase_order_item_id = poi.id
                AND (
                    d.status IN (
                        'PARTIALLY_DELIVERED',
                        'DELIVERED',
                        'CANCELLED'
                    )
                    OR d.id = NEW.id
                )
          ) < poi.quantity;

        IF incomplete_items > 0 THEN
            RAISE EXCEPTION
                'Delivery cannot become DELIVERED before all purchase order item quantities are fully delivered.'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN NEW;
END;
$function$;

-- Assert that the replacement function and its trigger are present.
DO $assert$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname = 'fn_validate_delivery_state'
    ) THEN
        RAISE EXCEPTION
            '016 validation failed: delivery state function is missing.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger t
        WHERE t.tgrelid = 'public.deliveries'::regclass
          AND t.tgname = 'trg_validate_delivery_state'
          AND t.tgfoid =
              'public.fn_validate_delivery_state()'::regprocedure
          AND NOT t.tgisinternal
          AND t.tgenabled IN ('O', 'A')
    ) THEN
        RAISE EXCEPTION
            '016 validation failed: active delivery state trigger is missing.';
    END IF;
END;
$assert$;

COMMIT;
