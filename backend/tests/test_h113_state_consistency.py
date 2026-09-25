import uuid

import psycopg
import requests


def _create_approval(base_url, auth_headers, request_id, entity_type="PURCHASE_REQUEST"):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": entity_type,
            "entity_id": request_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "H1.13-STATE-CONSISTENCY",
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


def _decision(base_url, auth_headers, approval_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/{approval_id}/decision",
        headers=auth_headers,
        json={
            "decision": "APPROVE",
            "comment": "H1.13 business state consistency test",
        },
        timeout=10,
    )


def _cleanup(db, approval_id):
    approval_uuid = uuid.UUID(approval_id)

    db.execute(
        """
        DELETE FROM audit_log
        WHERE entity_type = 'APPROVAL_REQUEST'
          AND entity_id = %s
        """,
        (approval_uuid,),
    )

    db.execute(
        """
        DELETE FROM approval_steps
        WHERE approval_request_id = %s
        """,
        (approval_uuid,),
    )

    db.execute(
        """
        DELETE FROM approval_requests
        WHERE id = %s
        """,
        (approval_uuid,),
    )


def test_h131_01_approval_decision_does_not_auto_approve_purchase_request(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    approval_id = None

    try:
        response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/{request_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=10,
        )

        assert response.status_code == 200, response.text

        before = db.execute(
            """
            SELECT status
            FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        ).fetchone()

        assert before is not None
        assert before[0] == "SUBMITTED"

        approval_response = _create_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert approval_response.status_code == 201, approval_response.text
        approval_id = approval_response.json()["id"]

        decision_response = _decision(
            base_url,
            auth_headers,
            approval_id,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "APPROVED"

        after = db.execute(
            """
            SELECT status
            FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        ).fetchone()

        assert after is not None
        assert after[0] == "SUBMITTED"

    finally:
        if approval_id is not None:
            _cleanup(db, approval_id)

        db.close()

def _reject_decision(base_url, auth_headers, approval_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/{approval_id}/decision",
        headers=auth_headers,
        json={
            "decision": "REJECT",
            "comment": "H1.13.2 business state consistency test",
        },
        timeout=10,
    )


def test_h132_01_rejection_does_not_auto_reject_purchase_request(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
    test_database_url,
):
    request_id = purchase_request_lifecycle_fixture["request_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    approval_id = None

    try:
        response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/{request_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=10,
        )

        assert response.status_code == 200, response.text

        before = db.execute(
            """
            SELECT status
            FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        ).fetchone()

        assert before is not None
        assert before[0] == "SUBMITTED"

        approval_response = _create_approval(
            base_url,
            auth_headers,
            request_id,
        )

        assert approval_response.status_code == 201, approval_response.text
        approval_id = approval_response.json()["id"]

        decision_response = _reject_decision(
            base_url,
            auth_headers,
            approval_id,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "REJECTED"

        after = db.execute(
            """
            SELECT status
            FROM purchase_requests
            WHERE id = %s
            """,
            (uuid.UUID(request_id),),
        ).fetchone()

        assert after is not None
        assert after[0] == "SUBMITTED"

    finally:
        if approval_id is not None:
            _cleanup(db, approval_id)

        db.close()


def test_h133_01_approval_decision_does_not_auto_approve_purchase_order(
    base_url,
    auth_headers,
    purchase_request_po_lifecycle_fixture,
    test_database_url,
):
    fixture = purchase_request_po_lifecycle_fixture
    selection_id = fixture["selection_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    approval_id = None
    purchase_order_id = None

    try:
        po_response = requests.post(
            f"{base_url}/api/v1/procurement/offer-selections/"
            f"{selection_id}/purchase-order",
            headers=auth_headers,
            json={
                "order_number": f"H1-13-03-{uuid.uuid4().hex[:8].upper()}",
                "notes": "H1.13 PO business state consistency test",
            },
            timeout=10,
        )

        assert po_response.status_code == 201, po_response.text
        purchase_order_id = po_response.json()["purchase_order_id"]

        submit_response = requests.post(
            f"{base_url}/api/v1/purchase-orders/"
            f"{purchase_order_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=10,
        )

        assert submit_response.status_code == 200, submit_response.text

        before = db.execute(
            """
            SELECT status
            FROM purchase_orders
            WHERE id = %s
            """,
            (uuid.UUID(purchase_order_id),),
        ).fetchone()

        assert before is not None
        assert before[0] == "SUBMITTED"

        approval_response = _create_approval(
            base_url,
            auth_headers,
            purchase_order_id,
            "PURCHASE_ORDER",
        )

        assert approval_response.status_code == 201, approval_response.text
        approval_id = approval_response.json()["id"]

        decision_response = _decision(
            base_url,
            auth_headers,
            approval_id,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "APPROVED"

        after = db.execute(
            """
            SELECT status
            FROM purchase_orders
            WHERE id = %s
            """,
            (uuid.UUID(purchase_order_id),),
        ).fetchone()

        assert after is not None
        assert after[0] == "SUBMITTED"

    finally:
        if approval_id is not None:
            _cleanup(db, approval_id)

        db.close()

def test_h134_01_approval_decision_does_not_auto_approve_need(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    from test_h18_need_approval import (
        _create_need,
        _move_to_under_review,
        _cleanup as _cleanup_need,
    )

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    need_id = None
    approval_id = None

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

        before = db.execute(
            """
            SELECT status
            FROM needs
            WHERE id = %s
            """,
            (uuid.UUID(need_id),),
        ).fetchone()

        assert before is not None
        assert before[0] == "UNDER_REVIEW"

        approval_response = _create_approval(
            base_url,
            auth_headers,
            need_id,
            "NEED",
        )

        assert approval_response.status_code == 201, approval_response.text
        approval_id = approval_response.json()["id"]

        decision_response = _decision(
            base_url,
            auth_headers,
            approval_id,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "APPROVED"

        after = db.execute(
            """
            SELECT status
            FROM needs
            WHERE id = %s
            """,
            (uuid.UUID(need_id),),
        ).fetchone()

        assert after is not None
        assert after[0] == "UNDER_REVIEW"

    finally:
        if approval_id is not None:
            _cleanup(db, approval_id)

        if need_id is not None:
            _cleanup_need(db, need_id)

        db.close()

def test_h135_01_approval_decision_does_not_change_supplier_offer_state(
    base_url,
    auth_headers,
    comparison_fixture,
    test_database_url,
):
    offer_id = comparison_fixture["offer_1_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    approval_id = None

    try:
        before = db.execute(
            """
            SELECT status
            FROM supplier_offers
            WHERE id = %s
            """,
            (uuid.UUID(offer_id),),
        ).fetchone()

        assert before is not None
        before_status = before[0]

        approval_response = _create_approval(
            base_url,
            auth_headers,
            offer_id,
            "SUPPLIER_OFFER",
        )

        assert approval_response.status_code == 201, approval_response.text
        approval_id = approval_response.json()["id"]

        decision_response = _decision(
            base_url,
            auth_headers,
            approval_id,
        )

        assert decision_response.status_code == 200, decision_response.text
        assert decision_response.json()["request"]["status"] == "APPROVED"

        after = db.execute(
            """
            SELECT status
            FROM supplier_offers
            WHERE id = %s
            """,
            (uuid.UUID(offer_id),),
        ).fetchone()

        assert after is not None
        assert after[0] == before_status

    finally:
        if approval_id is not None:
            _cleanup(db, approval_id)

        db.close()
