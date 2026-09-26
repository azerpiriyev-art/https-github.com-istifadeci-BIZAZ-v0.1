import uuid

import psycopg
import requests


def _create_approval(
    base_url,
    auth_headers,
    entity_type,
    entity_id,
    steps,
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
            "policy_key": "H1.7-TERMINAL-STATUS",
            "policy_version": "1.0",
            "steps": steps,
        },
        timeout=10,
    )


def _decision(base_url, auth_headers, approval_id, decision, comment):
    return requests.post(
        f"{base_url}/api/v1/approvals/{approval_id}/decision",
        headers=auth_headers,
        json={
            "decision": decision,
            "comment": comment,
        },
        timeout=10,
    )


def _cleanup_approvals(db, entity_type, entity_id):
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


def _create_and_submit_po(base_url, auth_headers, fixture):
    response = requests.post(
        f"{base_url}/api/v1/procurement/offer-selections/"
        f"{fixture['selection_id']}/purchase-order",
        headers=auth_headers,
        json={
            "order_number": f"H17-{uuid.uuid4().hex[:8].upper()}",
            "notes": "H1.7 terminal status integration test",
        },
        timeout=10,
    )

    assert response.status_code == 201, response.text

    po_id = response.json()["purchase_order_id"]

    submit_response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{po_id}/status",
        headers=auth_headers,
        json={"status": "SUBMITTED"},
        timeout=10,
    )

    assert submit_response.status_code == 200, submit_response.text

    return po_id


def test_h17_01_in_progress_approval_blocks_po_approval(
    base_url,
    auth_headers,
    purchase_request_po_lifecycle_fixture,
    test_database_url,
):
    fixture = purchase_request_po_lifecycle_fixture
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    po_id = None

    try:
        po_id = _create_and_submit_po(
            base_url,
            auth_headers,
            fixture,
        )

        approval_response = _create_approval(
            base_url,
            auth_headers,
            "PURCHASE_ORDER",
            po_id,
            [
                {
                    "step_order": 1,
                    "approver_role": "OWNER",
                },
                {
                    "step_order": 2,
                    "approver_role": "OWNER",
                },
            ],
        )

        assert approval_response.status_code == 201, approval_response.text

        approval_id = approval_response.json()["id"]

        first_decision = _decision(
            base_url,
            auth_headers,
            approval_id,
            "APPROVE",
            "H1.7 first step approved",
        )

        assert first_decision.status_code == 200, first_decision.text
        assert first_decision.json()["request"]["status"] == "IN_PROGRESS"

        response = requests.post(
            f"{base_url}/api/v1/purchase-orders/{po_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )

        assert response.status_code == 409, response.text

    finally:
        if po_id is not None:
            _cleanup_approvals(db, "PURCHASE_ORDER", po_id)
        db.close()
