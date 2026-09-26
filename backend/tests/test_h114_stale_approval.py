import uuid

import psycopg
import requests


def _create_approval(base_url, auth_headers, entity_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": "PURCHASE_REQUEST",
            "entity_id": entity_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "H1.14-STALE-APPROVAL",
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


def _cleanup_approvals(db, entity_id):
    entity_uuid = uuid.UUID(entity_id)

    rows = db.execute(
        """
        SELECT id
        FROM approval_requests
        WHERE entity_type = 'PURCHASE_REQUEST'
          AND entity_id = %s
        """,
        (entity_uuid,),
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


def test_h141_01_latest_pending_reapproval_blocks_old_approved_purchase_request(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        submit_response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/"
            f"{request_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=10,
        )

        assert submit_response.status_code == 200, submit_response.text

        first = _create_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert first.status_code == 201, first.text
        first_id = first.json()["id"]

        first_decision = _decision(
            base_url,
            auth_headers,
            first_id,
            "APPROVE",
            "H1.14 first approval approved",
        )

        assert first_decision.status_code == 200, first_decision.text
        assert first_decision.json()["request"]["status"] == "APPROVED"

        second = _create_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert second.status_code == 201, second.text
        second_id = second.json()["id"]
        assert second.json()["status"] == "PENDING"

        response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/"
            f"{request_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )

        assert response.status_code == 409, response.text

        request_row = db.execute(
            """
            SELECT status
            FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        ).fetchone()

        assert request_row is not None
        assert request_row[0] == "SUBMITTED"

        approval_rows = db.execute(
            """
            SELECT id, status
            FROM approval_requests
            WHERE entity_type = 'PURCHASE_REQUEST'
              AND entity_id = %s
            ORDER BY created_at ASC
            """,
            (uuid.UUID(request_id),),
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
        _cleanup_approvals(db, request_id)
        db.close()
