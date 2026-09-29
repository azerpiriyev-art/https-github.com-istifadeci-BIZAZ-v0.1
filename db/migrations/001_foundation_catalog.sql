BEGIN;

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sku VARCHAR(100),
    category TEXT,
    unit VARCHAR(30) NOT NULL DEFAULT 'ədəd',
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS product_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,
    product_id UUID NOT NULL
        REFERENCES products(id) ON DELETE CASCADE,
    price_type VARCHAR(20) NOT NULL,
    amount NUMERIC(18,4) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'AZN',
    vat_included BOOLEAN NOT NULL DEFAULT FALSE,
    supplier_id UUID,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    tax_id VARCHAR(10),
    contact_person TEXT,
    phone VARCHAR(50),
    email VARCHAR(255),
    address TEXT,
    bank_name TEXT,
    bank_account VARCHAR(100),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_products_company_sku'
          AND conrelid = 'products'::regclass
    ) THEN
        ALTER TABLE products
            ADD CONSTRAINT uq_products_company_sku
            UNIQUE (company_id, sku);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_product_prices_type'
          AND conrelid = 'product_prices'::regclass
    ) THEN
        ALTER TABLE product_prices
            ADD CONSTRAINT chk_product_prices_type
            CHECK (price_type IN ('PURCHASE', 'SALE'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'product_prices_amount_check'
          AND conrelid = 'product_prices'::regclass
    ) THEN
        ALTER TABLE product_prices
            ADD CONSTRAINT product_prices_amount_check
            CHECK (amount >= 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_suppliers_company_tax_id'
          AND conrelid = 'suppliers'::regclass
    ) THEN
        ALTER TABLE suppliers
            ADD CONSTRAINT uq_suppliers_company_tax_id
            UNIQUE (company_id, tax_id);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_products_company
    ON products(company_id);

CREATE INDEX IF NOT EXISTS idx_product_prices_company
    ON product_prices(company_id);

CREATE INDEX IF NOT EXISTS idx_product_prices_product
    ON product_prices(product_id);

CREATE INDEX IF NOT EXISTS idx_product_prices_type
    ON product_prices(product_id, price_type);

CREATE INDEX IF NOT EXISTS idx_product_prices_valid_from
    ON product_prices(product_id, valid_from DESC);

CREATE INDEX IF NOT EXISTS idx_suppliers_company
    ON suppliers(company_id);

CREATE INDEX IF NOT EXISTS idx_suppliers_company_name
    ON suppliers(company_id, name);

CREATE INDEX IF NOT EXISTS idx_suppliers_tax_id
    ON suppliers(tax_id);

CREATE INDEX IF NOT EXISTS idx_suppliers_active
    ON suppliers(company_id, is_active);

COMMIT;
