import uuid

import psycopg
import requests

from test_h18_need_approval import (
    _create_approval,
    _create_need,
    _decide,
    _move_to_under_review,
    _cleanup,
)


def test_h142_01_latest_pending_reapproval_blocks_old_approved_need(
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

        _move_to_under_review(
            base_url,
            auth_headers,
            need_id,
        )

        first = _create_approval(
            base_url,
            auth_headers,
            need_id,
        )

        assert first.status_code == 201, first.text
        first_id = first.json()["id"]

        first_decision = _decide(
            base_url,
            auth_headers,
            first_id,
            "APPROVE",
            "H1.14.2 first approval approved",
        )

        assert first_decision.status_code == 200, first_decision.text
        assert first_decision.json()["request"]["status"] == "APPROVED"

        need_row = db.execute(
            """
            SELECT status
            FROM needs
            WHERE id = %s
            """,
            (uuid.UUID(need_id),),
        ).fetchone()

        assert need_row is not None
        assert need_row[0] == "UNDER_REVIEW"

        second = _create_approval(
            base_url,
            auth_headers,
            need_id,
        )

        assert second.status_code == 201, second.text
        second_id = second.json()["id"]
        assert second.json()["status"] == "PENDING"

        response = requests.post(
            f"{base_url}/api/v1/needs/{need_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )

        assert response.status_code == 409, response.text

        need_row = db.execute(
            """
            SELECT status
            FROM needs
            WHERE id = %s
            """,
            (uuid.UUID(need_id),),
        ).fetchone()

        assert need_row is not None
        assert need_row[0] == "UNDER_REVIEW"

        approval_rows = db.execute(
            """
            SELECT id, status
            FROM approval_requests
            WHERE entity_type = 'NEED'
              AND entity_id = %s
            ORDER BY created_at ASC
            """,
            (uuid.UUID(need_id),),
        ).fetchall()

        assert any(
            str(row[0]) == first_id and row[1] == "APPROVED"
            for row in approval_rows
        )

        assert any(
            str(row[0]) == second_id and row[1] == "PENDING"
            for row in approval_rows
        )

    finally:
        if need_id is not None:
            _cleanup(db, need_id)
        db.close()
