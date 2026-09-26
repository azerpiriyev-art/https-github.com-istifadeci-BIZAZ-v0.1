import uuid

import psycopg
import requests


CROSS_COMPANY_ID = "6cf693c6-ad8a-4b4e-803a-f38d1544969c"


def test_h111_02_cross_company_approval_decision_blocked(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    approval_id = uuid.uuid4()
    po_id = None

    try:
        po_row = db.execute(
            """
            SELECT id
            FROM purchase_orders
            WHERE company_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(CROSS_COMPANY_ID),),
        ).fetchone()

        assert po_row is not None
        po_id = po_row[0]

        existing = db.execute(
            """
            SELECT COUNT(*)
            FROM approval_requests
            WHERE company_id = %s
              AND entity_type = 'PURCHASE_ORDER'
              AND entity_id = %s
            """,
            (
                uuid.UUID(CROSS_COMPANY_ID),
                po_id,
            ),
        ).fetchone()[0]

        assert existing == 0

        member_row = db.execute(
            """
            SELECT user_id
            FROM company_members
            WHERE company_id = %s
            LIMIT 1
            """,
            (uuid.UUID(CROSS_COMPANY_ID),),
        ).fetchone()

        assert member_row is not None
        requested_by = member_row[0]

        db.execute(
            """
            INSERT INTO approval_requests (
                id,
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
                %s,
                'PURCHASE_ORDER',
                %s,
                'PENDING',
                'SEQUENTIAL',
                'ALL',
                'NORMAL',
                'H1.11-CROSS-COMPANY',
                '1.0',
                %s,
                '{}'::jsonb
            )
            """,
            (
                approval_id,
                uuid.UUID(CROSS_COMPANY_ID),
                po_id,
                requested_by,
            ),
        )

        db.execute(
            """
            INSERT INTO approval_steps (
                approval_request_id,
                step_order,
                status,
                approver_role,
                metadata
            )
            VALUES (
                %s,
                1,
                'PENDING',
                'OWNER',
                '{}'::jsonb
            )
            """,
            (approval_id,),
        )

        response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "APPROVE",
                "comment": "H1.11 cross-company decision test",
            },
            timeout=10,
        )

        assert response.status_code == 404, response.text

        request_row = db.execute(
            """
            SELECT status
            FROM approval_requests
            WHERE id = %s
            """,
            (approval_id,),
        ).fetchone()

        assert request_row is not None
        assert request_row[0] == "PENDING"

        step_row = db.execute(
            """
            SELECT status, acted_by, acted_at
            FROM approval_steps
            WHERE approval_request_id = %s
              AND step_order = 1
            """,
            (approval_id,),
        ).fetchone()

        assert step_row is not None
        assert step_row[0] == "PENDING"
        assert step_row[1] is None
        assert step_row[2] is None

    finally:
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
