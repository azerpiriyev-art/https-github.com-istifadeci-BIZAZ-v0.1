from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg
import requests


def test_offer_selection_allows_only_one_concurrent_selection(
    base_url,
    auth_headers,
    comparison_fixture,
    test_database_url,
):
    fixture = comparison_fixture
    request_id = fixture["request_id"]
    offer_ids = [
        fixture["offer_1_id"],
        fixture["offer_2_id"],
    ]

    db = psycopg.connect(test_database_url)
    db.autocommit = True

    try:
        db.execute(
            """
            DELETE FROM offer_selections
            WHERE purchase_request_id = %s
            """,
            (request_id,),
        )

        barrier = Barrier(2)

        def select_offer(offer_id):
            barrier.wait()
            return requests.post(
                f"{base_url}/api/v1/procurement/offer-selections",
                headers=auth_headers,
                json={
                    "purchase_request_id": request_id,
                    "supplier_offer_id": offer_id,
                    "justification": "Concurrent selection race regression test",
                },
                timeout=10,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(select_offer, offer_id)
                for offer_id in offer_ids
            ]
            responses = [future.result() for future in futures]

        statuses = sorted(response.status_code for response in responses)

        assert statuses == [200, 409], [
            (response.status_code, response.text)
            for response in responses
        ]

        selected_count = db.execute(
            """
            SELECT COUNT(*)
            FROM offer_selections
            WHERE purchase_request_id = %s
              AND status = 'SELECTED'
            """,
            (request_id,),
        ).fetchone()[0]

        assert selected_count == 1

    finally:
        db.execute(
            """
            DELETE FROM offer_selections
            WHERE purchase_request_id = %s
            """,
            (request_id,),
        )
        db.close()
