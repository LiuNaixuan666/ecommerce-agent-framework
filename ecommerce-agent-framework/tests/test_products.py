"""Tests for product store, schemas, and API routes."""

import json
import tempfile
import os
import io
import csv

from fastapi.testclient import TestClient
from app.main import app
from app.storage.product_store import ProductStore


client = TestClient(app)


def make_temp_store(tmp_path):
    return ProductStore(str(tmp_path / "product_store.json"))


class TestProductStore:
    def test_create_and_get(self, tmp_path):
        store = make_temp_store(tmp_path)
        record = store.create({
            "merchant_id": "default",
            "platform": "pinduoduo",
            "title": "测试商品",
            "price": 99.0,
            "stock": 10,
            "source_type": "manual",
        })
        assert record["id"] is not None
        assert record["title"] == "测试商品"
        assert record["price"] == 99.0

        fetched = store.get(record["id"])
        assert fetched is not None
        assert fetched["title"] == "测试商品"

    def test_update(self, tmp_path):
        store = make_temp_store(tmp_path)
        record = store.create({"merchant_id": "default", "title": "旧标题"})
        updated = store.update(record["id"], {"title": "新标题", "price": 50.0})
        assert updated is not None
        assert updated["title"] == "新标题"
        assert updated["price"] == 50.0

    def test_delete(self, tmp_path):
        store = make_temp_store(tmp_path)
        record = store.create({"merchant_id": "default", "title": "待删除"})
        assert store.delete(record["id"]) is True
        assert store.get(record["id"]) is None
        assert store.delete("nonexistent") is False

    def test_list_filtering(self, tmp_path):
        store = make_temp_store(tmp_path)
        store.create({"merchant_id": "m1", "platform": "pinduoduo", "title": "A"})
        store.create({"merchant_id": "m1", "platform": "xianyu", "title": "B"})
        store.create({"merchant_id": "m2", "platform": "pinduoduo", "title": "C"})

        r = store.list(merchant_id="m1")
        assert r["total"] == 2

        r = store.list(merchant_id="m1", platform="pinduoduo")
        assert r["total"] == 1
        assert r["products"][0]["title"] == "A"

    def test_bulk_create_imports_new(self, tmp_path):
        store = make_temp_store(tmp_path)
        result = store.bulk_create([
            {"merchant_id": "default", "title": "商品1", "price": 10.0},
            {"merchant_id": "default", "title": "商品2", "price": 20.0},
        ])
        assert result["imported_count"] == 2
        assert result["skipped_count"] == 0

    def test_bulk_create_updates_existing_by_sku(self, tmp_path):
        store = make_temp_store(tmp_path)
        store.create({"merchant_id": "default", "platform": "pinduoduo", "title": "原版", "sku": "SKU-001"})
        result = store.bulk_create([
            {"merchant_id": "default", "platform": "pinduoduo", "title": "更新版", "sku": "SKU-001", "price": 99.0},
        ])
        assert result["imported_count"] == 1
        # Should have updated the existing one (title changed)
        all_products = store.list()
        titles = [p["title"] for p in all_products["products"]]
        assert "更新版" in titles

    def test_bulk_create_sku_dedup_respects_platform(self, tmp_path):
        """Same SKU on different platforms should NOT be treated as duplicate."""
        store = make_temp_store(tmp_path)
        store.create({"merchant_id": "default", "platform": "pinduoduo", "title": "拼多多原版", "sku": "SKU-001"})
        result = store.bulk_create([
            {"merchant_id": "default", "platform": "xianyu", "title": "闲鱼版本", "sku": "SKU-001", "price": 99.0},
        ])
        # Should create new (not update existing), imported_count = 1
        assert result["imported_count"] == 1
        all_products = store.list()
        assert len(all_products["products"]) == 2  # Both products coexist

    def test_persists_and_reloads_from_json(self, tmp_path):
        path = tmp_path / "product_store.json"
        store = ProductStore(str(path))
        record = store.create({
            "merchant_id": "default",
            "platform": "pinduoduo",
            "title": "持久化商品",
            "sku": "PERSIST-001",
        })

        reloaded = ProductStore(str(path))
        fetched = reloaded.get(record["id"])

        assert path.exists()
        assert fetched is not None
        assert fetched["title"] == "持久化商品"
        assert fetched["sku"] == "PERSIST-001"

    # ------------------------------------------------------------------
    # find_by_context tests
    # ------------------------------------------------------------------

    def test_find_by_platform_product_id(self, tmp_path):
        store = make_temp_store(tmp_path)
        store.create({
            "merchant_id": "default", "platform": "pinduoduo",
            "title": "镜子", "platform_product_id": "pdd-001",
        })
        matched = store.find_by_context(
            merchant_id="default", platform="pinduoduo",
            platform_product_id="pdd-001",
        )
        assert matched is not None
        assert matched["title"] == "镜子"

    def test_find_by_sku(self, tmp_path):
        store = make_temp_store(tmp_path)
        store.create({
            "merchant_id": "default", "platform": "pinduoduo",
            "title": "桌子", "sku": "SKU-888",
        })
        matched = store.find_by_context(
            merchant_id="default", platform="pinduoduo",
            sku="SKU-888",
        )
        assert matched is not None
        assert matched["title"] == "桌子"

    def test_find_by_title_exact(self, tmp_path):
        store = make_temp_store(tmp_path)
        store.create({
            "merchant_id": "default", "platform": "pinduoduo",
            "title": "立式全身镜",
        })
        matched = store.find_by_context(
            merchant_id="default", platform="pinduoduo",
            title="立式全身镜",
        )
        assert matched is not None
        assert matched["title"] == "立式全身镜"

    def test_find_by_title_normalized_contains(self, tmp_path):
        store = make_temp_store(tmp_path)
        store.create({
            "merchant_id": "default", "platform": "pinduoduo",
            "title": "北欧风立式全身镜 白色",
        })
        matched = store.find_by_context(
            merchant_id="default", platform="pinduoduo",
            title="立式全身镜",
        )
        assert matched is not None
        assert "镜" in matched["title"]

    def test_find_different_platform_not_cross_contaminated(self, tmp_path):
        store = make_temp_store(tmp_path)
        store.create({
            "merchant_id": "default", "platform": "pinduoduo",
            "title": "拼多多商品", "platform_product_id": "PDD-001",
        })
        store.create({
            "merchant_id": "default", "platform": "xianyu",
            "title": "闲鱼商品", "platform_product_id": "XY-001",
        })
        # 在闲鱼下搜索拼多多的 platform_product_id
        matched = store.find_by_context(
            merchant_id="default", platform="xianyu",
            platform_product_id="PDD-001",
        )
        assert matched is None

    def test_find_by_product_id(self, tmp_path):
        store = make_temp_store(tmp_path)
        record = store.create({
            "merchant_id": "default", "platform": "pinduoduo",
            "title": "通过ID查找",
        })
        matched = store.find_by_context(
            merchant_id="default", product_id=record["id"],
        )
        assert matched is not None
        assert matched["title"] == "通过ID查找"

    def test_find_by_context_no_match_returns_none(self, tmp_path):
        store = make_temp_store(tmp_path)
        store.create({
            "merchant_id": "default", "platform": "pinduoduo",
            "title": "某商品",
        })
        matched = store.find_by_context(
            merchant_id="default", platform="pinduoduo",
            sku="NONEXISTENT-SKU",
        )
        assert matched is None

    def test_find_by_context_match_first_priority(self, tmp_path):
        """product_id has higher priority than platform_product_id."""
        store = make_temp_store(tmp_path)
        store.create({
            "id": "fixed-id", "merchant_id": "default", "platform": "pinduoduo",
            "title": "正确商品", "platform_product_id": "PP-001",
        })
        store.create({
            "merchant_id": "default", "platform": "pinduoduo",
            "title": "错误商品", "platform_product_id": "PP-001",
        })
        matched = store.find_by_context(
            merchant_id="default", platform="pinduoduo",
            product_id="fixed-id", platform_product_id="PP-001",
        )
        assert matched is not None
        assert matched["title"] == "正确商品"


