"""
Connectors package for merchant data adapters.
"""

from .base import (
    MerchantDataAdapter,
    MockMerchantAdapter,
    mock_adapter,
    TaobaoAdapter,
    JDAdapter,
    AmazonAdapter,
    ERPAdapter,
    get_platform_adapter,
)

__all__ = [
    "MerchantDataAdapter",
    "MockMerchantAdapter",
    "mock_adapter",
    "TaobaoAdapter",
    "JDAdapter",
    "AmazonAdapter",
    "ERPAdapter",
    "get_platform_adapter",
]