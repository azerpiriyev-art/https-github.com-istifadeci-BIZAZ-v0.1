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
    test_database_url,
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

    import psycopg

    database_url = test_database_url

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


def test_05_expired_supplier_offer_excluded_from_comparison(
    base_url,
    auth_headers,
    expired_supplier_offer_fixture,
):
    fixture = expired_supplier_offer_fixture

    response = requests.get(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{fixture['request_id']}/comparison",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    comparison_offers = [
        offer
        for item in data["items"]
        for offer in item["offers"]
    ]

    assert fixture["offer_id"] not in {
        str(offer["offer_id"])
        for offer in comparison_offers
    }

def test_06_expired_supplier_offer_rejected_from_selection(
    base_url,
    auth_headers,
    expired_supplier_offer_fixture,
):
    fixture = expired_supplier_offer_fixture

    response = requests.post(
        f"{base_url}/api/v1/procurement/offer-selections",
        headers=auth_headers,
        json={
            "purchase_request_id": fixture["request_id"],
            "supplier_offer_id": fixture["offer_id"],
            "justification": "B22.7.2 expired offer selection test",
        },
        timeout=10,
    )

    assert response.status_code == 422, response.text

def test_07_expired_supplier_offer_rejected_from_purchase_order(
    base_url,
    auth_headers,
    expired_supplier_offer_fixture,
    test_database_url,
    test_credentials,
):
    fixture = expired_supplier_offer_fixture

    import psycopg

    connection = psycopg.connect(test_database_url)
    connection.autocommit = True

    try:
        user_row = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
            LIMIT 1
            """,
            (test_credentials["email"],),
        ).fetchone()

        assert user_row is not None

        connection.execute(
            """
            INSERT INTO offer_selections (
                company_id,
                purchase_request_id,
                supplier_offer_id,
                selected_by,
                status,
                justification
            )
            SELECT
                pr.company_id,
                pr.id,
                %s,
                %s,
                'SELECTED',
                %s
            FROM purchase_requests AS pr
            WHERE pr.id = %s
            """,
            (
                uuid.UUID(fixture["offer_id"]),
                user_row[0],
                "B22.7.3 expired offer purchase order test",
                uuid.UUID(fixture["request_id"]),
            ),
        )

        selection_row = connection.execute(
            """
            SELECT id
            FROM offer_selections
            WHERE supplier_offer_id = %s
              AND status = 'SELECTED'
            LIMIT 1
            """,
            (uuid.UUID(fixture["offer_id"]),),
        ).fetchone()

        assert selection_row is not None
        selection_id = str(selection_row[0])
    finally:
        connection.close()

    po_response = requests.post(
        f"{base_url}/api/v1/procurement/offer-selections/"
        f"{selection_id}/purchase-order",
        headers=auth_headers,
        json={
            "order_number": f"PO-B22-7-3-{uuid.uuid4().hex[:8].upper()}",
            "notes": "B22.7.3 expired offer purchase order test",
        },
        timeout=10,
    )

    assert po_response.status_code == 422, po_response.text
    assert po_response.json()["detail"] == "Supplier offer has expired"
