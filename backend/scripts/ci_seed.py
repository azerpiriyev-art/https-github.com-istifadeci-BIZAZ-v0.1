import os
from uuid import UUID
from decimal import Decimal
from pwdlib import PasswordHash
import psycopg


SEED_GUARD = os.getenv("BIZAZ_CI_SEED_ALLOW")
if SEED_GUARD != "1":
    raise RuntimeError(
        "CI seed blocked: BIZAZ_CI_SEED_ALLOW=1 required"
    )


DSN = os.getenv("BIZAZ_TEST_DATABASE_URL")
if not DSN:
    raise RuntimeError(
        "BIZAZ_TEST_DATABASE_URL is required"
    )


# Safety: CI seed must never target production database.
db_name = DSN.rsplit("/", 1)[-1].split("?", 1)[0]
if not db_name.endswith("_test"):
    raise RuntimeError(
        f"CI seed blocked for non-test database: {db_name}"
    )


TEST_EMAIL = os.getenv(
    "BIZAZ_TEST_EMAIL",
    "procurement-test@example.com",
)
TEST_PASSWORD = os.getenv(
    "BIZAZ_TEST_PASSWORD",
    "BIZAZ-Test-2026!",
)

OWNER_EMAIL = os.getenv(
    "BIZAZ_ACCEPTANCE_OWNER_EMAIL",
    "bizaz-rbac-owner-test@gmail.com",
)
OWNER_PASSWORD = os.getenv(
    "BIZAZ_ACCEPTANCE_OWNER_PASSWORD",
    "BIZAZ-Test-2026!",
)

VIEWER_EMAIL = os.getenv(
    "BIZAZ_ACCEPTANCE_VIEWER_EMAIL",
    "bizaz-rbac-viewer-test@gmail.com",
)
VIEWER_PASSWORD = os.getenv(
    "BIZAZ_ACCEPTANCE_VIEWER_PASSWORD",
    "BIZAZ-Test-2026!",
)


password_hash = PasswordHash.recommended()


def upsert_user(conn, email, password, full_name):
    hashed = password_hash.hash(password)

    row = conn.execute(
        """
        INSERT INTO users (
            email,
            password_hash,
            full_name,
            is_active
        )
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (email)
        DO UPDATE SET
            password_hash = EXCLUDED.password_hash,
            full_name = EXCLUDED.full_name,
            is_active = TRUE,
            updated_at = now()
        RETURNING id
        """,
        (email.lower(), hashed, full_name),
    ).fetchone()

    return row[0]


def upsert_company(
    conn,
    tax_id,
    legal_name,
):
    row = conn.execute(
        """
        INSERT INTO companies (
            legal_name,
            tax_id,
            legal_form,
            vat_registered,
            vat_rate,
            currency
        )
        VALUES (
            %s,
            %s,
            'MMC',
            FALSE,
            18.00,
            'AZN'
        )
        ON CONFLICT (tax_id)
        DO UPDATE SET
            legal_name = EXCLUDED.legal_name,
            legal_form = EXCLUDED.legal_form,
            vat_registered = EXCLUDED.vat_registered,
            vat_rate = EXCLUDED.vat_rate,
            currency = EXCLUDED.currency,
            updated_at = now()
        RETURNING id
        """,
        (legal_name, tax_id),
    ).fetchone()

    return row[0]


def ensure_membership(conn, user_id, company_id, role):
    conn.execute(
        """
        INSERT INTO company_members (
            user_id,
            company_id,
            role
        )
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, company_id)
        DO UPDATE SET role = EXCLUDED.role
        """,
        (user_id, company_id, role),
    )


def upsert_product(
    conn,
    company_id,
    name,
    sku,
):
    row = conn.execute(
        """
        INSERT INTO products (
            company_id,
            name,
            sku,
            category,
            unit,
            description,
            is_active
        )
        VALUES (
            %s,
            %s,
            %s,
            'CI',
            'ədəd',
            'Deterministic CI seed product',
            TRUE
        )
        ON CONFLICT (company_id, sku)
        DO UPDATE SET
            name = EXCLUDED.name,
            is_active = TRUE,
            updated_at = now()
        RETURNING id
        """,
        (company_id, name, sku),
    ).fetchone()

    return row[0]


def upsert_supplier(
    conn,
    company_id,
    name,
    tax_id,
):
    row = conn.execute(
        """
        INSERT INTO suppliers (
            company_id,
            name,
            tax_id,
            description,
            is_active
        )
        VALUES (
            %s,
            %s,
            %s,
            'Deterministic CI seed supplier',
            TRUE
        )
        ON CONFLICT (company_id, tax_id)
        DO UPDATE SET
            name = EXCLUDED.name,
            is_active = TRUE,
            updated_at = now()
        RETURNING id
        """,
        (company_id, name, tax_id),
    ).fetchone()

    return row[0]


