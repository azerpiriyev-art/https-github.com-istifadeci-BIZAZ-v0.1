import uuid

import psycopg
import requests


def _create_approval(base_url, auth_headers, offer_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": "SUPPLIER_OFFER",
            "entity_id": offer_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "H1.14-SUPPLIER-OFFER-STALE",
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


def _create_offer_selection(base_url, auth_headers, request_id, offer_id):
    return requests.post(
        f"{base_url}/api/v1/procurement/offer-selections",
        headers=auth_headers,
        json={
            "purchase_request_id": request_id,
            "supplier_offer_id": offer_id,
            "justification": "H1.14.3 supplier offer reapproval precedence",
        },
        timeout=10,
    )


def _cleanup_approvals(db, offer_id):
    offer_uuid = uuid.UUID(offer_id)

    rows = db.execute(
        """
        SELECT id
        FROM approval_requests
        WHERE entity_type = 'SUPPLIER_OFFER'
          AND entity_id = %s
        """,
        (offer_uuid,),
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


def _cleanup_selection(db, request_id):
    db.execute(
        """
        DELETE FROM offer_selections
        WHERE purchase_request_id = %s
        """,
        (uuid.UUID(request_id),),
    )


def test_h143_01_latest_pending_reapproval_blocks_old_approved_supplier_offer(
    base_url,
    auth_headers,
    comparison_fixture,
    test_database_url,
):
    request_id = comparison_fixture["request_id"]
    offer_id = comparison_fixture["offer_1_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        first = _create_approval(
            base_url,
            auth_headers,
            offer_id,
        )

        assert first.status_code == 201, first.text
        first_id = first.json()["id"]

        first_decision = _decision(
            base_url,
            auth_headers,
            first_id,
            "APPROVE",
            "H1.14.3 first supplier offer approval approved",
        )

        assert first_decision.status_code == 200, first_decision.text
        assert first_decision.json()["request"]["status"] == "APPROVED"

        second = _create_approval(
            base_url,
            auth_headers,
            offer_id,
        )

        assert second.status_code == 201, second.text
        second_id = second.json()["id"]
        assert second.json()["status"] == "PENDING"

        response = _create_offer_selection(
            base_url,
            auth_headers,
            request_id,
            offer_id,
        )

        assert response.status_code == 409, response.text

        approval_rows = db.execute(
            """
            SELECT id, status
            FROM approval_requests
            WHERE entity_type = 'SUPPLIER_OFFER'
              AND entity_id = %s
            ORDER BY created_at ASC
            """,
            (uuid.UUID(offer_id),),
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
        _cleanup_selection(db, request_id)
        _cleanup_approvals(db, offer_id)
        db.close()
