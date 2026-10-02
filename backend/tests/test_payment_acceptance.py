import uuid
import pytest

import psycopg
import requests


def _create_approved_po(base_url, auth_headers, test_company_data):
    suffix = uuid.uuid4().hex[:8].upper()

    payload = {
        "supplier_id": test_company_data["supplier_id"],
        "order_number": f"PO-PAY-{suffix}",
        "order_date": "2026-09-27T00:00:00",
        "currency": "AZN",
        "notes": "4.23.10 PAYMENT TEST",
        "items": [
            {
                "product_id": test_company_data["product_id"],
                "quantity": 1,
                "unit": "ədəd",
                "unit_price": 100,
                "vat_rate": 18,
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=auth_headers,
        json=payload,
        timeout=10,
    )
    assert response.status_code == 201, response.text

    po = response.json()

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{po['id']}/status",
        headers=auth_headers,
        json={"status": "SUBMITTED"},
        timeout=10,
    )
    assert response.status_code == 200, response.text

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{po['id']}/status",
        headers=auth_headers,
        json={"status": "APPROVED"},
        timeout=10,
    )
    assert response.status_code == 200, response.text

    return response.json()


def test_231_payment_creation(base_url, auth_headers, test_company_data):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["purchase_order_id"] == po["id"]
    assert float(data["amount"]) == 100
    assert data["currency"] == "AZN"
    assert data["status"] == "PENDING"


def test_232_payment_amount_must_be_positive(
    base_url, auth_headers, test_company_data
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 0,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert response.status_code == 422


def test_233_payment_currency_must_match_po(
    base_url, auth_headers, test_company_data
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "USD",
        },
        timeout=10,
    )

    assert response.status_code == 422


def test_234_payment_requires_existing_po(
    base_url, auth_headers
):
    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": str(uuid.uuid4()),
            "amount": 100,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert response.status_code == 404


def test_235_payment_audit_created(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    po = _create_approved_po(
        base_url,
        auth_headers,
        test_company_data,
    )

    payment_id = None
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        response = requests.post(
            f"{base_url}/api/v1/payments",
            headers=auth_headers,
            json={
                "purchase_order_id": po["id"],
                "amount": 100,
                "currency": "AZN",
            },
            timeout=10,
        )

        assert response.status_code == 201, response.text

        payment = response.json()
        payment_id = uuid.UUID(payment["id"])

        row = db.execute(
            """
            SELECT
                user_id,
                company_id,
                action,
                entity_type,
                entity_id,
                metadata
            FROM audit_log
            WHERE entity_type = 'payment'
              AND entity_id = %s
              AND action = 'PAYMENT_CREATED'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (payment_id,),
        ).fetchone()

        assert row is not None

        assert row[0] == uuid.UUID(test_company_data["user_id"])
        assert row[1] == uuid.UUID(test_company_data["company_id"])
        assert row[2] == "PAYMENT_CREATED"
        assert row[3] == "payment"
        assert row[4] == payment_id

        metadata = row[5]

        assert metadata["purchase_order_id"] == po["id"]
        assert metadata["order_number"] == po["order_number"]
        assert metadata["currency"] == "AZN"
        assert metadata["status"] == "PENDING"
        assert "amount" in metadata

    finally:
        if payment_id is not None:
            db.execute(
                """
                DELETE FROM audit_log
                WHERE entity_type = 'payment'
                  AND entity_id = %s
                  AND action = 'PAYMENT_CREATED'
                """,
                (payment_id,),
            )

            db.execute(
                """
                DELETE FROM payments
                WHERE id = %s
                """,
                (payment_id,),
            )

        db.close()


def test_236_cross_company_payment_creation_blocked(
    base_url,
    auth_headers,
    test_database_url, cross_company_context):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        row = db.execute(
            """
            SELECT id
            FROM purchase_orders
            WHERE company_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(cross_company_context["company_id"]),),
        ).fetchone()

        assert row is not None

        foreign_po_id = row[0]

        response = requests.post(
            f"{base_url}/api/v1/payments",
            headers=auth_headers,
            json={
                "purchase_order_id": str(foreign_po_id),
                "amount": 100,
                "currency": "AZN",
            },
            timeout=10,
        )

        assert response.status_code == 404, response.text

    finally:
        db.close()
