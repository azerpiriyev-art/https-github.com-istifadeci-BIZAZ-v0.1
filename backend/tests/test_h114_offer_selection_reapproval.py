import uuid

import psycopg
import requests


def _create_approval(base_url, auth_headers, selection_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": "OFFER_SELECTION",
            "entity_id": selection_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "H1.14-OFFER-SELECTION-STALE",
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


def _create_purchase_order(base_url, auth_headers, selection_id):
    return requests.post(
        f"{base_url}/api/v1/procurement/offer-selections/"
        f"{selection_id}/purchase-order",
        headers=auth_headers,
        json={
            "order_number": f"H14-04-{uuid.uuid4().hex[:8].upper()}",
            "notes": "H1.14.4 offer selection reapproval precedence",
        },
        timeout=10,
    )


def _cleanup_approvals(db, selection_id):
    selection_uuid = uuid.UUID(selection_id)

    rows = db.execute(
        """
        SELECT id
        FROM approval_requests
        WHERE entity_type = 'OFFER_SELECTION'
          AND entity_id = %s
        """,
        (selection_uuid,),
    ).fetchall()

    for row in rows:
        approval_id = row[0]

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
            DELETE FROM approval_steps
            WHERE approval_request_id = %s
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


def test_h144_01_latest_pending_reapproval_blocks_old_approved_offer_selection(
    base_url,
    auth_headers,
    purchase_request_po_lifecycle_fixture,
    test_database_url,
):
    selection_id = purchase_request_po_lifecycle_fixture["selection_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        first = _create_approval(
            base_url,
            auth_headers,
            selection_id,
        )

        assert first.status_code == 201, first.text
        first_id = first.json()["id"]

        first_decision = _decision(
            base_url,
            auth_headers,
            first_id,
            "APPROVE",
            "H1.14.4 first offer selection approval approved",
        )

        assert first_decision.status_code == 200, first_decision.text
        assert first_decision.json()["request"]["status"] == "APPROVED"

        second = _create_approval(
            base_url,
            auth_headers,
            selection_id,
        )

        assert second.status_code == 201, second.text
        second_id = second.json()["id"]
        assert second.json()["status"] == "PENDING"

        po_response = _create_purchase_order(
            base_url,
            auth_headers,
            selection_id,
        )

        assert po_response.status_code == 409, po_response.text

        selection_row = db.execute(
            """
            SELECT purchase_order_id
            FROM offer_selections
            WHERE id = %s
            """,
            (uuid.UUID(selection_id),),
        ).fetchone()

        assert selection_row is not None
        assert selection_row[0] is None

        approval_rows = db.execute(
            """
            SELECT id, status
            FROM approval_requests
            WHERE entity_type = 'OFFER_SELECTION'
              AND entity_id = %s
            ORDER BY created_at ASC
            """,
            (uuid.UUID(selection_id),),
        ).fetchall()

        assert any(
            str(row[0]) == first_id and row[1] == "APPROVED"
            for row in approval_rows
        )

        assert any(
            str(row[0]) == second_id and row[1] == "PENDING"
            for row in approval_rows
        )

    finally:
        _cleanup_approvals(db, selection_id)
        db.close()
