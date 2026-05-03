"""tests/test_connectors.py

单元测试：MerchantDataAdapter 和平台适配器骨架。
"""

import pytest
from app.connectors.base import (
    MockMerchantAdapter,
    TaobaoAdapter,
    JDAdapter,
    AmazonAdapter,
    ERPAdapter,
    get_platform_adapter,
)


def test_mock_merchant_adapter_product_inventory():
    adapter = MockMerchantAdapter()
    price = adapter.get_product_price("merchant_a", "《三体》")
    inventory = adapter.get_inventory("merchant_a", "《三体》")

    assert price is not None
    assert price["price"] == 35.00
    assert inventory is not None
    assert inventory["status"] == "in_stock"


def test_mock_merchant_adapter_order_and_shipping():
    adapter = MockMerchantAdapter()
    order_status = adapter.get_order_status("merchant_a", "ORDER001")
    shipping_info = adapter.get_shipping_info("merchant_a", "ORDER001")

    assert order_status is not None
    assert order_status["status"] == "shipped"
    assert shipping_info is not None
    assert shipping_info["carrier"] == "SF Express"


def test_mock_merchant_adapter_policy():
    adapter = MockMerchantAdapter()
    refund_policy = adapter.get_policy("merchant_a", "return")
    shipping_policy = adapter.get_policy("merchant_a", "shipping")

    assert refund_policy is not None
    assert refund_policy["title"] == "退货政策"
    assert shipping_policy is not None
    assert "运费信息" in shipping_policy["title"]


def test_platform_adapter_factory_returns_platform_classes():
    assert isinstance(get_platform_adapter("taobao"), TaobaoAdapter)
    assert isinstance(get_platform_adapter("JD"), JDAdapter)
    assert isinstance(get_platform_adapter("amazon"), AmazonAdapter)
    assert isinstance(get_platform_adapter("erp"), ERPAdapter)

    with pytest.raises(ValueError):
        get_platform_adapter("unsupported_platform")
