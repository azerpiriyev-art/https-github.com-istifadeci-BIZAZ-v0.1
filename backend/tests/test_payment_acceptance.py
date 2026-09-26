import uuid

import psycopg
import requests

CROSS_COMPANY_ID = "6cf693c6-ad8a-4b4e-803a-f38d1544969c"


def _create_approved_po(base_url, auth_headers, test_company_data):
    suffix = uuid.uuid4().hex[:8].upper()

    payload = {
        "supplier_id": test_company_data["supplier_id"],
        "order_number": f"PO-PAY-{suffix}",
        "order_date": "2026-09-27T00:00:00",
        "currency": "AZN",
        "notes": "4.23.10 PAYMENT TEST",
        "items": [
            {
                "product_id": test_company_data["product_id"],
                "quantity": 1,
                "unit": "ədəd",
                "unit_price": 100,
                "vat_rate": 18,
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=auth_headers,
        json=payload,
        timeout=10,
    )
    assert response.status_code == 201, response.text

    po = response.json()

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{po['id']}/status",
        headers=auth_headers,
        json={"status": "SUBMITTED"},
        timeout=10,
    )
    assert response.status_code == 200, response.text

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{po['id']}/status",
        headers=auth_headers,
        json={"status": "APPROVED"},
        timeout=10,
    )
    assert response.status_code == 200, response.text

    return response.json()


def test_231_payment_creation(base_url, auth_headers, test_company_data):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["purchase_order_id"] == po["id"]
    assert float(data["amount"]) == 100
    assert data["currency"] == "AZN"
    assert data["status"] == "PENDING"


def test_232_payment_amount_must_be_positive(
    base_url, auth_headers, test_company_data
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 0,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert response.status_code == 422


def test_233_payment_currency_must_match_po(
    base_url, auth_headers, test_company_data
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "USD",
        },
        timeout=10,
    )

    assert response.status_code == 422


def test_234_payment_requires_existing_po(
    base_url, auth_headers
):
    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": str(uuid.uuid4()),
            "amount": 100,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert response.status_code == 404


def test_235_payment_audit_created(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    po = _create_approved_po(
        base_url,
        auth_headers,
        test_company_data,
    )

    payment_id = None
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        response = requests.post(
            f"{base_url}/api/v1/payments",
            headers=auth_headers,
            json={
                "purchase_order_id": po["id"],
                "amount": 100,
                "currency": "AZN",
            },
            timeout=10,
        )

        assert response.status_code == 201, response.text

        payment = response.json()
        payment_id = uuid.UUID(payment["id"])

        row = db.execute(
            """
            SELECT
                user_id,
                company_id,
                action,
                entity_type,
                entity_id,
                metadata
            FROM audit_log
            WHERE entity_type = 'payment'
              AND entity_id = %s
              AND action = 'PAYMENT_CREATED'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (payment_id,),
        ).fetchone()

        assert row is not None

        assert row[0] == uuid.UUID(test_company_data["user_id"])
        assert row[1] == uuid.UUID(test_company_data["company_id"])
        assert row[2] == "PAYMENT_CREATED"
        assert row[3] == "payment"
        assert row[4] == payment_id

        metadata = row[5]

        assert metadata["purchase_order_id"] == po["id"]
        assert metadata["order_number"] == po["order_number"]
        assert metadata["currency"] == "AZN"
        assert metadata["status"] == "PENDING"
        assert "amount" in metadata

    finally:
        if payment_id is not None:
            db.execute(
                """
                DELETE FROM audit_log
                WHERE entity_type = 'payment'
                  AND entity_id = %s
                  AND action = 'PAYMENT_CREATED'
                """,
                (payment_id,),
            )

            db.execute(
                """
                DELETE FROM payments
                WHERE id = %s
                """,
                (payment_id,),
            )

        db.close()


def test_236_cross_company_payment_creation_blocked(
    base_url,
    auth_headers,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        row = db.execute(
            """
            SELECT id
            FROM purchase_orders
            WHERE company_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(CROSS_COMPANY_ID),),
        ).fetchone()

        assert row is not None

        foreign_po_id = row[0]

        response = requests.post(
            f"{base_url}/api/v1/payments",
            headers=auth_headers,
            json={
                "purchase_order_id": str(foreign_po_id),
                "amount": 100,
                "currency": "AZN",
            },
            timeout=10,
        )

        assert response.status_code == 404, response.text

    finally:
        db.close()
