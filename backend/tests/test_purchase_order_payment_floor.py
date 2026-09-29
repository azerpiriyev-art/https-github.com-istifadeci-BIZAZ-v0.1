import uuid
import requests


def create_po(base_url, headers, test_company_data):
    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=headers,
        json={
            "supplier_id": test_company_data["supplier_id"],
            "order_number": f"PO-PAYMENT-FLOOR-{uuid.uuid4().hex[:10].upper()}",
            "order_date": "2026-09-29T00:00:00",
            "currency": "AZN",
            "notes": "PAYMENT FLOOR REGRESSION TEST",
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": 1,
                    "unit": "ədəd",
                    "unit_price": 500,
                    "vat_rate": 18,
                }
            ],
        },
        timeout=10,
    )
    assert response.status_code == 201, response.text
    return response.json()


def update_total(base_url, headers, po_id, unit_price, test_company_data):
    return requests.put(
        f"{base_url}/api/v1/purchase-orders/{po_id}",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": 1,
                    "unit": "ədəd",
                    "unit_price": unit_price,
                    "vat_rate": 0,
                }
            ]
        },
        timeout=10,
    )


def create_payment(base_url, headers, po_id, amount, status=None):
    response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "amount": amount,
            "currency": "AZN",
            "reference": f"PO-FLOOR-{uuid.uuid4()}",
        },
        timeout=10,
    )
    assert response.status_code == 201, response.text

    payment = response.json()

    if status:
        response = requests.post(
            f"{base_url}/api/v1/payments/{payment['id']}/status",
            headers=headers,
            json={"status": status},
            timeout=10,
        )
        assert response.status_code == 200, response.text

    return payment


def test_pending_payment_exact_total_allowed(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    create_payment(base_url, headers, po["id"], 100)

    response = update_total(base_url, headers, po["id"], 100, test_company_data)

    assert response.status_code == 200, response.text
    assert float(response.json()["total_amount"]) == 100

def test_failed_payment_does_not_block_total_reduction(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    create_payment(base_url, headers, po["id"], 100, status="FAILED")

    response = update_total(base_url, headers, po["id"], 50, test_company_data)

    assert response.status_code == 200, response.text
    assert float(response.json()["total_amount"]) == 50

def test_cancelled_payment_does_not_block_total_reduction(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    create_payment(base_url, headers, po["id"], 100, status="CANCELLED")

    response = update_total(base_url, headers, po["id"], 50, test_company_data)

    assert response.status_code == 200, response.text
    assert float(response.json()["total_amount"]) == 50

def test_paid_payment_blocks_total_reduction(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    create_payment(base_url, headers, po["id"], 100, status="PAID")

    response = update_total(base_url, headers, po["id"], 99, test_company_data)

    assert response.status_code == 400, response.text
    assert "payment" in response.text.lower()

def test_empty_items_must_be_rejected(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "items": []
        },
        timeout=10,
    )

    assert response.status_code == 422, response.text

def test_update_item_null_quantity_must_be_rejected(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": None,
                    "unit": "ədəd",
                    "unit_price": 100,
                    "vat_rate": 18,
                }
            ]
        },
        timeout=10,
    )

    assert response.status_code == 422, response.text

def test_active_payment_blocks_currency_change(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    create_payment(base_url, headers, po["id"], 100)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "currency": "USD"
        },
        timeout=10,
    )

    assert response.status_code == 400, response.text
    assert "currency" in response.text.lower() or "payment" in response.text.lower()

def test_currency_change_allowed_without_active_payment(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "currency": "USD"
        },
        timeout=10,
    )

    assert response.status_code == 200, response.text
    assert response.json()["currency"] == "USD"

def test_active_payment_blocks_supplier_change(base_url, auth_headers, test_company_data, alternate_supplier_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    create_payment(base_url, headers, po["id"], 100)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "supplier_id": alternate_supplier_data["supplier_id"]
        },
        timeout=10,
    )

    assert response.status_code == 400, response.text
    assert "?d?ni?" in response.text.lower() or "payment" in response.text.lower()

