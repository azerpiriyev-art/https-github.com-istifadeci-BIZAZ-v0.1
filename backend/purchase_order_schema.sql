CREATE TABLE IF NOT EXISTS purchase_orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    supplier_id uuid NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,

    order_number varchar(50) NOT NULL,
    order_date date NOT NULL DEFAULT CURRENT_DATE,

    status varchar(20) NOT NULL DEFAULT 'DRAFT',

    currency varchar(3) NOT NULL DEFAULT 'AZN',

    subtotal numeric(18,4) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    vat_amount numeric(18,4) NOT NULL DEFAULT 0 CHECK (vat_amount >= 0),
    total_amount numeric(18,4) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),

    notes text,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_purchase_orders_company_number
        UNIQUE (company_id, order_number),

    CONSTRAINT chk_purchase_orders_status
        CHECK (status IN ('DRAFT', 'SUBMITTED', 'APPROVED', 'RECEIVED', 'CANCELLED'))
);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_company
    ON purchase_orders(company_id);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier
    ON purchase_orders(supplier_id);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_company_date
    ON purchase_orders(company_id, order_date DESC);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_status
    ON purchase_orders(company_id, status);


CREATE TABLE IF NOT EXISTS purchase_order_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_id uuid NOT NULL
        REFERENCES purchase_orders(id) ON DELETE CASCADE,

    product_id uuid NOT NULL
        REFERENCES products(id) ON DELETE RESTRICT,

    quantity numeric(18,4) NOT NULL CHECK (quantity > 0),
    unit varchar(30) NOT NULL DEFAULT 'ədəd',

    unit_price numeric(18,4) NOT NULL CHECK (unit_price >= 0),

    vat_rate numeric(5,2) NOT NULL DEFAULT 18.00
        CHECK (vat_rate >= 0 AND vat_rate <= 100),

    vat_amount numeric(18,4) NOT NULL DEFAULT 0
        CHECK (vat_amount >= 0),

    line_total numeric(18,4) NOT NULL DEFAULT 0
        CHECK (line_total >= 0),

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_purchase_order_items_order
    ON purchase_order_items(purchase_order_id);

CREATE INDEX IF NOT EXISTS idx_purchase_order_items_product
    ON purchase_order_items(product_id);
