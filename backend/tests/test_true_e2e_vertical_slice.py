import uuid

import psycopg
import requests


def _create_approval(base_url, auth_headers, entity_type, entity_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/requests",
        headers=auth_headers,
        json={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "execution_mode": "SEQUENTIAL",
            "decision_mode": "ALL",
            "priority": "NORMAL",
            "policy_key": "H2.3-E2E",
            "policy_version": "1.0",
            "steps": [
                {
                    "step_order": 1,
                    "approver_role": "OWNER",
                }
            ],
        },
        timeout=10,
    )


def _approve(base_url, auth_headers, approval_id):
    return requests.post(
        f"{base_url}/api/v1/approvals/{approval_id}/decision",
        headers=auth_headers,
        json={
            "decision": "APPROVE",
            "comment": "H2.3 true E2E acceptance test",
        },
        timeout=10,
    )


def test_true_e2e_need_to_payment(
    base_url,
    auth_headers,
    test_company_data,
    test_database_url,
):
    db = psycopg.connect(test_database_url)
    db.autocommit = True

    need_id = None
    request_id = None
    offer_id = None
    selection_id = None
    po_id = None
    payment_id = None
    approval_ids = []

    try:
        suffix = uuid.uuid4().hex[:10].upper()

        # 1. NEED
        response = requests.post(
            f"{base_url}/api/v1/needs",
            headers=auth_headers,
            json={
                "need_number": f"NEED-E2E-{suffix}",
                "source": "MANUAL",
                "title": "H2.3 true E2E vertical slice",
                "priority": "NORMAL",
                "items": [
                    {
                        "product_id": test_company_data["product_id"],
                        "quantity": 1,
                        "unit": "ədəd",
                    }
                ],
            },
            timeout=10,
        )
        assert response.status_code == 201, response.text

        need = response.json()
        need_id = need["id"]
        need_item_id = need["items"][0]["id"]

        # 2. NEED APPROVAL/LIFECYCLE
        for status in ("SUBMITTED", "UNDER_REVIEW", "APPROVED"):
            response = requests.post(
                f"{base_url}/api/v1/needs/{need_id}/status",
                headers=auth_headers,
                json={"status": status},
                timeout=10,
            )
            assert response.status_code == 200, response.text
            assert response.json()["new_status"] == status

        # 3. NEED -> PURCHASE REQUEST
        request_number = f"PR-E2E-{suffix}"

        response = requests.post(
            f"{base_url}/api/v1/procurement/needs/{need_id}/convert",
            headers=auth_headers,
            json={
                "request_number": request_number,
                "items": [
                    {
                        "need_item_id": need_item_id,
                        "quantity": 1,
                    }
                ],
            },
            timeout=10,
        )
        assert response.status_code == 200, response.text

        conversion = response.json()
        request_id = conversion["purchase_request_id"]

        assert conversion["purchase_request_status"] == "DRAFT"

        # 4. SUPPLIER OFFER
        connection = psycopg.connect(test_database_url)
        try:
            row = connection.execute(
                """
                SELECT id
                FROM purchase_request_items
                WHERE purchase_request_id = %s
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (uuid.UUID(request_id),),
            ).fetchone()
        finally:
            connection.close()

        assert row is not None
        request_item_id = str(row[0])

        offer_number = f"SO-E2E-{suffix}"

        response = requests.post(
            f"{base_url}/api/v1/procurement/supplier-offers",
            headers=auth_headers,
            json={
                "purchase_request_id": request_id,
                "supplier_id": test_company_data["supplier_id"],
                "offer_number": offer_number,
                "status": "SUBMITTED",
                "items": [
                    {
                        "purchase_request_item_id": request_item_id,
                        "product_id": test_company_data["product_id"],
                        "quantity": 1,
                        "unit": "ədəd",
                        "unit_price": 100,
                        "vat_rate": 18,
                        "delivery_days": 5,
                    }
                ],
            },
            timeout=10,
        )
        assert response.status_code == 200, response.text

        offer_id = response.json()["id"]

        # 5. COMPARISON
        response = requests.get(
            f"{base_url}/api/v1/procurement/purchase-requests/"
            f"{request_id}/comparison",
            headers=auth_headers,
            timeout=10,
        )
        assert response.status_code == 200, response.text

        comparison = response.json()
        assert comparison["purchase_request_id"] == request_id
        assert any(
            str(offer["offer_id"]) == str(offer_id)
            for item in comparison["items"]
            for offer in item["offers"]
        )

        # 6. PR SUBMITTED
        response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/"
            f"{request_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=10,
        )
        assert response.status_code == 200, response.text

        # 7. PR APPROVAL
        response = _create_approval(
            base_url,
            auth_headers,
            "PURCHASE_REQUEST",
            request_id,
        )
        assert response.status_code == 201, response.text

        approval_id = response.json()["id"]
        approval_ids.append(("PURCHASE_REQUEST", request_id, approval_id))

        response = _approve(base_url, auth_headers, approval_id)
        assert response.status_code == 200, response.text
        assert response.json()["request"]["status"] == "APPROVED"

        response = requests.put(
            f"{base_url}/api/v1/procurement/purchase-requests/"
            f"{request_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )
        assert response.status_code == 200, response.text

        # 8. OFFER SELECTION
        response = requests.post(
            f"{base_url}/api/v1/procurement/offer-selections",
            headers=auth_headers,
            json={
                "purchase_request_id": request_id,
                "supplier_offer_id": offer_id,
                "justification": "H2.3 true E2E selection",
            },
            timeout=10,
        )
        assert response.status_code == 200, response.text

        selection_id = response.json()["id"]

        # 9. SELECTION APPROVAL
        response = _create_approval(
            base_url,
            auth_headers,
            "OFFER_SELECTION",
            selection_id,
        )
        assert response.status_code == 201, response.text

        approval_id = response.json()["id"]
        approval_ids.append(("OFFER_SELECTION", selection_id, approval_id))

        response = _approve(base_url, auth_headers, approval_id)
        assert response.status_code == 200, response.text
        assert response.json()["request"]["status"] == "APPROVED"

        # 10. PURCHASE ORDER
        response = requests.post(
            f"{base_url}/api/v1/procurement/offer-selections/"
            f"{selection_id}/purchase-order",
            headers=auth_headers,
            json={
                "order_number": f"PO-E2E-{suffix}",
                "notes": "H2.3 true E2E purchase order",
            },
            timeout=10,
        )
        assert response.status_code == 201, response.text

        po_id = response.json()["purchase_order_id"]

        # 11. PO SUBMITTED
        response = requests.post(
            f"{base_url}/api/v1/purchase-orders/"
            f"{po_id}/status",
            headers=auth_headers,
            json={"status": "SUBMITTED"},
            timeout=10,
        )
        assert response.status_code == 200, response.text

        # 12. PO APPROVAL
        response = _create_approval(
            base_url,
            auth_headers,
            "PURCHASE_ORDER",
            po_id,
        )
        assert response.status_code == 201, response.text

        approval_id = response.json()["id"]
        approval_ids.append(("PURCHASE_ORDER", po_id, approval_id))

        response = _approve(base_url, auth_headers, approval_id)
        assert response.status_code == 200, response.text
        assert response.json()["request"]["status"] == "APPROVED"

        response = requests.post(
            f"{base_url}/api/v1/purchase-orders/"
            f"{po_id}/status",
            headers=auth_headers,
            json={"status": "APPROVED"},
            timeout=10,
        )
        assert response.status_code == 200, response.text

        # 13. PAYMENT
        response = requests.post(
            f"{base_url}/api/v1/payments",
            headers=auth_headers,
            json={
                "purchase_order_id": po_id,
                "amount": 118,
                "currency": "AZN",
            },
            timeout=10,
        )
        assert response.status_code == 201, response.text

        payment = response.json()
        payment_id = payment["id"]

        assert payment["purchase_order_id"] == po_id
        assert float(payment["amount"]) == 118
        assert payment["currency"] == "AZN"
        assert payment["status"] == "PENDING"

    finally:
        for entity_type, entity_id, approval_id in reversed(approval_ids):
            db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (uuid.UUID(approval_id),),
            )
            db.execute(
                "DELETE FROM approval_steps WHERE approval_request_id = %s",
                (uuid.UUID(approval_id),),
            )
            db.execute(
                "DELETE FROM approval_requests WHERE id = %s",
                (uuid.UUID(approval_id),),
            )

        if payment_id:
            db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (uuid.UUID(payment_id),),
            )
            db.execute(
                "DELETE FROM payments WHERE id = %s",
                (uuid.UUID(payment_id),),
            )

        if po_id:
            db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (uuid.UUID(po_id),),
            )
            db.execute(
                "DELETE FROM purchase_order_items WHERE purchase_order_id = %s",
                (uuid.UUID(po_id),),
            )
            db.execute(
                "UPDATE offer_selections SET purchase_order_id = NULL WHERE purchase_order_id = %s",
                (uuid.UUID(po_id),),
            )
            db.execute(
                "DELETE FROM purchase_orders WHERE id = %s",
                (uuid.UUID(po_id),),
            )

        if selection_id:
            db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (uuid.UUID(selection_id),),
            )
            db.execute(
                "DELETE FROM offer_selections WHERE id = %s",
                (uuid.UUID(selection_id),),
            )

        if offer_id:
            db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (uuid.UUID(offer_id),),
            )
            db.execute(
                "DELETE FROM supplier_offer_items WHERE supplier_offer_id = %s",
                (uuid.UUID(offer_id),),
            )
            db.execute(
                "DELETE FROM supplier_offers WHERE id = %s",
                (uuid.UUID(offer_id),),
            )

        if request_id:
            db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (uuid.UUID(request_id),),
            )
            db.execute(
                "DELETE FROM need_pr_conversions WHERE purchase_request_id = %s",
                (uuid.UUID(request_id),),
            )
            db.execute(
                "DELETE FROM purchase_request_items WHERE purchase_request_id = %s",
                (uuid.UUID(request_id),),
            )
            db.execute(
                "DELETE FROM purchase_requests WHERE id = %s",
                (uuid.UUID(request_id),),
            )

        if need_id:
            db.execute(
                "DELETE FROM audit_log WHERE entity_id = %s",
                (uuid.UUID(need_id),),
            )
            db.execute(
                "DELETE FROM need_items WHERE need_id = %s",
                (uuid.UUID(need_id),),
            )
            db.execute(
                "DELETE FROM needs WHERE id = %s",
                (uuid.UUID(need_id),),
            )

        db.close()
