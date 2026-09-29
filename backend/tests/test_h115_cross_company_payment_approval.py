import uuid

import psycopg
import requests


def _cleanup_payment(db, payment_id):
    db.execute(
        "DELETE FROM payments WHERE id = %s",
        (payment_id,),
    )


def _cleanup_approval(db, approval_id):
    db.execute(
        "DELETE FROM approval_steps WHERE approval_request_id = %s",
        (approval_id,),
    )
    db.execute(
        "DELETE FROM approval_requests WHERE id = %s",
        (approval_id,),
    )


def test_h115_01_cross_company_payment_approval_creation_blocked(
    base_url,
    auth_headers,
    test_database_url,
    cross_company_context,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    payment_id = uuid.uuid4()

    try:
        po_row = db.execute(
            """
            SELECT id, currency
            FROM purchase_orders
            WHERE company_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(cross_company_context["company_id"]),),
        ).fetchone()

        assert po_row is not None
        po_id, currency = po_row

        db.execute(
            """
            INSERT INTO payments (
                id,
                company_id,
                purchase_order_id,
                amount,
                currency,
                status
            )
            VALUES (%s, %s, %s, %s, %s, 'PENDING')
            """,
            (
                payment_id,
                uuid.UUID(cross_company_context["company_id"]),
                po_id,
                1,
                currency,
            ),
        )

        before = db.execute(
            """
            SELECT COUNT(*)
            FROM approval_requests
            WHERE entity_type = 'PAYMENT'
              AND entity_id = %s
            """,
            (payment_id,),
        ).fetchone()[0]

        response = requests.post(
            f"{base_url}/api/v1/approvals/requests",
            headers=auth_headers,
            json={
                "entity_type": "PAYMENT",
                "entity_id": str(payment_id),
                "execution_mode": "SEQUENTIAL",
                "decision_mode": "ALL",
                "priority": "NORMAL",
                "policy_key": "H1.15-CROSS-COMPANY-PAYMENT",
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

        assert response.status_code == 404, response.text

        after = db.execute(
            """
            SELECT COUNT(*)
            FROM approval_requests
            WHERE entity_type = 'PAYMENT'
              AND entity_id = %s
            """,
            (payment_id,),
        ).fetchone()[0]

        assert after == before

        payment_row = db.execute(
            """
            SELECT status
            FROM payments
            WHERE id = %s
            """,
            (payment_id,),
        ).fetchone()

        assert payment_row is not None
        assert payment_row[0] == "PENDING"

    finally:
        _cleanup_payment(db, payment_id)
        db.close()


def test_h115_02_cross_company_payment_approval_decision_blocked(
    base_url,
    auth_headers,
    test_database_url,
    cross_company_context,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    payment_id = uuid.uuid4()
    approval_id = uuid.uuid4()

    try:
        po_row = db.execute(
            """
            SELECT id, currency
            FROM purchase_orders
            WHERE company_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(cross_company_context["company_id"]),),
        ).fetchone()

        assert po_row is not None
        po_id, currency = po_row

        db.execute(
            """
            INSERT INTO payments (
                id,
                company_id,
                purchase_order_id,
                amount,
                currency,
                status
            )
            VALUES (%s, %s, %s, %s, %s, 'PENDING')
            """,
            (
                payment_id,
                uuid.UUID(cross_company_context["company_id"]),
                po_id,
                1,
                currency,
            ),
        )

        member_row = db.execute(
            """
            SELECT user_id
            FROM company_members
            WHERE company_id = %s
            LIMIT 1
            """,
            (uuid.UUID(cross_company_context["company_id"]),),
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
                'PAYMENT',
                %s,
                'PENDING',
                'SEQUENTIAL',
                'ALL',
                'NORMAL',
                'H1.15-CROSS-COMPANY-PAYMENT',
                '1.0',
                %s,
                '{}'::jsonb
            )
            """,
            (
                approval_id,
                uuid.UUID(cross_company_context["company_id"]),
                payment_id,
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
                "comment": "H1.15 cross-company payment decision test",
            },
            timeout=10,
        )

        assert response.status_code == 404, response.text

        approval_row = db.execute(
            """
            SELECT status
            FROM approval_requests
            WHERE id = %s
            """,
            (approval_id,),
        ).fetchone()

        assert approval_row is not None
        assert approval_row[0] == "PENDING"

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

        payment_row = db.execute(
            """
            SELECT status
            FROM payments
            WHERE id = %s
            """,
            (payment_id,),
        ).fetchone()

        assert payment_row is not None
        assert payment_row[0] == "PENDING"

    finally:
        _cleanup_approval(db, approval_id)
        _cleanup_payment(db, payment_id)
        db.close()
