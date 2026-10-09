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
    supplier_id = uuid.UUID(test_company_data["supplier_id"])
    product_id = uuid.UUID(test_company_data["product_id"])
    received_by = test_company_data["user_id"]
    suffix = uuid.uuid4().hex[:12].upper()
    po_id = None
    po_item_id = None
    delivery_ids = []

    try:
        po_row = test_db.execute(
            """
            INSERT INTO purchase_orders (
                company_id,
                supplier_id,
                order_number,
                order_date,
                status,
                currency,
                subtotal,
                vat_amount,
                total_amount,
                notes
            )
            VALUES (
                %s, %s, %s, CURRENT_DATE, 'APPROVED', 'AZN',
                100.0000, 18.0000, 118.0000, %s
            )
            RETURNING id
            """,
            (
                company_id,
                supplier_id,
                f"PO-R85E-{suffix}",
                "R8.5-E isolated delivery regression fixture",
            ),
        ).fetchone()
        assert po_row is not None
        po_id = po_row[0]

        item_row = test_db.execute(
            """
            INSERT INTO purchase_order_items (
                purchase_order_id,
                product_id,
                quantity,
                unit,
                unit_price,
                vat_rate,
                vat_amount,
                line_total
            )
            VALUES (
                %s, %s, 1.0000, 'PCS', 100.0000, 18.00, 18.0000, 118.0000
            )
            RETURNING id
            """,
            (po_id, product_id),
        ).fetchone()
        assert item_row is not None
        po_item_id = item_row[0]

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

        if po_id is not None:
            test_db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (po_id,),
            )
            test_db.execute(
                "DELETE FROM purchase_order_items WHERE purchase_order_id = %s",
                (po_id,),
            )
            test_db.execute(
                "DELETE FROM purchase_orders WHERE id = %s",
                (po_id,),
            )