def upsert_po(
    conn,
    company_id,
    supplier_id,
    order_number,
    status,
):
    row = conn.execute(
        """
        INSERT INTO purchase_orders (
            company_id,
            supplier_id,
            order_number,
            order_date,
            status,
            currency,
            subtotal,
            vat_amount,
            total_amount,
            notes
        )
        VALUES (
            %s,
            %s,
            %s,
            CURRENT_DATE,
            %s,
            'AZN',
            100.0000,
            18.0000,
            118.0000,
            'Deterministic CI seed PO'
        )
        ON CONFLICT (company_id, order_number)
        DO UPDATE SET
            supplier_id = EXCLUDED.supplier_id,
            status = EXCLUDED.status,
            currency = EXCLUDED.currency,
            subtotal = EXCLUDED.subtotal,
            vat_amount = EXCLUDED.vat_amount,
            total_amount = EXCLUDED.total_amount,
            notes = EXCLUDED.notes,
            updated_at = now()
        RETURNING id
        """,
        (
            company_id,
            supplier_id,
            order_number,
            status,
        ),
    ).fetchone()

    return row[0]


def ensure_po_item(
    conn,
    purchase_order_id,
    product_id,
):
    existing = conn.execute(
        """
        SELECT id
        FROM purchase_order_items
        WHERE purchase_order_id = %s
        ORDER BY created_at
        LIMIT 1
        """,
        (purchase_order_id,),
    ).fetchone()

    if existing:
        return existing[0]

    row = conn.execute(
        """
        INSERT INTO purchase_order_items (
            purchase_order_id,
            product_id,
            quantity,
            unit,
            unit_price,
            vat_rate,
            vat_amount,
            line_total
        )
        VALUES (
            %s,
            %s,
            1.0000,
            'ədəd',
            100.0000,
            18.00,
            18.0000,
            118.0000
        )
        RETURNING id
        """,
        (purchase_order_id, product_id),
    ).fetchone()

    return row[0]


def require_one(conn, sql, params, label):
    row = conn.execute(sql, params).fetchone()
    if not row:
        raise RuntimeError(f"CI seed verification failed: {label}")
    return row


