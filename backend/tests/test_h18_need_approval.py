import uuid

import psycopg
import requests


def _create_need(base_url, auth_headers, test_company_data):
    suffix = uuid.uuid4().hex[:10].upper()

    response = requests.post(
        f"{base_url}/api/v1/needs",
        headers=auth_headers,
        json={
            "need_number": f"H18-NEED-{suffix}",
            "source": "MANUAL",
            "title": "H1.8 approval gate test",
            "priority": "NORMAL",
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": 10,
                    "unit": "ed",
                }
            ],
        },
        timeout=10,
    )

    assert response.status_code == 201, response.text
    return response.json()["id"]


def _move_to_under_review(base_url, auth_headers, need_id):
    for status in ("SUBMITTED", "UNDER_REVIEW"):
        response = requests.post(
            f"{base_url}/api/v1/needs/{need_id}/status",
            headers=auth_headers,
            json={"status": status},
            timeout=10,
        )
        assert response.status_code == 200, response.text
        assert response.json()["new_status"] == status


def _create_approval(base_url, auth_headers, need_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": "NEED",
            "entity_id": need_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "H1.8-NEED-STATUS",
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


def _decide(
    base_url,
    auth_headers,
    approval_id,
    decision,
    comment,
):
    return requests.post(
        f"{base_url}/api/v1/approvals/{approval_id}/decision",
        headers=auth_headers,
        json={
            "decision": decision,
            "comment": comment,
        },
        timeout=10,
    )


def _set_need_approved(base_url, auth_headers, need_id):
    response = requests.post(
        f"{base_url}/api/v1/needs/{need_id}/status",
        headers=auth_headers,
        json={"status": "APPROVED"},
        timeout=10,
    )

    return response


def _cleanup(db, need_id):
    need_uuid = uuid.UUID(need_id)

    approval_rows = db.execute(
        """
        SELECT id
        FROM approval_requests
        WHERE entity_type = 'NEED'
          AND entity_id = %s
        """,
        (need_uuid,),
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

    db.execute(
        """
        DELETE FROM audit_log
        WHERE entity_type = 'NEED'
          AND entity_id = %s
        """,
        (need_uuid,),
    )

    db.execute(
        """
        DELETE FROM need_items
        WHERE need_id = %s
        """,
        (need_uuid,),
    )

    db.execute(
        """
        DELETE FROM needs
        WHERE id = %s
        """,
        (need_uuid,),
    )


def test_h18_01_pending_need_approval_blocks_approval(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True
    need_id = None

    try:
        need_id = _create_need(
            base_url,
            auth_headers,
            test_company_data,
        )
        _move_to_under_review(base_url, auth_headers, need_id)

        approval_response = _create_approval(
            base_url,
            auth_headers,
            need_id,
        )

        assert approval_response.status_code == 201, approval_response.text
        assert approval_response.json()["status"] == "PENDING"

        response = _set_need_approved(
            base_url,
            auth_headers,
            need_id,
        )

        assert response.status_code == 409, response.text

    finally:
        if need_id is not None:
            _cleanup(db, need_id)
        db.close()


def test_h18_02_rejected_need_approval_blocks_approval(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True
    need_id = None

    try:
        need_id = _create_need(
            base_url,
            auth_headers,
            test_company_data,
        )
        _move_to_under_review(base_url, auth_headers, need_id)

        approval_response = _create_approval(
            base_url,
            auth_headers,
            need_id,
        )

        assert approval_response.status_code == 201, approval_response.text
        approval_id = approval_response.json()["id"]

        decision_response = _decide(
            base_url,
            auth_headers,
            approval_id,
            "REJECT",
            "H1.8 rejected approval test",
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "REJECTED"

        response = _set_need_approved(
            base_url,
            auth_headers,
            need_id,
        )

        assert response.status_code == 409, response.text

    finally:
        if need_id is not None:
            _cleanup(db, need_id)
        db.close()


def test_h18_03_approved_need_approval_allows_approval(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True
    need_id = None

    try:
        need_id = _create_need(
            base_url,
            auth_headers,
            test_company_data,
        )
        _move_to_under_review(base_url, auth_headers, need_id)

        approval_response = _create_approval(
            base_url,
            auth_headers,
            need_id,
        )

        assert approval_response.status_code == 201, approval_response.text
        approval_id = approval_response.json()["id"]

        decision_response = _decide(
            base_url,
            auth_headers,
            approval_id,
            "APPROVE",
            "H1.8 approved approval test",
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "APPROVED"

        response = _set_need_approved(
            base_url,
            auth_headers,
            need_id,
        )

        assert response.status_code == 200, response.text
        assert response.json()["new_status"] == "APPROVED"

    finally:
        if need_id is not None:
            _cleanup(db, need_id)
        db.close()


def test_h18_04_no_need_approval_preserves_legacy_approval(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True
    need_id = None

    try:
        need_id = _create_need(
            base_url,
            auth_headers,
            test_company_data,
        )
        _move_to_under_review(base_url, auth_headers, need_id)

        response = _set_need_approved(
            base_url,
            auth_headers,
            need_id,
        )

        assert response.status_code == 200, response.text
        assert response.json()["new_status"] == "APPROVED"

    finally:
        if need_id is not None:
            _cleanup(db, need_id)
        db.close()
