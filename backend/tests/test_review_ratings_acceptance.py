import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pwdlib import PasswordHash


def _create_approved_purchase_order(
    base_url,
    auth_headers,
    test_company_data,
):
    suffix = uuid.uuid4().hex[:12].upper()
    payload = {
        "supplier_id": test_company_data["supplier_id"],
        "order_number": f"REV-{suffix}",
        "status": "APPROVED",
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
    }
    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=auth_headers,
        json=payload,
        timeout=15,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _complete_delivery(
    base_url,
    auth_headers,
    test_company_data,
    purchase_order,
):
    suffix = uuid.uuid4().hex[:12].upper()
    response = requests.post(
        f"{base_url}/api/v1/deliveries",
        headers=auth_headers,
        json={
            "purchase_order_id": purchase_order["id"],
            "delivery_number": f"REV-DEL-{suffix}",
        },
        timeout=15,
    )
    assert response.status_code == 201, response.text
    delivery = response.json()

    for status in ("DISPATCHED", "IN_TRANSIT"):
        response = requests.post(
            f"{base_url}/api/v1/deliveries/{delivery['id']}/status",
            headers=auth_headers,
            json={"status": status},
            timeout=15,
        )
        assert response.status_code == 200, response.text

    order_item = purchase_order["items"][0]
    response = requests.post(
        f"{base_url}/api/v1/deliveries/{delivery['id']}/items",
        headers=auth_headers,
        json={
            "purchase_order_item_id": order_item["id"],
            "quantity_delivered": "1",
        },
        timeout=15,
    )
    assert response.status_code == 201, response.text

    response = requests.post(
        f"{base_url}/api/v1/deliveries/{delivery['id']}/status",
        headers=auth_headers,
        json={
            "status": "DELIVERED",
            "received_by": test_company_data["user_id"],
        },
        timeout=15,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_review_requires_a_delivered_purchase_order(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    purchase_order = _create_approved_purchase_order(
        base_url,
        auth_headers,
        test_company_data,
    )

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
        headers=auth_headers,
        json={"rating": 5, "comment": "Hələ çatdırılmayıb."},
        timeout=15,
    )
    assert response.status_code == 409, response.text

    count = test_db.execute(
        "SELECT count(*) FROM reviews WHERE purchase_order_id = %s",
        (uuid.UUID(purchase_order["id"]),),
    ).fetchone()[0]
    assert count == 0


def test_review_create_duplicate_read_list_edit_and_audit(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    purchase_order = _create_approved_purchase_order(
        base_url,
        auth_headers,
        test_company_data,
    )
    _complete_delivery(
        base_url,
        auth_headers,
        test_company_data,
        purchase_order,
    )

    create_response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
        headers=auth_headers,
        json={"rating": 5, "comment": "Çatdırılma tam və vaxtında oldu."},
        timeout=15,
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["rating"] == 5
    assert created["purchase_order_id"] == purchase_order["id"]
    assert created["supplier_id"] == test_company_data["supplier_id"]

    duplicate_response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
        headers=auth_headers,
        json={"rating": 4},
        timeout=15,
    )
    assert duplicate_response.status_code == 409, duplicate_response.text

    read_response = requests.get(
        f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
        headers=auth_headers,
        timeout=15,
    )
    assert read_response.status_code == 200, read_response.text
    assert read_response.json()["id"] == created["id"]

    list_response = requests.get(
        f"{base_url}/api/v1/suppliers/{test_company_data['supplier_id']}/reviews",
        headers=auth_headers,
        params={"page": 1, "limit": 20},
        timeout=15,
    )
    assert list_response.status_code == 200, list_response.text
    listing = list_response.json()
    assert listing["total"] >= 1
    assert listing["rating_count"] == listing["total"]
    assert listing["average_rating"] is not None
    assert any(item["id"] == created["id"] for item in listing["items"])

    summary_response = requests.post(
        f"{base_url}/api/v1/reviews/summary",
        headers=auth_headers,
        json={"purchase_order_ids": [purchase_order["id"]]},
        timeout=15,
    )
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()
    assert any(item["id"] == created["id"] for item in summary["items"])
    supplier_summary = next(
        (
            item for item in summary["supplier_stats"]
            if item["supplier_id"] == test_company_data["supplier_id"]
        ),
        None,
    )
    assert supplier_summary is not None, summary_response.text
    assert supplier_summary["rating_count"] >= 1
    assert supplier_summary["average_rating"] is not None

    update_response = requests.patch(
        f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
        headers=auth_headers,
        json={"rating": 4, "comment": "Ümumi qiymətləndirmə yeniləndi."},
        timeout=15,
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["rating"] == 4
    assert updated["comment"] == "Ümumi qiymətləndirmə yeniləndi."

    review_id = uuid.UUID(created["id"])
    audit_rows = test_db.execute(
        """
        SELECT action, metadata
        FROM audit_log
        WHERE entity_type = 'review' AND entity_id = %s
        ORDER BY id
        """,
        (review_id,),
    ).fetchall()
    assert [row[0] for row in audit_rows] == [
        "REVIEW_CREATED",
        "REVIEW_UPDATED",
    ]
    assert "comment" not in str(audit_rows[0][1]).lower()


@pytest.mark.parametrize("rating", [0, 6, -1])
def test_review_rejects_rating_outside_range(
    base_url,
    auth_headers,
    rating,
):
    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{uuid.uuid4()}/review",
        headers=auth_headers,
        json={"rating": rating},
        timeout=15,
    )
    assert response.status_code == 422, response.text


def test_review_rejects_comment_over_2000_characters(
    base_url,
    auth_headers,
):
    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{uuid.uuid4()}/review",
        headers=auth_headers,
        json={"rating": 5, "comment": "x" * 2001},
        timeout=15,
    )
    assert response.status_code == 422, response.text



