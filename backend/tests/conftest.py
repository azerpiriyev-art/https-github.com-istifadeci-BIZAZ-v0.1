import os
import uuid

import pytest
import requests
import psycopg


@pytest.fixture(scope="session")
def base_url():
    return os.getenv("BIZAZ_TEST_BASE_URL", "http://127.0.0.1:8001")


@pytest.fixture(scope="session")
def test_credentials():
    return {
        "email": os.getenv(
            "BIZAZ_TEST_EMAIL",
            "procurement-test@example.com",
        ),
        "password": os.getenv(
            "BIZAZ_TEST_PASSWORD",
            "BIZAZ-Test-2026!",
        ),
    }


@pytest.fixture(scope="session")
def auth_headers(base_url, test_credentials):
    response = requests.post(
        f"{base_url}/api/v1/login",
        json=test_credentials,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    token = response.json()["token"]

    return {
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture(scope="session")
def test_database_url():
    root_env = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    )

    database_url = None

    with open(root_env, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                database_url = line.split("=", 1)[1].strip()
                break

    assert database_url, "DATABASE_URL not found in root .env"

    assert database_url.endswith("/bizaz"), (
        "Expected production database URL ending with /bizaz"
    )

    return (database_url[:-5] + "bizaz_procurement_test").replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture(scope="session")
def test_db(test_database_url):
    connection = psycopg.connect(test_database_url)
    connection.autocommit = True

    yield connection

    connection.close()


@pytest.fixture(scope="session")
def test_company_data(test_db):
    row = test_db.execute(
        """
        SELECT
            c.id AS company_id,
            u.id AS user_id,
            p.id AS product_id,
            s.id AS supplier_id
        FROM companies c
        JOIN company_members cm
            ON cm.company_id = c.id
        JOIN users u
            ON u.id = cm.user_id
        CROSS JOIN LATERAL (
            SELECT id
            FROM products
            WHERE company_id = c.id
              AND is_active = TRUE
            ORDER BY created_at
            LIMIT 1
        ) p
        CROSS JOIN LATERAL (
            SELECT id
            FROM suppliers
            WHERE company_id = c.id
              AND is_active = TRUE
            ORDER BY created_at
            LIMIT 1
        ) s
        WHERE u.email = %s
        LIMIT 1
        """,
        ("procurement-test@example.com",),
    ).fetchone()

    assert row, "Test company/product/supplier fixture not found"

    return {
        "company_id": str(row[0]),
        "user_id": str(row[1]),
        "product_id": str(row[2]),
        "supplier_id": str(row[3]),
    }


@pytest.fixture
def purchase_request_lifecycle_fixture(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    suffix = uuid.uuid4().hex[:10].upper()
    request_number = f"PR-LIFECYCLE-{suffix}"

    payload = {
        "request_number": request_number,
        "status": "DRAFT",
        "items": [
            {
                "product_id": test_company_data["product_id"],
                "quantity": 1,
                "unit": "?d?d",
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/procurement/purchase-requests",
        headers=auth_headers,
        json=payload,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    yield {
        "request_id": data["id"],
        "request_number": data["request_number"],
    }

    request_id = uuid.UUID(data["id"])

    cleanup_db = psycopg.connect(
        os.getenv("BIZAZ_TEST_DATABASE_URL", "")
        or _database_url_from_env()
    )
    cleanup_db.autocommit = True

    try:
        cleanup_db.execute(
            """
            DELETE FROM purchase_request_items
            WHERE purchase_request_id = %s
            """,
            (request_id,),
        )

        cleanup_db.execute(
            """
            DELETE FROM purchase_requests
            WHERE id = %s
            """,
            (request_id,),
        )
    finally:
        cleanup_db.close()


@pytest.fixture(scope="session")
def comparison_fixture(base_url, auth_headers, test_company_data, test_db):
    suffix = uuid.uuid4().hex[:10].upper()

    request_number = f"PR-DYN-{suffix}"
    offer_number_1 = f"SO-DYN-{suffix}-001"
    offer_number_2 = f"SO-DYN-{suffix}-002"

    request_payload = {
        "request_number": request_number,
        "status": "DRAFT",
        "items": [
            {
                "product_id": test_company_data["product_id"],
                "quantity": 100,
                "unit": "ədəd",
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/procurement/purchase-requests",
        headers=auth_headers,
        json=request_payload,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    request_data = response.json()
    request_id = request_data["id"]
    request_item_id = str(test_db.execute("SELECT id FROM purchase_request_items WHERE purchase_request_id = %s ORDER BY id LIMIT 1", (uuid.UUID(request_id),)).fetchone()[0])

    offer_payload_1 = {
        "purchase_request_id": request_id,
        "supplier_id": test_company_data["supplier_id"],
        "offer_number": offer_number_1,
        "status": "SUBMITTED",
        "items": [
            {
                "purchase_request_item_id": request_item_id,
                "product_id": test_company_data["product_id"],
                "quantity": 100,
                "unit": "ədəd",
                "unit_price": 95,
                "vat_rate": 18,
                "delivery_days": 10,
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/procurement/supplier-offers",
        headers=auth_headers,
        json=offer_payload_1,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    offer_1 = response.json()

    offer_payload_2 = {
        "purchase_request_id": request_id,
        "supplier_id": test_company_data["supplier_id"],
        "offer_number": offer_number_2,
        "status": "SUBMITTED",
        "items": [
            {
                "purchase_request_item_id": request_item_id,
                "product_id": test_company_data["product_id"],
                "quantity": 100,
                "unit": "ədəd",
                "unit_price": 97,
                "vat_rate": 18,
                "delivery_days": 7,
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/procurement/supplier-offers",
        headers=auth_headers,
        json=offer_payload_2,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    offer_2 = response.json()

    fixture = {
        "request_id": request_id,
        "request_item_id": request_item_id,
        "request_number": request_number,
        "offer_1_id": offer_1["id"],
        "offer_1_number": offer_number_1,
        "offer_2_id": offer_2["id"],
        "offer_2_number": offer_number_2,
    }

    yield fixture

    request_id_uuid = uuid.UUID(request_id)

    test_db = psycopg.connect(
        os.getenv("BIZAZ_TEST_DATABASE_URL", "")
        or _database_url_from_env()
    )
    test_db.autocommit = True

    try:
        test_db.execute(
            """
            DELETE FROM offer_selections
            WHERE purchase_request_id = %s
            """,
            (request_id_uuid,),
        )

        test_db.execute(
            """
            DELETE FROM supplier_offer_items
            WHERE supplier_offer_id IN (
                SELECT id
                FROM supplier_offers
                WHERE purchase_request_id = %s
            )
            """,
            (request_id_uuid,),
        )

        test_db.execute(
            """
            DELETE FROM supplier_offers
            WHERE purchase_request_id = %s
            """,
            (request_id_uuid,),
        )

        test_db.execute(
            """
            DELETE FROM purchase_request_items
            WHERE purchase_request_id = %s
            """,
            (request_id_uuid,),
        )

        test_db.execute(
            """
            DELETE FROM purchase_requests
            WHERE id = %s
            """,
            (request_id_uuid,),
        )
    finally:
        test_db.close()


@pytest.fixture(scope="session")
def cancelled_request_fixture(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    suffix = uuid.uuid4().hex[:10].upper()
    request_number = f"PR-CANCEL-DYN-{suffix}"

    request_payload = {
        "request_number": request_number,
        "status": "DRAFT",
        "items": [
            {
                "product_id": test_company_data["product_id"],
                "quantity": 1,
                "unit": "ədəd",
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/procurement/purchase-requests",
        headers=auth_headers,
        json=request_payload,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    request_id = response.json()["id"]

    connection = psycopg.connect(test_database_url)
    connection.autocommit = True

    try:
        connection.execute(
            """
            UPDATE purchase_requests
            SET status = 'CANCELLED'
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        )
    finally:
        connection.close()

    yield {
        "request_id": request_id,
        "request_number": request_number,
    }

    connection = psycopg.connect(test_database_url)
    connection.autocommit = True

    try:
        connection.execute(
            """
            DELETE FROM purchase_request_items
            WHERE purchase_request_id = %s
            """,
            (uuid.UUID(request_id),),
        )

        connection.execute(
            """
            DELETE FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        )
    finally:
        connection.close()

@pytest.fixture(scope="function")
def purchase_request_po_lifecycle_fixture(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    suffix = uuid.uuid4().hex[:10].upper()

    request_number = f"PR-PO-LIFECYCLE-{suffix}"
    offer_number = f"SO-PO-LIFECYCLE-{suffix}"

    request_payload = {
        "request_number": request_number,
        "status": "DRAFT",
        "items": [
            {
                "product_id": test_company_data["product_id"],
                "quantity": 1,
                "unit": "ədəd",
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/procurement/purchase-requests",
        headers=auth_headers,
        json=request_payload,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    request_data = response.json()
    request_id = request_data["id"]

    connection = psycopg.connect(test_database_url)

    try:
        request_item_row = connection.execute(
            """
            SELECT id
            FROM purchase_request_items
            WHERE purchase_request_id = %s
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (uuid.UUID(request_id),),
        ).fetchone()
    finally:
        connection.close()

    assert request_item_row is not None

    request_item_id = str(request_item_row[0])

    offer_payload = {
        "purchase_request_id": request_id,
        "supplier_id": test_company_data["supplier_id"],
        "offer_number": offer_number,
        "status": "SUBMITTED",
        "items": [
            {
                "purchase_request_item_id": request_item_id,
                "product_id": test_company_data["product_id"],
                "quantity": 1,
                "unit": "ədəd",
                "unit_price": 500,
                "vat_rate": 18,
                "delivery_days": 5,
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/procurement/supplier-offers",
        headers=auth_headers,
        json=offer_payload,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    offer_data = response.json()
    offer_id = offer_data["id"]

    selection_payload = {
        "purchase_request_id": request_id,
        "supplier_offer_id": offer_id,
        "justification": "B21.2 lifecycle acceptance test",
    }

    response = requests.post(
        f"{base_url}/api/v1/procurement/offer-selections",
        headers=auth_headers,
        json=selection_payload,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    selection_data = response.json()

    yield {
        "request_id": request_id,
        "request_number": request_number,
        "offer_id": offer_id,
        "offer_number": offer_number,
        "selection_id": selection_data["id"],
    }

    connection = psycopg.connect(test_database_url)
    connection.autocommit = True

    try:
        purchase_order_rows = connection.execute(
            """
            SELECT purchase_order_id
            FROM offer_selections
            WHERE purchase_request_id = %s
              AND purchase_order_id IS NOT NULL
            """,
            (uuid.UUID(request_id),),
        ).fetchall()

        purchase_order_ids = [row[0] for row in purchase_order_rows]

        for purchase_order_id in purchase_order_ids:
            connection.execute(
                """
                DELETE FROM purchase_order_items
                WHERE purchase_order_id = %s
                """,
                (purchase_order_id,),
            )

            connection.execute(
                """
                UPDATE offer_selections
                SET purchase_order_id = NULL
                WHERE purchase_order_id = %s
                """,
                (purchase_order_id,),
            )

            connection.execute(
                """
                DELETE FROM purchase_orders
                WHERE id = %s
                """,
                (purchase_order_id,),
            )

        connection.execute(
            """
            DELETE FROM offer_selections
            WHERE purchase_request_id = %s
            """,
            (uuid.UUID(request_id),),
        )

        connection.execute(
            """
            DELETE FROM supplier_offer_items
            WHERE supplier_offer_id = %s
            """,
            (uuid.UUID(offer_id),),
        )

        connection.execute(
            """
            DELETE FROM supplier_offers
            WHERE id = %s
            """,
            (uuid.UUID(offer_id),),
        )

        connection.execute(
            """
            DELETE FROM purchase_request_items
            WHERE purchase_request_id = %s
            """,
            (uuid.UUID(request_id),),
        )

        connection.execute(
            """
            DELETE FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        )
    finally:
        connection.close()

def _database_url_from_env():
    root_env = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    )

    with open(root_env, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()

            if line.startswith("DATABASE_URL="):
                database_url = line.split("=", 1)[1].strip()

                if database_url.endswith("/bizaz"):
                    return (database_url[:-5] + "bizaz_procurement_test").replace("postgresql+psycopg://", "postgresql://")

    raise AssertionError("DATABASE_URL not found")
