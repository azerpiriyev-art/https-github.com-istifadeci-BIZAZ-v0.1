import uuid

import requests


def test_p01_delete_product_success_and_verify(
    base_url,
    auth_headers,
    test_db,
):
    suffix = uuid.uuid4().hex[:10].upper()

    create_response = requests.post(
        f"{base_url}/api/v1/products",
        headers=auth_headers,
        json={
            "name": f"Acceptance Delete Product {suffix}",
            "sku": f"ACC-DEL-{suffix}",
            "unit": "ədəd",
        },
        timeout=10,
    )

    assert create_response.status_code == 200, create_response.text

    create_data = create_response.json()
    assert create_data["status"] == "success"
    assert create_data["message"] == "Məhsul uğurla yaradıldı."
    assert create_data["product"]["id"]

    product_id = create_data["product"]["id"]

    try:
        response = requests.delete(
            f"{base_url}/api/v1/products/{product_id}",
            headers=auth_headers,
            timeout=10,
        )

        assert response.status_code == 200, response.text

        data = response.json()
        assert data["status"] == "success"
        assert data["product_id"] == product_id

        audit_row = test_db.execute(
            """
            SELECT action, entity_type
            FROM audit_log
            WHERE entity_id = %s
              AND action = 'PRODUCT_DELETED'
              AND entity_type = 'product'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(product_id),),
        ).fetchone()

        assert audit_row is not None
        assert audit_row[0] == "PRODUCT_DELETED"
        assert audit_row[1] == "product"

        verify = requests.get(
            f"{base_url}/api/v1/products/{product_id}",
            headers=auth_headers,
            timeout=10,
        )

        assert verify.status_code == 404, verify.text

    finally:
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (uuid.UUID(product_id),),
        )
        test_db.execute(
            "DELETE FROM products WHERE id = %s",
            (uuid.UUID(product_id),),
        )


def test_p01_delete_product_referenced_returns_409(
    base_url,
    auth_headers,
    test_company_data,
):
    product_id = test_company_data["product_id"]

    response = requests.delete(
        f"{base_url}/api/v1/products/{product_id}",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 409, response.text

    data = response.json()
    assert data["detail"] == (
        "Məhsul digər biznes sənədlərində istifadə olunduğuna görə silinə bilməz."
    )

    verify = requests.get(
        f"{base_url}/api/v1/products/{product_id}",
        headers=auth_headers,
        timeout=10,
    )

    assert verify.status_code == 200, verify.text


def test_p01_delete_product_missing_returns_404(
    base_url,
    auth_headers,
):
    missing_product_id = str(uuid.uuid4())

    response = requests.delete(
        f"{base_url}/api/v1/products/{missing_product_id}",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 404, response.text


def test_p02_delete_product_price_missing_returns_404(
    base_url,
    auth_headers,
    test_company_data,
):
    product_id = test_company_data["product_id"]
    missing_price_id = str(uuid.uuid4())

    response = requests.delete(
        f"{base_url}/api/v1/products/{product_id}/prices/{missing_price_id}",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 404, response.text


def test_p03_list_purchase_requests_success_and_company_scope(
    base_url,
    auth_headers,
    purchase_request_lifecycle_fixture,
):
    fixture = purchase_request_lifecycle_fixture

    response = requests.get(
        f"{base_url}/api/v1/procurement/purchase-requests",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert isinstance(data, list)

    ids = {item["id"] for item in data}

    assert fixture["request_id"] in ids


def test_p03_list_purchase_requests_unauthenticated_returns_401(
    base_url,
):
    response = requests.get(
        f"{base_url}/api/v1/procurement/purchase-requests",
        timeout=10,
    )

    assert response.status_code == 401, response.text


def test_p04_list_products_success(
    base_url,
    auth_headers,
    test_company_data,
):
    response = requests.get(
        f"{base_url}/api/v1/products",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "success"
    assert isinstance(data["products"], list)
    assert data["count"] == len(data["products"])

    product_ids = {
        product["id"]
        for product in data["products"]
    }

    assert test_company_data["product_id"] in product_ids


def test_p04_list_products_unauthenticated_returns_401(
    base_url,
):
    response = requests.get(
        f"{base_url}/api/v1/products",
        timeout=10,
    )

    assert response.status_code == 401, response.text

def test_s01_delete_supplier_referenced_returns_409(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    row = test_db.execute(
        """
        SELECT s.id
        FROM suppliers s
        WHERE s.company_id = %s
          AND (
              EXISTS (
                  SELECT 1
                  FROM purchase_orders po
                  WHERE po.supplier_id = s.id
              )
              OR EXISTS (
                  SELECT 1
                  FROM supplier_offers so
                  WHERE so.supplier_id = s.id
              )
          )
        ORDER BY s.created_at
        LIMIT 1
        """,
        (test_company_data["company_id"],),
    ).fetchone()

    assert row is not None, "Referenced supplier fixture not found"

    supplier_id = str(row[0])

    response = requests.delete(
        f"{base_url}/api/v1/suppliers/{supplier_id}",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 409, response.text

    data = response.json()

    assert data["detail"] == (
        "Təchizatçı digər biznes sənədlərində istifadə olunduğuna görə "
        "silinə bilməz."
    )

    verify = requests.get(
        f"{base_url}/api/v1/suppliers/{supplier_id}",
        headers=auth_headers,
        timeout=10,
    )

    assert verify.status_code == 200, verify.text


def test_s02_delete_supplier_success_and_verify(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    suffix = uuid.uuid4().hex[:10].upper()

    create_response = requests.post(
        f"{base_url}/api/v1/suppliers",
        headers=auth_headers,
        json={
            "name": f"Acceptance Delete Supplier {suffix}",
            "is_active": True,
        },
        timeout=10,
    )

    assert create_response.status_code == 201, create_response.text

    supplier = create_response.json()
    supplier_id = supplier["id"]

    try:
        assert supplier["company_id"] == test_company_data["company_id"]

        response = requests.delete(
            f"{base_url}/api/v1/suppliers/{supplier_id}",
            headers=auth_headers,
            timeout=10,
        )

        assert response.status_code == 200, response.text

        data = response.json()

        assert data["status"] == "success"
        assert data["message"] == "Təchizatçı silindi."

        audit_row = test_db.execute(
            """
            SELECT action, entity_type
            FROM audit_log
            WHERE entity_id = %s
              AND action = 'SUPPLIER_DELETED'
              AND entity_type = 'supplier'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(supplier_id),),
        ).fetchone()

        assert audit_row is not None
        assert audit_row[0] == "SUPPLIER_DELETED"
        assert audit_row[1] == "supplier"

        verify = requests.get(
            f"{base_url}/api/v1/suppliers/{supplier_id}",
            headers=auth_headers,
            timeout=10,
        )

        assert verify.status_code == 404, verify.text

    finally:
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (uuid.UUID(supplier_id),),
        )
        test_db.execute(
            "DELETE FROM suppliers WHERE id = %s",
            (uuid.UUID(supplier_id),),
        )