def test_review_cannot_be_read_from_another_company(
    base_url,
    auth_headers,
    test_company_data,
    acceptance_owner_credentials,
):
    purchase_order = _create_approved_purchase_order(
        base_url,
        auth_headers,
        test_company_data,
    )
    _complete_delivery(
        base_url,
        auth_headers,
        test_company_data,
        purchase_order,
    )
    created = requests.post(
        f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
        headers=auth_headers,
        json={"rating": 4},
        timeout=15,
    )
    assert created.status_code == 201, created.text

    login = requests.post(
        f"{base_url}/api/v1/login",
        json=acceptance_owner_credentials,
        timeout=15,
    )
    assert login.status_code == 200, login.text
    other_company_headers = {
        "Authorization": f"Bearer {login.json()['token']}",
    }

    review_response = requests.get(
        f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
        headers=other_company_headers,
        timeout=15,
    )
    assert review_response.status_code == 404, review_response.text

    supplier_response = requests.get(
        f"{base_url}/api/v1/suppliers/{test_company_data['supplier_id']}/reviews",
        headers=other_company_headers,
        timeout=15,
    )
    assert supplier_response.status_code == 404, supplier_response.text

    summary_response = requests.post(
        f"{base_url}/api/v1/reviews/summary",
        headers=other_company_headers,
        json={"purchase_order_ids": [purchase_order["id"]]},
        timeout=15,
    )
    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json()["items"] == []
    assert summary_response.json()["supplier_stats"] == []


def test_viewer_role_cannot_create_review(
    base_url,
    acceptance_viewer_credentials,
):
    login = requests.post(
        f"{base_url}/api/v1/login",
        json=acceptance_viewer_credentials,
        timeout=15,
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{uuid.uuid4()}/review",
        headers=headers,
        json={"rating": 5},
        timeout=15,
    )
    assert response.status_code == 403, response.text



def test_review_concurrent_duplicate_submission_creates_one_row(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    purchase_order = _create_approved_purchase_order(
        base_url,
        auth_headers,
        test_company_data,
    )
    _complete_delivery(
        base_url,
        auth_headers,
        test_company_data,
        purchase_order,
    )

    def submit():
        response = requests.post(
            f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
            headers=auth_headers,
            json={"rating": 5, "comment": "Paralel sorğu testi"},
            timeout=20,
        )
        return response.status_code, response.text

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: submit(), range(4)))

    statuses = [status for status, _ in results]
    assert statuses.count(201) == 1, results
    assert statuses.count(409) == 3, results

    count = test_db.execute(
        "SELECT count(*) FROM reviews WHERE purchase_order_id = %s",
        (uuid.UUID(purchase_order["id"]),),
    ).fetchone()[0]
    assert count == 1


def test_only_review_author_can_edit_and_edit_window_expires(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    purchase_order = _create_approved_purchase_order(
        base_url,
        auth_headers,
        test_company_data,
    )
    _complete_delivery(
        base_url,
        auth_headers,
        test_company_data,
        purchase_order,
    )
    created = requests.post(
        f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
        headers=auth_headers,
        json={"rating": 5},
        timeout=15,
    )
    assert created.status_code == 201, created.text
    review_id = uuid.UUID(created.json()["id"])

    other_user_id = uuid.uuid4()
    other_email = f"review-non-author-{other_user_id.hex}@example.com"
    other_password = "Review-Author-Test-2026!"
    password_hash = PasswordHash.recommended().hash(other_password)
    test_db.execute(
        """
        INSERT INTO users (id, email, password_hash, full_name, is_active)
        VALUES (%s, %s, %s, %s, TRUE)
        """,
        (other_user_id, other_email, password_hash, "Rəy müəllifi olmayan üzv"),
    )
    test_db.execute(
        """
        INSERT INTO company_members (user_id, company_id, role)
        VALUES (%s, %s, 'PROCUREMENT')
        """,
        (other_user_id, uuid.UUID(test_company_data["company_id"])),
    )

    login = requests.post(
        f"{base_url}/api/v1/login",
        json={"email": other_email, "password": other_password},
        timeout=15,
    )
    assert login.status_code == 200, login.text
    other_headers = {"Authorization": f"Bearer {login.json()['token']}"}
    forbidden = requests.patch(
        f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
        headers=other_headers,
        json={"rating": 3},
        timeout=15,
    )
    assert forbidden.status_code == 403, forbidden.text

    test_db.execute(
        "UPDATE reviews SET created_at = now() - interval '25 hours' WHERE id = %s",
        (review_id,),
    )
    expired = requests.patch(
        f"{base_url}/api/v1/purchase-orders/{purchase_order['id']}/review",
        headers=auth_headers,
        json={"rating": 2},
        timeout=15,
    )
    assert expired.status_code == 409, expired.text

    row = test_db.execute(
        "SELECT rating FROM reviews WHERE id = %s",
        (review_id,),
    ).fetchone()
    assert row[0] == 5
