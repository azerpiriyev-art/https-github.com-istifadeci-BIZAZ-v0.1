import uuid
from datetime import datetime, timedelta, timezone

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
