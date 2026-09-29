BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_supplier_offer_items_offer_request_item'
          AND conrelid = 'supplier_offer_items'::regclass
    ) THEN
        ALTER TABLE supplier_offer_items
            ADD CONSTRAINT uq_supplier_offer_items_offer_request_item
            UNIQUE (supplier_offer_id, purchase_request_item_id);
    END IF;
END
$$;

COMMIT;