def _cleanup_payment(test_database_url, payment_id):
    db = psycopg.connect(test_database_url)
    db.autocommit = True
    try:
        db.execute("DELETE FROM audit_log WHERE entity_type = 'payment' AND entity_id = %s", (uuid.UUID(str(payment_id)),))
        db.execute("DELETE FROM payments WHERE id = %s", (uuid.UUID(str(payment_id)),))
    finally:
        db.close()


def _create_payment(base_url, auth_headers, test_company_data):
    po = _create_approved_po(base_url, auth_headers, test_company_data)
    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={"purchase_order_id": po["id"], "amount": 100, "currency": "AZN"},
        timeout=10,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _status(base_url, auth_headers, payment_id, status):
    return requests.post(
        f"{base_url}/api/v1/payments/{payment_id}/status",
        headers=auth_headers,
        json={"status": status},
        timeout=10,
    )


def test_237_payment_pending_to_paid(base_url, auth_headers, test_company_data, test_database_url):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    try:
        response = _status(base_url, auth_headers, payment["id"], "PAID")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["old_status"] == "PENDING"
        assert data["new_status"] == "PAID"
        assert data["paid_at"] is not None
    finally:
        _cleanup_payment(test_database_url, payment["id"])


def test_238_payment_pending_to_failed(base_url, auth_headers, test_company_data, test_database_url):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    try:
        response = _status(base_url, auth_headers, payment["id"], "FAILED")
        assert response.status_code == 200, response.text
        assert response.json()["paid_at"] is None
    finally:
        _cleanup_payment(test_database_url, payment["id"])


def test_239_payment_pending_to_cancelled(base_url, auth_headers, test_company_data, test_database_url):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    try:
        response = _status(base_url, auth_headers, payment["id"], "CANCELLED")
        assert response.status_code == 200, response.text
        assert response.json()["paid_at"] is None
    finally:
        _cleanup_payment(test_database_url, payment["id"])


@pytest.mark.parametrize("final_status,blocked_status", [
    ("PAID", "FAILED"), ("PAID", "CANCELLED"),
    ("FAILED", "PAID"), ("FAILED", "CANCELLED"),
    ("CANCELLED", "PAID"), ("CANCELLED", "FAILED"),
])
def test_240_payment_terminal_transitions_blocked(base_url, auth_headers, test_company_data, test_database_url, final_status, blocked_status):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    try:
        first = _status(base_url, auth_headers, payment["id"], final_status)
        assert first.status_code == 200, first.text
        response = _status(base_url, auth_headers, payment["id"], blocked_status)
        assert response.status_code == 400, response.text
    finally:
        _cleanup_payment(test_database_url, payment["id"])


def test_241_payment_same_status_rejected(base_url, auth_headers, test_company_data, test_database_url):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    try:
        response = _status(base_url, auth_headers, payment["id"], "PENDING")
        assert response.status_code == 400, response.text
    finally:
        _cleanup_payment(test_database_url, payment["id"])


def test_242_payment_paid_at_persisted(base_url, auth_headers, test_company_data, test_database_url):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    try:
        assert _status(base_url, auth_headers, payment["id"], "PAID").status_code == 200
        db = psycopg.connect(test_database_url); db.autocommit = True
        try:
            row = db.execute("SELECT status, paid_at FROM payments WHERE id = %s", (uuid.UUID(payment["id"]),)).fetchone()
            assert row is not None and row[0] == "PAID" and row[1] is not None
        finally:
            db.close()
    finally:
        _cleanup_payment(test_database_url, payment["id"])


def test_243_payment_failed_paid_at_null(base_url, auth_headers, test_company_data, test_database_url):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    try:
        assert _status(base_url, auth_headers, payment["id"], "FAILED").status_code == 200
        db = psycopg.connect(test_database_url); db.autocommit = True
        try:
            row = db.execute("SELECT paid_at FROM payments WHERE id = %s", (uuid.UUID(payment["id"]),)).fetchone()
            assert row is not None and row[0] is None
        finally:
            db.close()
    finally:
        _cleanup_payment(test_database_url, payment["id"])


