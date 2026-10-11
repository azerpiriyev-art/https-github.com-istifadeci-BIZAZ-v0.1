BEGIN;

-- ============================================================
-- 014 REVIEW & RATINGS
-- Additive tenant-scoped review storage; existing business data
-- is not modified by this migration.
-- ============================================================

CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,

    purchase_order_id UUID NOT NULL,

    supplier_id UUID NOT NULL
        REFERENCES suppliers(id) ON DELETE RESTRICT,

    reviewer_user_id UUID NOT NULL,

    rating SMALLINT NOT NULL
        CHECK (rating BETWEEN 1 AND 5),

    comment TEXT
        CHECK (comment IS NULL OR char_length(comment) <= 2000),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_reviews_purchase_order_company_supplier
        FOREIGN KEY (purchase_order_id, company_id, supplier_id)
        REFERENCES purchase_orders (id, company_id, supplier_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_reviews_reviewer_company_member
        FOREIGN KEY (reviewer_user_id, company_id)
        REFERENCES company_members (user_id, company_id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_reviews_purchase_order
        UNIQUE (purchase_order_id),

    CONSTRAINT chk_reviews_rating_range
        CHECK (rating >= 1 AND rating <= 5),

    CONSTRAINT chk_reviews_comment_length
        CHECK (comment IS NULL OR char_length(comment) <= 2000)
);

CREATE INDEX idx_reviews_company_supplier_created
    ON reviews (company_id, supplier_id, created_at DESC);

CREATE INDEX idx_reviews_company_purchase_order
    ON reviews (company_id, purchase_order_id);

COMMIT;
