import requests


def test_01_comparison_returns_submitted_offers(
    base_url,
    auth_headers,
    comparison_fixture,
):
    response = requests.get(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{comparison_fixture['request_id']}/comparison",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["purchase_request_id"] == comparison_fixture["request_id"]
    assert data["request_number"] == comparison_fixture["request_number"]
    assert len(data["items"]) == 1

    offers = data["items"][0]["offers"]

    assert len(offers) == 2
    assert {offer["offer_number"] for offer in offers} == {
        comparison_fixture["offer_1_number"],
        comparison_fixture["offer_2_number"],
    }


def test_02_ranking_by_line_total(
    base_url,
    auth_headers,
    comparison_fixture,
):
    response = requests.get(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{comparison_fixture['request_id']}/comparison",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    offers = response.json()["items"][0]["offers"]

    assert offers[0]["rank"] == 1
    assert offers[0]["offer_number"] == comparison_fixture["offer_1_number"]
    assert float(offers[0]["line_total"]) == 11210.00

    assert offers[1]["rank"] == 2
    assert offers[1]["offer_number"] == comparison_fixture["offer_2_number"]
    assert float(offers[1]["line_total"]) == 11446.00


def test_03_vat_calculation(
    base_url,
    auth_headers,
    comparison_fixture,
):
    response = requests.get(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{comparison_fixture['request_id']}/comparison",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    offers = response.json()["items"][0]["offers"]

    first = next(
        offer
        for offer in offers
        if offer["offer_number"] == comparison_fixture["offer_1_number"]
    )

    second = next(
        offer
        for offer in offers
        if offer["offer_number"] == comparison_fixture["offer_2_number"]
    )

    assert float(first["vat_amount"]) == 1710.00
    assert float(first["line_total"]) == 11210.00

    assert float(second["vat_amount"]) == 1746.00
    assert float(second["line_total"]) == 11446.00


def test_04_unauthenticated_blocked(
    base_url,
    comparison_fixture,
):
    response = requests.get(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{comparison_fixture['request_id']}/comparison",
        timeout=10,
    )

    assert response.status_code == 403


def test_05_cancelled_request_blocked(
    base_url,
    auth_headers,
    cancelled_request_fixture,
):
    response = requests.get(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        f"{cancelled_request_fixture['request_id']}/comparison",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 422


def test_06_nonexistent_request_returns_404(
    base_url,
    auth_headers,
):
    response = requests.get(
        f"{base_url}/api/v1/procurement/purchase-requests/"
        "00000000-0000-0000-0000-000000000000/comparison",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 404
