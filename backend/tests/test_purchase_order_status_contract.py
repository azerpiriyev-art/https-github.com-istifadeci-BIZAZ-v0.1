import uuid
from decimal import Decimal

import psycopg
import pytest


@pytest.fixture
def po_contract_db(test_database_url, test_company_data):
    conn = psycopg.connect(test_database_url)
    refs = {
        "company_id": uuid.UUID(str(test_company_data["company_id"])),
        "supplier_id": uuid.UUID(str(test_company_data["supplier_id"])),
        "product_id": uuid.UUID(str(test_company_data["product_id"])),
        "user_id": uuid.UUID(str(test_company_data["user_id"])),
    }

    try:
        yield conn, refs
    finally:
        conn.rollback()
        conn.close()


def _create_po(conn, refs, status="DRAFT"):
    row = conn.execute(
        """
        INSERT INTO purchase_orders (
            company_id, supplier_id, order_number, order_date,
            status, currency, subtotal, vat_amount, total_amount, notes
        )
        VALUES (
            %s, %s, %s, CURRENT_DATE,
            %s, 'AZN', 100.0000, 18.0000, 118.0000, %s
        )
        RETURNING id
        """,
        (
            refs["company_id"],
            refs["supplier_id"],
            f"R9-PO-{uuid.uuid4().hex.upper()}",
            status,
            "R9 automated PO status contract test",
        ),
    ).fetchone()

    return row[0]


def _expect_po_transition_rejected(conn, po_id, new_status):
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute(
                "UPDATE purchase_orders SET status = %s WHERE id = %s",
                (new_status, po_id),
            )


def _create_po_item(conn, refs, po_id, quantity=Decimal("1.0000")):
    row = conn.execute(
        """
        INSERT INTO purchase_order_items (
            purchase_order_id, product_id, quantity, unit,
            unit_price, vat_rate, vat_amount, line_total
        )
        VALUES (%s, %s, %s, 'PCS', 100.0000, 18.00, %s, %s)
        RETURNING id
        """,
        (
            po_id,
            refs["product_id"],
            quantity,
            quantity * Decimal("18.00"),
            quantity * Decimal("118.00"),
        ),
    ).fetchone()

    return row[0]


def _create_delivery(conn, refs, po_id):
    row = conn.execute(
        """
        INSERT INTO deliveries (
            company_id, purchase_order_id, supplier_id,
            delivery_number, notes
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            refs["company_id"],
            po_id,
            refs["supplier_id"],
            f"R9-DEL-{uuid.uuid4().hex.upper()}",
            "R9 automated receiving contract test",
        ),
    ).fetchone()

    return row[0]


def _add_delivery_item(conn, po_id, po_item_id, delivery_id, quantity):
    conn.execute(
        """
        INSERT INTO delivery_items (
            delivery_id, purchase_order_id,
            purchase_order_item_id, quantity_delivered
        )
        VALUES (%s, %s, %s, %s)
        """,
        (delivery_id, po_id, po_item_id, Decimal(quantity)),
    )


def _advance_delivery(conn, delivery_id, statuses, received_by):
    for status in statuses:
        if status == "DELIVERED":
            conn.execute(
                """
                UPDATE deliveries
                SET status = %s,
                    delivered_at = now(),
                    received_by = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (status, received_by, delivery_id),
            )
        else:
            conn.execute(
                """
                UPDATE deliveries
                SET status = %s, updated_at = now()
                WHERE id = %s
                """,
                (status, delivery_id),
            )


def test_allowed_po_status_transitions_and_legacy_receipt(po_contract_db):
    conn, refs = po_contract_db

    # DRAFT -> SUBMITTED -> APPROVED -> RECEIVED without deliveries.
    po_id = _create_po(conn, refs, "DRAFT")

    for status in ("SUBMITTED", "APPROVED", "RECEIVED"):
        conn.execute(
            "UPDATE purchase_orders SET status = %s WHERE id = %s",
            (status, po_id),
        )

    final_status = conn.execute(
        "SELECT status FROM purchase_orders WHERE id = %s",
        (po_id,),
    ).fetchone()[0]

    assert final_status == "RECEIVED"

    # DRAFT -> CANCELLED is allowed.
    draft_po = _create_po(conn, refs, "DRAFT")
    conn.execute(
        "UPDATE purchase_orders SET status = 'CANCELLED' WHERE id = %s",
        (draft_po,),
    )

    # SUBMITTED -> CANCELLED is allowed.
    submitted_po = _create_po(conn, refs, "SUBMITTED")
    conn.execute(
        "UPDATE purchase_orders SET status = 'CANCELLED' WHERE id = %s",
        (submitted_po,),
    )


