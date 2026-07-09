"""Pydantic schemas for product management."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    merchant_id: str = "default"
    platform: str = "unknown"
    shop_id: Optional[str] = None
    platform_product_id: Optional[str] = None
    sku: Optional[str] = None
    title: str = Field(..., min_length=1)
    category: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    description: Optional[str] = None
    attributes_json: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    source_type: str = "manual"
    source_url: Optional[str] = None


class ProductUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    description: Optional[str] = None
    attributes_json: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    sku: Optional[str] = None


class ProductResponse(BaseModel):
    id: str
    merchant_id: str
    platform: str
    shop_id: Optional[str] = None
    platform_product_id: Optional[str] = None
    sku: Optional[str] = None
    title: str
    category: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    description: Optional[str] = None
    attributes_json: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    source_type: str
    source_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProductListResponse(BaseModel):
    total: int
    products: List[ProductResponse]


class ProductImportResult(BaseModel):
    imported_count: int
    skipped_count: int
    errors: List[str] = []


class ScrapeTaskResponse(BaseModel):
    task_id: str
    status: str = "pending"
    message: str = ""