def test_cross_company_product_update_is_blocked_and_rolls_back(base_url, auth_headers, test_company_data, cross_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": cross_company_data["product_id"],
                    "quantity": 1,
                    "unit": "ədəd",
                    "unit_price": 500,
                    "vat_rate": 18,
                }
            ]
        },
        timeout=10,
    )

    assert response.status_code == 400, response.text

    verify = requests.get(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        timeout=10,
    )

    assert verify.status_code == 200, verify.text
    data = verify.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == test_company_data["product_id"]

def test_inactive_product_update_is_blocked_and_rolls_back(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    deactivate = requests.put(
        f"{base_url}/api/v1/products/{test_company_data['product_id']}",
        headers=headers,
        json={"is_active": False},
        timeout=10,
    )

    assert deactivate.status_code in (200, 204), deactivate.text

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": 2,
                    "unit": "ədəd",
                    "unit_price": 500,
                    "vat_rate": 18,
                }
            ]
        },
        timeout=10,
    )

    assert response.status_code == 400, response.text

    verify = requests.get(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        timeout=10,
    )

    assert verify.status_code == 200, verify.text
    data = verify.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == test_company_data["product_id"]
    assert data["items"][0]["quantity"] == "1.0000"

    reactivate = requests.put(
        f"{base_url}/api/v1/products/{test_company_data['product_id']}",
        headers=headers,
        json={"is_active": True},
        timeout=10,
    )

    assert reactivate.status_code in (200, 204), reactivate.text

def test_zero_price_and_max_vat_boundary_update(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": 1,
                    "unit": "ədəd",
                    "unit_price": 0,
                    "vat_rate": 100,
                }
            ]
        },
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert data["items"][0]["unit_price"] == "0.0000"
    assert data["items"][0]["vat_rate"] == "100.00"
    assert data["items"][0]["line_total"] == "0.0000"
    assert data["items"][0]["vat_amount"] == "0.0000"
    assert data["subtotal"] == "0.0000"
    assert data["vat_amount"] == "0.0000"
    assert data["total_amount"] == "0.0000"

def test_multi_item_totals_and_vat_calculation(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": 2,
                    "unit": "ədəd",
                    "unit_price": 100,
                    "vat_rate": 18,
                },
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": 3,
                    "unit": "ədəd",
                    "unit_price": 200,
                    "vat_rate": 10,
                },
            ]
        },
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert len(data["items"]) == 2

    assert data["items"][0]["line_total"] == "200.0000"
    assert data["items"][0]["vat_amount"] == "36.0000"

    assert data["items"][1]["line_total"] == "600.0000"
    assert data["items"][1]["vat_amount"] == "60.0000"

    assert data["subtotal"] == "800.0000"
    assert data["vat_amount"] == "96.0000"
    assert data["total_amount"] == "896.0000"

def test_decimal_precision_and_rounding(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": 3.3333,
                    "unit": "ədəd",
                    "unit_price": 12.3456,
                    "vat_rate": 18.25,
                }
            ]
        },
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["items"][0]["quantity"] == "3.3333"
    assert data["items"][0]["unit_price"] == "12.3456"
    assert data["items"][0]["line_total"] == "41.1516"
    assert data["items"][0]["vat_amount"] == "7.5102"
    assert data["subtotal"] == "41.1516"
    assert data["vat_amount"] == "7.5102"
    assert data["total_amount"] == "48.6618"

def test_status_change_via_update_endpoint_is_blocked(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        json={"status": "SUBMITTED"},
        timeout=10,
    )

    assert response.status_code == 400, response.text
    assert "status" in response.text.lower()

    verify = requests.get(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        timeout=10,
    )

    assert verify.status_code == 200, verify.text
    assert verify.json()["status"] == "DRAFT"

