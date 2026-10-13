import uuid

import requests
from pwdlib import PasswordHash


def _insert_notification_member(test_db, company_id, role):
    user_id = uuid.uuid4()
    suffix = uuid.uuid4().hex
    email = f"notification-event-{suffix}@example.com"
    password = f"NotifTest-{suffix}-A1!"
    password_hash = PasswordHash.recommended().hash(password)

    test_db.execute(
        """
        INSERT INTO users (id, email, password_hash, full_name, is_active)
        VALUES (%s, %s, %s, %s, TRUE)
        """,
        (user_id, email, password_hash, f"Notification Test {role}"),
    )
    test_db.execute(
        """
        INSERT INTO company_members (user_id, company_id, role)
        VALUES (%s, %s, %s)
        """,
        (user_id, company_id, role),
    )
    return user_id, email, password


def _login_test_member(base_url, email, password):
    response = requests.post(
        f"{base_url}/api/v1/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    assert response.status_code == 200, response.text

    body = response.json()
    token = body.get("access_token") or body.get("token")
    assert token, f"Login cavabında token yoxdur: {body.keys()}"
    return {"Authorization": f"Bearer {token}"}


def _cleanup_notification_member(test_db, company_id, user_id):
    if user_id is None:
        return
    test_db.execute(
        "DELETE FROM notifications WHERE company_id = %s AND recipient_user_id = %s",
        (company_id, user_id),
    )
    test_db.execute(
        "DELETE FROM company_members WHERE company_id = %s AND user_id = %s",
        (company_id, user_id),
    )
    test_db.execute("DELETE FROM users WHERE id = %s", (user_id,))


def _create_notification_test_po(base_url, auth_headers, test_company_data):
    suffix = uuid.uuid4().hex[:10].upper()
    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=auth_headers,
        json={
            "supplier_id": test_company_data["supplier_id"],
            "order_number": f"NOTIF-EVENT-{suffix}",
            "order_date": "2026-09-27T00:00:00",
            "currency": "AZN",
            "notes": "Notification business event acceptance test",
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": 1,
                    "unit": "ədəd",
                    "unit_price": 100,
                    "vat_rate": 18,
                }
            ],
        },
        timeout=15,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _approve_notification_test_po(base_url, auth_headers, po):
    for status in ("SUBMITTED", "APPROVED"):
        response = requests.post(
            f"{base_url}/api/v1/purchase-orders/{po['id']}/status",
            headers=auth_headers,
            json={"status": status},
            timeout=15,
        )
        assert response.status_code == 200, response.text


def _event_rows(test_db, company_id, recipient_id, source_id, event_type):
    return test_db.execute(
        """
        SELECT event_type, source_event_key, source_entity_type
        FROM notifications
        WHERE company_id = %s
          AND recipient_user_id = %s
          AND source_entity_id = %s
          AND event_type = %s
        """,
        (company_id, recipient_id, source_id, event_type),
    ).fetchall()


def _cleanup_notification_test_po(
    test_db,
    company_id,
    po_id,
    *,
    delivery_id=None,
    payment_id=None,
):
    if payment_id is not None:
        test_db.execute(
            "DELETE FROM notifications WHERE company_id = %s AND source_entity_id = %s",
            (company_id, payment_id),
        )
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (payment_id,),
        )
        test_db.execute("DELETE FROM payments WHERE id = %s", (payment_id,))

    if delivery_id is not None:
        test_db.execute(
            "DELETE FROM notifications WHERE company_id = %s AND source_entity_id = %s",
            (company_id, delivery_id),
        )
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (delivery_id,),
        )
        test_db.execute(
            "DELETE FROM deliveries WHERE id = %s",
            (delivery_id,),
        )

    if po_id is not None:
        test_db.execute(
            "DELETE FROM notifications WHERE company_id = %s AND source_entity_id = %s",
            (company_id, po_id),
        )
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (po_id,),
        )
        test_db.execute(
            "DELETE FROM purchase_orders WHERE id = %s",
            (po_id,),
        )


