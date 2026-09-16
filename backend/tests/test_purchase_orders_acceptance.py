import uuid
import requests
import pytest
from app.database import SessionLocal
from app.models import AuditLog


BASE_URL = "http://127.0.0.1:8000"

OWNER_EMAIL = "bizaz-rbac-owner-test@gmail.com"
OWNER_PASSWORD = "BIZAZ-Test-2026!"

VIEWER_EMAIL = "bizaz-rbac-viewer-test@gmail.com"
VIEWER_PASSWORD = "BIZAZ-Test-2026!"

SUPPLIER_ID = "d1fa4bd4-13eb-48da-b2d5-f3c46a711d6f"
PRODUCT_ID = "6f0b0b80-5dce-41ad-a131-d60f0e52d58b"

OWNER_COMPANY_ID = "6cf693c6-ad8a-4b4e-803a-f38d1544969c"

CROSS_COMPANY_PO_ID = "5f5ad4e8-ab76-42bf-81aa-1e2f7ebc6786"


def login(email, password):
    response = requests.post(
        f"{BASE_URL}/api/v1/login",
        json={
            "email": email,
            "password": password,
        },
        timeout=10,
    )

    assert response.status_code == 200, response.text

    token = response.json()["token"]

    return {
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture(scope="module")
def owner_headers():
    return login(OWNER_EMAIL, OWNER_PASSWORD)


@pytest.fixture(scope="module")
def viewer_headers():
    return login(VIEWER_EMAIL, VIEWER_PASSWORD)


def create_po(headers, prefix="PO-4-15"):
    order_number = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    payload = {
        "supplier_id": SUPPLIER_ID,
        "order_number": order_number,
        "order_date": "2026-09-04T00:00:00",
        "currency": "AZN",
        "notes": "4.15 AUTOMATED ACCEPTANCE TEST",
        "items": [
            {
                "product_id": PRODUCT_ID,
                "quantity": 1,
                "unit": "ədəd",
                "unit_price": 500,
                "vat_rate": 18,
            }
        ],
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/purchase-orders",
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


def change_status(headers, po_id, status):
    response = requests.post(
        f"{BASE_URL}/api/v1/purchase-orders/{po_id}/status",
        headers=headers,
        json={"status": status},
        timeout=10,
    )

    return response


def test_01_create_po(owner_headers):
    data = create_po(owner_headers)

    assert data["status"] == "DRAFT"


def test_02_draft_update_allowed(owner_headers):
    data = create_po(owner_headers)

    response = requests.put(
        f"{BASE_URL}/api/v1/purchase-orders/{data['id']}",
        headers=owner_headers,
        json={
            "notes": "4.15 DRAFT UPDATE ALLOWED",
        },
        timeout=10,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "DRAFT"


def test_03_status_bypass_blocked(owner_headers):
    data = create_po(owner_headers)

    response = requests.put(
        f"{BASE_URL}/api/v1/purchase-orders/{data['id']}",
        headers=owner_headers,
        json={
            "status": "APPROVED",
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert "yalnız /status endpointi vasitəsilə" in response.text


def test_04_full_status_workflow(owner_headers):
    data = create_po(owner_headers)
    po_id = data["id"]

    response = change_status(owner_headers, po_id, "SUBMITTED")
    assert response.status_code == 200, response.text

    response = change_status(owner_headers, po_id, "APPROVED")
    assert response.status_code == 200, response.text

    response = change_status(owner_headers, po_id, "RECEIVED")
    assert response.status_code == 200, response.text


def test_05_received_update_blocked(owner_headers):
    data = create_po(owner_headers)
    po_id = data["id"]

    assert change_status(owner_headers, po_id, "SUBMITTED").status_code == 200
    assert change_status(owner_headers, po_id, "APPROVED").status_code == 200
    assert change_status(owner_headers, po_id, "RECEIVED").status_code == 200

    response = requests.put(
        f"{BASE_URL}/api/v1/purchase-orders/{po_id}",
        headers=owner_headers,
        json={
            "notes": "MUST BE BLOCKED",
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert "RECEIVED" in response.text


def test_06_received_delete_blocked(owner_headers):
    data = create_po(owner_headers)
    po_id = data["id"]

    assert change_status(owner_headers, po_id, "SUBMITTED").status_code == 200
    assert change_status(owner_headers, po_id, "APPROVED").status_code == 200
    assert change_status(owner_headers, po_id, "RECEIVED").status_code == 200

    response = requests.delete(
        f"{BASE_URL}/api/v1/purchase-orders/{po_id}",
        headers=owner_headers,
        timeout=10,
    )

    assert response.status_code == 400
    assert "RECEIVED" in response.text


def test_07_draft_delete_allowed(owner_headers):
    data = create_po(owner_headers)

    response = requests.delete(
        f"{BASE_URL}/api/v1/purchase-orders/{data['id']}",
        headers=owner_headers,
        timeout=10,
    )

    assert response.status_code == 200, response.text


def test_08_cancelled_update_blocked(owner_headers):
    data = create_po(owner_headers)
    po_id = data["id"]

    response = change_status(owner_headers, po_id, "CANCELLED")
    assert response.status_code == 200, response.text

    response = requests.put(
        f"{BASE_URL}/api/v1/purchase-orders/{po_id}",
        headers=owner_headers,
        json={
            "notes": "MUST BE BLOCKED",
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert "CANCELLED" in response.text


def test_09_cancelled_delete_blocked(owner_headers):
    data = create_po(owner_headers)
    po_id = data["id"]

    response = change_status(owner_headers, po_id, "CANCELLED")
    assert response.status_code == 200, response.text

    response = requests.delete(
        f"{BASE_URL}/api/v1/purchase-orders/{po_id}",
        headers=owner_headers,
        timeout=10,
    )

    assert response.status_code == 400
    assert "CANCELLED" in response.text


def test_10_viewer_create_blocked(viewer_headers):
    payload = {
        "supplier_id": SUPPLIER_ID,
        "order_number": f"PO-4-15-VIEWER-{uuid.uuid4().hex[:8].upper()}",
        "order_date": "2026-09-04T00:00:00",
        "currency": "AZN",
        "items": [
            {
                "product_id": PRODUCT_ID,
                "quantity": 1,
                "unit": "ədəd",
                "unit_price": 500,
                "vat_rate": 18,
            }
        ],
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/purchase-orders",
        headers=viewer_headers,
        json=payload,
        timeout=10,
    )

    assert response.status_code == 403


def test_11_viewer_update_blocked(owner_headers, viewer_headers):
    data = create_po(owner_headers)

    response = requests.put(
        f"{BASE_URL}/api/v1/purchase-orders/{data['id']}",
        headers=viewer_headers,
        json={
            "notes": "VIEWER MUST NOT UPDATE",
        },
        timeout=10,
    )

    assert response.status_code == 403


def test_12_viewer_delete_blocked(owner_headers, viewer_headers):
    data = create_po(owner_headers)

    response = requests.delete(
        f"{BASE_URL}/api/v1/purchase-orders/{data['id']}",
        headers=viewer_headers,
        timeout=10,
    )

    assert response.status_code == 403


def test_13_viewer_status_blocked(owner_headers, viewer_headers):
    data = create_po(owner_headers)

    response = change_status(
        viewer_headers,
        data["id"],
        "SUBMITTED",
    )

    assert response.status_code == 403


def test_14_cross_company_isolation(owner_headers):
    response = requests.get(
        f"{BASE_URL}/api/v1/purchase-orders/{CROSS_COMPANY_PO_ID}",
        headers=owner_headers,
        timeout=10,
    )

    assert response.status_code == 404


def test_15_invalid_status_transition_blocked(owner_headers):
    data = create_po(owner_headers)

    response = change_status(
        owner_headers,
        data["id"],
        "RECEIVED",
    )

    assert response.status_code == 400
    assert "Yanlış status keçidi" in response.text


def test_16_audit_create_and_status(owner_headers):
    data = create_po(owner_headers)
    po_id = data["id"]

    db = SessionLocal()
    try:
        created_audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "purchase_order",
            AuditLog.entity_id == uuid.UUID(po_id),
            AuditLog.company_id == uuid.UUID(OWNER_COMPANY_ID),
            AuditLog.action == "PURCHASE_ORDER_CREATED",
        ).first()

        assert created_audit is not None
        assert created_audit.entity_id == uuid.UUID(po_id)
        assert created_audit.company_id == uuid.UUID(OWNER_COMPANY_ID)
    finally:
        db.close()

    response = change_status(
        owner_headers,
        po_id,
        "SUBMITTED",
    )

    assert response.status_code == 200

    db = SessionLocal()
    try:
        status_audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "purchase_order",
            AuditLog.entity_id == uuid.UUID(po_id),
            AuditLog.company_id == uuid.UUID(OWNER_COMPANY_ID),
            AuditLog.action == "PURCHASE_ORDER_STATUS_CHANGED",
        ).first()

        assert status_audit is not None
        assert status_audit.entity_id == uuid.UUID(po_id)
        assert status_audit.company_id == uuid.UUID(OWNER_COMPANY_ID)
    finally:
        db.close()

    response = requests.get(
        f"{BASE_URL}/api/v1/purchase-orders/{po_id}",
        headers=owner_headers,
        timeout=10,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "SUBMITTED"