def test_submitted_to_approved_without_approval_request_is_measured(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    submit = requests.post(
        f"{base_url}/api/v1/purchase-orders/{po['id']}/status",
        headers=headers,
        json={"status": "SUBMITTED"},
        timeout=10,
    )

    assert submit.status_code == 200, submit.text

    approve = requests.post(
        f"{base_url}/api/v1/purchase-orders/{po['id']}/status",
        headers=headers,
        json={"status": "APPROVED"},
        timeout=10,
    )

    print("APPROVAL_ABSENT_RESULT=", approve.status_code, approve.text)

    assert approve.status_code in (200, 409), approve.text


def test_draft_purchase_order_with_payment_delete_is_measured(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    payment = requests.post(
        f"{base_url}/api/v1/payments",
        headers=headers,
        json={
            "purchase_order_id": po["id"],
            "amount": "100.00",
            "currency": "AZN",
            "reference": f"PAYMENT-DELETE-DIAG-{uuid.uuid4().hex[:10]}",
        },
        timeout=10,
    )

    print("PAYMENT_CREATE_RESULT=", payment.status_code, payment.text)
    assert payment.status_code == 201, payment.text

    delete = requests.delete(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        timeout=10,
    )

    print("PO_DELETE_RESULT=", delete.status_code, delete.text)

    assert delete.status_code in (200, 400, 409, 500), delete.text


def test_failed_item_update_rolls_back_existing_items_and_total(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    before_response = requests.get(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        timeout=10,
    )
    assert before_response.status_code == 200, before_response.text
    before = before_response.json()

    create_payment(base_url, headers, po["id"], 590)

    response = update_total(base_url, headers, po["id"], 100, test_company_data)

    assert response.status_code == 400, response.text
    assert "payment" in response.text.lower()

    after_response = requests.get(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=headers,
        timeout=10,
    )
    assert after_response.status_code == 200, after_response.text
    after = after_response.json()

    assert float(after["total_amount"]) == float(before["total_amount"])
    assert after["items"] == before["items"]

def test_create_quantity_more_than_4_decimals_rejected(base_url, auth_headers, test_company_data):
    headers = auth_headers
    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=headers,
        json={
            "supplier_id": test_company_data["supplier_id"],
            "order_number": f"PO-CREATE-Q-PRECISION-{uuid.uuid4().hex[:10].upper()}",
            "order_date": "2026-09-29T00:00:00",
            "currency": "AZN",
            "items": [{
                "product_id": test_company_data["product_id"],
                "quantity": "1.00001",
                "unit": "ədəd",
            }]
        },
        timeout=10,
    )
    assert response.status_code == 422, response.text


def test_create_unit_price_more_than_4_decimals_rejected(base_url, auth_headers, test_company_data):
    headers = auth_headers
    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=headers,
        json={
            "supplier_id": test_company_data["supplier_id"],
            "order_number": f"PO-CREATE-P-PRECISION-{uuid.uuid4().hex[:10].upper()}",
            "order_date": "2026-09-29T00:00:00",
            "currency": "AZN",
            "items": [{
                "product_id": test_company_data["product_id"],
                "quantity": 1,
                "unit": "ədəd",
                "unit_price": "500.00001",
                "vat_rate": 18
            }]
        },
        timeout=10,
    )
    assert response.status_code == 422, response.text


def test_create_vat_rate_more_than_2_decimals_rejected(base_url, auth_headers, test_company_data):
    headers = auth_headers
    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=headers,
        json={
            "supplier_id": test_company_data["supplier_id"],
            "order_number": f"PO-CREATE-VAT-PRECISION-{uuid.uuid4().hex[:10].upper()}",
            "order_date": "2026-09-29T00:00:00",
            "currency": "AZN",
            "items": [{
                "product_id": test_company_data["product_id"],
                "quantity": 1,
                "unit": "ədəd",
                "unit_price": 500,
                "vat_rate": "18.001"
            }]
        },
        timeout=10,
    )
    assert response.status_code == 422, response.text
