import uuid
import requests


def create_po(base_url, headers, test_company_data):
    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=headers,
        json={
            "supplier_id": test_company_data["supplier_id"],
            "order_number": f"PO-UPDATE-PRECISION-{uuid.uuid4().hex[:10].upper()}",
            "order_date": "2026-09-29T00:00:00",
            "currency": "AZN",
            "notes": "PO UPDATE PRECISION TEST",
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


def update_item(base_url, headers, po_id, quantity, unit_price, vat_rate, test_company_data):
    return requests.put(
        f"{base_url}/api/v1/purchase-orders/{po_id}",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": test_company_data["product_id"],
                    "quantity": quantity,
                    "unit": "ədəd",
                    "unit_price": unit_price,
                    "vat_rate": vat_rate,
                }
            ]
        },
        timeout=10,
    )


def test_update_quantity_more_than_4_decimals_rejected(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = update_item(base_url, headers,
        po["id"],
        "1.00001",
        "500.0000",
        "18.00",
        test_company_data,
    )

    assert response.status_code == 422, response.text


def test_update_unit_price_more_than_4_decimals_rejected(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = update_item(base_url, headers,
        po["id"],
        "1.0000",
        "500.00001",
        "18.00",
        test_company_data,
    )

    assert response.status_code == 422, response.text


def test_update_vat_rate_more_than_2_decimals_rejected(base_url, auth_headers, test_company_data):
    headers = auth_headers
    po = create_po(base_url, headers, test_company_data)

    response = update_item(base_url, headers,
        po["id"],
        "1.0000",
        "500.0000",
        "18.001",
        test_company_data,
    )

    assert response.status_code == 422, response.text