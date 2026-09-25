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
            "policy_key": "H1.12-AUDIT",
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


def _decide(base_url, auth_headers, approval_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/{approval_id}/decision",
        headers=auth_headers,
        json={
            "decision": "APPROVE",
            "comment": "H1.12 audit metadata test",
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


def test_h112_01_approval_audit_metadata_integrity(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_company_data,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]
    company_id = uuid.UUID(test_company_data["company_id"])
    user_id = uuid.UUID(test_company_data["user_id"])

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

        create_data = create_response.json()
        approval_id = create_data["id"]

        step_id = create_data["steps"][0]["id"]

        create_audit = db.execute(
            """
            SELECT
                user_id,
                company_id,
                action,
                entity_type,
                entity_id,
                metadata
            FROM audit_log
            WHERE entity_type = 'APPROVAL_REQUEST'
              AND entity_id = %s
              AND action = 'APPROVAL_REQUEST_CREATED'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(approval_id),),
        ).fetchone()

        assert create_audit is not None
        assert create_audit[0] == user_id
        assert create_audit[1] == company_id
        assert create_audit[2] == "APPROVAL_REQUEST_CREATED"
        assert create_audit[3] == "APPROVAL_REQUEST"
        assert create_audit[4] == uuid.UUID(approval_id)

        create_metadata = create_audit[5]

        assert create_metadata["approval_request_id"] == approval_id
        assert create_metadata["entity_type"] == "PURCHASE_REQUEST"
        assert create_metadata["entity_id"] == request_id
        assert create_metadata["execution_mode"] == "SEQUENTIAL"
        assert create_metadata["decision_mode"] == "ALL"
        assert create_metadata["priority"] == "NORMAL"
        assert create_metadata["step_count"] == 1

        decision_response = _decide(
            base_url,
            auth_headers,
            approval_id,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "APPROVED"

        decision_audit = db.execute(
            """
            SELECT
                user_id,
                company_id,
                action,
                entity_type,
                entity_id,
                metadata
            FROM audit_log
            WHERE entity_type = 'APPROVAL_REQUEST'
              AND entity_id = %s
              AND action = 'APPROVAL_STEP_APPROVED'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(approval_id),),
        ).fetchone()

        assert decision_audit is not None
        assert decision_audit[0] == user_id
        assert decision_audit[1] == company_id
        assert decision_audit[2] == "APPROVAL_STEP_APPROVED"
        assert decision_audit[3] == "APPROVAL_REQUEST"
        assert decision_audit[4] == uuid.UUID(approval_id)

        decision_metadata = decision_audit[5]

        assert decision_metadata["approval_request_id"] == approval_id
        assert decision_metadata["approval_step_id"] == step_id
        assert decision_metadata["decision"] == "APPROVE"
        assert decision_metadata["step_order"] == 1
        assert decision_metadata["actor_user_id"] == str(user_id)
        assert decision_metadata["comment"] == "H1.12 audit metadata test"
        assert decision_metadata["request_status"] == "APPROVED"

    finally:
        if approval_id is not None:
            _cleanup(db, approval_id)

        db.close()
