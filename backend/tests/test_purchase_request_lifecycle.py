import requests
import uuid


def test_01_draft_to_submitted(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    response = requests.put(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{request_id}/status",
        headers=auth_headers,
        json={"status": "SUBMITTED"},
        timeout=10,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    assert data["new_status"] == "SUBMITTED"


def test_02_submitted_to_approved(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    response = requests.put(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{request_id}/status",
        headers=auth_headers,
        json={"status": "SUBMITTED"},
        timeout=10,
    )

    assert response.status_code == 200, response.text

    response = requests.put(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{request_id}/status",
        headers=auth_headers,
        json={"status": "APPROVED"},
        timeout=10,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    assert data["new_status"] == "APPROVED"
    assert data["approved_by"] is not None
    assert data["approved_at"] is not None



def test_03_status_change_audit(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    response = requests.put(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{request_id}/status",
        headers=auth_headers,
        json={"status": "SUBMITTED"},
        timeout=10,
    )

    assert response.status_code == 200, response.text

    import os
    import psycopg

    database_url = os.getenv("BIZAZ_TEST_DATABASE_URL", "")
    if not database_url:
        database_url = "postgresql://bizaz:change-me-local-only@localhost:5432/bizaz_procurement_test"

    database_url = database_url.replace(
        "postgresql+psycopg://",
        "postgresql://",
    )

    db = psycopg.connect(database_url)
    try:
        row = db.execute(
            """
            SELECT entity_id
            FROM audit_log
            WHERE entity_type = %s
              AND entity_id = %s
              AND action = %s
            LIMIT 1
            """,
            (
                "PURCHASE_REQUEST",
                uuid.UUID(request_id),
                "PURCHASE_REQUEST_STATUS_CHANGED",
            ),
        ).fetchone()

        assert row is not None
        assert row[0] == uuid.UUID(request_id)
    finally:
        db.close()


def test_04_po_received_closes_purchase_request(
    base_url,
    auth_headers,
    purchase_request_po_lifecycle_fixture,
):
    fixture = purchase_request_po_lifecycle_fixture

    request_id = fixture["request_id"]
    selection_id = fixture["selection_id"]

    response = requests.put(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{request_id}/status",
        headers=auth_headers,
        json={"status": "SUBMITTED"},
        timeout=10,
    )
    assert response.status_code == 200, response.text

    response = requests.put(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{request_id}/status",
        headers=auth_headers,
        json={"status": "APPROVED"},
        timeout=10,
    )
    assert response.status_code == 200, response.text

    response = requests.post(
        f"{base_url}/api/v1/procurement/offer-selections/"
        f"{selection_id}/purchase-order",
        headers=auth_headers,
        json={
            "order_number": f"PO-B21-2-{uuid.uuid4().hex[:8].upper()}",
            "notes": "B21.2 lifecycle test",
        },
        timeout=10,
    )
    assert response.status_code == 201, response.text

    purchase_order_id = response.json()["purchase_order_id"]

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/"
        f"{purchase_order_id}/status",
        headers=auth_headers,
        json={"status": "SUBMITTED"},
        timeout=10,
    )
    assert response.status_code == 200, response.text

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/"
        f"{purchase_order_id}/status",
        headers=auth_headers,
        json={"status": "APPROVED"},
        timeout=10,
    )
    assert response.status_code == 200, response.text

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/"
        f"{purchase_order_id}/status",
        headers=auth_headers,
        json={"status": "RECEIVED"},
        timeout=10,
    )
    assert response.status_code == 200, response.text

    response = requests.get(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{request_id}/",
        headers=auth_headers,
        timeout=10,
    )
    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "CLOSED"
