import requests
import uuid


def _offer_payload(fixture, test_company_data, offer_number, quantity, unit_price, vat_rate):
    return {
        "purchase_request_id": fixture["request_id"],
        "supplier_id": test_company_data["supplier_id"],
        "offer_number": offer_number,
        "status": "SUBMITTED",
        "items": [
            {
                "purchase_request_item_id": fixture["request_item_id"],
                "product_id": test_company_data["product_id"],
                "quantity": quantity,
                "unit": "ədəd",
                "unit_price": unit_price,
                "vat_rate": vat_rate,
                "delivery_days": 10,
            }
        ],
    }


def test_supplier_offer_quantity_more_than_4_decimals_rejected(
    base_url, auth_headers, comparison_fixture, test_company_data
):
    payload = _offer_payload(
        comparison_fixture,
        test_company_data,
        f"SO-Q-PRECISION-{uuid.uuid4().hex[:10].upper()}",
        "25.12345",
        "95.0000",
        "18.00",
    )

    response = requests.post(
        f"{base_url}/api/v1/procurement/supplier-offers",
        headers=auth_headers,
        json=payload,
        timeout=10,
    )

    assert response.status_code == 422, response.text


def test_supplier_offer_unit_price_more_than_4_decimals_rejected(
    base_url, auth_headers, comparison_fixture, test_company_data
):
    payload = _offer_payload(
        comparison_fixture,
        test_company_data,
        f"SO-P-PRECISION-{uuid.uuid4().hex[:10].upper()}",
        "25.0000",
        "95.12345",
        "18.00",
    )

    response = requests.post(
        f"{base_url}/api/v1/procurement/supplier-offers",
        headers=auth_headers,
        json=payload,
        timeout=10,
    )

    assert response.status_code == 422, response.text


def test_supplier_offer_vat_rate_more_than_2_decimals_rejected(
    base_url, auth_headers, comparison_fixture, test_company_data
):
    payload = _offer_payload(
        comparison_fixture,
        test_company_data,
        f"SO-VAT-PRECISION-{uuid.uuid4().hex[:10].upper()}",
        "25.0000",
        "95.0000",
        "18.001",
    )

    response = requests.post(
        f"{base_url}/api/v1/procurement/supplier-offers",
        headers=auth_headers,
        json=payload,
        timeout=10,
    )

    assert response.status_code == 422, response.text