def test_244_payment_status_response_fields(base_url, auth_headers, test_company_data, test_database_url):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    try:
        response = _status(base_url, auth_headers, payment["id"], "PAID")
        assert response.status_code == 200, response.text
        data = response.json()
        assert {"id", "purchase_order_id", "old_status", "new_status", "amount", "currency", "paid_at", "updated_at"} <= data.keys()
    finally:
        _cleanup_payment(test_database_url, payment["id"])


def test_245_payment_missing_id_404(base_url, auth_headers):
    response = _status(base_url, auth_headers, str(uuid.uuid4()), "PAID")
    assert response.status_code == 404, response.text


def test_246_payment_status_audit_created(base_url, auth_headers, test_company_data, test_database_url):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    db = psycopg.connect(test_database_url); db.autocommit = True
    try:
        assert _status(base_url, auth_headers, payment["id"], "PAID").status_code == 200
        row = db.execute(
            "SELECT user_id, company_id, action, entity_type, entity_id, metadata FROM audit_log "
            "WHERE entity_type = 'payment' AND entity_id = %s AND action = 'PAYMENT_STATUS_CHANGED' "
            "ORDER BY created_at DESC LIMIT 1", (uuid.UUID(payment["id"]),)
        ).fetchone()
        assert row is not None
        assert row[0] == uuid.UUID(test_company_data["user_id"])
        assert row[1] == uuid.UUID(test_company_data["company_id"])
        assert row[2] == "PAYMENT_STATUS_CHANGED"
        assert row[3] == "payment"
        assert row[4] == uuid.UUID(payment["id"])
        assert row[5]["old_status"] == "PENDING"
        assert row[5]["new_status"] == "PAID"
        assert row[5]["purchase_order_id"] == payment["purchase_order_id"]
        assert row[5]["currency"] == "AZN"
    finally:
        db.close(); _cleanup_payment(test_database_url, payment["id"])


def test_247_payment_invalid_status_rejected(base_url, auth_headers, test_company_data, test_database_url):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    try:
        payment_id = payment["id"]
        response = requests.post(f"{base_url}/api/v1/payments/{payment_id}/status", headers=auth_headers, json={"status": "REFUNDED"}, timeout=10)
        assert response.status_code == 422, response.text
    finally:
        _cleanup_payment(test_database_url, payment["id"])



def test_248_payment_cross_company_status_blocked(base_url, auth_headers, test_database_url, cross_company_context):
    db = psycopg.connect(test_database_url); db.autocommit = True
    payment_id = None
    try:
        row = db.execute("SELECT id, currency FROM purchase_orders WHERE company_id = %s ORDER BY created_at DESC LIMIT 1", (uuid.UUID(cross_company_context["company_id"]),)).fetchone()
        assert row is not None
        payment_id = db.execute(
            "INSERT INTO payments (company_id, purchase_order_id, amount, currency, status) VALUES (%s, %s, %s, %s, 'PENDING') RETURNING id",
            (uuid.UUID(cross_company_context["company_id"]), row[0], 1, row[1])
        ).fetchone()[0]
        response = _status(base_url, auth_headers, payment_id, "PAID")
        assert response.status_code == 404, response.text
    finally:
        if payment_id is not None: db.execute("DELETE FROM payments WHERE id = %s", (payment_id,))
        db.close()


