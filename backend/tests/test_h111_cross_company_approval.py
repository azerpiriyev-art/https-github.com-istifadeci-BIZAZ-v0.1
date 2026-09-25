import uuid

import psycopg
import requests


CROSS_COMPANY_PO_ID = "db7f6321-2321-4a35-b6cd-dd22006d3ee4"


def test_h111_01_cross_company_approval_creation_blocked(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    approval_id = None

    try:
        before = db.execute(
            """
            SELECT COUNT(*)
            FROM approval_requests
            WHERE entity_type = 'PURCHASE_ORDER'
              AND entity_id = %s
            """,
            (uuid.UUID(CROSS_COMPANY_PO_ID),),
        ).fetchone()[0]

        response = requests.post(
            f"{base_url}/api/v1/approvals/requests",
            headers=auth_headers,
            json={
                "entity_type": "PURCHASE_ORDER",
                "entity_id": CROSS_COMPANY_PO_ID,
                "execution_mode": "SEQUENTIAL",
                "decision_mode": "ALL",
                "priority": "NORMAL",
                "policy_key": "H1.11-CROSS-COMPANY",
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
            WHERE entity_type = 'PURCHASE_ORDER'
              AND entity_id = %s
            """,
            (uuid.UUID(CROSS_COMPANY_PO_ID),),
        ).fetchone()[0]

        assert after == before

        if response.status_code == 201:
            approval_id = response.json().get("id")

    finally:
        if approval_id is not None:
            db.execute(
                "DELETE FROM approval_steps WHERE approval_request_id = %s",
                (uuid.UUID(approval_id),),
            )
            db.execute(
                "DELETE FROM approval_requests WHERE id = %s",
                (uuid.UUID(approval_id),),
            )

        db.close()
