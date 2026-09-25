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
            "policy_key": "H1.13-STATE-CONSISTENCY",
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


def _decision(base_url, auth_headers, approval_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/{approval_id}/decision",
        headers=auth_headers,
        json={
            "decision": "APPROVE",
            "comment": "H1.13 business state consistency test",
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


def test_h131_01_approval_decision_does_not_auto_approve_purchase_request(
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
        response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/{request_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=10,
        )

        assert response.status_code == 200, response.text

        before = db.execute(
            """
            SELECT status
            FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        ).fetchone()

        assert before is not None
        assert before[0] == "SUBMITTED"

        approval_response = _create_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert approval_response.status_code == 201, approval_response.text
        approval_id = approval_response.json()["id"]

        decision_response = _decision(
            base_url,
            auth_headers,
            approval_id,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "APPROVED"

        after = db.execute(
            """
            SELECT status
            FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        ).fetchone()

        assert after is not None
        assert after[0] == "SUBMITTED"

    finally:
        if approval_id is not None:
            _cleanup(db, approval_id)

        db.close()

def _reject_decision(base_url, auth_headers, approval_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/{approval_id}/decision",
        headers=auth_headers,
        json={
            "decision": "REJECT",
            "comment": "H1.13.2 business state consistency test",
        },
        timeout=10,
    )


def test_h132_01_rejection_does_not_auto_reject_purchase_request(
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
        response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/{request_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=10,
        )

        assert response.status_code == 200, response.text

        before = db.execute(
            """
            SELECT status
            FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        ).fetchone()

        assert before is not None
        assert before[0] == "SUBMITTED"

        approval_response = _create_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert approval_response.status_code == 201, approval_response.text
        approval_id = approval_response.json()["id"]

        decision_response = _reject_decision(
            base_url,
            auth_headers,
            approval_id,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "REJECTED"

        after = db.execute(
            """
            SELECT status
            FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        ).fetchone()

        assert after is not None
        assert after[0] == "SUBMITTED"

    finally:
        if approval_id is not None:
            _cleanup(db, approval_id)

        db.close()
