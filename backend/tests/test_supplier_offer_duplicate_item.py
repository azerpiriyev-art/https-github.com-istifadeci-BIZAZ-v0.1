from uuid import uuid4

import psycopg
import requests


def test_supplier_offer_rejects_duplicate_request_item_entries(
    base_url,
    auth_headers,
    comparison_fixture,
    test_database_url,
):
    request_id = comparison_fixture["request_id"]
    request_item_id = comparison_fixture["request_item_id"]
    offer_number = f"SO-DUP-{uuid4().hex[:10].upper()}"

    with psycopg.connect(test_database_url) as db:
        supplier_id, product_id = db.execute(
            """
            SELECT so.supplier_id, pri.product_id
            FROM purchase_request_items pri
            JOIN supplier_offers so
              ON so.purchase_request_id = pri.purchase_request_id
            WHERE pri.id = %s
            ORDER BY so.created_at
            LIMIT 1
            """,
            (request_item_id,),
        ).fetchone()

    payload = {
        "purchase_request_id": request_id,
        "supplier_id": str(supplier_id),
        "offer_number": offer_number,
        "status": "SUBMITTED",
        "items": [
            {
                "purchase_request_item_id": request_item_id,
                "product_id": str(product_id),
                "quantity": 50,
                "unit": "ədəd",
                "unit_price": 95,
                "vat_rate": 18,
            },
            {
                "purchase_request_item_id": request_item_id,
                "product_id": str(product_id),
                "quantity": 50,
                "unit": "ədəd",
                "unit_price": 95,
                "vat_rate": 18,
            },
        ],
    }

    try:
        response = requests.post(
            f"{base_url}/api/v1/procurement/supplier-offers",
            headers=auth_headers,
            json=payload,
            timeout=10,
        )

        assert response.status_code == 422, response.text

    finally:
        with psycopg.connect(test_database_url) as db:
            db.autocommit = True

            offer_row = db.execute(
                """
                SELECT id
                FROM supplier_offers
                WHERE offer_number = %s
                """,
                (offer_number,),
            ).fetchone()

            if offer_row:
                db.execute(
                    """
                    DELETE FROM supplier_offer_items
                    WHERE supplier_offer_id = %s
                    """,
                    (offer_row[0],),
                )
                db.execute(
                    """
                    DELETE FROM supplier_offers
                    WHERE id = %s
                    """,
                    (offer_row[0],),
                )
