import uuid

import psycopg
import requests


def _create_approval(
    base_url,
    auth_headers,
    entity_type,
    entity_id,
):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "H1.4-INTEGRATION",
            "policy_version": "1.0",
            "steps": [
                {
                    "step_order": 1,
                    "approver_role": "OWNER",
                }
            ],
        },
        timeout=10,
    )


def _cleanup_approval(db, entity_type, entity_id):
    rows = db.execute(
        """
        SELECT id
        FROM approval_requests
        WHERE entity_type = %s
          AND entity_id = %s
        """,
        (entity_type, uuid.UUID(entity_id)),
    ).fetchall()

    for row in rows:
        approval_id = row[0]

        db.execute(
            """
            DELETE FROM approval_steps
            WHERE approval_request_id = %s
            """,
            (approval_id,),
        )

        db.execute(
            """
            DELETE FROM audit_log
            WHERE entity_type = 'APPROVAL_REQUEST'
              AND entity_id = %s
            """,
            (approval_id,),
        )

        db.execute(
            """
            DELETE FROM approval_requests
            WHERE id = %s
            """,
            (approval_id,),
        )


def test_h14_01_pending_offer_selection_approval_blocks_po_creation(
    base_url,
    auth_headers,
    purchase_request_po_lifecycle_fixture,
    test_database_url,
):
    fixture = purchase_request_po_lifecycle_fixture
    selection_id = fixture["selection_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        approval_response = _create_approval(
            base_url,
            auth_headers,
            "OFFER_SELECTION",
            selection_id,
        )

        assert approval_response.status_code == 201, approval_response.text

        response = requests.post(
            f"{base_url}/api/v1/procurement/offer-selections/"
            f"{selection_id}/purchase-order",
            headers=auth_headers,
            json={
                "order_number": f"H14-01-{uuid.uuid4().hex[:8].upper()}",
                "notes": "H1.4 pending selection approval gate",
            },
            timeout=10,
        )

        assert response.status_code == 409, response.text

    finally:
        _cleanup_approval(db, "OFFER_SELECTION", selection_id)
        db.close()


def test_h14_02_approved_offer_selection_approval_allows_po_creation(
    base_url,
    auth_headers,
    purchase_request_po_lifecycle_fixture,
    test_database_url,
):
    fixture = purchase_request_po_lifecycle_fixture
    selection_id = fixture["selection_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        approval_response = _create_approval(
            base_url,
            auth_headers,
            "OFFER_SELECTION",
            selection_id,
        )

        assert approval_response.status_code == 201, approval_response.text

        approval_id = approval_response.json()["id"]

        decision_response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "APPROVE",
                "comment": "H1.4 approved selection",
            },
            timeout=10,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "APPROVED"

        response = requests.post(
            f"{base_url}/api/v1/procurement/offer-selections/"
            f"{selection_id}/purchase-order",
            headers=auth_headers,
            json={
                "order_number": f"H14-02-{uuid.uuid4().hex[:8].upper()}",
                "notes": "H1.4 approved selection gate",
            },
            timeout=10,
        )

        assert response.status_code == 201, response.text

    finally:
        _cleanup_approval(db, "OFFER_SELECTION", selection_id)
        db.close()


def test_h14_03_pending_purchase_order_approval_blocks_po_approval(
    base_url,
    auth_headers,
    purchase_request_po_lifecycle_fixture,
    test_database_url,
):
    fixture = purchase_request_po_lifecycle_fixture
    selection_id = fixture["selection_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        po_response = requests.post(
            f"{base_url}/api/v1/procurement/offer-selections/"
            f"{selection_id}/purchase-order",
            headers=auth_headers,
            json={
                "order_number": f"H14-03-{uuid.uuid4().hex[:8].upper()}",
                "notes": "H1.4 PO approval gate",
            },
            timeout=10,
        )

        assert po_response.status_code == 201, po_response.text
        po_id = po_response.json()["purchase_order_id"]

        submit_response = requests.post(
            f"{base_url}/api/v1/purchase-orders/"
            f"{po_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=10,
        )

        assert submit_response.status_code == 200, submit_response.text

        approval_response = _create_approval(
            base_url,
            auth_headers,
            "PURCHASE_ORDER",
            po_id,
        )

        assert approval_response.status_code == 201, approval_response.text

        approve_response = requests.post(
            f"{base_url}/api/v1/purchase-orders/"
            f"{po_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )

        assert approve_response.status_code == 409, approve_response.text

    finally:
        _cleanup_approval(db, "PURCHASE_ORDER", po_id)
        db.close()


def test_h14_04_approved_purchase_order_approval_allows_po_approval(
    base_url,
    auth_headers,
    purchase_request_po_lifecycle_fixture,
    test_database_url,
):
    fixture = purchase_request_po_lifecycle_fixture
    selection_id = fixture["selection_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        po_response = requests.post(
            f"{base_url}/api/v1/procurement/offer-selections/"
            f"{selection_id}/purchase-order",
            headers=auth_headers,
            json={
                "order_number": f"H14-04-{uuid.uuid4().hex[:8].upper()}",
                "notes": "H1.4 approved PO gate",
            },
            timeout=10,
        )

        assert po_response.status_code == 201, po_response.text
        po_id = po_response.json()["purchase_order_id"]

        submit_response = requests.post(
            f"{base_url}/api/v1/purchase-orders/"
            f"{po_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=10,
        )

        assert submit_response.status_code == 200, submit_response.text

        approval_response = _create_approval(
            base_url,
            auth_headers,
            "PURCHASE_ORDER",
            po_id,
        )

        assert approval_response.status_code == 201, approval_response.text
        approval_id = approval_response.json()["id"]

        decision_response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "APPROVE",
                "comment": "H1.4 approved PO",
            },
            timeout=10,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "APPROVED"

        approve_response = requests.post(
            f"{base_url}/api/v1/purchase-orders/"
            f"{po_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )

        assert approve_response.status_code == 200, approve_response.text

    finally:
        _cleanup_approval(db, "PURCHASE_ORDER", po_id)
        db.close()