def test_s03_delete_supplier_missing_returns_404(
    base_url,
    auth_headers,
):
    missing_supplier_id = str(uuid.uuid4())

    response = requests.delete(
        f"{base_url}/api/v1/suppliers/{missing_supplier_id}",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 404, response.text


def test_s04_delete_supplier_unauthenticated_returns_401(
    base_url,
    test_company_data,
):
    supplier_id = test_company_data["supplier_id"]

    response = requests.delete(
        f"{base_url}/api/v1/suppliers/{supplier_id}",
        timeout=10,
    )

    assert response.status_code == 401, response.text



def _find_foreign_active_supplier(test_db, company_id):
    row = test_db.execute(
        """
        SELECT s.id
        FROM suppliers s
        WHERE s.company_id <> %s
          AND s.is_active = TRUE
        ORDER BY s.created_at
        LIMIT 1
        """,
        (uuid.UUID(company_id),),
    ).fetchone()

    assert row is not None, "Foreign active supplier fixture not found"

    return str(row[0])


def test_p05_product_price_cross_company_create_blocked(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    product_id = uuid.UUID(test_company_data["product_id"])
    company_id = test_company_data["company_id"]

    foreign_supplier_id = _find_foreign_active_supplier(
        test_db,
        company_id,
    )

    response = requests.post(
        f"{base_url}/api/v1/products/{product_id}/prices",
        headers=auth_headers,
        json={
            "price_type": "PURCHASE",
            "amount": "11.01",
            "currency": "AZN",
            "vat_included": False,
            "supplier_id": foreign_supplier_id,
        },
        timeout=10,
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Təchizatçı tapılmadı."

    leaked = test_db.execute(
        """
        SELECT id
        FROM product_prices
        WHERE product_id = %s
          AND company_id = %s
          AND supplier_id = %s
          AND amount = 11.0100
        LIMIT 1
        """,
        (
            product_id,
            uuid.UUID(company_id),
            uuid.UUID(foreign_supplier_id),
        ),
    ).fetchone()

    assert leaked is None


def test_p06_product_price_same_company_create_success(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    product_id = test_company_data["product_id"]
    supplier_id = test_company_data["supplier_id"]

    response = requests.post(
        f"{base_url}/api/v1/products/{product_id}/prices",
        headers=auth_headers,
        json={
            "price_type": "PURCHASE",
            "amount": "12.01",
            "currency": "AZN",
            "vat_included": False,
            "supplier_id": supplier_id,
        },
        timeout=10,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["product_id"] == product_id
    assert data["price_type"] == "PURCHASE"
    assert data["amount"] == "12.0100"
    assert data["currency"] == "AZN"
    assert data["supplier_id"] == supplier_id

    price_id = uuid.UUID(data["id"])

    try:
        assert price_id
    finally:
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (price_id,),
        )
        test_db.execute(
            "DELETE FROM product_prices WHERE id = %s",
            (price_id,),
        )
        test_db.commit()


def test_p07_product_price_cross_company_update_blocked(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    product_id = uuid.UUID(test_company_data["product_id"])
    company_id = test_company_data["company_id"]
    own_supplier_id = uuid.UUID(test_company_data["supplier_id"])

    foreign_supplier_id = uuid.UUID(
        _find_foreign_active_supplier(
            test_db,
            company_id,
        )
    )

    create_response = requests.post(
        f"{base_url}/api/v1/products/{product_id}/prices",
        headers=auth_headers,
        json={
            "price_type": "PURCHASE",
            "amount": "13.01",
            "currency": "AZN",
            "vat_included": False,
            "supplier_id": str(own_supplier_id),
        },
        timeout=10,
    )

    assert create_response.status_code == 201, create_response.text

    price_id = uuid.UUID(create_response.json()["id"])

    try:
        update_response = requests.put(
            f"{base_url}/api/v1/products/{product_id}/prices/{price_id}",
            headers=auth_headers,
            json={
                "supplier_id": str(foreign_supplier_id),
            },
            timeout=10,
        )

        assert update_response.status_code == 404, update_response.text
        assert update_response.json()["detail"] == "Təchizatçı tapılmadı."

        verify_response = requests.get(
            f"{base_url}/api/v1/products/{product_id}/prices",
            headers=auth_headers,
            timeout=10,
        )

        assert verify_response.status_code == 200, verify_response.text

        matching = [
            item
            for item in verify_response.json()
            if uuid.UUID(item["id"]) == price_id
        ]

        assert len(matching) == 1
        assert uuid.UUID(matching[0]["supplier_id"]) == own_supplier_id
        assert uuid.UUID(matching[0]["supplier_id"]) != foreign_supplier_id

        audit_row = test_db.execute(
            """
            SELECT id
            FROM audit_log
            WHERE entity_id = %s
              AND action = 'PRODUCT_PRICE_UPDATED'
              AND entity_type = 'product_price'
            LIMIT 1
            """,
            (price_id,),
        ).fetchone()

        assert audit_row is None

    finally:
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (price_id,),
        )
        test_db.execute(
            "DELETE FROM product_prices WHERE id = %s",
            (price_id,),
        )
        test_db.commit()
def test_p08_update_product_success_and_verify(
    base_url,
    auth_headers,
    test_db,
):
    suffix = uuid.uuid4().hex[:10].upper()

    create_response = requests.post(
        f"{base_url}/api/v1/products",
        headers=auth_headers,
        json={
            "name": f"Acceptance Update Product {suffix}",
            "sku": f"ACC-UPD-{suffix}",
            "unit": "ədəd",
            "description": "Before update",
            "is_active": True,
        },
        timeout=10,
    )

    assert create_response.status_code == 200, create_response.text

    product_id = create_response.json()["product"]["id"]

    try:
        update_response = requests.put(
            f"{base_url}/api/v1/products/{product_id}",
            headers=auth_headers,
            json={
                "name": f"Acceptance Updated Product {suffix}",
                "description": "After update",
            },
            timeout=10,
        )

        assert update_response.status_code == 200, update_response.text

        data = update_response.json()
        assert data["status"] == "success"
        assert data["product"]["id"] == product_id
        assert data["product"]["name"] == f"Acceptance Updated Product {suffix}"
        assert data["product"]["description"] == "After update"

        verify = requests.get(
            f"{base_url}/api/v1/products/{product_id}",
            headers=auth_headers,
            timeout=10,
        )

        assert verify.status_code == 200, verify.text

        verified = verify.json()["product"]
        assert verified["name"] == f"Acceptance Updated Product {suffix}"
        assert verified["description"] == "After update"

        audit_row = test_db.execute(
            """
            SELECT action, entity_type
            FROM audit_log
            WHERE entity_id = %s
              AND action = 'PRODUCT_UPDATED'
              AND entity_type = 'product'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(product_id),),
        ).fetchone()

        assert audit_row is not None
        assert audit_row[0] == "PRODUCT_UPDATED"
        assert audit_row[1] == "product"

    finally:
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (uuid.UUID(product_id),),
        )
        test_db.execute(
            "DELETE FROM products WHERE id = %s",
            (uuid.UUID(product_id),),
        )
        test_db.commit()


def test_p09_product_price_same_company_update_success(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    product_id = test_company_data["product_id"]
    supplier_id = test_company_data["supplier_id"]

    create_response = requests.post(
        f"{base_url}/api/v1/products/{product_id}/prices",
        headers=auth_headers,
        json={
            "price_type": "PURCHASE",
            "amount": "13.02",
            "currency": "AZN",
            "vat_included": False,
            "supplier_id": supplier_id,
        },
        timeout=10,
    )

    assert create_response.status_code == 201, create_response.text

    price_id = uuid.UUID(create_response.json()["id"])

    try:
        update_response = requests.put(
            f"{base_url}/api/v1/products/{product_id}/prices/{price_id}",
            headers=auth_headers,
            json={
                "amount": "17.02",
            },
            timeout=10,
        )

        assert update_response.status_code == 200, update_response.text

        data = update_response.json()
        assert data["id"] == str(price_id)
        assert data["product_id"] == product_id
        assert data["amount"] == "17.0200"
        assert data["currency"] == "AZN"
        assert data["supplier_id"] == supplier_id

        verify_response = requests.get(
            f"{base_url}/api/v1/products/{product_id}/prices",
            headers=auth_headers,
            timeout=10,
        )

        assert verify_response.status_code == 200, verify_response.text

        matching = [
            item
            for item in verify_response.json()
            if uuid.UUID(item["id"]) == price_id
        ]

        assert len(matching) == 1
        assert matching[0]["amount"] == "17.0200"
        assert matching[0]["supplier_id"] == supplier_id

        audit_row = test_db.execute(
            """
            SELECT action, entity_type
            FROM audit_log
            WHERE entity_id = %s
              AND action = 'PRODUCT_PRICE_UPDATED'
              AND entity_type = 'product_price'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (price_id,),
        ).fetchone()

        assert audit_row is not None
        assert audit_row[0] == "PRODUCT_PRICE_UPDATED"
        assert audit_row[1] == "product_price"

    finally:
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (price_id,),
        )
        test_db.execute(
            "DELETE FROM product_prices WHERE id = %s",
            (price_id,),
        )
        test_db.commit()


def test_p10_delete_product_price_success_and_verify(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    product_id = test_company_data["product_id"]
    supplier_id = test_company_data["supplier_id"]

    create_response = requests.post(
        f"{base_url}/api/v1/products/{product_id}/prices",
        headers=auth_headers,
        json={
            "price_type": "PURCHASE",
            "amount": "14.03",
            "currency": "AZN",
            "vat_included": False,
            "supplier_id": supplier_id,
        },
        timeout=10,
    )

    assert create_response.status_code == 201, create_response.text

    price_id = uuid.UUID(create_response.json()["id"])

    try:
        response = requests.delete(
            f"{base_url}/api/v1/products/{product_id}/prices/{price_id}",
            headers=auth_headers,
            timeout=10,
        )

        assert response.status_code == 200, response.text

        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Məhsul qiyməti silindi."

        verify_response = requests.get(
            f"{base_url}/api/v1/products/{product_id}/prices",
            headers=auth_headers,
            timeout=10,
        )

        assert verify_response.status_code == 200, verify_response.text

        matching = [
            item
            for item in verify_response.json()
            if uuid.UUID(item["id"]) == price_id
        ]

        assert matching == []

        audit_row = test_db.execute(
            """
            SELECT action, entity_type
            FROM audit_log
            WHERE entity_id = %s
              AND action = 'PRODUCT_PRICE_DELETED'
              AND entity_type = 'product_price'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (price_id,),
        ).fetchone()

        assert audit_row is not None
        assert audit_row[0] == "PRODUCT_PRICE_DELETED"
        assert audit_row[1] == "product_price"

    finally:
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (price_id,),
        )
        test_db.execute(
            "DELETE FROM product_prices WHERE id = %s",
            (price_id,),
        )
        test_db.commit()


def test_s05_list_suppliers_success_and_company_scope(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    supplier_id = test_company_data["supplier_id"]
    company_id = test_company_data["company_id"]

    foreign_row = test_db.execute(
        """
        SELECT s.id
        FROM suppliers s
        WHERE s.company_id <> %s
        ORDER BY s.created_at
        LIMIT 1
        """,
        (uuid.UUID(company_id),),
    ).fetchone()

    assert foreign_row is not None, "Foreign supplier fixture not found"

    foreign_supplier_id = str(foreign_row[0])

    response = requests.get(
        f"{base_url}/api/v1/suppliers",
        headers=auth_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert isinstance(data, list)

    supplier_ids = {item["id"] for item in data}

    assert supplier_id in supplier_ids
    assert foreign_supplier_id not in supplier_ids

    for item in data:
        assert item["company_id"] == company_id


def test_s06_update_supplier_success_and_verify(
    base_url,
    auth_headers,
    test_company_data,
    test_db,
):
    suffix = uuid.uuid4().hex[:10].upper()

    create_response = requests.post(
        f"{base_url}/api/v1/suppliers",
        headers=auth_headers,
        json={
            "name": f"Acceptance Update Supplier {suffix}",
            "is_active": True,
        },
        timeout=10,
    )

    assert create_response.status_code == 201, create_response.text

    supplier_id = create_response.json()["id"]

    try:
        update_response = requests.put(
            f"{base_url}/api/v1/suppliers/{supplier_id}",
            headers=auth_headers,
            json={
                "name": f"Acceptance Updated Supplier {suffix}",
                "description": "After supplier update",
            },
            timeout=10,
        )

        assert update_response.status_code == 200, update_response.text

        data = update_response.json()

        assert data["id"] == supplier_id
        assert data["company_id"] == test_company_data["company_id"]
        assert data["name"] == f"Acceptance Updated Supplier {suffix}"
        assert data["description"] == "After supplier update"

        verify = requests.get(
            f"{base_url}/api/v1/suppliers/{supplier_id}",
            headers=auth_headers,
            timeout=10,
        )

        assert verify.status_code == 200, verify.text

        verified = verify.json()

        assert verified["name"] == f"Acceptance Updated Supplier {suffix}"
        assert verified["description"] == "After supplier update"

        audit_row = test_db.execute(
            """
            SELECT action, entity_type
            FROM audit_log
            WHERE entity_id = %s
              AND action = 'SUPPLIER_UPDATED'
              AND entity_type = 'supplier'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uuid.UUID(supplier_id),),
        ).fetchone()

        assert audit_row is not None
        assert audit_row[0] == "SUPPLIER_UPDATED"
        assert audit_row[1] == "supplier"

    finally:
        test_db.execute(
            "DELETE FROM audit_log WHERE entity_id = %s",
            (uuid.UUID(supplier_id),),
        )
        test_db.execute(
            "DELETE FROM suppliers WHERE id = %s",
            (uuid.UUID(supplier_id),),
        )
        test_db.commit()