def test_invalid_and_terminal_po_status_transitions_are_rejected(
    po_contract_db,
):
    conn, refs = po_contract_db

    invalid_transitions = [
        ("DRAFT", "DRAFT"),
        ("DRAFT", "APPROVED"),
        ("DRAFT", "RECEIVED"),
        ("SUBMITTED", "DRAFT"),
        ("APPROVED", "CANCELLED"),
        ("RECEIVED", "DRAFT"),
        ("CANCELLED", "SUBMITTED"),
    ]

    for old_status, new_status in invalid_transitions:
        po_id = _create_po(conn, refs, old_status)

        _expect_po_transition_rejected(conn, po_id, new_status)

        actual_status = conn.execute(
            "SELECT status FROM purchase_orders WHERE id = %s",
            (po_id,),
        ).fetchone()[0]

        assert actual_status == old_status


def test_receiving_rejected_when_delivery_is_active(po_contract_db):
    conn, refs = po_contract_db

    po_id = _create_po(conn, refs, "APPROVED")
    _create_po_item(conn, refs, po_id)

    delivery_id = _create_delivery(conn, refs, po_id)
    _advance_delivery(
        conn,
        delivery_id,
        ("DISPATCHED", "IN_TRANSIT"),
        refs["user_id"],
    )

    _expect_po_transition_rejected(conn, po_id, "RECEIVED")


def test_receiving_rejected_when_linked_delivery_has_no_po_items(
    po_contract_db,
):
    conn, refs = po_contract_db

    po_id = _create_po(conn, refs, "APPROVED")
    delivery_id = _create_delivery(conn, refs, po_id)

    _advance_delivery(
        conn,
        delivery_id,
        ("CANCELLED",),
        refs["user_id"],
    )

    _expect_po_transition_rejected(conn, po_id, "RECEIVED")


def test_receiving_rejected_when_recorded_quantity_is_incomplete(
    po_contract_db,
):
    conn, refs = po_contract_db

    po_id = _create_po(conn, refs, "APPROVED")
    po_item_id = _create_po_item(conn, refs, po_id, Decimal("1.0000"))

    delivery_id = _create_delivery(conn, refs, po_id)
    _add_delivery_item(
        conn, po_id, po_item_id, delivery_id, "0.5000"
    )

    _advance_delivery(
        conn,
        delivery_id,
        (
            "DISPATCHED",
            "IN_TRANSIT",
            "PARTIALLY_DELIVERED",
            "CANCELLED",
        ),
        refs["user_id"],
    )

    _expect_po_transition_rejected(conn, po_id, "RECEIVED")


def test_receiving_counts_cancelled_delivery_quantity(po_contract_db):
    conn, refs = po_contract_db

    po_id = _create_po(conn, refs, "APPROVED")
    po_item_id = _create_po_item(conn, refs, po_id, Decimal("1.0000"))

    # A cancelled delivery contributes 0.6000 to the total recorded quantity.
    cancelled_delivery = _create_delivery(conn, refs, po_id)
    _add_delivery_item(
        conn, po_id, po_item_id, cancelled_delivery, "0.6000"
    )

    _advance_delivery(
        conn,
        cancelled_delivery,
        (
            "DISPATCHED",
            "IN_TRANSIT",
            "PARTIALLY_DELIVERED",
            "CANCELLED",
        ),
        refs["user_id"],
    )

    # A second delivery records the remaining 0.4000.
    delivered = _create_delivery(conn, refs, po_id)
    _add_delivery_item(
        conn, po_id, po_item_id, delivered, "0.4000"
    )

    _advance_delivery(
        conn,
        delivered,
        ("DISPATCHED", "IN_TRANSIT", "DELIVERED"),
        refs["user_id"],
    )

    conn.execute(
        "UPDATE purchase_orders SET status = 'RECEIVED' WHERE id = %s",
        (po_id,),
    )

    result = conn.execute(
        "SELECT status FROM purchase_orders WHERE id = %s",
        (po_id,),
    ).fetchone()[0]

    assert result == "RECEIVED"
