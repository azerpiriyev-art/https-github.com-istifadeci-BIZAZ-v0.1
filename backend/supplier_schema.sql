CREATE TABLE IF NOT EXISTS suppliers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name text NOT NULL,
    tax_id varchar(10),
    contact_person text,
    phone varchar(50),
    email varchar(255),
    address text,
    bank_name text,
    bank_account varchar(100),
    description text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_suppliers_company_tax_id UNIQUE (company_id, tax_id)
);

CREATE INDEX IF NOT EXISTS idx_suppliers_company
    ON suppliers(company_id);

CREATE INDEX IF NOT EXISTS idx_suppliers_company_name
    ON suppliers(company_id, name);

CREATE INDEX IF NOT EXISTS idx_suppliers_tax_id
    ON suppliers(tax_id);

CREATE INDEX IF NOT EXISTS idx_suppliers_active
    ON suppliers(company_id, is_active);
