import uuid

import psycopg
import requests


def _create_purchase_request_approval(
    base_url,
    auth_headers,
    request_id,
):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": "PURCHASE_REQUEST",
            "entity_id": request_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "H1.3-PR-APPROVAL",
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


def _cleanup_purchase_request_approvals(
    db,
    request_id,
):
    approval_rows = db.execute(
        """
        SELECT id
        FROM approval_requests
        WHERE entity_type = 'PURCHASE_REQUEST'
          AND entity_id = %s
        """,
        (uuid.UUID(request_id),),
    ).fetchall()

    for row in approval_rows:
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


def test_h13_01_pending_approval_blocks_direct_purchase_request_approval(
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

        approval_response = _create_purchase_request_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert approval_response.status_code == 201, approval_response.text

        direct_approve_response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/"
            f"{request_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )

        assert direct_approve_response.status_code == 409, (
            direct_approve_response.text
        )

        detail_response = requests.get(
            f"{base_url}/api/v1/procurement/purchase-requests/"
            f"{request_id}/",
            headers=auth_headers,
            timeout=10,
        )

        assert detail_response.status_code == 200, detail_response.text
        assert detail_response.json()["status"] == "SUBMITTED"

    finally:
        _cleanup_purchase_request_approvals(db, request_id)
        db.close()


def test_h13_02_rejected_approval_blocks_direct_purchase_request_approval(
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

        approval_response = _create_purchase_request_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert approval_response.status_code == 201, approval_response.text

        approval_id = approval_response.json()["id"]

        reject_response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "REJECT",
                "comment": "H1.3 rejection gate test",
            },
            timeout=10,
        )

        assert reject_response.status_code == 200, reject_response.text
        assert reject_response.json()["request"]["status"] == "REJECTED"

        direct_approve_response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/"
            f"{request_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )

        assert direct_approve_response.status_code == 409, (
            direct_approve_response.text
        )

        detail_response = requests.get(
            f"{base_url}/api/v1/procurement/purchase-requests/"
            f"{request_id}/",
            headers=auth_headers,
            timeout=10,
        )

        assert detail_response.status_code == 200, detail_response.text
        assert detail_response.json()["status"] == "SUBMITTED"

    finally:
        _cleanup_purchase_request_approvals(db, request_id)
        db.close()


def test_h13_03_approved_approval_allows_purchase_request_approval(
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

        approval_response = _create_purchase_request_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert approval_response.status_code == 201, approval_response.text

        approval_id = approval_response.json()["id"]

        approve_response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "APPROVE",
                "comment": "H1.3 approval gate test",
            },
            timeout=10,
        )

        assert approve_response.status_code == 200, approve_response.text
        assert approve_response.json()["request"]["status"] == "APPROVED"

        direct_approve_response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/"
            f"{request_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )

        assert direct_approve_response.status_code == 200, (
            direct_approve_response.text
        )

        data = direct_approve_response.json()

        assert data["status"] == "success"
        assert data["new_status"] == "APPROVED"
        assert data["approved_by"] is not None
        assert data["approved_at"] is not None

    finally:
        _cleanup_purchase_request_approvals(db, request_id)
        db.close()
