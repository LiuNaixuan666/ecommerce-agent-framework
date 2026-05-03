"""
Merchant Data Adapter Interface

This module defines the interface for accessing structured data from various e-commerce platforms.
Each platform (Taobao, JD, Amazon, ERP, etc.) should implement this interface.
"""

from typing import Protocol, Dict, Optional
from abc import ABC, abstractmethod


class MerchantDataAdapter(Protocol):
    """Protocol for merchant data adapters"""

    def get_product_price(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        """
        Get product price information.

        Args:
            merchant_id: Merchant identifier
            product_id: Product identifier (SKU, title, etc.)

        Returns:
            Dict with price info, e.g.:
            {
                "price": 29.99,
                "currency": "CNY",
                "last_updated": "2024-01-01T10:00:00Z"
            }
        """
        ...

    def get_inventory(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        """
        Get product inventory information.

        Args:
            merchant_id: Merchant identifier
            product_id: Product identifier

        Returns:
            Dict with inventory info, e.g.:
            {
                "quantity": 50,
                "status": "in_stock",  # in_stock, low_stock, out_of_stock
                "location": "warehouse_a"
            }
        """
        ...

    def get_order_status(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        """
        Get order status information.

        Args:
            merchant_id: Merchant identifier
            order_id: Order identifier

        Returns:
            Dict with order info, e.g.:
            {
                "status": "shipped",
                "tracking_number": "123456789",
                "estimated_delivery": "2024-01-05"
            }
        """
        ...

    def get_shipping_info(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        """
        Get shipping information for an order.

        Args:
            merchant_id: Merchant identifier
            order_id: Order identifier

        Returns:
            Dict with shipping info, e.g.:
            {
                "carrier": "SF Express",
                "tracking_url": "https://...",
                "shipping_cost": 5.00
            }
        """
        ...

    def get_policy(self, merchant_id: str, policy_type: str) -> Optional[Dict]:
        """
        Get merchant policy information.

        Args:
            merchant_id: Merchant identifier
            policy_type: Type of policy (return, shipping, warranty, refund, etc.)

        Returns:
            Dict with policy info, e.g.:
            {
                "title": "退货政策",
                "description": "7天无理由退货",
                "condition": "商品完好"
            }
        """
        ...


class TaobaoAdapter(MerchantDataAdapter):
    """Taobao 平台适配器骨架。

    该类为真实平台适配器预留接口，实际实现时可以接入淘宝 OpenAPI / SDK。
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def get_product_price(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        raise NotImplementedError("Taobao API integration required for get_product_price")

    def get_inventory(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        raise NotImplementedError("Taobao API integration required for get_inventory")

    def get_order_status(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        raise NotImplementedError("Taobao API integration required for get_order_status")

    def get_shipping_info(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        raise NotImplementedError("Taobao API integration required for get_shipping_info")

    def get_policy(self, merchant_id: str, policy_type: str) -> Optional[Dict]:
        raise NotImplementedError("Taobao API integration required for get_policy")


class JDAdapter(MerchantDataAdapter):
    """JD 平台适配器骨架。"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def get_product_price(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        raise NotImplementedError("JD API integration required for get_product_price")

    def get_inventory(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        raise NotImplementedError("JD API integration required for get_inventory")

    def get_order_status(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        raise NotImplementedError("JD API integration required for get_order_status")

    def get_shipping_info(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        raise NotImplementedError("JD API integration required for get_shipping_info")

    def get_policy(self, merchant_id: str, policy_type: str) -> Optional[Dict]:
        raise NotImplementedError("JD API integration required for get_policy")


class AmazonAdapter(MerchantDataAdapter):
    """Amazon 平台适配器骨架。"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def get_product_price(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        raise NotImplementedError("Amazon API integration required for get_product_price")

    def get_inventory(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        raise NotImplementedError("Amazon API integration required for get_inventory")

    def get_order_status(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        raise NotImplementedError("Amazon API integration required for get_order_status")

    def get_shipping_info(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        raise NotImplementedError("Amazon API integration required for get_shipping_info")

    def get_policy(self, merchant_id: str, policy_type: str) -> Optional[Dict]:
        raise NotImplementedError("Amazon API integration required for get_policy")


class ERPAdapter(MerchantDataAdapter):
    """ERP 系统适配器骨架。"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def get_product_price(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        raise NotImplementedError("ERP integration required for get_product_price")

    def get_inventory(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        raise NotImplementedError("ERP integration required for get_inventory")

    def get_order_status(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        raise NotImplementedError("ERP integration required for get_order_status")

    def get_shipping_info(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        raise NotImplementedError("ERP integration required for get_shipping_info")

    def get_policy(self, merchant_id: str, policy_type: str) -> Optional[Dict]:
        raise NotImplementedError("ERP integration required for get_policy")


def get_platform_adapter(platform_name: str) -> MerchantDataAdapter:
    platform_key = platform_name.strip().lower()
    if platform_key == "taobao":
        return TaobaoAdapter()
    if platform_key == "jd":
        return JDAdapter()
    if platform_key == "amazon":
        return AmazonAdapter()
    if platform_key == "erp":
        return ERPAdapter()
    raise ValueError(f"Unsupported platform adapter: {platform_name}")


class MockMerchantAdapter(MerchantDataAdapter):
    """Mock adapter for development and testing.
    Uses in-memory data to simulate e-commerce platform responses.
    """

    def __init__(self):
        # Mock data - in real implementation, this would connect to actual APIs
        self.mock_data = {
            "merchant_a": {
                "products": {
                    "《三体》": {
                        "price": {"price": 35.00, "currency": "CNY"},
                        "inventory": {"quantity": 20, "status": "in_stock"}
                    },
                    "《Java编程思想》": {
                        "price": {"price": 89.00, "currency": "CNY"},
                        "inventory": {"quantity": 5, "status": "low_stock"}
                    },
                    "《百年孤独》": {
                        "price": {"price": 68.00, "currency": "CNY"},
                        "inventory": {"quantity": 15, "status": "in_stock"}
                    }
                },
                "orders": {
                    "ORDER001": {
                        "status": "shipped",
                        "tracking_number": "SF123456789",
                        "estimated_delivery": "2026-05-05"
                    },
                    "ORDER002": {
                        "status": "delivered",
                        "tracking_number": "ZTO987654321",
                        "estimated_delivery": "2026-04-28"
                    },
                    "ORDER123": {
                        "status": "processing",
                        "tracking_number": "YT555666777",
                        "estimated_delivery": "2026-05-02"
                    }
                },
                "policies": {
                    "return": {
                        "title": "退货政策",
                        "description": "7天无理由退货，商品完好即可申请退款",
                        "condition": "自收货之日起7天内，商品无破损、无使用迹象"
                    },
                    "shipping": {
                        "title": "运费信息",
                        "description": "订单满 50 元免运费，不满 50 元运费 5 元",
                        "delivery_time": "一般 2-3 个工作日送达，偏远地区可能延长"
                    },
                    "warranty": {
                        "title": "售后保障",
                        "description": "所有图书享受 30 天内非人为损坏的保修服务",
                        "contact": "客服电话:400-100-1000"
                    },
                    "refund": {
                        "title": "退款政策",
                        "description": "退货确认后 3-5 个工作日内原路返款",
                        "detail": "金额到账后会通知消费者，如超期未到账请联系客服"
                    }
                }
            }
        }

    def get_product_price(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        merchant_data = self.mock_data.get(merchant_id, {})
        products = merchant_data.get("products", {})
        product_data = products.get(product_id, {})
        return product_data.get("price")

    def get_inventory(self, merchant_id: str, product_id: str) -> Optional[Dict]:
        merchant_data = self.mock_data.get(merchant_id, {})
        products = merchant_data.get("products", {})
        product_data = products.get(product_id, {})
        return product_data.get("inventory")

    def get_order_status(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        merchant_data = self.mock_data.get(merchant_id, {})
        orders = merchant_data.get("orders", {})
        return orders.get(order_id)

    def get_shipping_info(self, merchant_id: str, order_id: str) -> Optional[Dict]:
        # For mock, return basic shipping info if order exists
        order_status = self.get_order_status(merchant_id, order_id)
        if order_status:
            return {
                "carrier": "SF Express",
                "tracking_url": f"https://sf.com/track/{order_status.get('tracking_number')}",
                "shipping_cost": 5.00
            }
        return None

    def get_policy(self, merchant_id: str, policy_type: str) -> Optional[Dict]:
        """Get merchant policy information"""
        merchant_data = self.mock_data.get(merchant_id, {})
        policies = merchant_data.get("policies", {})
        return policies.get(policy_type)


# Global adapter instance - in production, this would be configured per merchant
mock_adapter = MockMerchantAdapter()