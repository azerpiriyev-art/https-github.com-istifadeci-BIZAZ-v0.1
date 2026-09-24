import uuid

import psycopg
import requests


def _create_approved_need(base_url, auth_headers, test_company_data):
    suffix = uuid.uuid4().hex[:10].upper()

    response = requests.post(
        f"{base_url}/api/v1/needs",
        headers=auth_headers,
        json={
            "need_number": f"NEED-M33-{suffix}",
            "source": "MANUAL",
            "title": "M3.3 automated conversion test",
            "priority": "NORMAL",
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": 10,
                    "unit": "ədəd",
                }
            ],
        },
        timeout=10,
    )

    assert response.status_code == 201, response.text

    data = response.json()
    need_id = data["id"]
    need_item_id = data["items"][0]["id"]

    for status in ("SUBMITTED", "UNDER_REVIEW", "APPROVED"):
        response = requests.post(
            f"{base_url}/api/v1/needs/{need_id}/status",
            headers=auth_headers,
            json={"status": status},
            timeout=10,
        )
        assert response.status_code == 200, response.text
        assert response.json()["new_status"] == status

    return need_id, need_item_id, data["need_number"]


def _cleanup(db, need_id, purchase_request_ids):
    need_uuid = uuid.UUID(need_id)

    db.execute(
        """
        DELETE FROM audit_log
        WHERE entity_id = %s
        """,
        (need_uuid,),
    )

    for request_id in purchase_request_ids:
        request_uuid = uuid.UUID(request_id)

        db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (request_uuid,),
        )
        db.execute(
            "DELETE FROM need_pr_conversions WHERE purchase_request_id = %s",
            (request_uuid,),
        )
        db.execute(
            "DELETE FROM purchase_request_items WHERE purchase_request_id = %s",
            (request_uuid,),
        )
        db.execute(
            "DELETE FROM purchase_requests WHERE id = %s",
            (request_uuid,),
        )

    db.execute(
        "DELETE FROM need_items WHERE need_id = %s",
        (need_uuid,),
    )
    db.execute(
        "DELETE FROM needs WHERE id = %s",
        (need_uuid,),
    )


