import os
import uuid

import psycopg
import requests


def _cleanup_approval(db, entity_id):
    entity_uuid = uuid.UUID(entity_id)

    rows = db.execute(
        """
        SELECT id
        FROM approval_requests
        WHERE entity_id = %s
        """,
        (entity_uuid,),
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


def _create_approval(
    base_url,
    auth_headers,
    entity_id,
    *,
    steps=None,
    execution_mode="SEQUENTIAL",
    decision_mode="ALL",
    priority="NORMAL",
    policy_key="TEST-POLICY",
    policy_version="1.0",
):
    if steps is None:
        steps = [
            {
                "step_order": 1,
                "approver_role": "ADMIN",
            }
        ]

    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": "PURCHASE_REQUEST",
            "entity_id": entity_id,
            "execution_mode": execution_mode,
            "decision_mode": decision_mode,
            "priority": priority,
            "policy_key": policy_key,
            "policy_version": policy_version,
            "steps": steps,
        },
        timeout=10,
    )


def test_01_create_approval_request_success(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    db = psycopg.connect(test_database_url)

    try:
        response = _create_approval(
            base_url,
            auth_headers,
            request_id,
            steps=[
                {
                    "step_order": 1,
                    "approver_role": "ADMIN",
                },
                {
                    "step_order": 2,
                    "approver_role": "PROCUREMENT",
                },
            ],
            execution_mode="SEQUENTIAL",
            decision_mode="ALL",
            priority="HIGH",
            policy_key="PURCHASE-APPROVAL",
            policy_version="1.0",
        )

        assert response.status_code == 201, response.text

        data = response.json()

        assert data["status"] == "PENDING"
        assert data["entity_type"] == "PURCHASE_REQUEST"
        assert data["entity_id"] == request_id
        assert data["execution_mode"] == "SEQUENTIAL"
        assert data["decision_mode"] == "ALL"
        assert data["priority"] == "HIGH"
        assert data["policy_key"] == "PURCHASE-APPROVAL"
        assert data["policy_version"] == "1.0"
        assert data["requested_by"] is not None

        assert len(data["steps"]) == 2
        assert data["steps"][0]["step_order"] == 1
        assert data["steps"][0]["status"] == "PENDING"
        assert data["steps"][0]["approver_role"] == "ADMIN"

        assert data["steps"][1]["step_order"] == 2
        assert data["steps"][1]["status"] == "PENDING"
        assert data["steps"][1]["approver_role"] == "PROCUREMENT"

    finally:
        _cleanup_approval(db, request_id)
        db.close()


def test_02_duplicate_step_order_rejected(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    response = _create_approval(
        base_url,
        auth_headers,
        request_id,
        steps=[
            {
                "step_order": 1,
                "approver_role": "ADMIN",
            },
            {
                "step_order": 1,
                "approver_role": "PROCUREMENT",
            },
        ],
    )

    assert response.status_code == 400, response.text


def test_03_step_without_approver_rejected(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    response = _create_approval(
        base_url,
        auth_headers,
        request_id,
        steps=[
            {
                "step_order": 1,
            }
        ],
    )

    assert response.status_code == 400, response.text


def test_04_self_approver_rejected(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_company_data,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    response = _create_approval(
        base_url,
        auth_headers,
        request_id,
        steps=[
            {
                "step_order": 1,
                "approver_user_id": test_company_data["user_id"],
            }
        ],
    )

    assert response.status_code == 400, response.text


def test_05_non_member_approver_rejected(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    response = _create_approval(
        base_url,
        auth_headers,
        request_id,
        steps=[
            {
                "step_order": 1,
                "approver_user_id": str(uuid.uuid4()),
            }
        ],
    )

    assert response.status_code == 404, response.text


def test_06_duplicate_active_approval_rejected(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    db = psycopg.connect(test_database_url)

    try:
        first = _create_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert first.status_code == 201, first.text

        second = _create_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert second.status_code == 409, second.text

    finally:
        _cleanup_approval(db, request_id)
        db.close()


def test_07_approval_request_audit_created(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    db = psycopg.connect(test_database_url)

    try:
        response = _create_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert response.status_code == 201, response.text

        approval_id = response.json()["id"]

        row = db.execute(
            """
            SELECT entity_type, entity_id, action
            FROM audit_log
            WHERE entity_type = 'APPROVAL_REQUEST'
              AND entity_id = %s
              AND action = 'APPROVAL_REQUEST_CREATED'
            LIMIT 1
            """,
            (uuid.UUID(approval_id),),
        ).fetchone()

        assert row is not None
        assert row[0] == "APPROVAL_REQUEST"
        assert row[1] == uuid.UUID(approval_id)
        assert row[2] == "APPROVAL_REQUEST_CREATED"

    finally:
        _cleanup_approval(db, request_id)
        db.close()


def test_08_schema_entity_type_without_backend_mapping(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    response = requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": "RFQ",
            "entity_id": request_id,
            "steps": [
                {
                    "step_order": 1,
                    "approver_role": "ADMIN",
                }
            ],
        },
        timeout=10,
    )

    assert response.status_code == 422, response.text



def _get_approval_request(db, approval_id):
    return db.execute(
        """
        SELECT id, status, completed_at
        FROM approval_requests
        WHERE id = %s
        """,
        (uuid.UUID(approval_id),),
    ).fetchone()


def _get_approval_step(db, approval_id, step_order=1):
    return db.execute(
        """
        SELECT
            id,
            status,
            approver_user_id,
            approver_role,
            acted_by,
            acted_at,
            comment
        FROM approval_steps
        WHERE approval_request_id = %s
          AND step_order = %s
        """,
        (uuid.UUID(approval_id), step_order),
    ).fetchone()


def test_09_approval_request_can_be_approved(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    db = psycopg.connect(test_database_url)

    try:
        response = _create_approval(
            base_url,
            auth_headers,
            request_id,
            steps=[
                {
                    "step_order": 1,
                    "approver_role": "OWNER",
                }
            ],
        )

        assert response.status_code == 201, response.text

        approval_id = response.json()["id"]

        # Decision endpoint hələ implementasiya edilməyib.
        response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "APPROVE",
                "comment": "Test approval",
            },
            timeout=10,
        )

        assert response.status_code == 200, response.text

        data = response.json()

        assert data["step"]["status"] == "APPROVED"
        assert data["request"]["status"] == "APPROVED"

        step = _get_approval_step(db, approval_id)

        assert step is not None
        assert step[1] == "APPROVED"
        assert step[4] is not None
        assert step[5] is not None
        assert step[6] == "Test approval"

    finally:
        _cleanup_approval(db, request_id)
        db.close()


def test_10_approval_request_can_be_rejected(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    db = psycopg.connect(test_database_url)

    try:
        response = _create_approval(
            base_url,
            auth_headers,
            request_id,
            steps=[
                {
                    "step_order": 1,
                    "approver_role": "OWNER",
                }
            ],
        )

        assert response.status_code == 201, response.text

        approval_id = response.json()["id"]

        response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "REJECT",
                "comment": "Test rejection",
            },
            timeout=10,
        )

        assert response.status_code == 200, response.text

        data = response.json()

        assert data["step"]["status"] == "REJECTED"
        assert data["request"]["status"] == "REJECTED"

        step = _get_approval_step(db, approval_id)

        assert step is not None
        assert step[1] == "REJECTED"
        assert step[4] is not None
        assert step[5] is not None
        assert step[6] == "Test rejection"

    finally:
        _cleanup_approval(db, request_id)
        db.close()


def test_11_already_decided_step_cannot_be_decided_again(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    response = _create_approval(
        base_url,
        auth_headers,
        request_id,
        steps=[
            {
                "step_order": 1,
                "approver_role": "OWNER",
            }
        ],
    )

    assert response.status_code == 201, response.text

    approval_id = response.json()["id"]

    first = requests.post(
        f"{base_url}/api/v1/approvals/{approval_id}/decision",
        headers=auth_headers,
        json={
            "decision": "APPROVE",
            "comment": "First decision",
        },
        timeout=10,
    )

    assert first.status_code == 200, first.text

    second = requests.post(
        f"{base_url}/api/v1/approvals/{approval_id}/decision",
        headers=auth_headers,
        json={
            "decision": "REJECT",
            "comment": "Second decision",
        },
        timeout=10,
    )

    assert second.status_code in (400, 409), second.text
