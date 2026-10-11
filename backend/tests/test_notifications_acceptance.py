import uuid

import requests


def _insert_notification(
    test_db,
    *,
    company_id: str,
    recipient_user_id: str,
    read_at=None,
):
    notification_id = uuid.uuid4()
    source_event_key = f"test-notification:{uuid.uuid4()}"
    test_db.execute(
        """
        INSERT INTO notifications (
            id, company_id, recipient_user_id, event_type,
            title, body, source_entity_type, source_entity_id,
            source_event_key, read_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            notification_id,
            uuid.UUID(company_id),
            uuid.UUID(recipient_user_id),
            "PURCHASE_ORDER_STATUS_CHANGED",
            "Test bildirişi",
            "Acceptance test bildiriş mətni.",
            "PURCHASE_ORDER",
            uuid.uuid4(),
            source_event_key,
            read_at,
        ),
    )
    return str(notification_id)


def test_notifications_list_unread_count_and_idempotent_mark_read(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    before = requests.get(
        f"{base_url}/api/v1/notifications/unread-count",
        headers=auth_headers,
        timeout=15,
    )
    assert before.status_code == 200, before.text
    before_count = before.json()["count"]

    notification_id = _insert_notification(
        test_db,
        company_id=test_company_data["company_id"],
        recipient_user_id=test_company_data["user_id"],
    )

    try:
        unread_list = requests.get(
            f"{base_url}/api/v1/notifications",
            headers=auth_headers,
            params={"page": 1, "limit": 20, "unread_only": "true"},
            timeout=15,
        )
        assert unread_list.status_code == 200, unread_list.text
        assert notification_id in {
            item["id"] for item in unread_list.json()["items"]
        }

        count_after_insert = requests.get(
            f"{base_url}/api/v1/notifications/unread-count",
            headers=auth_headers,
            timeout=15,
        )
        assert count_after_insert.status_code == 200, count_after_insert.text
        assert count_after_insert.json()["count"] == before_count + 1

        first = requests.patch(
            f"{base_url}/api/v1/notifications/{notification_id}/read",
            headers=auth_headers,
            timeout=15,
        )
        assert first.status_code == 200, first.text
        first_read_at = first.json()["read_at"]
        assert first_read_at is not None

        second = requests.patch(
            f"{base_url}/api/v1/notifications/{notification_id}/read",
            headers=auth_headers,
            timeout=15,
        )
        assert second.status_code == 200, second.text
        assert second.json()["read_at"] == first_read_at

        count_after_read = requests.get(
            f"{base_url}/api/v1/notifications/unread-count",
            headers=auth_headers,
            timeout=15,
        )
        assert count_after_read.status_code == 200, count_after_read.text
        assert count_after_read.json()["count"] == before_count

        audit_count = test_db.execute(
            """
            SELECT count(*) FROM audit_log
            WHERE action = 'NOTIFICATION_MARKED_READ'
              AND entity_id = %s
            """,
            (uuid.UUID(notification_id),),
        ).fetchone()[0]
        assert audit_count == 1
    finally:
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (uuid.UUID(notification_id),),
        )
        test_db.execute(
            "DELETE FROM notifications WHERE id = %s",
            (uuid.UUID(notification_id),),
        )


def test_notifications_are_private_to_recipient_and_company(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    same_company_other_user = test_db.execute(
        """
        SELECT cm.user_id
        FROM company_members cm
        JOIN users u ON u.id = cm.user_id
        WHERE cm.company_id = %s
          AND cm.user_id <> %s
          AND u.is_active IS TRUE
        ORDER BY cm.created_at
        LIMIT 1
        """,
        (
            uuid.UUID(test_company_data["company_id"]),
            uuid.UUID(test_company_data["user_id"]),
        ),
    ).fetchone()

    other_company_user = test_db.execute(
        """
        SELECT cm.user_id, cm.company_id
        FROM company_members cm
        JOIN users u ON u.id = cm.user_id
        WHERE cm.company_id <> %s
          AND u.is_active IS TRUE
        ORDER BY cm.created_at
        LIMIT 1
        """,
        (uuid.UUID(test_company_data["company_id"]),),
    ).fetchone()

    assert same_company_other_user or other_company_user, (
        "Test database needs another active company member for isolation coverage"
    )

    recipient_rows = []
    if same_company_other_user:
        recipient_rows.append(
            (
                test_company_data["company_id"],
                str(same_company_other_user[0]),
            )
        )
    if other_company_user:
        recipient_rows.append(
            (
                str(other_company_user[1]),
                str(other_company_user[0]),
            )
        )

    inserted_ids = []
    try:
        for company_id, recipient_id in recipient_rows:
            inserted_ids.append(
                _insert_notification(
                    test_db,
                    company_id=company_id,
                    recipient_user_id=recipient_id,
                )
            )

        listing = requests.get(
            f"{base_url}/api/v1/notifications",
            headers=auth_headers,
            params={"page": 1, "limit": 100},
            timeout=15,
        )
        assert listing.status_code == 200, listing.text
        returned_ids = {item["id"] for item in listing.json()["items"]}

        for notification_id in inserted_ids:
            assert notification_id not in returned_ids
            response = requests.patch(
                f"{base_url}/api/v1/notifications/{notification_id}/read",
                headers=auth_headers,
                timeout=15,
            )
            assert response.status_code == 404, response.text
    finally:
        for notification_id in inserted_ids:
            test_db.execute(
                "DELETE FROM notifications WHERE id = %s",
                (uuid.UUID(notification_id),),
            )



def test_notification_event_queue_is_idempotent(
    test_database_url,
    test_company_data,
    test_db,
):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    from app.main import _queue_notifications

    source_entity_id = uuid.uuid4()
    source_event_key = f"test-idempotency:{uuid.uuid4()}"
    database_url = make_url(test_database_url).set(drivername="postgresql+psycopg")
    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            _queue_notifications(
                db,
                company_id=uuid.UUID(test_company_data["company_id"]),
                recipient_ids=[uuid.UUID(test_company_data["user_id"])],
                event_type="PURCHASE_ORDER_STATUS_CHANGED",
                title="Təkrar bildiriş testi",
                body="Eyni hadisə yalnız bir bildiriş yaratmalıdır.",
                source_entity_type="PURCHASE_ORDER",
                source_entity_id=source_entity_id,
                source_event_key=source_event_key,
            )
            _queue_notifications(
                db,
                company_id=uuid.UUID(test_company_data["company_id"]),
                recipient_ids=[uuid.UUID(test_company_data["user_id"])],
                event_type="PURCHASE_ORDER_STATUS_CHANGED",
                title="Təkrar bildiriş testi",
                body="Eyni hadisə yalnız bir bildiriş yaratmalıdır.",
                source_entity_type="PURCHASE_ORDER",
                source_entity_id=source_entity_id,
                source_event_key=source_event_key,
            )
            db.commit()

        row = test_db.execute(
            """
            SELECT count(*) FROM notifications
            WHERE company_id = %s AND recipient_user_id = %s
              AND source_event_key = %s
            """,
            (
                uuid.UUID(test_company_data["company_id"]),
                uuid.UUID(test_company_data["user_id"]),
                source_event_key,
            ),
        ).fetchone()
        assert row[0] == 1
    finally:
        test_db.execute(
            "DELETE FROM notifications WHERE source_event_key = %s",
            (source_event_key,),
        )
        engine.dispose()


def test_business_events_create_transactional_notifications(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    suffix = uuid.uuid4().hex[:10].upper()
    recipient_id = uuid.uuid4()
    recipient_email = f"notification-recipient-{suffix.lower()}@example.invalid"
    purchase_order_id = None
    approval_request_id = None
    company_id = uuid.UUID(test_company_data["company_id"])

    test_db.execute(
        """
        INSERT INTO users (id, email, password_hash, full_name, is_active)
        VALUES (%s, %s, %s, %s, TRUE)
        """,
        (
            recipient_id,
            recipient_email,
            "acceptance-test-only-hash",
            "Notification Acceptance Recipient",
        ),
    )
    test_db.execute(
        """
        INSERT INTO company_members (user_id, company_id, role)
        VALUES (%s, %s, 'PROCUREMENT')
        """,
        (recipient_id, company_id),
    )

    try:
        po_response = requests.post(
            f"{base_url}/api/v1/purchase-orders",
            headers=auth_headers,
            json={
                "supplier_id": test_company_data["supplier_id"],
                "order_number": f"NOTIF-{suffix}",
                "status": "DRAFT",
                "currency": "AZN",
                "items": [
                    {
                        "product_id": test_company_data["product_id"],
                        "quantity": "1",
                        "unit": "ədəd",
                        "unit_price": "10",
                        "vat_rate": "18",
                    }
                ],
            },
            timeout=15,
        )
        assert po_response.status_code == 201, po_response.text
        purchase_order = po_response.json()
        purchase_order_id = uuid.UUID(purchase_order["id"])

        status_response = requests.post(
            f"{base_url}/api/v1/purchase-orders/{purchase_order_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=15,
        )
        assert status_response.status_code == 200, status_response.text

        order_notification = test_db.execute(
            """
            SELECT event_type, source_event_key
            FROM notifications
            WHERE company_id = %s
              AND recipient_user_id = %s
              AND source_entity_id = %s
            """,
            (company_id, recipient_id, purchase_order_id),
        ).fetchall()
        assert len(order_notification) == 1
        assert order_notification[0][0] == "PURCHASE_ORDER_STATUS_CHANGED"
        assert order_notification[0][1] == (
            f"purchase-order-status:{purchase_order_id}:DRAFT:SUBMITTED"
        )

        actor_notification_count = test_db.execute(
            """
            SELECT count(*) FROM notifications
            WHERE company_id = %s
              AND recipient_user_id = %s
              AND source_entity_id = %s
              AND event_type = 'PURCHASE_ORDER_STATUS_CHANGED'
            """,
            (company_id, uuid.UUID(test_company_data["user_id"]), purchase_order_id),
        ).fetchone()[0]
        assert actor_notification_count == 0

        approval_response = requests.post(
            f"{base_url}/api/v1/approvals/requests",
            headers=auth_headers,
            json={
                "entity_type": "PURCHASE_ORDER",
                "entity_id": str(purchase_order_id),
                "execution_mode": "SEQUENTIAL",
                "decision_mode": "ALL",
                "priority": "NORMAL",
                "steps": [
                    {
                        "step_order": 1,
                        "approver_user_id": str(recipient_id),
                    }
                ],
            },
            timeout=15,
        )
        assert approval_response.status_code == 201, approval_response.text
        approval_request_id = uuid.UUID(approval_response.json()["id"])

        approval_notification_count = test_db.execute(
            """
            SELECT count(*) FROM notifications
            WHERE company_id = %s
              AND recipient_user_id = %s
              AND source_entity_id = %s
              AND event_type = 'APPROVAL_ACTION_REQUIRED'
            """,
            (company_id, recipient_id, approval_request_id),
        ).fetchone()[0]
        assert approval_notification_count == 1

        # Audit and notification records are committed with their source event.
        audit_count = test_db.execute(
            """
            SELECT count(*) FROM audit_log
            WHERE company_id = %s
              AND action = 'PURCHASE_ORDER_STATUS_CHANGED'
              AND entity_id = %s
            """,
            (company_id, purchase_order_id),
        ).fetchone()[0]
        assert audit_count == 1
    finally:
        if approval_request_id:
            test_db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (approval_request_id,),
            )
            test_db.execute(
                "DELETE FROM notifications WHERE company_id = %s AND source_entity_id = %s",
                (company_id, approval_request_id),
            )
            test_db.execute(
                "DELETE FROM approval_requests WHERE id = %s",
                (approval_request_id,),
            )
        if purchase_order_id:
            test_db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (purchase_order_id,),
            )
            test_db.execute(
                "DELETE FROM notifications WHERE company_id = %s AND source_entity_id = %s",
                (company_id, purchase_order_id),
            )
            test_db.execute(
                "DELETE FROM purchase_orders WHERE id = %s",
                (purchase_order_id,),
            )
        test_db.execute(
            "DELETE FROM company_members WHERE user_id = %s AND company_id = %s",
            (recipient_id, company_id),
        )
        test_db.execute("DELETE FROM users WHERE id = %s", (recipient_id,))

def test_purchase_request_status_change_notifies_request_owner(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    recipient_id = uuid.uuid4()
    recipient_email = f"notification-recipient-{uuid.uuid4().hex}@example.test"
    purchase_request_id = None

    test_db.execute(
        """
        INSERT INTO users (id, email, password_hash, full_name, is_active)
        VALUES (%s, %s, %s, %s, TRUE)
        """,
        (
            recipient_id,
            recipient_email,
            "acceptance-test-no-login",
            "Notification Test Recipient",
        ),
    )
    test_db.execute(
        """
        INSERT INTO company_members (user_id, company_id, role)
        VALUES (%s, %s, 'ADMIN')
        """,
        (
            recipient_id,
            uuid.UUID(test_company_data["company_id"]),
        ),
    )

    try:
        created = requests.post(
            f"{base_url}/api/v1/procurement/purchase-requests",
            headers=auth_headers,
            json={
                "request_number": f"NOTIF-{uuid.uuid4().hex[:12].upper()}",
                "status": "DRAFT",
                "items": [
                    {
                        "product_id": test_company_data["product_id"],
                        "quantity": "1",
                        "unit": "ədəd",
                    }
                ],
            },
            timeout=20,
        )
        assert created.status_code in (200, 201), created.text
        purchase_request_id = created.json()["id"]

        # In production this requester is the initiator assigned by the
        # workflow. Reassigning only this newly-created test row lets the
        # acceptance test verify delivery to a different active member.
        test_db.execute(
            "UPDATE purchase_requests SET requested_by = %s WHERE id = %s",
            (recipient_id, uuid.UUID(purchase_request_id)),
        )

        changed = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/{purchase_request_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=20,
        )
        assert changed.status_code == 200, changed.text

        rows = test_db.execute(
            """
            SELECT id, event_type, title, body, source_event_key
            FROM notifications
            WHERE company_id = %s
              AND recipient_user_id = %s
              AND source_entity_type = 'PURCHASE_REQUEST'
              AND source_entity_id = %s
            """,
            (
                uuid.UUID(test_company_data["company_id"]),
                recipient_id,
                uuid.UUID(purchase_request_id),
            ),
        ).fetchall()
        assert len(rows) == 1, rows
        assert rows[0][1] == "PURCHASE_REQUEST_STATUS_CHANGED"
        assert "SUBMITTED" in rows[0][3]
        assert rows[0][4] == (
            f"purchase-request-status:{purchase_request_id}:DRAFT:SUBMITTED"
        )
    finally:
        if purchase_request_id:
            request_uuid = uuid.UUID(purchase_request_id)
            test_db.execute(
                "DELETE FROM notifications WHERE source_entity_id = %s",
                (request_uuid,),
            )
            test_db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (request_uuid,),
            )
            test_db.execute(
                "DELETE FROM purchase_requests WHERE id = %s",
                (request_uuid,),
            )
        test_db.execute(
            "DELETE FROM company_members WHERE user_id = %s",
            (recipient_id,),
        )
        test_db.execute(
            "DELETE FROM users WHERE id = %s",
            (recipient_id,),
        )

