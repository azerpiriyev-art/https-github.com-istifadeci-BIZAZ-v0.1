from decimal import Decimal
import uuid

import psycopg
import requests


def test_selection_to_purchase_order_precision_consistency(
    base_url,
    auth_headers,
    purchase_request_po_lifecycle_fixture,
    test_database_url,
):
    fixture = purchase_request_po_lifecycle_fixture
    selection_id = fixture["selection_id"]
    offer_id = fixture["offer_id"]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    po_id = None

    try:
        db.execute(
            """
            UPDATE supplier_offer_items
            SET quantity = %s,
                unit_price = %s,
                vat_rate = %s
            WHERE supplier_offer_id = %s
            """,
            (
                Decimal("1.0000"),
                Decimal("500.1234"),
                Decimal("18.25"),
                uuid.UUID(offer_id),
            ),
        )

        response = requests.post(
            f"{base_url}/api/v1/procurement/offer-selections/"
            f"{selection_id}/purchase-order",
            headers=auth_headers,
            json={
                "order_number": f"PO-PRECISION-{uuid.uuid4().hex[:10].upper()}",
                "notes": "Selection to PO precision consistency test",
            },
            timeout=10,
        )

        assert response.status_code == 201, response.text
        response_data = response.json()
        po_id = response_data["purchase_order_id"]

        assert Decimal(response_data["subtotal"]) == Decimal("500.1234")
        assert Decimal(response_data["vat_amount"]) == Decimal("91.2725")
        assert Decimal(response_data["total_amount"]) == Decimal("591.3959")

        row = db.execute(
            """
            SELECT subtotal, vat_amount, total_amount
            FROM purchase_orders
            WHERE id = %s
            """,
            (uuid.UUID(po_id),),
        ).fetchone()

        item_row = db.execute(
            """
            SELECT quantity, unit_price, vat_rate, vat_amount, line_total
            FROM purchase_order_items
            WHERE purchase_order_id = %s
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (uuid.UUID(po_id),),
        ).fetchone()

        assert row is not None
        assert item_row is not None

        expected_subtotal = Decimal("500.1234")
        expected_vat = Decimal("91.2725")
        expected_total = Decimal("591.3959")

        assert row[0] == expected_subtotal
        assert row[1] == expected_vat
        assert row[2] == expected_total

        assert item_row[0] == Decimal("1.0000")
        assert item_row[1] == Decimal("500.1234")
        assert item_row[2] == Decimal("18.25")
        assert item_row[3] == expected_vat
        assert item_row[4] == expected_subtotal

        assert row[2] == row[0] + row[1]

        audit_row = db.execute(
            """
            SELECT metadata
            FROM audit_log
            WHERE action = 'PURCHASE_ORDER_CREATED'
              AND entity_type = 'purchase_order'
              AND entity_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(po_id),),
        ).fetchone()

        assert audit_row is not None

        metadata = audit_row[0]
        assert metadata["subtotal"] == "500.1234"
        assert metadata["vat_amount"] == "91.2725"
        assert metadata["total_amount"] == "591.3959"

    finally:
        if po_id is not None:
            db.execute(
                "DELETE FROM purchase_order_items WHERE purchase_order_id = %s",
                (uuid.UUID(po_id),),
            )
            db.execute(
                """
                UPDATE offer_selections
                SET purchase_order_id = NULL
                WHERE purchase_order_id = %s
                """,
                (uuid.UUID(po_id),),
            )
            db.execute(
                "DELETE FROM purchase_orders WHERE id = %s",
                (uuid.UUID(po_id),),
            )

        db.close()