def _create_payment_approval(base_url, auth_headers, payment_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": "PAYMENT",
            "entity_id": payment_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "PAYMENT-APPROVAL",
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


def _cleanup_payment_approval(test_database_url, approval_id):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        db.execute(
            """
            DELETE FROM approval_steps
            WHERE approval_request_id = %s
            """,
            (uuid.UUID(str(approval_id)),),
        )

        db.execute(
            """
            DELETE FROM audit_log
            WHERE entity_type = 'APPROVAL_REQUEST'
              AND entity_id = %s
            """,
            (uuid.UUID(str(approval_id)),),
        )

        db.execute(
            """
            DELETE FROM approval_requests
            WHERE id = %s
            """,
            (uuid.UUID(str(approval_id)),),
        )
    finally:
        db.close()


def test_249_payment_approval_request_success(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    approval_id = None

    try:
        response = _create_payment_approval(
            base_url,
            auth_headers,
            payment["id"],
        )

        assert response.status_code == 201, response.text

        data = response.json()
        approval_id = data["id"]

        assert data["entity_type"] == "PAYMENT"
        assert data["entity_id"] == payment["id"]
        assert data["status"] == "PENDING"

    finally:
        if approval_id is not None:
            _cleanup_payment_approval(test_database_url, approval_id)

        _cleanup_payment(test_database_url, payment["id"])


def test_250_payment_approval_duplicate_blocked(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    approval_id = None

    try:
        first = _create_payment_approval(
            base_url,
            auth_headers,
            payment["id"],
        )

        assert first.status_code == 201, first.text
        approval_id = first.json()["id"]

        second = _create_payment_approval(
            base_url,
            auth_headers,
            payment["id"],
        )

        assert second.status_code == 409, second.text

    finally:
        if approval_id is not None:
            _cleanup_payment_approval(test_database_url, approval_id)

        _cleanup_payment(test_database_url, payment["id"])


def test_251_payment_approval_does_not_change_payment_status(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    payment = _create_payment(base_url, auth_headers, test_company_data)
    approval_id = None

    try:
        create_response = _create_payment_approval(
            base_url,
            auth_headers,
            payment["id"],
        )

        assert create_response.status_code == 201, create_response.text
        approval_id = create_response.json()["id"]

        decision = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=auth_headers,
            json={
                "decision": "APPROVE",
                "comment": "Payment approval integration test",
            },
            timeout=10,
        )

        assert decision.status_code == 200, decision.text

        db = psycopg.connect(test_database_url)
        db.autocommit = True

        try:
            approval_row = db.execute(
                """
                SELECT status
                FROM approval_requests
                WHERE id = %s
                """,
                (uuid.UUID(approval_id),),
            ).fetchone()

            payment_row = db.execute(
                """
                SELECT status
                FROM payments
                WHERE id = %s
                """,
                (uuid.UUID(payment["id"]),),
            ).fetchone()

            assert approval_row is not None
            assert approval_row[0] == "APPROVED"

            assert payment_row is not None
            assert payment_row[0] == "PENDING"

        finally:
            db.close()

    finally:
        if approval_id is not None:
            _cleanup_payment_approval(test_database_url, approval_id)

        _cleanup_payment(test_database_url, payment["id"])

def test_payment_limit_direct_oversize(base_url, auth_headers, test_company_data):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 119,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert response.status_code == 400, response.text
    assert "remaining purchase order balance" in response.text


def test_payment_limit_cumulative_oversize(base_url, auth_headers, test_company_data):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    first = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "AZN",
        },
        timeout=10,
    )
    assert first.status_code == 201, first.text

    second = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 19,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert second.status_code == 400, second.text


def test_payment_limit_exact_remaining_amount(
    base_url, auth_headers, test_company_data
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    first = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "AZN",
        },
        timeout=10,
    )
    assert first.status_code == 201, first.text

    second = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 18,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert second.status_code == 201, second.text


def test_payment_limit_releases_failed_payment(
    base_url, auth_headers, test_company_data
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    first = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "AZN",
        },
        timeout=10,
    )
    assert first.status_code == 201, first.text
    payment_id = first.json()["id"]

    failed = requests.post(
        f"{base_url}/api/v1/payments/{payment_id}/status",
        headers=auth_headers,
        json={"status": "FAILED"},
        timeout=10,
    )
    assert failed.status_code == 200, failed.text

    second = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 19,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert second.status_code == 201, second.text


def test_payment_limit_keeps_paid_payment(
    base_url, auth_headers, test_company_data
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    first = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "AZN",
        },
        timeout=10,
    )
    assert first.status_code == 201, first.text
    payment_id = first.json()["id"]

    paid = requests.post(
        f"{base_url}/api/v1/payments/{payment_id}/status",
        headers=auth_headers,
        json={"status": "PAID"},
        timeout=10,
    )
    assert paid.status_code == 200, paid.text

    second = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 19,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert second.status_code == 400, second.text


