from app.main import ProductCreateSchema, PurchaseOrderItemCreateSchema
from app.models import Product, PurchaseOrderItem


def test_product_unit_default_is_azerbaijani():
    assert Product.__table__.c.unit.default.arg == "ədəd"


def test_purchase_order_item_unit_default_is_azerbaijani():
    assert PurchaseOrderItem.__table__.c.unit.default.arg == "ədəd"

def test_product_create_schema_unit_default_is_azerbaijani():
    assert ProductCreateSchema.model_fields["unit"].default == "\u0259d\u0259d"


def test_purchase_order_item_create_schema_unit_default_is_azerbaijani():
    assert (
        PurchaseOrderItemCreateSchema.model_fields["unit"].default
        == "\u0259d\u0259d"
    )
