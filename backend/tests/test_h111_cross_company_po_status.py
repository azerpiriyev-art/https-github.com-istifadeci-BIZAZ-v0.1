import uuid

import psycopg
import requests


def test_h111_03_cross_company_po_status_bypass_blocked(
    base_url,
    auth_headers,
    test_database_url,
    cross_company_context,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    po_id = None

    try:
        row = db.execute(
            """
            SELECT id, status
            FROM purchase_orders
            WHERE id = %s
            """,
            (uuid.UUID(cross_company_context["submitted_po_id"]),),
        ).fetchone()

        assert row is not None

        po_id = row[0]
        assert row[1] == "SUBMITTED"

        response = requests.post(
            f"{base_url}/api/v1/purchase-orders/{po_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )

        assert response.status_code == 404, response.text

        after = db.execute(
            """
            SELECT status
            FROM purchase_orders
            WHERE id = %s
            """,
            (po_id,),
        ).fetchone()

        assert after is not None
        assert after[0] == "SUBMITTED"

    finally:
        db.close()
