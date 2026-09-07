BEGIN;

CREATE TABLE IF NOT EXISTS purchase_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,
    request_number VARCHAR(50) NOT NULL,
    request_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT','SUBMITTED','APPROVED','CLOSED','CANCELLED')),
    requested_by UUID NOT NULL
        REFERENCES users(id) ON DELETE RESTRICT,
    approved_by UUID
        REFERENCES users(id) ON DELETE RESTRICT,
    approved_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_purchase_requests_company_number
        UNIQUE (company_id, request_number),

    CONSTRAINT ck_purchase_requests_approval
        CHECK (
            (status <> 'APPROVED')
            OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
        )
);

CREATE TABLE IF NOT EXISTS purchase_request_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_request_id UUID NOT NULL
        REFERENCES purchase_requests(id) ON DELETE CASCADE,
    product_id UUID NOT NULL
        REFERENCES products(id) ON DELETE RESTRICT,
    quantity NUMERIC(18,4) NOT NULL
        CHECK (quantity > 0),
    unit VARCHAR(30) NOT NULL,
    required_date DATE,
    specifications TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS supplier_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,
    purchase_request_id UUID NOT NULL
        REFERENCES purchase_requests(id) ON DELETE RESTRICT,
    supplier_id UUID NOT NULL
        REFERENCES suppliers(id) ON DELETE RESTRICT,
    offer_number VARCHAR(50) NOT NULL,
    offer_date DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_until DATE,
    currency CHAR(3) NOT NULL DEFAULT 'AZN',
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT','SUBMITTED','ACCEPTED','REJECTED','EXPIRED')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_supplier_offers_company_number
        UNIQUE (company_id, offer_number),

    CONSTRAINT ck_supplier_offers_validity
        CHECK (valid_until IS NULL OR valid_until >= offer_date)
);

CREATE TABLE IF NOT EXISTS supplier_offer_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_offer_id UUID NOT NULL
        REFERENCES supplier_offers(id) ON DELETE CASCADE,
    purchase_request_item_id UUID NOT NULL
        REFERENCES purchase_request_items(id) ON DELETE RESTRICT,
    product_id UUID NOT NULL
        REFERENCES products(id) ON DELETE RESTRICT,
    quantity NUMERIC(18,4) NOT NULL
        CHECK (quantity > 0),
    unit VARCHAR(30) NOT NULL,
    unit_price NUMERIC(18,4) NOT NULL
        CHECK (unit_price >= 0),
    vat_rate NUMERIC(5,2) NOT NULL DEFAULT 18.00
        CHECK (vat_rate >= 0 AND vat_rate <= 100),
    vat_amount NUMERIC(18,4) NOT NULL DEFAULT 0
        CHECK (vat_amount >= 0),
    line_total NUMERIC(18,4) NOT NULL DEFAULT 0
        CHECK (line_total >= 0),
    delivery_days INTEGER
        CHECK (delivery_days IS NULL OR delivery_days >= 0),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS offer_selections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,
    purchase_request_id UUID NOT NULL
        REFERENCES purchase_requests(id) ON DELETE RESTRICT,
    supplier_offer_id UUID NOT NULL
        REFERENCES supplier_offers(id) ON DELETE RESTRICT,
    selected_by UUID NOT NULL
        REFERENCES users(id) ON DELETE RESTRICT,
    selected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(20) NOT NULL DEFAULT 'SELECTED'
        CHECK (status IN ('SELECTED','CANCELLED')),
    justification TEXT NOT NULL,
    purchase_order_id UUID
        REFERENCES purchase_orders(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_offer_selections_active_request
    ON offer_selections(purchase_request_id)
    WHERE status = 'SELECTED';

CREATE UNIQUE INDEX IF NOT EXISTS uq_offer_selections_active_offer
    ON offer_selections(supplier_offer_id)
    WHERE status = 'SELECTED';

CREATE INDEX IF NOT EXISTS idx_purchase_requests_company_status
    ON purchase_requests(company_id, status);

CREATE INDEX IF NOT EXISTS idx_purchase_requests_requested_by
    ON purchase_requests(requested_by);

CREATE INDEX IF NOT EXISTS idx_purchase_request_items_request
    ON purchase_request_items(purchase_request_id);

CREATE INDEX IF NOT EXISTS idx_purchase_request_items_product
    ON purchase_request_items(product_id);

CREATE INDEX IF NOT EXISTS idx_supplier_offers_company_status
    ON supplier_offers(company_id, status);

CREATE INDEX IF NOT EXISTS idx_supplier_offers_request
    ON supplier_offers(purchase_request_id);

CREATE INDEX IF NOT EXISTS idx_supplier_offers_supplier
    ON supplier_offers(supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_offer_items_offer
    ON supplier_offer_items(supplier_offer_id);

CREATE INDEX IF NOT EXISTS idx_supplier_offer_items_request_item
    ON supplier_offer_items(purchase_request_item_id);

CREATE INDEX IF NOT EXISTS idx_supplier_offer_items_product
    ON supplier_offer_items(product_id);

CREATE INDEX IF NOT EXISTS idx_offer_selections_company_status
    ON offer_selections(company_id, status);

CREATE INDEX IF NOT EXISTS idx_offer_selections_request
    ON offer_selections(purchase_request_id);

CREATE INDEX IF NOT EXISTS idx_offer_selections_offer
    ON offer_selections(supplier_offer_id);

CREATE INDEX IF NOT EXISTS idx_offer_selections_po
    ON offer_selections(purchase_order_id);

COMMIT;