with psycopg.connect(DSN) as conn:
    # --------------------------------------------------------
    # COMPANY A — procurement test company
    # --------------------------------------------------------
    procurement_user_id = upsert_user(
        conn,
        TEST_EMAIL,
        TEST_PASSWORD,
        "BIZAZ CI Procurement Test",
    )

    procurement_company_id = upsert_company(
        conn,
        "9000000001",
        "BIZAZ CI PROCUREMENT TEST MMC",
    )

    ensure_membership(
        conn,
        procurement_user_id,
        procurement_company_id,
        "OWNER",
    )

    procurement_product_id = upsert_product(
        conn,
        procurement_company_id,
        "CI Procurement Product",
        "CI-PROC-001",
    )

    procurement_supplier_id = upsert_supplier(
        conn,
        procurement_company_id,
        "CI Procurement Supplier",
        "9100000001",
    )

    procurement_po_id = upsert_po(
        conn,
        procurement_company_id,
        procurement_supplier_id,
        "CI-PO-PROC-001",
        "DRAFT",
    )

    ensure_po_item(
        conn,
        procurement_po_id,
        procurement_product_id,
    )

    # --------------------------------------------------------
    # COMPANY B — acceptance / cross-company company
    # --------------------------------------------------------
    owner_user_id = upsert_user(
        conn,
        OWNER_EMAIL,
        OWNER_PASSWORD,
        "BIZAZ CI Acceptance Owner",
    )

    viewer_user_id = upsert_user(
        conn,
        VIEWER_EMAIL,
        VIEWER_PASSWORD,
        "BIZAZ CI Acceptance Viewer",
    )

    acceptance_company_id = upsert_company(
        conn,
        "9000000002",
        "BIZAZ CI ACCEPTANCE TEST MMC",
    )

    ensure_membership(
        conn,
        owner_user_id,
        acceptance_company_id,
        "OWNER",
    )

    ensure_membership(
        conn,
        viewer_user_id,
        acceptance_company_id,
        "VIEWER",
    )

    acceptance_product_id = upsert_product(
        conn,
        acceptance_company_id,
        "CI Acceptance Product",
        "CI-ACC-001",
    )

    acceptance_supplier_id = upsert_supplier(
        conn,
        acceptance_company_id,
        "CI Acceptance Supplier",
        "9200000001",
    )

    acceptance_draft_po_id = upsert_po(
        conn,
        acceptance_company_id,
        acceptance_supplier_id,
        "CI-PO-ACC-DRAFT-001",
        "DRAFT",
    )

    acceptance_submitted_po_id = upsert_po(
        conn,
        acceptance_company_id,
        acceptance_supplier_id,
        "CI-PO-ACC-SUB-001",
        "SUBMITTED",
    )

    ensure_po_item(
        conn,
        acceptance_draft_po_id,
        acceptance_product_id,
    )

    ensure_po_item(
        conn,
        acceptance_submitted_po_id,
        acceptance_product_id,
    )

    conn.commit()

    # --------------------------------------------------------
    # FINAL CONTRACT VERIFICATION
    # --------------------------------------------------------

    require_one(
        conn,
        """
        SELECT 1
        FROM users
        WHERE email = %s
          AND is_active = TRUE
        """,
        (TEST_EMAIL,),
        "procurement user",
    )

    require_one(
        conn,
        """
        SELECT 1
        FROM users
        WHERE email = %s
          AND is_active = TRUE
        """,
        (OWNER_EMAIL,),
        "acceptance owner",
    )

    require_one(
        conn,
        """
        SELECT 1
        FROM users
        WHERE email = %s
          AND is_active = TRUE
        """,
        (VIEWER_EMAIL,),
        "acceptance viewer",
    )

    require_one(
        conn,
        """
        SELECT 1
        FROM company_members cm
        JOIN users u ON u.id = cm.user_id
        WHERE u.email = %s
          AND cm.role = 'OWNER'
        """,
        (TEST_EMAIL,),
        "procurement membership",
    )

    require_one(
        conn,
        """
        SELECT 1
        FROM company_members cm
        JOIN users u ON u.id = cm.user_id
        WHERE u.email = %s
          AND cm.role = 'OWNER'
        """,
        (OWNER_EMAIL,),
        "acceptance owner membership",
    )

    require_one(
        conn,
        """
        SELECT 1
        FROM company_members cm
        JOIN users u ON u.id = cm.user_id
        WHERE u.email = %s
          AND cm.role = 'VIEWER'
        """,
        (VIEWER_EMAIL,),
        "acceptance viewer membership",
    )

    require_one(
        conn,
        """
        SELECT 1
        FROM products p
        JOIN companies c ON c.id = p.company_id
        JOIN company_members cm ON cm.company_id = c.id
        JOIN users u ON u.id = cm.user_id
        WHERE u.email = %s
          AND p.is_active = TRUE
        """,
        (TEST_EMAIL,),
        "procurement active product",
    )

    require_one(
        conn,
        """
        SELECT 1
        FROM suppliers s
        JOIN companies c ON c.id = s.company_id
        JOIN company_members cm ON cm.company_id = c.id
        JOIN users u ON u.id = cm.user_id
        WHERE u.email = %s
          AND s.is_active = TRUE
        """,
        (TEST_EMAIL,),
        "procurement active supplier",
    )

    require_one(
        conn,
        """
        SELECT 1
        FROM products p
        JOIN companies c ON c.id = p.company_id
        JOIN company_members cm ON cm.company_id = c.id
        JOIN users u ON u.id = cm.user_id
        WHERE u.email = %s
          AND p.is_active = TRUE
        """,
        (OWNER_EMAIL,),
        "acceptance active product",
    )

    require_one(
        conn,
        """
        SELECT 1
        FROM suppliers s
        JOIN companies c ON c.id = s.company_id
        JOIN company_members cm ON cm.company_id = c.id
        JOIN users u ON u.id = cm.user_id
        WHERE u.email = %s
          AND s.is_active = TRUE
        """,
        (OWNER_EMAIL,),
        "acceptance active supplier",
    )

    cross_company_po_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM purchase_orders po
        JOIN companies c ON c.id = po.company_id
        JOIN company_members cm ON cm.company_id = c.id
        JOIN users u ON u.id = cm.user_id
        WHERE u.email = %s
        """,
        (VIEWER_EMAIL,),
    ).fetchone()[0]

    if cross_company_po_count < 2:
        raise RuntimeError(
            "CI seed verification failed: acceptance company needs "
            "DRAFT + SUBMITTED PO"
        )

    print("=" * 80)
    print("CI SEED SUCCESS")
    print("=" * 80)
    print("PROCUREMENT USER :", TEST_EMAIL)
    print("OWNER USER       :", OWNER_EMAIL)
    print("VIEWER USER      :", VIEWER_EMAIL)
    print("COMPANY A        :", procurement_company_id)
    print("COMPANY B        :", acceptance_company_id)
    print("PROCUREMENT PO   :", procurement_po_id)
    print("ACC DRAFT PO     :", acceptance_draft_po_id)
    print("ACC SUBMITTED PO :", acceptance_submitted_po_id)
    print("=" * 80)