def test_approval_decision_notifies_requester_once(
    base_url, auth_headers, test_company_data, test_db
):
    company_id = uuid.UUID(test_company_data["company_id"])
    requester_id = uuid.UUID(test_company_data["user_id"])
    approver_id = None
    po_id = None
    approval_id = None

    approver_id, email, password = _insert_notification_member(
        test_db, company_id, "PROCUREMENT"
    )

    try:
        po = _create_notification_test_po(
            base_url, auth_headers, test_company_data
        )
        po_id = uuid.UUID(po["id"])

        create_response = requests.post(
            f"{base_url}/api/v1/approvals/requests",
            headers=auth_headers,
            json={
                "entity_type": "PURCHASE_ORDER",
                "entity_id": str(po_id),
                "execution_mode": "SEQUENTIAL",
                "decision_mode": "ALL",
                "priority": "NORMAL",
                "steps": [
                    {
                        "step_order": 1,
                        "approver_user_id": str(approver_id),
                    }
                ],
            },
            timeout=15,
        )
        assert create_response.status_code == 201, create_response.text
        approval_id = uuid.UUID(create_response.json()["id"])

        step_row = test_db.execute(
            """
            SELECT id FROM approval_steps
            WHERE approval_request_id = %s
            ORDER BY step_order LIMIT 1
            """,
            (approval_id,),
        ).fetchone()
        assert step_row is not None
        step_id = step_row[0]

        approver_headers = _login_test_member(base_url, email, password)
        decision_response = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=approver_headers,
            json={"decision": "APPROVE"},
            timeout=15,
        )
        assert decision_response.status_code == 200, decision_response.text

        rows = _event_rows(
            test_db,
            company_id,
            requester_id,
            approval_id,
            "APPROVAL_DECISION_RECORDED",
        )
        assert len(rows) == 1
        assert rows[0][1] == f"approval-decision:{step_id}"
        assert rows[0][2] == "APPROVAL_REQUEST"

        approver_rows = _event_rows(
            test_db,
            company_id,
            approver_id,
            approval_id,
            "APPROVAL_DECISION_RECORDED",
        )
        assert len(approver_rows) == 0

        repeated = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=approver_headers,
            json={"decision": "APPROVE"},
            timeout=15,
        )
        assert repeated.status_code == 409, repeated.text

        rows_after_repeat = _event_rows(
            test_db,
            company_id,
            requester_id,
            approval_id,
            "APPROVAL_DECISION_RECORDED",
        )
        assert len(rows_after_repeat) == 1
    finally:
        if approval_id is not None:
            test_db.execute(
                "DELETE FROM notifications WHERE company_id = %s AND source_entity_id = %s",
                (company_id, approval_id),
            )
            test_db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (approval_id,),
            )
            test_db.execute(
                "DELETE FROM approval_steps WHERE approval_request_id = %s",
                (approval_id,),
            )
            test_db.execute(
                "DELETE FROM approval_requests WHERE id = %s",
                (approval_id,),
            )

        _cleanup_notification_test_po(test_db, company_id, po_id)
        _cleanup_notification_member(test_db, company_id, approver_id)


def test_supplier_offer_submission_notifies_company_role_once(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
    purchase_request_lifecycle_fixture,
):
    company_id = uuid.UUID(test_company_data["company_id"])
    actor_id = uuid.UUID(test_company_data["user_id"])
    recipient_id = None
    offer_id = None

    recipient_id, _, _ = _insert_notification_member(
        test_db, company_id, "PROCUREMENT"
    )

    try:
        request_id = uuid.UUID(purchase_request_lifecycle_fixture["request_id"])
        item_row = test_db.execute(
            """
            SELECT id FROM purchase_request_items
            WHERE purchase_request_id = %s
            ORDER BY id LIMIT 1
            """,
            (request_id,),
        ).fetchone()
        assert item_row is not None
        request_item_id = item_row[0]

        suffix = uuid.uuid4().hex[:10].upper()
        response = requests.post(
            f"{base_url}/api/v1/procurement/supplier-offers",
            headers=auth_headers,
            json={
                "purchase_request_id": str(request_id),
                "supplier_id": test_company_data["supplier_id"],
                "offer_number": f"NOTIF-SO-{suffix}",
                "status": "SUBMITTED",
                "items": [
                    {
                        "purchase_request_item_id": str(request_item_id),
                        "product_id": test_company_data["product_id"],
                        "quantity": 1,
                        "unit": "ədəd",
                        "unit_price": 10,
                        "vat_rate": 18,
                        "delivery_days": 5,
                    }
                ],
            },
            timeout=15,
        )
        assert response.status_code == 200, response.text
        offer_id = uuid.UUID(response.json()["id"])

        rows = _event_rows(
            test_db,
            company_id,
            recipient_id,
            offer_id,
            "SUPPLIER_OFFER_SUBMITTED",
        )
        assert len(rows) == 1
        assert rows[0][1] == f"supplier-offer-submitted:{offer_id}"
        assert rows[0][2] == "SUPPLIER_OFFER"

        actor_rows = _event_rows(
            test_db,
            company_id,
            actor_id,
            offer_id,
            "SUPPLIER_OFFER_SUBMITTED",
        )
        assert len(actor_rows) == 0
    finally:
        if offer_id is not None:
            test_db.execute(
                "DELETE FROM notifications WHERE company_id = %s AND source_entity_id = %s",
                (company_id, offer_id),
            )
            test_db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (offer_id,),
            )
            test_db.execute(
                "DELETE FROM supplier_offer_items WHERE supplier_offer_id = %s",
                (offer_id,),
            )
            test_db.execute(
                "DELETE FROM supplier_offers WHERE id = %s",
                (offer_id,),
            )

        _cleanup_notification_member(test_db, company_id, recipient_id)


