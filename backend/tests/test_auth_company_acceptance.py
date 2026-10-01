import uuid

import psycopg
import pytest
import requests


def _cleanup_registered_company(test_db, email, company_id):
    company_uuid = uuid.UUID(company_id)

    test_db.execute(
        """
        DELETE FROM audit_log
        WHERE user_id IN (
            SELECT id FROM users WHERE email = %s
        )
           OR company_id = %s
        """,
        (email, company_uuid),
    )

    test_db.execute(
        """
        DELETE FROM company_members
        WHERE company_id = %s
        """,
        (company_uuid,),
    )

    test_db.execute(
        """
        DELETE FROM companies
        WHERE id = %s
        """,
        (company_uuid,),
    )

    test_db.execute(
        """
        DELETE FROM users
        WHERE email = %s
        """,
        (email,),
    )

    test_db.commit()

def test_auth_login_success(base_url, test_credentials):
    response = requests.post(
        f"{base_url}/api/v1/login",
        json=test_credentials,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "success"
    assert data["token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == test_credentials["email"]


def test_auth_login_invalid_password(base_url, test_credentials):
    payload = {
        **test_credentials,
        "password": test_credentials["password"] + "-WRONG",
    }

    response = requests.post(
        f"{base_url}/api/v1/login",
        json=payload,
        timeout=10,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "E-poçt və ya şifrə yanlışdır."


def test_auth_me_success(base_url, auth_headers, test_credentials, test_company_data):
    response = requests.get(
        f"{base_url}/api/v1/me",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "success"
    assert data["user"]["id"] == test_company_data["user_id"]
    assert data["user"]["email"] == test_credentials["email"]
    assert data["company"]["id"] == test_company_data["company_id"]
    assert data["company"]["role"]


def test_company_get_my_company_success(
    base_url,
    auth_headers,
    test_company_data,
):
    response = requests.get(
        f"{base_url}/api/v1/company/me",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    company = response.json()["company"]

    assert company["id"] == test_company_data["company_id"]
    assert "legal_name" in company
    assert "tax_id" in company
    assert "legal_form" in company
    assert "vat_registered" in company
    assert "vat_rate" in company
    assert company["currency"] == "AZN"
    assert company["role"]


def test_company_rbac_owner_success(
    base_url,
    acceptance_owner_headers,
    acceptance_owner_credentials,
):
    response = requests.get(
        f"{base_url}/api/v1/company/rbac-test-owner",
        headers=acceptance_owner_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "success"
    assert data["role_required"] == "OWNER"
    assert data["user"] == acceptance_owner_credentials["email"]


def test_company_rbac_viewer_forbidden(
    base_url,
    acceptance_viewer_headers,
):
    response = requests.get(
        f"{base_url}/api/v1/company/rbac-test-owner",
        headers=acceptance_viewer_headers,
        timeout=10,
    )

    assert response.status_code == 403


def test_company_update_success(
    base_url,
    acceptance_owner_headers,
    acceptance_owner_data,
    test_db,
):
    company_id = uuid.UUID(acceptance_owner_data["company_id"])

    row = test_db.execute(
        """
        SELECT legal_name
        FROM companies
        WHERE id = %s
        """,
        (company_id,),
    ).fetchone()

    assert row is not None

    old_name = row[0]
    new_name = f"{old_name} TEST"

    try:
        response = requests.put(
            f"{base_url}/api/v1/company/me",
            headers=acceptance_owner_headers,
            json={"legal_name": new_name},
            timeout=10,
        )

        assert response.status_code == 200, response.text

        data = response.json()

        assert data["status"] == "success"
        assert data["company"]["id"] == str(company_id)
        assert data["company"]["legal_name"] == new_name

        db_row = test_db.execute(
            """
            SELECT legal_name
            FROM companies
            WHERE id = %s
            """,
            (company_id,),
        ).fetchone()

        assert db_row is not None
        assert db_row[0] == new_name

    finally:
        restore = requests.put(
            f"{base_url}/api/v1/company/me",
            headers=acceptance_owner_headers,
            json={"legal_name": old_name},
            timeout=10,
        )

        assert restore.status_code == 200, restore.text


def test_company_update_duplicate_tax_id(
    base_url,
    acceptance_owner_headers,
    acceptance_owner_data,
    test_db,
):
    current_company_id = uuid.UUID(
        acceptance_owner_data["company_id"]
    )

    row = test_db.execute(
        """
        SELECT tax_id
        FROM companies
        WHERE tax_id IS NOT NULL
          AND id <> %s
        ORDER BY created_at
        LIMIT 1
        """,
        (current_company_id,),
    ).fetchone()

    if row is None:
        pytest.skip("No second company with non-null tax_id exists")

    response = requests.put(
        f"{base_url}/api/v1/company/me",
        headers=acceptance_owner_headers,
        json={"tax_id": row[0]},
        timeout=10,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Bu VÖEN artıq başqa şirkətə məxsusdur."
    )


def test_company_update_invalid_legal_form(
    base_url,
    acceptance_owner_headers,
):
    response = requests.put(
        f"{base_url}/api/v1/company/me",
        headers=acceptance_owner_headers,
        json={"legal_form": "INVALID_TEST_FORM"},
        timeout=10,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Etibarsız hüquqi forma."



def test_register_success(
    base_url,
    test_db,
):
    suffix = uuid.uuid4().hex[:10].upper()

    email = f"bizaz-auth-register-{suffix}@example.com"
    password = "BIZAZ-Register-2026!"
    company_name = f"BIZAZ TEST COMPANY {suffix}"
    full_name = f"BIZAZ Test User {suffix}"
    tax_id = str(uuid.uuid4().int)[:10]

    payload = {
        "company_name": company_name,
        "email": email,
        "password": password,
        "full_name": full_name,
        "legal_form": "MMC",
        "tax_id": tax_id,
    }

    response = requests.post(
        f"{base_url}/api/v1/register",
        json=payload,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()
    company_id = data["data"]["company_id"]

    try:
        assert data["status"] == "success"
        assert data["data"]["company_name"] == company_name
        assert data["data"]["email"] == email.lower()
        assert data["data"]["role"] == "OWNER"

        user_row = test_db.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
            """,
            (email.lower(),),
        ).fetchone()

        company_row = test_db.execute(
            """
            SELECT id, legal_name, tax_id
            FROM companies
            WHERE id = %s
            """,
            (uuid.UUID(company_id),),
        ).fetchone()

        member_row = test_db.execute(
            """
            SELECT role
            FROM company_members
            WHERE user_id = %s
              AND company_id = %s
            """,
            (
                uuid.UUID(data["data"]["user_id"]),
                uuid.UUID(company_id),
            ),
        ).fetchone()

        assert user_row is not None
        assert company_row is not None
        assert company_row[1] == company_name
        assert company_row[2] == tax_id
        assert member_row is not None
        assert member_row[0] == "OWNER"

    finally:
        _cleanup_registered_company(
            test_db,
            email.lower(),
            company_id,
        )

def test_register_duplicate_email(
    base_url,
    test_credentials,
):
    response = requests.post(
        f"{base_url}/api/v1/register",
        json={
            "company_name": "BIZAZ DUPLICATE EMAIL TEST",
            "email": test_credentials["email"],
            "password": "BIZAZ-Register-2026!",
            "full_name": "Duplicate Email Test",
            "legal_form": "MMC",
        },
        timeout=10,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Bu e-poçt ünvanı artıq qeydiyyatdan keçib."
    )


def test_register_invalid_legal_form(base_url):
    suffix = uuid.uuid4().hex[:10].upper()

    response = requests.post(
        f"{base_url}/api/v1/register",
        json={
            "company_name": f"BIZAZ INVALID FORM {suffix}",
            "email": f"bizaz-invalid-form-{suffix}@example.com",
            "password": "BIZAZ-Register-2026!",
            "full_name": f"Invalid Form {suffix}",
            "legal_form": "INVALID_TEST_FORM",
        },
        timeout=10,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Yanlış hüquqi forma."
