BEGIN;

ALTER TABLE purchase_request_items
    ADD CONSTRAINT uq_purchase_request_items_id_request_product
    UNIQUE (id, purchase_request_id, product_id);

CREATE TABLE IF NOT EXISTS needs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,

    need_number VARCHAR(50) NOT NULL,

    source VARCHAR(20) NOT NULL DEFAULT 'MANUAL'
        CHECK (source IN ('MANUAL','PROJECT','INVENTORY')),

    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT'
        CHECK (
            status IN (
                'DRAFT',
                'SUBMITTED',
                'UNDER_REVIEW',
                'APPROVED',
                'PARTIALLY_CONVERTED',
                'FULLY_CONVERTED',
                'CLOSED',
                'REJECTED',
                'CANCELLED',
                'EXPIRED'
            )
        ),

    title VARCHAR(255) NOT NULL,
    description TEXT,

    requested_by UUID NOT NULL
        REFERENCES users(id) ON DELETE RESTRICT,

    required_date DATE,

    priority VARCHAR(20) NOT NULL DEFAULT 'NORMAL'
        CHECK (priority IN ('LOW','NORMAL','HIGH','URGENT')),

    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_needs_company_number
        UNIQUE (company_id, need_number)
);

CREATE TABLE IF NOT EXISTS need_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    need_id UUID NOT NULL
        REFERENCES needs(id) ON DELETE CASCADE,

    product_id UUID NOT NULL
        REFERENCES products(id) ON DELETE RESTRICT,

    quantity NUMERIC(18,4) NOT NULL
        CHECK (quantity > 0),

    unit VARCHAR(30) NOT NULL,

    required_date DATE,
    specifications TEXT,
    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_need_items_id_need_product
        UNIQUE (id, need_id, product_id)
);

CREATE TABLE IF NOT EXISTS need_pr_conversions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    need_id UUID NOT NULL,
    need_item_id UUID NOT NULL,
    product_id UUID NOT NULL,

    purchase_request_id UUID NOT NULL,
    purchase_request_item_id UUID NOT NULL,

    quantity NUMERIC(18,4) NOT NULL
        CHECK (quantity > 0),

    created_by UUID NOT NULL
        REFERENCES users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    notes TEXT,

    CONSTRAINT fk_conversion_need_item_product
        FOREIGN KEY (need_item_id, need_id, product_id)
        REFERENCES need_items(id, need_id, product_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_conversion_pr_item_product
        FOREIGN KEY (purchase_request_item_id, purchase_request_id, product_id)
        REFERENCES purchase_request_items(id, purchase_request_id, product_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_needs_company_status
    ON needs(company_id, status);

CREATE INDEX IF NOT EXISTS idx_needs_requested_by
    ON needs(requested_by);

CREATE INDEX IF NOT EXISTS idx_needs_company_source
    ON needs(company_id, source);

CREATE INDEX IF NOT EXISTS idx_need_items_need
    ON need_items(need_id);

CREATE INDEX IF NOT EXISTS idx_need_items_product
    ON need_items(product_id);

CREATE INDEX IF NOT EXISTS idx_need_pr_conversions_need
    ON need_pr_conversions(need_id);

CREATE INDEX IF NOT EXISTS idx_need_pr_conversions_need_item
    ON need_pr_conversions(need_item_id);

CREATE INDEX IF NOT EXISTS idx_need_pr_conversions_pr
    ON need_pr_conversions(purchase_request_id);

CREATE INDEX IF NOT EXISTS idx_need_pr_conversions_pr_item
    ON need_pr_conversions(purchase_request_item_id);

COMMIT;