def test_delivery_status_change_notifies_company_role_once(
    base_url, auth_headers, test_company_data, test_db
):
    company_id = uuid.UUID(test_company_data["company_id"])
    actor_id = uuid.UUID(test_company_data["user_id"])
    recipient_id = None
    po_id = None
    delivery_id = None

    recipient_id, _, _ = _insert_notification_member(
        test_db, company_id, "PROCUREMENT"
    )

    try:
        po = _create_notification_test_po(
            base_url, auth_headers, test_company_data
        )
        po_id = uuid.UUID(po["id"])
        _approve_notification_test_po(base_url, auth_headers, po)

        delivery_response = requests.post(
            f"{base_url}/api/v1/deliveries",
            headers=auth_headers,
            json={
                "purchase_order_id": str(po_id),
                "delivery_number": f"NOTIF-DEL-{uuid.uuid4().hex[:10].upper()}",
                "notes": "Notification business event acceptance test",
            },
            timeout=15,
        )
        assert delivery_response.status_code == 201, delivery_response.text
        delivery_id = uuid.UUID(delivery_response.json()["id"])

        status_response = requests.post(
            f"{base_url}/api/v1/deliveries/{delivery_id}/status",
            headers=auth_headers,
            json={"status": "DISPATCHED"},
            timeout=15,
        )
        assert status_response.status_code == 200, status_response.text

        expected_key = f"delivery-status:{delivery_id}:PLANNED:DISPATCHED"
        rows = _event_rows(
            test_db,
            company_id,
            recipient_id,
            delivery_id,
            "DELIVERY_STATUS_CHANGED",
        )
        assert len(rows) == 1
        assert rows[0][1] == expected_key
        assert rows[0][2] == "DELIVERY"

        actor_rows = _event_rows(
            test_db,
            company_id,
            actor_id,
            delivery_id,
            "DELIVERY_STATUS_CHANGED",
        )
        assert len(actor_rows) == 0

        repeated = requests.post(
            f"{base_url}/api/v1/deliveries/{delivery_id}/status",
            headers=auth_headers,
            json={"status": "DISPATCHED"},
            timeout=15,
        )
        assert repeated.status_code == 400, repeated.text

        rows_after_repeat = _event_rows(
            test_db,
            company_id,
            recipient_id,
            delivery_id,
            "DELIVERY_STATUS_CHANGED",
        )
        assert len(rows_after_repeat) == 1
    finally:
        _cleanup_notification_test_po(
            test_db,
            company_id,
            po_id,
            delivery_id=delivery_id,
        )
        _cleanup_notification_member(test_db, company_id, recipient_id)


def test_payment_status_change_notifies_finance_once(
    base_url, auth_headers, test_company_data, test_db
):
    company_id = uuid.UUID(test_company_data["company_id"])
    actor_id = uuid.UUID(test_company_data["user_id"])
    recipient_id = None
    po_id = None
    payment_id = None

    recipient_id, _, _ = _insert_notification_member(
        test_db, company_id, "FINANCE"
    )

    try:
        po = _create_notification_test_po(
            base_url, auth_headers, test_company_data
        )
        po_id = uuid.UUID(po["id"])
        _approve_notification_test_po(base_url, auth_headers, po)

        payment_response = requests.post(
            f"{base_url}/api/v1/payments",
            headers=auth_headers,
            json={
                "purchase_order_id": str(po_id),
                "amount": 10,
                "currency": "AZN",
            },
            timeout=15,
        )
        assert payment_response.status_code == 201, payment_response.text
        payment_id = uuid.UUID(payment_response.json()["id"])

        status_response = requests.post(
            f"{base_url}/api/v1/payments/{payment_id}/status",
            headers=auth_headers,
            json={"status": "PAID"},
            timeout=15,
        )
        assert status_response.status_code == 200, status_response.text

        expected_key = f"payment-status:{payment_id}:PENDING:PAID"
        rows = _event_rows(
            test_db,
            company_id,
            recipient_id,
            payment_id,
            "PAYMENT_STATUS_CHANGED",
        )
        assert len(rows) == 1
        assert rows[0][1] == expected_key
        assert rows[0][2] == "PAYMENT"

        actor_rows = _event_rows(
            test_db,
            company_id,
            actor_id,
            payment_id,
            "PAYMENT_STATUS_CHANGED",
        )
        assert len(actor_rows) == 0

        repeated = requests.post(
            f"{base_url}/api/v1/payments/{payment_id}/status",
            headers=auth_headers,
            json={"status": "PAID"},
            timeout=15,
        )
        assert repeated.status_code == 400, repeated.text

        rows_after_repeat = _event_rows(
            test_db,
            company_id,
            recipient_id,
            payment_id,
            "PAYMENT_STATUS_CHANGED",
        )
        assert len(rows_after_repeat) == 1
    finally:
        _cleanup_notification_test_po(
            test_db,
            company_id,
            po_id,
            payment_id=payment_id,
        )
        _cleanup_notification_member(test_db, company_id, recipient_id)