def test_256_duplicate_payment_reference_returns_409(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)
    reference = f"DUP-REFERENCE-{uuid.uuid4().hex[:12].upper()}"
    payment_id = None

    try:
        first = requests.post(
            f"{base_url}/api/v1/payments",
            headers=auth_headers,
            json={
                "purchase_order_id": po["id"],
                "amount": 50,
                "currency": "AZN",
                "reference": reference,
            },
            timeout=10,
        )

        assert first.status_code == 201, first.text
        payment_id = first.json()["id"]

        second = requests.post(
            f"{base_url}/api/v1/payments",
            headers=auth_headers,
            json={
                "purchase_order_id": po["id"],
                "amount": 50,
                "currency": "AZN",
                "reference": reference,
            },
            timeout=10,
        )

        assert second.status_code == 409, second.text
        assert second.json()["detail"] == "Payment reference already exists"

        db = psycopg.connect(test_database_url)
        db.autocommit = True
        try:
            payment_count = db.execute(
                """
                SELECT COUNT(*)
                FROM payments
                WHERE reference = %s
                """,
                (reference,),
            ).fetchone()[0]

            audit_count = db.execute(
                """
                SELECT COUNT(*)
                FROM audit_log
                WHERE entity_type = 'payment'
                  AND entity_id = %s
                  AND action = 'PAYMENT_CREATED'
                """,
                (uuid.UUID(payment_id),),
            ).fetchone()[0]

            assert payment_count == 1
            assert audit_count == 1
        finally:
            db.close()

    finally:
        if payment_id is not None:
            _cleanup_payment(test_database_url, payment_id)


def test_257_payment_creation_requires_payment_role(
    base_url,
    acceptance_owner_headers,
    acceptance_viewer_headers,
    acceptance_owner_data,
):
    po = _create_approved_po(
        base_url,
        acceptance_owner_headers,
        acceptance_owner_data,
    )

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=acceptance_viewer_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 1,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert response.status_code == 403, response.text


def test_258_payment_status_requires_payment_role(
    base_url,
    acceptance_owner_headers,
    acceptance_viewer_headers,
    acceptance_owner_data,
    test_database_url,
):
    payment = _create_payment(
        base_url,
        acceptance_owner_headers,
        acceptance_owner_data,
    )

    try:
        response = _status(
            base_url,
            acceptance_viewer_headers,
            payment["id"],
            "PAID",
        )

        assert response.status_code == 403, response.text

        db = psycopg.connect(test_database_url)
        db.autocommit = True
        try:
            row = db.execute(
                """
                SELECT status
                FROM payments
                WHERE id = %s
                """,
                (uuid.UUID(payment["id"]),),
            ).fetchone()

            assert row is not None
            assert row[0] == "PENDING"
        finally:
            db.close()

    finally:
        _cleanup_payment(test_database_url, payment["id"])


def test_252_payment_negative_amount_rejected(
    base_url, auth_headers, test_company_data
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": -1,
            "currency": "AZN",
        },
        timeout=10,
    )

    assert response.status_code == 422


def test_253_payment_currency_too_short_rejected(
    base_url, auth_headers, test_company_data
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "AZ",
        },
        timeout=10,
    )

    assert response.status_code == 422


def test_254_payment_currency_too_long_rejected(
    base_url, auth_headers, test_company_data
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "AZNN",
        },
        timeout=10,
    )

    assert response.status_code == 422


def test_255_payment_amount_more_than_4_decimals_rejected(
    base_url, auth_headers, test_company_data, test_database_url
):
    po = _create_approved_po(base_url, auth_headers, test_company_data)

    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=auth_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": "0.00001",
            "currency": "AZN",
            "reference": f"DECIMAL-TEST-{uuid.uuid4().hex[:10]}",
        },
        timeout=10,
    )

    assert response.status_code == 422, response.text
