import uuid

import psycopg
import requests


def test_h191_get_approval_request_detail(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    db = psycopg.connect(test_database_url)

    approval_id = None

    try:
        create_response = requests.post(
            f"{base_url}/api/v1/approvals/requests",
            headers=auth_headers,
            json={
                "entity_type": "PURCHASE_REQUEST",
                "entity_id": request_id,
                "execution_mode": "SEQUENTIAL",
                "decision_mode": "ALL",
                "priority": "NORMAL",
                "policy_key": "H1.19.1-READ-DETAIL",
                "policy_version": "1.0",
                "steps": [
                    {
                        "step_order": 1,
                        "approver_role": "OWNER",
                    },
                    {
                        "step_order": 2,
                        "approver_role": "PROCUREMENT",
                    },
                ],
            },
            timeout=10,
        )

        assert create_response.status_code == 201, create_response.text

        created = create_response.json()
        approval_id = created["id"]

        before_audit = db.execute(
            """
            SELECT COUNT(*)
            FROM audit_log
            WHERE entity_type = 'APPROVAL_REQUEST'
              AND entity_id = %s
            """,
            (uuid.UUID(approval_id),),
        ).fetchone()[0]

        response = requests.get(
            f"{base_url}/api/v1/approvals/requests/{approval_id}",
            headers=auth_headers,
            timeout=10,
        )

        assert response.status_code == 200, response.text

        data = response.json()

        assert data["id"] == approval_id
        assert data["entity_type"] == "PURCHASE_REQUEST"
        assert data["entity_id"] == request_id
        assert data["status"] == "PENDING"
        assert data["execution_mode"] == "SEQUENTIAL"
        assert data["decision_mode"] == "ALL"
        assert data["priority"] == "NORMAL"
        assert data["policy_key"] == "H1.19.1-READ-DETAIL"
        assert data["policy_version"] == "1.0"
        assert data["completed_at"] is None

        assert len(data["steps"]) == 2

        assert data["steps"][0]["step_order"] == 1
        assert data["steps"][0]["status"] == "PENDING"
        assert data["steps"][0]["approver_role"] == "OWNER"

        assert data["steps"][1]["step_order"] == 2
        assert data["steps"][1]["status"] == "PENDING"
        assert data["steps"][1]["approver_role"] == "PROCUREMENT"

        after_audit = db.execute(
            """
            SELECT COUNT(*)
            FROM audit_log
            WHERE entity_type = 'APPROVAL_REQUEST'
              AND entity_id = %s
            """,
            (uuid.UUID(approval_id),),
        ).fetchone()[0]

        assert after_audit == before_audit

    finally:
        if approval_id is not None:
            db.execute(
                """
                DELETE FROM approval_steps
                WHERE approval_request_id = %s
                """,
                (uuid.UUID(approval_id),),
            )

            db.execute(
                """
                DELETE FROM audit_log
                WHERE entity_type = 'APPROVAL_REQUEST'
                  AND entity_id = %s
                """,
                (uuid.UUID(approval_id),),
            )

            db.execute(
                """
                DELETE FROM approval_requests
                WHERE id = %s
                """,
                (uuid.UUID(approval_id),),
            )

        db.close()

def test_h192_cross_company_approval_detail_blocked(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    approval_id = None

    try:
        foreign = db.execute(
            """
            SELECT company_id, user_id
            FROM company_members
            WHERE company_id <> %s
            LIMIT 1
            """,
            (uuid.UUID(test_company_data["company_id"]),),
        ).fetchone()

        assert foreign is not None, "Foreign company membership tapılmadı."

        foreign_company_id, foreign_user_id = foreign
        foreign_entity_id = uuid.uuid4()

        approval_id = db.execute(
            """
            INSERT INTO approval_requests (
                company_id,
                entity_type,
                entity_id,
                status,
                execution_mode,
                decision_mode,
                priority,
                policy_key,
                policy_version,
                requested_by,
                metadata
            )
            VALUES (
                %s,
                'PURCHASE_REQUEST',
                %s,
                'PENDING',
                'SEQUENTIAL',
                'ALL',
                'NORMAL',
                'H1.19.2-CROSS-COMPANY',
                '1.0',
                %s,
                '{}'::jsonb
            )
            RETURNING id
            """,
            (
                foreign_company_id,
                foreign_entity_id,
                foreign_user_id,
            ),
        ).fetchone()[0]

        db.execute(
            """
            INSERT INTO approval_steps (
                approval_request_id,
                step_order,
                status,
                approver_user_id,
                metadata
            )
            VALUES (
                %s,
                1,
                'PENDING',
                %s,
                '{}'::jsonb
            )
            """,
            (approval_id, foreign_user_id),
        )

        response = requests.get(
            f"{base_url}/api/v1/approvals/requests/{approval_id}",
            headers=auth_headers,
            timeout=10,
        )

        assert response.status_code == 404, response.text

        audit_count = db.execute(
            """
            SELECT COUNT(*)
            FROM audit_log
            WHERE entity_type = 'APPROVAL_REQUEST'
              AND entity_id = %s
            """,
            (approval_id,),
        ).fetchone()[0]

        assert audit_count == 0

    finally:
        if approval_id is not None:
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

        db.close()
