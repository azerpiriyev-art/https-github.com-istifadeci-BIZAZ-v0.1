BEGIN;

-- ============================================================
-- 008 DELIVERY ENGINE
-- Additive migration.
-- Existing procurement/payment data is not migrated or modified.
-- ============================================================


-- ============================================================
-- 1. Composite uniqueness required for cross-column FK integrity
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_purchase_orders_id_company_supplier'
          AND conrelid = 'purchase_orders'::regclass
    ) THEN
        ALTER TABLE purchase_orders
            ADD CONSTRAINT uq_purchase_orders_id_company_supplier
            UNIQUE (id, company_id, supplier_id);
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_purchase_order_items_id_purchase_order'
          AND conrelid = 'purchase_order_items'::regclass
    ) THEN
        ALTER TABLE purchase_order_items
            ADD CONSTRAINT uq_purchase_order_items_id_purchase_order
            UNIQUE (id, purchase_order_id);
    END IF;
END
$$;


-- ============================================================
-- 2. DELIVERIES
-- ============================================================

CREATE TABLE IF NOT EXISTS deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,

    purchase_order_id UUID NOT NULL,

    supplier_id UUID NOT NULL
        REFERENCES suppliers(id) ON DELETE RESTRICT,

    delivery_number VARCHAR(50) NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'PLANNED'
        CHECK (
            status IN (
                'PLANNED',
                'DISPATCHED',
                'IN_TRANSIT',
                'PARTIALLY_DELIVERED',
                'DELIVERED',
                'CANCELLED'
            )
        ),

    scheduled_date DATE,

    dispatched_at TIMESTAMPTZ,

    delivered_at TIMESTAMPTZ,

    received_by UUID
        REFERENCES users(id) ON DELETE SET NULL,

    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_deliveries_purchase_order_company_supplier
        FOREIGN KEY (
            purchase_order_id,
            company_id,
            supplier_id
        )
        REFERENCES purchase_orders (
            id,
            company_id,
            supplier_id
        )
        ON DELETE RESTRICT,

    CONSTRAINT uq_deliveries_id_purchase_order
        UNIQUE (id, purchase_order_id),

    CONSTRAINT uq_deliveries_company_number
        UNIQUE (company_id, delivery_number),

    CONSTRAINT chk_deliveries_timestamps
        CHECK (
            (
                status IN (
                    'PLANNED',
                    'CANCELLED'
                )
                AND delivered_at IS NULL
            )
            OR
            (
                status IN (
                    'DISPATCHED',
                    'IN_TRANSIT',
                    'PARTIALLY_DELIVERED'
                )
                AND delivered_at IS NULL
            )
            OR
            (
                status = 'DELIVERED'
                AND delivered_at IS NOT NULL
            )
        )
);


CREATE INDEX IF NOT EXISTS idx_deliveries_company
    ON deliveries(company_id);

CREATE INDEX IF NOT EXISTS idx_deliveries_purchase_order
    ON deliveries(purchase_order_id);

CREATE INDEX IF NOT EXISTS idx_deliveries_supplier
    ON deliveries(supplier_id);

CREATE INDEX IF NOT EXISTS idx_deliveries_company_status
    ON deliveries(company_id, status);


-- ============================================================
-- 2A. COMPANY-SCOPED RECEIVER INTEGRITY
-- A delivery receiver must belong to the delivery company.
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_deliveries_received_by_company'
          AND conrelid = 'deliveries'::regclass
    ) THEN
        ALTER TABLE deliveries
            ADD CONSTRAINT fk_deliveries_received_by_company
            FOREIGN KEY (received_by, company_id)
            REFERENCES company_members (user_id, company_id);
    END IF;
END
$$;


-- ============================================================
-- 3. DELIVERY ITEMS
-- ============================================================

CREATE TABLE IF NOT EXISTS delivery_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    delivery_id UUID NOT NULL,

    purchase_order_id UUID NOT NULL,

    purchase_order_item_id UUID NOT NULL,

    quantity_delivered NUMERIC(18,4) NOT NULL
        CHECK (quantity_delivered > 0),

    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_delivery_items_delivery
        FOREIGN KEY (
            delivery_id,
            purchase_order_id
        )
        REFERENCES deliveries (
            id,
            purchase_order_id
        )
        ON DELETE CASCADE,

    CONSTRAINT fk_delivery_items_purchase_order_item
        FOREIGN KEY (
            purchase_order_item_id,
            purchase_order_id
        )
        REFERENCES purchase_order_items (
            id,
            purchase_order_id
        )
        ON DELETE RESTRICT
);


CREATE INDEX IF NOT EXISTS idx_delivery_items_delivery
    ON delivery_items(delivery_id);