def test_partial_then_full_conversion(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    need_id = None
    purchase_request_ids = []

    try:
        need_id, need_item_id, need_number = _create_approved_need(
            base_url,
            auth_headers,
            test_company_data,
        )

        first_number = f"PR-M33-{uuid.uuid4().hex[:10].upper()}"
        response = requests.post(
            f"{base_url}/api/v1/procurement/needs/{need_id}/convert",
            headers=auth_headers,
            json={
                "request_number": first_number,
                "items": [
                    {
                        "need_item_id": need_item_id,
                        "quantity": 6,
                    }
                ],
            },
            timeout=10,
        )

        assert response.status_code == 200, response.text
        first = response.json()

        assert first["need_status"] == "PARTIALLY_CONVERTED"
        assert first["purchase_request_status"] == "DRAFT"
        assert first["conversions"][0]["quantity"] == "6"

        purchase_request_ids.append(first["purchase_request_id"])

        second_number = f"PR-M33-{uuid.uuid4().hex[:10].upper()}"
        response = requests.post(
            f"{base_url}/api/v1/procurement/needs/{need_id}/convert",
            headers=auth_headers,
            json={
                "request_number": second_number,
                "items": [
                    {
                        "need_item_id": need_item_id,
                        "quantity": 4,
                    }
                ],
            },
            timeout=10,
        )

        assert response.status_code == 200, response.text
        second = response.json()

        assert second["need_status"] == "FULLY_CONVERTED"
        assert second["purchase_request_status"] == "DRAFT"
        assert second["conversions"][0]["quantity"] == "4"

        purchase_request_ids.append(second["purchase_request_id"])

        row = db.execute(
            """
            SELECT n.status, COALESCE(SUM(c.quantity), 0)
            FROM needs n
            LEFT JOIN need_pr_conversions c
              ON c.need_id = n.id
            WHERE n.id = %s
            GROUP BY n.status
            """,
            (uuid.UUID(need_id),),
        ).fetchone()

        assert row is not None
        assert row[0] == "FULLY_CONVERTED"
        assert row[1] == 10

    finally:
        if need_id:
            _cleanup(db, need_id, purchase_request_ids)
        db.close()


def test_over_conversion_rejected(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    need_id = None
    purchase_request_ids = []

    try:
        need_id, need_item_id, _ = _create_approved_need(
            base_url,
            auth_headers,
            test_company_data,
        )

        first_number = f"PR-M33-{uuid.uuid4().hex[:10].upper()}"

        response = requests.post(
            f"{base_url}/api/v1/procurement/needs/{need_id}/convert",
            headers=auth_headers,
            json={
                "request_number": first_number,
                "items": [
                    {
                        "need_item_id": need_item_id,
                        "quantity": 6,
                    }
                ],
            },
            timeout=10,
        )

        assert response.status_code == 200, response.text
        purchase_request_ids.append(response.json()["purchase_request_id"])

        rejected_number = f"PR-M33-{uuid.uuid4().hex[:10].upper()}"

        response = requests.post(
            f"{base_url}/api/v1/procurement/needs/{need_id}/convert",
            headers=auth_headers,
            json={
                "request_number": rejected_number,
                "items": [
                    {
                        "need_item_id": need_item_id,
                        "quantity": 5,
                    }
                ],
            },
            timeout=10,
        )

        assert response.status_code == 400, response.text

        row = db.execute(
            """
            SELECT COUNT(*)
            FROM purchase_requests
            WHERE request_number = %s
            """,
            (rejected_number,),
        ).fetchone()

        assert row[0] == 0

    finally:
        if need_id:
            _cleanup(db, need_id, purchase_request_ids)
        db.close()


def test_duplicate_need_item_rejected(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    need_id = None

    try:
        need_id, need_item_id, _ = _create_approved_need(
            base_url,
            auth_headers,
            test_company_data,
        )

        request_number = f"PR-M33-{uuid.uuid4().hex[:10].upper()}"

        response = requests.post(
            f"{base_url}/api/v1/procurement/needs/{need_id}/convert",
            headers=auth_headers,
            json={
                "request_number": request_number,
                "items": [
                    {
                        "need_item_id": need_item_id,
                        "quantity": 1,
                    },
                    {
                        "need_item_id": need_item_id,
                        "quantity": 1,
                    },
                ],
            },
            timeout=10,
        )

        assert response.status_code == 400, response.text

    finally:
        if need_id:
            _cleanup(db, need_id, [])
        db.close()


def test_unknown_need_item_rejected(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    need_id = None

    try:
        need_id, _, _ = _create_approved_need(
            base_url,
            auth_headers,
            test_company_data,
        )

        response = requests.post(
            f"{base_url}/api/v1/procurement/needs/{need_id}/convert",
            headers=auth_headers,
            json={
                "request_number": f"PR-M33-{uuid.uuid4().hex[:10].upper()}",
                "items": [
                    {
                        "need_item_id": str(uuid.uuid4()),
                        "quantity": 1,
                    }
                ],
            },
            timeout=10,
        )

        assert response.status_code == 404, response.text

    finally:
        if need_id:
            _cleanup(db, need_id, [])
        db.close()


def test_conversion_audit_created(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    need_id = None
    purchase_request_ids = []

    try:
        need_id, need_item_id, need_number = _create_approved_need(
            base_url,
            auth_headers,
            test_company_data,
        )

        request_number = f"PR-M33-{uuid.uuid4().hex[:10].upper()}"

        response = requests.post(
            f"{base_url}/api/v1/procurement/needs/{need_id}/convert",
            headers=auth_headers,
            json={
                "request_number": request_number,
                "notes": "M3.3 audit test",
                "items": [
                    {
                        "need_item_id": need_item_id,
                        "quantity": 6,
                    }
                ],
            },
            timeout=10,
        )

        assert response.status_code == 200, response.text
        data = response.json()
        purchase_request_ids.append(data["purchase_request_id"])

        row = db.execute(
            """
            SELECT metadata
            FROM audit_log
            WHERE entity_type = 'NEED'
              AND entity_id = %s
              AND action = 'NEED_CONVERTED_TO_PR'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(need_id),),
        ).fetchone()

        assert row is not None

        metadata = row[0]
        assert metadata["need_number"] == need_number
        assert metadata["purchase_request_number"] == request_number
        assert metadata["old_status"] == "APPROVED"
        assert metadata["new_status"] == "PARTIALLY_CONVERTED"
        assert metadata["item_count"] == 1

    finally:
        if need_id:
            _cleanup(db, need_id, purchase_request_ids)
        db.close()