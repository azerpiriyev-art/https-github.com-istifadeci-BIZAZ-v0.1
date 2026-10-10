"""API-level tenant-isolation regression for Delivery and Payment endpoints.

The foreign tenant fixtures are created directly in the test database so the
API caller remains authenticated only in its own company. All fixtures are
removed in finally; this test must run against the isolated BIZAZ test database.
"""

import json
import uuid

import requests


def test_delivery_and_payment_api_reject_foreign_company_objects(
    base_url,
    auth_headers,
    test_db,
):
    suffix = uuid.uuid4().hex[:8].upper()

    company_b_id = uuid.uuid4()
    supplier_b_id = uuid.uuid4()
    product_b_id = uuid.uuid4()
    po_b_id = None
    po_item_b_id = None
    delivery_b_id = None
    delivery_item_b_id = None

    # Resolve the caller's tenant via the same public API contract.
    me_response = requests.get(
        f"{base_url}/api/v1/me", headers=auth_headers, timeout=10
    )
    assert me_response.status_code == 200, me_response.text
    own_company = me_response.json().get("company")
    assert own_company and own_company.get("id"), me_response.text
    own_company_id = uuid.UUID(own_company["id"])
    assert own_company_id != company_b_id

    try:
        # Create an isolated foreign company and its supplier/product.
        test_db.execute(
            """
            INSERT INTO companies (
                id, legal_name, tax_id, legal_form,
                vat_registered, vat_rate, currency
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                company_b_id,
                f"R10.8 F3 Foreign Company {suffix}",
                f"F3{suffix}",  # 10 characters, matching companies.tax_id limit.
                "MMC",
                True,
                18,
                "AZN",
            ),
        )

        test_db.execute(
            """
            INSERT INTO suppliers (id, company_id, name, tax_id, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            """,
            (
                supplier_b_id,
                company_b_id,
                f"R10.8 F3 Supplier {suffix}",
                f"S{suffix}",
            ),
        )

        test_db.execute(
            """
            INSERT INTO products (id, company_id, name, sku, unit, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            """,
            (
                product_b_id,
                company_b_id,
                f"R10.8 F3 Product {suffix}",
                f"R10-F3-{suffix}",
                "ədəd",
            ),
        )

        po_row = test_db.execute(
            """
            INSERT INTO purchase_orders (
                id, company_id, supplier_id, order_number,
                order_date, status, currency,
                subtotal, vat_amount, total_amount, notes
            ) VALUES (
                %s, %s, %s, %s, CURRENT_DATE, 'DRAFT', 'AZN',
                100.0000, 18.0000, 118.0000, %s
            ) RETURNING id
            """,
            (
                uuid.uuid4(),
                company_b_id,
                supplier_b_id,
                f"PO-R108F3-{suffix}",
                "R10.8-F3 foreign tenant isolation fixture",
            ),
        ).fetchone()
        assert po_row is not None
        po_b_id = po_row[0]

        item_row = test_db.execute(
            """
            INSERT INTO purchase_order_items (
                id, purchase_order_id, product_id,
                quantity, unit, unit_price,
                vat_rate, vat_amount, line_total
            ) VALUES (
                %s, %s, %s, 1.0000, 'ədəd', 100.0000,
                18.00, 18.0000, 118.0000
            ) RETURNING id
            """,
            (uuid.uuid4(), po_b_id, product_b_id),
        ).fetchone()
        assert item_row is not None
        po_item_b_id = item_row[0]

        # Reach APPROVED using the legal transition path, not a direct status bypass.
        test_db.execute(
            "UPDATE purchase_orders SET status = 'SUBMITTED' WHERE id = %s",
            (po_b_id,),
        )
        test_db.execute(
            "UPDATE purchase_orders SET status = 'APPROVED' WHERE id = %s",
            (po_b_id,),
        )

        delivery_row = test_db.execute(
            """
            INSERT INTO deliveries (
                company_id, purchase_order_id, supplier_id,
                delivery_number, status, notes
            ) VALUES (%s, %s, %s, %s, 'PLANNED', %s)
            RETURNING id
            """,
            (
                company_b_id,
                po_b_id,
                supplier_b_id,
                f"DEL-R108F3-{suffix}",
                "R10.8-F3 foreign tenant isolation fixture",
            ),
        ).fetchone()
        assert delivery_row is not None
        delivery_b_id = delivery_row[0]

        delivery_item_row = test_db.execute(
            """
            INSERT INTO delivery_items (
                delivery_id, purchase_order_id,
                purchase_order_item_id, quantity_delivered, notes
            ) VALUES (%s, %s, %s, 1.0000, %s)
            RETURNING id
            """,
            (
                delivery_b_id,
                po_b_id,
                po_item_b_id,
                "R10.8-F3 foreign tenant isolation fixture",
            ),
        ).fetchone()
        assert delivery_item_row is not None
        delivery_item_b_id = delivery_item_row[0]

        # 1. Foreign delivery must not appear in the caller's list.
        response = requests.get(
            f"{base_url}/api/v1/deliveries?page=1&limit=100",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 200, response.text
        assert str(delivery_b_id) not in json.dumps(response.json())

        # 2. Foreign delivery detail is concealed as not found.
        response = requests.get(
            f"{base_url}/api/v1/deliveries/{delivery_b_id}",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 404, response.text

        # 3. Foreign delivery item listing is concealed as not found.
        response = requests.get(
            f"{base_url}/api/v1/deliveries/{delivery_b_id}/items",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 404, response.text

        # 4. Adding an item to a foreign delivery is blocked before mutation.
        response = requests.post(
            f"{base_url}/api/v1/deliveries/{delivery_b_id}/items",
            headers=auth_headers,
            json={
                "purchase_order_item_id": str(po_item_b_id),
                "quantity_delivered": "0.1000",
            },
            timeout=10,
        )
        assert response.status_code == 404, response.text

        # 5. Status mutation of a foreign delivery is blocked.
        response = requests.post(
            f"{base_url}/api/v1/deliveries/{delivery_b_id}/status",
            headers=auth_headers,
            json={"status": "DISPATCHED"},
            timeout=10,
        )
        assert response.status_code == 404, response.text

        # 6. Creating a delivery against a foreign PO is blocked.
        response = requests.post(
            f"{base_url}/api/v1/deliveries",
            headers=auth_headers,
            json={
                "purchase_order_id": str(po_b_id),
                "delivery_number": f"DEL-R108F3-API-{suffix}",
                "notes": "Must be rejected: foreign company PO",
            },
            timeout=10,
        )
        assert response.status_code == 404, response.text

        # 7. Creating a payment against a foreign PO is blocked.
        response = requests.post(
            f"{base_url}/api/v1/payments",
            headers=auth_headers,
            json={
                "purchase_order_id": str(po_b_id),
                "amount": "1.0000",
                "currency": "AZN",
                "reference": f"R108F3-FOREIGN-PAY-{suffix}",
            },
            timeout=10,
        )
        assert response.status_code == 404, response.text

        # Verify denied API calls did not mutate the foreign objects.
        delivery_state = test_db.execute(
            "SELECT status FROM deliveries WHERE id = %s",
            (delivery_b_id,),
        ).fetchone()
        assert delivery_state is not None and delivery_state[0] == "PLANNED"

        item_count = test_db.execute(
            "SELECT COUNT(*) FROM delivery_items WHERE delivery_id = %s",
            (delivery_b_id,),
        ).fetchone()[0]
        assert item_count == 1

        payment_count = test_db.execute(
            """
            SELECT COUNT(*) FROM payments
            WHERE company_id = %s AND purchase_order_id = %s
              AND reference = %s
            """,
            (own_company_id, po_b_id, f"R108F3-FOREIGN-PAY-{suffix}"),
        ).fetchone()[0]
        assert payment_count == 0

    finally:
        # Clean up only this test's rows. Delete dependants before parents.
        if delivery_item_b_id is not None:
            test_db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (delivery_item_b_id,),
            )
            test_db.execute(
                "DELETE FROM delivery_items WHERE id = %s",
                (delivery_item_b_id,),
            )

        if delivery_b_id is not None:
            test_db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (delivery_b_id,),
            )
            test_db.execute(
                "DELETE FROM deliveries WHERE id = %s",
                (delivery_b_id,),
            )

        if po_b_id is not None:
            test_db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (po_b_id,),
            )
            test_db.execute(
                "DELETE FROM purchase_order_items WHERE purchase_order_id = %s",
                (po_b_id,),
            )
            test_db.execute(
                "DELETE FROM purchase_orders WHERE id = %s",
                (po_b_id,),
            )

        test_db.execute(
            "DELETE FROM suppliers WHERE id = %s",
            (supplier_b_id,),
        )
        test_db.execute(
            "DELETE FROM products WHERE id = %s",
            (product_b_id,),
        )
        test_db.execute(
            "DELETE FROM companies WHERE id = %s",
            (company_b_id,),
        )
