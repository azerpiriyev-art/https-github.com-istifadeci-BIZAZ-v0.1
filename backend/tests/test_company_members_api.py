"""Tenant-scoped read API tests for company members used by the delivery receiver picker."""

import requests


def test_company_members_returns_only_active_members_of_callers_company(
    base_url,
    auth_headers,
    test_db,
):
    me_response = requests.get(
        f"{base_url}/api/v1/me",
        headers=auth_headers,
        timeout=10,
    )
    assert me_response.status_code == 200, me_response.text
    me_data = me_response.json()
    company = me_data.get("company")
    assert company and company.get("id"), me_response.text
    company_id = company["id"]

    expected_rows = test_db.execute(
        """
        SELECT u.id, u.full_name, cm.role
        FROM company_members cm
        JOIN users u ON u.id = cm.user_id
        WHERE cm.company_id = %s
          AND u.is_active = TRUE
        ORDER BY u.full_name ASC, u.email ASC
        """,
        (company_id,),
    ).fetchall()
    expected = [
        {"id": str(row[0]), "full_name": row[1], "role": row[2]}
        for row in expected_rows
    ]

    response = requests.get(
        f"{base_url}/api/v1/company/members",
        headers=auth_headers,
        timeout=10,
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["total"] == len(expected)
    assert payload["items"] == expected
    assert all(set(item) == {"id", "full_name", "role"} for item in payload["items"])
