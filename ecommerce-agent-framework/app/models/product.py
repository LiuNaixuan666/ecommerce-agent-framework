"""Product ORM model for structured product data."""

from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, JSON
from app.models.database import Base


class Product(Base):
    """商品结构化数据表"""
    __tablename__ = "products"

    id = Column(String(36), primary_key=True)  # UUID
    merchant_id = Column(String(100), nullable=False, index=True)
    platform = Column(String(50), nullable=False, default="unknown")
    shop_id = Column(String(100), nullable=True)
    platform_product_id = Column(String(100), nullable=True, index=True)
    sku = Column(String(100), nullable=True)
    title = Column(String(500), nullable=False)
    category = Column(String(200), nullable=True)
    price = Column(Float, nullable=True)
    stock = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    attributes_json = Column(JSON, nullable=True)
    image_url = Column(String(1000), nullable=True)
    source_type = Column(String(50), default="manual")  # platform_scrape | csv_import | manual
    source_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "merchant_id": self.merchant_id,
            "platform": self.platform,
            "shop_id": self.shop_id,
            "platform_product_id": self.platform_product_id,
            "sku": self.sku,
            "title": self.title,
            "category": self.category,
            "price": self.price,
            "stock": self.stock,
            "description": self.description,
            "attributes_json": self.attributes_json,
            "image_url": self.image_url,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
