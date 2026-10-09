import uuid

import requests


def _post_delivery_status(
    base_url,
    auth_headers,
    delivery_id,
    status,
    received_by=None,
):
    payload = {"status": status}
    if received_by is not None:
        payload["received_by"] = received_by

    return requests.post(
        f"{base_url}/api/v1/deliveries/{delivery_id}/status",
        headers=auth_headers,
        json=payload,
        timeout=10,
    )


def test_cancelled_delivery_quantity_and_status_contract(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    company_id = uuid.UUID(test_company_data["company_id"])
    received_by = test_company_data["user_id"]

    row = test_db.execute(
        """
        SELECT po.id, poi.id, poi.quantity
        FROM purchase_orders po
        JOIN purchase_order_items poi
          ON poi.purchase_order_id = po.id
        WHERE po.company_id = %s
          AND po.status = 'APPROVED'
          AND poi.quantity = 1.0000
          AND (
              SELECT count(*)
              FROM purchase_order_items all_items
              WHERE all_items.purchase_order_id = po.id
          ) = 1
          AND NOT EXISTS (
              SELECT 1
              FROM deliveries d
              WHERE d.purchase_order_id = po.id
          )
        ORDER BY po.created_at DESC
        LIMIT 1
        """,
        (company_id,),
    ).fetchone()

    assert row is not None, (
        "Test üçün Delivery-si olmayan, bir item-li APPROVED PO tapılmadı"
    )

    po_id, po_item_id, ordered_quantity = row
    assert ordered_quantity == 1

    suffix = uuid.uuid4().hex[:12].upper()
    delivery_ids = []

    try:
        # 1. First delivery: 0.6000 of the ordered 1.0000.
        response = requests.post(
            f"{base_url}/api/v1/deliveries",
            headers=auth_headers,
            json={
                "purchase_order_id": str(po_id),
                "delivery_number": f"DEL-R85E-{suffix}-A",
                "notes": "R8.5-E cancellation regression test",
            },
            timeout=10,
        )
        assert response.status_code == 201, response.text
        delivery_a = response.json()["id"]
        delivery_ids.append(delivery_a)

        response = requests.post(
            f"{base_url}/api/v1/deliveries/{delivery_a}/items",
            headers=auth_headers,
            json={
                "purchase_order_item_id": str(po_item_id),
                "quantity_delivered": "0.6000",
            },
            timeout=10,
        )
        assert response.status_code == 201, response.text

        for status in (
            "DISPATCHED",
            "IN_TRANSIT",
            "PARTIALLY_DELIVERED",
        ):
            response = _post_delivery_status(
                base_url, auth_headers, delivery_a, status
            )
            assert response.status_code == 200, response.text

        # Repeating PARTIALLY_DELIVERED must be rejected.
        response = _post_delivery_status(
            base_url,
            auth_headers,
            delivery_a,
            "PARTIALLY_DELIVERED",
        )
        assert response.status_code == 400, response.text

        # Cancellation must not erase the physical quantity already recorded.
        response = _post_delivery_status(
            base_url, auth_headers, delivery_a, "CANCELLED"
        )
        assert response.status_code == 200, response.text

        # 2. Second delivery: the remaining 0.4000.
        response = requests.post(
            f"{base_url}/api/v1/deliveries",
            headers=auth_headers,
            json={
                "purchase_order_id": str(po_id),
                "delivery_number": f"DEL-R85E-{suffix}-B",
                "notes": "R8.5-E remaining quantity regression test",
            },
            timeout=10,
        )
        assert response.status_code == 201, response.text
        delivery_b = response.json()["id"]
        delivery_ids.append(delivery_b)

        response = requests.post(
            f"{base_url}/api/v1/deliveries/{delivery_b}/items",
            headers=auth_headers,
            json={
                "purchase_order_item_id": str(po_item_id),
                "quantity_delivered": "0.4000",
            },
            timeout=10,
        )
        assert response.status_code == 201, response.text

        for status in ("DISPATCHED", "IN_TRANSIT"):
            response = _post_delivery_status(
                base_url, auth_headers, delivery_b, status
            )
            assert response.status_code == 200, response.text

        # 011 must count the cancelled delivery when checking completeness.
        response = _post_delivery_status(
            base_url,
            auth_headers,
            delivery_b,
            "DELIVERED",
            received_by=received_by,
        )
        assert response.status_code == 200, response.text

        # 3. Any extra quantity would exceed the PO quantity of 1.0000.
        response = requests.post(
            f"{base_url}/api/v1/deliveries",
            headers=auth_headers,
            json={
                "purchase_order_id": str(po_id),
                "delivery_number": f"DEL-R85E-{suffix}-C",
                "notes": "R8.5-E overdelivery regression test",
            },
            timeout=10,
        )
        assert response.status_code == 201, response.text
        delivery_c = response.json()["id"]
        delivery_ids.append(delivery_c)

        response = requests.post(
            f"{base_url}/api/v1/deliveries/{delivery_c}/items",
            headers=auth_headers,
            json={
                "purchase_order_item_id": str(po_item_id),
                "quantity_delivered": "0.0001",
            },
            timeout=10,
        )
        assert response.status_code == 409, response.text

    finally:
        # Remove only audit entries and records owned by this test.
        for delivery_id in delivery_ids:
            delivery_uuid = uuid.UUID(delivery_id)

            test_db.execute(
                """
                DELETE FROM audit_log
                WHERE entity_id IN (
                    SELECT id
                    FROM delivery_items
                    WHERE delivery_id = %s
                )
                """,
                (delivery_uuid,),
            )
            test_db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (delivery_uuid,),
            )
            test_db.execute(
                "DELETE FROM delivery_items WHERE delivery_id = %s",
                (delivery_uuid,),
            )
            test_db.execute(
                "DELETE FROM deliveries WHERE id = %s",
                (delivery_uuid,),
            )