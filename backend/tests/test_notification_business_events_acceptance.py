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


def test_sequential_approval_notifies_only_next_eligible_step(
    base_url, auth_headers, test_company_data, test_db
):
    company_id = uuid.UUID(test_company_data["company_id"])
    requester_id = uuid.UUID(test_company_data["user_id"])
    first_approver_id = None
    second_approver_id = None
    po_id = None
    approval_id = None

    try:
        first_approver_id, first_email, first_password = (
            _insert_notification_member(test_db, company_id, "PROCUREMENT")
        )
        second_approver_id, second_email, second_password = (
            _insert_notification_member(test_db, company_id, "PROCUREMENT")
        )

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
                        "approver_user_id": str(first_approver_id),
                    },
                    {
                        "step_order": 2,
                        "approver_user_id": str(second_approver_id),
                    },
                ],
            },
            timeout=15,
        )
        assert create_response.status_code == 201, create_response.text
        approval_id = uuid.UUID(create_response.json()["id"])

        step_rows = test_db.execute(
            """
            SELECT id, step_order, approver_user_id, status
            FROM approval_steps
            WHERE approval_request_id = %s
            ORDER BY step_order
            """,
            (approval_id,),
        ).fetchall()

        assert len(step_rows) == 2
        first_step_id = step_rows[0][0]
        second_step_id = step_rows[1][0]

        first_key = f"approval-action:{first_step_id}"
        second_key = f"approval-action:{second_step_id}"

        # On creation, only the first sequential step may be notified.
        first_rows = _event_rows(
            test_db, company_id, first_approver_id,
            approval_id, "APPROVAL_ACTION_REQUIRED"
        )
        second_rows = _event_rows(
            test_db, company_id, second_approver_id,
            approval_id, "APPROVAL_ACTION_REQUIRED"
        )
        assert len(first_rows) == 1
        assert first_rows[0][1] == first_key
        assert len(second_rows) == 0

        first_headers = _login_test_member(
            base_url, first_email, first_password
        )
        second_headers = _login_test_member(
            base_url, second_email, second_password
        )

        # The second approver must not be able to act before step 1.
        premature = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=second_headers,
            json={"decision": "APPROVE"},
            timeout=15,
        )
        assert premature.status_code == 403, premature.text

        statuses = test_db.execute(
            """
            SELECT status
            FROM approval_steps
            WHERE approval_request_id = %s
            ORDER BY step_order
            """,
            (approval_id,),
        ).fetchall()
        assert [row[0] for row in statuses] == ["PENDING", "PENDING"]

        second_rows = _event_rows(
            test_db, company_id, second_approver_id,
            approval_id, "APPROVAL_ACTION_REQUIRED"
        )
        assert len(second_rows) == 0

        first_decision = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=first_headers,
            json={"decision": "APPROVE"},
            timeout=15,
        )
        assert first_decision.status_code == 200, first_decision.text
        assert first_decision.json()["request"]["status"] == "IN_PROGRESS"

        # Step 2 must become actionable only after step 1 succeeds.
        first_rows_after = _event_rows(
            test_db, company_id, first_approver_id,
            approval_id, "APPROVAL_ACTION_REQUIRED"
        )
        second_rows_after = _event_rows(
            test_db, company_id, second_approver_id,
            approval_id, "APPROVAL_ACTION_REQUIRED"
        )
        assert len(first_rows_after) == 1
        assert first_rows_after[0][1] == first_key
        assert len(second_rows_after) == 1
        assert second_rows_after[0][1] == second_key

        requester_rows_after_first = _event_rows(
            test_db, company_id, requester_id,
            approval_id, "APPROVAL_DECISION_RECORDED"
        )
        assert len(requester_rows_after_first) == 1
        assert requester_rows_after_first[0][1] == (
            f"approval-decision:{first_step_id}"
        )

        second_decision = requests.post(
            f"{base_url}/api/v1/approvals/{approval_id}/decision",
            headers=second_headers,
            json={"decision": "APPROVE"},
            timeout=15,
        )
        assert second_decision.status_code == 200, second_decision.text
        assert second_decision.json()["request"]["status"] == "APPROVED"

        requester_rows_final = _event_rows(
            test_db, company_id, requester_id,
            approval_id, "APPROVAL_DECISION_RECORDED"
        )
        assert len(requester_rows_final) == 2
        assert {row[1] for row in requester_rows_final} == {
            f"approval-decision:{first_step_id}",
            f"approval-decision:{second_step_id}",
        }

        first_rows_final = _event_rows(
            test_db, company_id, first_approver_id,
            approval_id, "APPROVAL_ACTION_REQUIRED"
        )
        second_rows_final = _event_rows(
            test_db, company_id, second_approver_id,
            approval_id, "APPROVAL_ACTION_REQUIRED"
        )
        assert len(first_rows_final) == 1
        assert len(second_rows_final) == 1

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
        _cleanup_notification_member(test_db, company_id, first_approver_id)
        _cleanup_notification_member(test_db, company_id, second_approver_id)



