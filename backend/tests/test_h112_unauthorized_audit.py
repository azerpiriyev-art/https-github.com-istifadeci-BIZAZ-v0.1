import uuid

import psycopg
import requests


def _create_approval(base_url, auth_headers, request_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": "PURCHASE_REQUEST",
            "entity_id": request_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "H1.12-UNAUTHORIZED",
            "policy_version": "1.0",
            "steps": [
                {
                    "step_order": 1,
                    "approver_role": "ADMIN",
                }
            ],
        },
        timeout=10,
    )


def _cleanup(db, approval_id):
    approval_uuid = uuid.UUID(approval_id)

    db.execute(
        """
        DELETE FROM audit_log
        WHERE entity_type = 'APPROVAL_REQUEST'
          AND entity_id = %s
        """,
        (approval_uuid,),
    )

    db.execute(
        """
        DELETE FROM approval_steps
        WHERE approval_request_id = %s
        """,
        (approval_uuid,),
    )

    db.execute(
        """
        DELETE FROM approval_requests
        WHERE id = %s
        """,
        (approval_uuid,),
    )


def test_h112_02_unauthorized_decision_does_not_write_success_audit(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    approval_id = None

    try:
        create_response = _create_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert create_response.status_code == 201, create_response.text

        approval_id = create_response.json()["id"]
        step_id = create_response.json()["steps"][0]["id"]

        decision_response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "APPROVE",
                "comment": "H1.12 unauthorized decision test",
            },
            timeout=10,
        )

        assert decision_response.status_code == 403, decision_response.text

        request_row = db.execute(
            """
            SELECT status
            FROM approval_requests
            WHERE id = %s
            """,
            (uuid.UUID(approval_id),),
        ).fetchone()

        assert request_row is not None
        assert request_row[0] == "PENDING"

        step_row = db.execute(
            """
            SELECT status, acted_by, acted_at
            FROM approval_steps
            WHERE id = %s
            """,
            (uuid.UUID(step_id),),
        ).fetchone()

        assert step_row is not None
        assert step_row[0] == "PENDING"
        assert step_row[1] is None
        assert step_row[2] is None

        success_audit_count = db.execute(
            """
            SELECT COUNT(*)
            FROM audit_log
            WHERE entity_type = 'APPROVAL_REQUEST'
              AND entity_id = %s
              AND action IN (
                  'APPROVAL_STEP_APPROVED',
                  'APPROVAL_STEP_REJECTED'
              )
            """,
            (uuid.UUID(approval_id),),
        ).fetchone()[0]

        assert success_audit_count == 0

    finally:
        if approval_id is not None:
            _cleanup(db, approval_id)

        db.close()
