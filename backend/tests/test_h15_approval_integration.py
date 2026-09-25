import uuid
import psycopg
import requests


def _create_approval(
    base_url,
    auth_headers,
    entity_type,
    entity_id,
):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "H1.5-INTEGRATION",
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


def _cleanup_approval(db, entity_type, entity_id):
    rows = db.execute(
        """
        SELECT id
        FROM approval_requests
        WHERE entity_type = %s
          AND entity_id = %s
        """,
        (entity_type, uuid.UUID(entity_id)),
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


def _cleanup_selection(db, request_id):
    db.execute(
        """
        DELETE FROM offer_selections
        WHERE purchase_request_id = %s
        """,
        (uuid.UUID(request_id),),
    )


def _create_offer_selection(
    base_url,
    auth_headers,
    request_id,
    offer_id,
):
    return requests.post(
        f"{base_url}/api/v1/procurement/offer-selections",
        headers=auth_headers,
        json={
            "purchase_request_id": request_id,
            "supplier_offer_id": offer_id,
            "justification": "H1.5 supplier offer approval integration test",
        },
        timeout=10,
    )


def test_h15_01_pending_supplier_offer_approval_blocks_selection(
    base_url,
    auth_headers,
    comparison_fixture,
    test_database_url,
):
    fixture = comparison_fixture
    request_id = fixture["request_id"]
    offer_id = fixture["offer_1_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        approval_response = _create_approval(
            base_url,
            auth_headers,
            "SUPPLIER_OFFER",
            offer_id,
        )

        assert approval_response.status_code == 201, approval_response.text

        response = _create_offer_selection(
            base_url,
            auth_headers,
            request_id,
            offer_id,
        )

        assert response.status_code == 409, response.text

    finally:
        _cleanup_approval(db, "SUPPLIER_OFFER", offer_id)
        _cleanup_selection(db, request_id)
        db.close()


def test_h15_02_rejected_supplier_offer_approval_blocks_selection(
    base_url,
    auth_headers,
    comparison_fixture,
    test_database_url,
):
    fixture = comparison_fixture
    request_id = fixture["request_id"]
    offer_id = fixture["offer_1_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        approval_response = _create_approval(
            base_url,
            auth_headers,
            "SUPPLIER_OFFER",
            offer_id,
        )

        assert approval_response.status_code == 201, approval_response.text

        approval_id = approval_response.json()["id"]

        decision_response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "REJECT",
                "comment": "H1.5 rejected supplier offer",
            },
            timeout=10,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "REJECTED"

        response = _create_offer_selection(
            base_url,
            auth_headers,
            request_id,
            offer_id,
        )

        assert response.status_code == 409, response.text

    finally:
        _cleanup_approval(db, "SUPPLIER_OFFER", offer_id)
        _cleanup_selection(db, request_id)
        db.close()


def test_h15_03_approved_supplier_offer_approval_allows_selection(
    base_url,
    auth_headers,
    comparison_fixture,
    test_database_url,
):
    fixture = comparison_fixture
    request_id = fixture["request_id"]
    offer_id = fixture["offer_1_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        approval_response = _create_approval(
            base_url,
            auth_headers,
            "SUPPLIER_OFFER",
            offer_id,
        )

        assert approval_response.status_code == 201, approval_response.text

        approval_id = approval_response.json()["id"]

        decision_response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "APPROVE",
                "comment": "H1.5 approved supplier offer",
            },
            timeout=10,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "APPROVED"

        response = _create_offer_selection(
            base_url,
            auth_headers,
            request_id,
            offer_id,
        )

        assert response.status_code == 200, response.text

    finally:
        _cleanup_approval(db, "SUPPLIER_OFFER", offer_id)
        _cleanup_selection(db, request_id)
        db.close()


def test_h15_04_no_supplier_offer_approval_preserves_legacy_selection(
    base_url,
    auth_headers,
    comparison_fixture,
):
    fixture = comparison_fixture
    request_id = fixture["request_id"]
    offer_id = fixture["offer_1_id"]

    response = _create_offer_selection(
        base_url,
        auth_headers,
        request_id,
        offer_id,
    )

    assert response.status_code == 200, response.text
