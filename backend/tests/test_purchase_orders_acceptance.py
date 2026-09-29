import uuid
import requests
import pytest
from app.database import SessionLocal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import AuditLog


def create_po(base_url, headers, acceptance_owner_data, prefix="PO-4-15"):
    order_number = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    payload = {
        "supplier_id": acceptance_owner_data["supplier_id"],
        "order_number": order_number,
        "order_date": "2026-09-04T00:00:00",
        "currency": "AZN",
        "notes": "4.15 AUTOMATED ACCEPTANCE TEST",
        "items": [
            {
                "product_id": acceptance_owner_data["product_id"],
                "quantity": 1,
                "unit": "?d?d",
                "unit_price": 500,
                "vat_rate": 18,
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=headers,
        json=payload,
        timeout=10,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["status"] == "DRAFT"
    assert float(data["subtotal"]) == 500
    assert float(data["vat_amount"]) == 90
    assert float(data["total_amount"]) == 590

    return data


def change_status(base_url, headers, po_id, status):
    response = requests.post(
        f"{base_url}/api/v1/purchase-orders/{po_id}/status",
        headers=headers,
        json={"status": status},
        timeout=10,
    )

    return response

def test_01_create_po(base_url, acceptance_owner_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)

    assert data["status"] == "DRAFT"


def test_02_draft_update_allowed(base_url, acceptance_owner_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{data['id']}",
        headers=acceptance_owner_headers,
        json={
            "notes": "4.15 DRAFT UPDATE ALLOWED",
        },
        timeout=10,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "DRAFT"


def test_03_status_bypass_blocked(base_url, acceptance_owner_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{data['id']}",
        headers=acceptance_owner_headers,
        json={
            "status": "APPROVED",
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert "yalnız /status endpointi vasitəsilə" in response.text


def test_04_full_status_workflow(base_url, acceptance_owner_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)
    po_id = data["id"]

    response = change_status(base_url, acceptance_owner_headers, po_id, "SUBMITTED")
    assert response.status_code == 200, response.text

    response = change_status(base_url, acceptance_owner_headers, po_id, "APPROVED")
    assert response.status_code == 200, response.text

    response = change_status(base_url, acceptance_owner_headers, po_id, "RECEIVED")
    assert response.status_code == 200, response.text


def test_05_received_update_blocked(base_url, acceptance_owner_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)
    po_id = data["id"]

    assert change_status(base_url, acceptance_owner_headers, po_id, "SUBMITTED").status_code == 200
    assert change_status(base_url, acceptance_owner_headers, po_id, "APPROVED").status_code == 200
    assert change_status(base_url, acceptance_owner_headers, po_id, "RECEIVED").status_code == 200

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po_id}",
        headers=acceptance_owner_headers,
        json={
            "notes": "MUST BE BLOCKED",
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert "RECEIVED" in response.text


def test_06_received_delete_blocked(base_url, acceptance_owner_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)
    po_id = data["id"]

    assert change_status(base_url, acceptance_owner_headers, po_id, "SUBMITTED").status_code == 200
    assert change_status(base_url, acceptance_owner_headers, po_id, "APPROVED").status_code == 200
    assert change_status(base_url, acceptance_owner_headers, po_id, "RECEIVED").status_code == 200

    response = requests.delete(
        f"{base_url}/api/v1/purchase-orders/{po_id}",
        headers=acceptance_owner_headers,
        timeout=10,
    )

    assert response.status_code == 400
    assert "RECEIVED" in response.text


def test_07_draft_delete_allowed(base_url, acceptance_owner_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)

    response = requests.delete(
        f"{base_url}/api/v1/purchase-orders/{data['id']}",
        headers=acceptance_owner_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text


def test_08_cancelled_update_blocked(base_url, acceptance_owner_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)
    po_id = data["id"]

    response = change_status(base_url, acceptance_owner_headers, po_id, "CANCELLED")
    assert response.status_code == 200, response.text

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po_id}",
        headers=acceptance_owner_headers,
        json={
            "notes": "MUST BE BLOCKED",
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert "CANCELLED" in response.text


def test_09_cancelled_delete_blocked(base_url, acceptance_owner_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)
    po_id = data["id"]

    response = change_status(base_url, acceptance_owner_headers, po_id, "CANCELLED")
    assert response.status_code == 200, response.text

    response = requests.delete(
        f"{base_url}/api/v1/purchase-orders/{po_id}",
        headers=acceptance_owner_headers,
        timeout=10,
    )

    assert response.status_code == 400
    assert "CANCELLED" in response.text


def test_10_viewer_create_blocked(base_url, acceptance_viewer_headers, acceptance_owner_data):
    payload = {
        "supplier_id": acceptance_owner_data["supplier_id"],
        "order_number": f"PO-4-15-VIEWER-{uuid.uuid4().hex[:8].upper()}",
        "order_date": "2026-09-04T00:00:00",
        "currency": "AZN",
        "items": [
            {
                "product_id": acceptance_owner_data["product_id"],
                "quantity": 1,
                "unit": "ədəd",
                "unit_price": 500,
                "vat_rate": 18,
            }
        ],
    }

    response = requests.post(
        f"{base_url}/api/v1/purchase-orders",
        headers=acceptance_viewer_headers,
        json=payload,
        timeout=10,
    )

    assert response.status_code == 403


def test_11_viewer_update_blocked(base_url, acceptance_owner_headers, acceptance_viewer_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{data['id']}",
        headers=acceptance_viewer_headers,
        json={
            "notes": "VIEWER MUST NOT UPDATE",
        },
        timeout=10,
    )

    assert response.status_code == 403


def test_12_viewer_delete_blocked(base_url, acceptance_owner_headers, acceptance_viewer_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)

    response = requests.delete(
        f"{base_url}/api/v1/purchase-orders/{data['id']}",
        headers=acceptance_viewer_headers,
        timeout=10,
    )

    assert response.status_code == 403


def test_13_viewer_status_blocked(base_url, acceptance_owner_headers, acceptance_viewer_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)

    response = change_status(
        base_url,
        acceptance_viewer_headers,
        data["id"],
        "SUBMITTED",
    )

    assert response.status_code == 403


def test_14_cross_company_isolation(base_url, acceptance_owner_headers, acceptance_cross_company_po_id):
    response = requests.get(
        f"{base_url}/api/v1/purchase-orders/{acceptance_cross_company_po_id}",
        headers=acceptance_owner_headers,
        timeout=10,
    )

    assert response.status_code == 404


def test_15_invalid_status_transition_blocked(base_url, acceptance_owner_headers, acceptance_owner_data):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)

    response = change_status(
        base_url,
        acceptance_owner_headers,
        data["id"],
        "RECEIVED",
    )

    assert response.status_code == 400
    assert "Yanlış status keçidi" in response.text


def test_16_audit_create_and_status(base_url, acceptance_owner_headers, acceptance_owner_data, test_database_url):
    data = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)
    po_id = data["id"]

    test_engine = create_engine(test_database_url.replace("postgresql://", "postgresql+psycopg://"))
    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    db = TestSessionLocal()
    try:
        created_audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "purchase_order",
            AuditLog.entity_id == uuid.UUID(po_id),
            AuditLog.company_id == uuid.UUID(acceptance_owner_data["company_id"]),
            AuditLog.action == "PURCHASE_ORDER_CREATED",
        ).first()

        assert created_audit is not None
        assert created_audit.entity_id == uuid.UUID(po_id)
        assert created_audit.company_id == uuid.UUID(acceptance_owner_data["company_id"])
    finally:
        db.close()

    response = change_status(
        base_url,
        acceptance_owner_headers,
        po_id,
        "SUBMITTED",
    )

    assert response.status_code == 200

    db = TestSessionLocal()
    try:
        status_audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "purchase_order",
            AuditLog.entity_id == uuid.UUID(po_id),
            AuditLog.company_id == uuid.UUID(acceptance_owner_data["company_id"]),
            AuditLog.action == "PURCHASE_ORDER_STATUS_CHANGED",
        ).first()

        assert status_audit is not None
        assert status_audit.entity_id == uuid.UUID(po_id)
        assert status_audit.company_id == uuid.UUID(acceptance_owner_data["company_id"])
    finally:
        db.close()

    response = requests.get(
        f"{base_url}/api/v1/purchase-orders/{po_id}",
        headers=acceptance_owner_headers,
        timeout=10,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "SUBMITTED"

def test_17_update_total_below_active_payment_blocked(base_url, acceptance_owner_headers, acceptance_owner_data):
    po = create_po(base_url, acceptance_owner_headers, acceptance_owner_data)

    payment_response = requests.post(
        f"{base_url}/api/v1/payments",
        headers=acceptance_owner_headers,
        json={
            "purchase_order_id": po["id"],
            "amount": 100,
            "currency": "AZN",
            "reference": f"PO-UPDATE-LIMIT-TEST-{uuid.uuid4()}",
        },
        timeout=10,
    )

    assert payment_response.status_code == 201, payment_response.text

    response = requests.put(
        f"{base_url}/api/v1/purchase-orders/{po['id']}",
        headers=acceptance_owner_headers,
        json={
            "items": [
                {
                    "product_id": acceptance_owner_data["product_id"],
                    "quantity": 1,
                    "unit": "ədəd",
                    "unit_price": 50,
                    "vat_rate": 18,
                }
            ]
        },
        timeout=10,
    )

    assert response.status_code == 400, response.text
    assert "payment" in response.text.lower() or "?d?ni?" in response.text.lower()