class TestProductAPI:
    def test_create_product_api(self):
        response = client.post("/api/products", json={
            "merchant_id": "default",
            "platform": "pinduoduo",
            "title": "API测试商品",
            "price": 88.0,
            "stock": 5,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "API测试商品"
        assert data["price"] == 88.0
        assert data["id"] is not None

    def test_list_products_api(self):
        # Create one
        client.post("/api/products", json={"title": "列表测试"})
        response = client.get("/api/products?merchant_id=default")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "products" in data

    def test_get_product_404(self):
        response = client.get("/api/products/nonexistent-id")
        assert response.status_code == 404

    def test_delete_product(self):
        resp = client.post("/api/products", json={"title": "待删除"})
        pid = resp.json()["id"]
        response = client.delete(f"/api/products/{pid}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

    def test_import_csv(self):
        # Create a CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["title", "price", "stock", "sku", "category"])
        writer.writerow(["CSV商品1", "29.9", "100", "CSV-001", "电子产品"])
        writer.writerow(["CSV商品2", "59.9", "50", "CSV-002", "家居用品"])
        output.seek(0)

        response = client.post(
            "/api/products/import-csv?merchant_id=default&platform=pinduoduo",
            files={"file": ("test.csv", output.getvalue(), "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] >= 2

    def test_csv_without_title_skipped(self):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["price", "stock"])
        writer.writerow(["29.9", "100"])  # no title
        output.seek(0)

        response = client.post(
            "/api/products/import-csv",
            files={"file": ("empty.csv", output.getvalue(), "text/csv")},
        )
        assert response.status_code == 400  # no valid products

    def test_scrape_endpoint_returns_task(self):
        response = client.post("/api/products/scrape", json={
            "merchant_id": "default",
            "platform": "pinduoduo",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] is not None
        assert data["status"] == "pending"

    def test_scrape_status_endpoint(self):
        # First create a task
        resp = client.post("/api/products/scrape", json={
            "merchant_id": "default",
            "platform": "pinduoduo",
        })
        task_id = resp.json()["task_id"]

        # Poll status
        resp2 = client.get(f"/api/products/scrape/{task_id}/status")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["task_id"] == task_id
        assert data["status"] in ("pending", "running", "completed", "error")

    def test_scrape_status_404(self):
        response = client.get("/api/products/scrape/nonexistent-task-id")
        assert response.status_code == 404