CREATE INDEX IF NOT EXISTS idx_delivery_items_purchase_order
    ON delivery_items(purchase_order_id);

CREATE INDEX IF NOT EXISTS idx_delivery_items_po_item
    ON delivery_items(purchase_order_item_id);


-- ============================================================
-- 3A. DELIVERY ITEM UNIQUENESS
-- One PO item may appear only once in a delivery.
-- Partial quantities must be distributed across separate
-- deliveries, not duplicate lines in the same delivery.
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_delivery_items_delivery_item'
          AND conrelid = 'delivery_items'::regclass
    ) THEN
        ALTER TABLE delivery_items
            ADD CONSTRAINT uq_delivery_items_delivery_item
            UNIQUE (delivery_id, purchase_order_item_id);
    END IF;
END
$$;


-- ============================================================
-- 4. DELIVERY STATUS TRANSITION + PO DEPENDENCY VALIDATION
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


    -- No-op status update is allowed.
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;


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
           'PARTIALLY_DELIVERED',
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
        WHERE d.purchase_order_id = NEW.purchase_order_id;
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


DROP TRIGGER IF EXISTS trg_validate_delivery_state ON deliveries;

CREATE TRIGGER trg_validate_delivery_state
BEFORE INSERT OR UPDATE OF status
ON deliveries
FOR EACH ROW
EXECUTE FUNCTION fn_validate_delivery_state();


-- ============================================================
-- 5. DELIVERY ITEM QUANTITY INVARIANT
-- ============================================================

CREATE OR REPLACE FUNCTION fn_validate_delivery_item_quantity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    ordered_qty NUMERIC(18,4);
    already_delivered NUMERIC(18,4);
    delivery_status VARCHAR(30);
    po_status VARCHAR(20);
BEGIN

    SELECT
        poi.quantity,
        po.status,
        d.status
    INTO
        ordered_qty,
        po_status,
        delivery_status
    FROM purchase_order_items poi
    JOIN purchase_orders po
      ON po.id = poi.purchase_order_id
    JOIN deliveries d
      ON d.id = NEW.delivery_id
    WHERE poi.id = NEW.purchase_order_item_id
      AND poi.purchase_order_id = NEW.purchase_order_id
      AND d.purchase_order_id = NEW.purchase_order_id
    FOR UPDATE OF poi;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Delivery item does not belong to the delivery purchase order.'
            USING ERRCODE = '23503';
    END IF;


    IF po_status <> 'APPROVED' THEN
        RAISE EXCEPTION
            'Delivery items can only be changed while the purchase order is APPROVED.'
            USING ERRCODE = '23514';
    END IF;


    IF delivery_status IN ('DELIVERED', 'CANCELLED') THEN
        RAISE EXCEPTION
            'Delivery items cannot be changed after delivery reaches a terminal state.'
            USING ERRCODE = '23514';
    END IF;


    SELECT
        COALESCE(SUM(di.quantity_delivered), 0)
    INTO already_delivered
    FROM delivery_items di
    JOIN deliveries d
      ON d.id = di.delivery_id
    WHERE di.purchase_order_item_id = NEW.purchase_order_item_id
      AND di.purchase_order_id = NEW.purchase_order_id
      AND d.purchase_order_id = NEW.purchase_order_id
AND di.id <> NEW.id;


    IF already_delivered + NEW.quantity_delivered > ordered_qty THEN
        RAISE EXCEPTION
            'Delivered quantity exceeds ordered quantity. Ordered: %, Already delivered: %, New quantity: %',
            ordered_qty,
            already_delivered,
            NEW.quantity_delivered
            USING ERRCODE = '23514';
    END IF;


    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS trg_validate_delivery_item_quantity
ON delivery_items;

CREATE TRIGGER trg_validate_delivery_item_quantity
BEFORE INSERT OR UPDATE OF
    delivery_id,
    purchase_order_id,
    purchase_order_item_id,
    quantity_delivered
ON delivery_items
FOR EACH ROW
EXECUTE FUNCTION fn_validate_delivery_item_quantity();


-- ============================================================
-- 6. UPDATED_AT MAINTENANCE
-- ============================================================

CREATE OR REPLACE FUNCTION fn_touch_delivery_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS trg_touch_deliveries_updated_at
ON deliveries;

CREATE TRIGGER trg_touch_deliveries_updated_at
BEFORE UPDATE
ON deliveries
FOR EACH ROW
EXECUTE FUNCTION fn_touch_delivery_updated_at();


DROP TRIGGER IF EXISTS trg_touch_delivery_items_updated_at
ON delivery_items;

CREATE TRIGGER trg_touch_delivery_items_updated_at
BEFORE UPDATE
ON delivery_items
FOR EACH ROW
EXECUTE FUNCTION fn_touch_delivery_updated_at();


COMMIT;