def test_notification_insert_failure_rolls_back_purchase_order_and_audit(
    base_url, auth_headers, test_company_data, test_db
):
    from psycopg import sql

    company_id = uuid.UUID(test_company_data["company_id"])
    recipient_id = None
    po_id = None
    function_name = None
    trigger_name = None
    function_created = False
    trigger_created = False

    try:
        # Ensure that a notification recipient exists for the status event.
        recipient_id, _, _ = _insert_notification_member(
            test_db, company_id, "PROCUREMENT"
        )

        po = _create_notification_test_po(
            base_url, auth_headers, test_company_data
        )
        po_id = uuid.UUID(po["id"])

        # Fail only notification inserts for this test purchase order.
        suffix = uuid.uuid4().hex[:12]
        function_name = f"bizaz_test_notif_fail_{suffix}_fn"
        trigger_name = f"bizaz_test_notif_fail_{suffix}_trg"

        test_db.execute(
            sql.SQL("""
                CREATE FUNCTION {}()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $body$
                BEGIN
                    IF NEW.source_entity_id = {}::uuid
                       AND NEW.event_type = 'PURCHASE_ORDER_STATUS_CHANGED'
                    THEN
                        RAISE EXCEPTION
                            'intentional notification failure acceptance test';
                    END IF;
                    RETURN NEW;
                END;
                $body$;
            """).format(
                sql.Identifier(function_name),
                sql.Literal(str(po_id)),
            )
        )
        function_created = True

        test_db.execute(
            sql.SQL("""
                CREATE TRIGGER {}
                BEFORE INSERT ON notifications
                FOR EACH ROW
                EXECUTE FUNCTION {}()
            """).format(
                sql.Identifier(trigger_name),
                sql.Identifier(function_name),
            )
        )
        trigger_created = True

        trigger_exists = test_db.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgname = %s
                  AND NOT tgisinternal
            )
            """,
            (trigger_name,),
        ).fetchone()[0]
        assert trigger_exists, "Failure trigger yaradılmadı."

        # The status and audit changes must roll back if notification
        # insertion fails within the same database transaction.
        response = requests.post(
            f"{base_url}/api/v1/purchase-orders/{po_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=15,
        )
        assert response.status_code == 500, (
            f"Gözlənilən 500 alınmadı: {response.status_code} {response.text}"
        )

        status_row = test_db.execute(
            """
            SELECT status
            FROM purchase_orders
            WHERE id = %s AND company_id = %s
            """,
            (po_id, company_id),
        ).fetchone()
        assert status_row is not None
        assert status_row[0] == "DRAFT", (
            f"Status rollback edilmədi: {status_row[0]}"
        )

        audit_count = test_db.execute(
            """
            SELECT count(*)
            FROM audit_log
            WHERE company_id = %s
              AND entity_id = %s
              AND action = 'PURCHASE_ORDER_STATUS_CHANGED'
            """,
            (company_id, po_id),
        ).fetchone()[0]
        assert audit_count == 0, (
            f"Rollback-dan sonra {audit_count} audit qeydi qalıb."
        )

        notification_count = test_db.execute(
            """
            SELECT count(*)
            FROM notifications
            WHERE company_id = %s
              AND source_entity_id = %s
              AND event_type = 'PURCHASE_ORDER_STATUS_CHANGED'
            """,
            (company_id, po_id),
        ).fetchone()[0]
        assert notification_count == 0, (
            f"Rollback-dan sonra {notification_count} bildiriş qalıb."
        )

    finally:
        # Always remove the temporary trigger/function before cleaning data.
        try:
            if trigger_created:
                test_db.execute(
                    sql.SQL("DROP TRIGGER IF EXISTS {} ON notifications").format(
                        sql.Identifier(trigger_name)
                    )
                )
        finally:
            try:
                if function_created:
                    test_db.execute(
                        sql.SQL("DROP FUNCTION IF EXISTS {}()").format(
                            sql.Identifier(function_name)
                        )
                    )
            finally:
                try:
                    _cleanup_notification_test_po(test_db, company_id, po_id)
                finally:
                    _cleanup_notification_member(
                        test_db, company_id, recipient_id
                    )
