"""Product management API routes.

Provides endpoints for importing products via CSV, listing products,
and triggering platform scraping.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import re
import sys
import threading
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.models.product_schemas import (
    ProductCreate,
    ProductImportResult,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.storage.product_store import product_store

# Lazy import for the scraper registry — we only touch it at runtime.
from app.local_agent.scrapers.registry import (
    get_product_scraper,
    is_product_scraper_supported,
    list_supported_product_scraper_platforms,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/products", tags=["products"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _record_to_response(record: Dict[str, Any]) -> dict:
    return ProductResponse(**record).model_dump()


# ---------------------------------------------------------------------------
# List / Query
# ---------------------------------------------------------------------------


@router.get("", response_model=ProductListResponse)
async def list_products(
    merchant_id: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    shop_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List products with optional merchant_id / platform filtering."""
    result = product_store.list(
        merchant_id=merchant_id or "default",
        platform=platform,
        shop_id=shop_id,
        limit=limit,
        offset=offset,
    )
    return {
        "total": result["total"],
        "products": [_record_to_response(p) for p in result["products"]],
    }


@router.get("/{product_id}")
async def get_product(product_id: str):
    """Get a single product by ID."""
    record = product_store.get(product_id)
    if not record:
        raise HTTPException(status_code=404, detail="商品不存在")
    return _record_to_response(record)


# ---------------------------------------------------------------------------
# Create / Update / Delete
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def create_product(payload: ProductCreate):
    """Create a single product manually."""
    record = product_store.create(payload.model_dump(exclude_none=True))
    return _record_to_response(record)


@router.put("/{product_id}")
async def update_product(product_id: str, payload: ProductUpdate):
    """Update product fields."""
    record = product_store.update(
        product_id,
        payload.model_dump(exclude_none=True),
    )
    if not record:
        raise HTTPException(status_code=404, detail="商品不存在")
    return _record_to_response(record)


@router.delete("/{product_id}")
async def delete_product(product_id: str):
    """Delete a product."""
    ok = product_store.delete(product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"status": "deleted", "id": product_id}


@router.post("/batch-delete")
async def batch_delete_products(payload: Dict[str, List[str]]):
    """Batch delete products by IDs."""
    ids = payload.get("ids", [])
    deleted = 0
    for pid in ids:
        if product_store.delete(pid):
            deleted += 1
    return {"status": "ok", "deleted": deleted}


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------


@router.post("/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    merchant_id: str = Form("default"),
    platform: str = Form("unknown"),
):
    """Import products from a CSV file.

    Expected CSV columns:
        title (required), price, stock, sku, category, description,
        platform_product_id, shop_id, image_url, source_url
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("gbk")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV 文件为空或格式不正确")

    records: List[Dict[str, Any]] = []
    for row in reader:
        title = (row.get("title") or "").strip()
        if not title:
            continue
        record = {
            "merchant_id": merchant_id,
            "platform": platform,
            "title": title,
            "sku": (row.get("sku") or "").strip() or None,
            "category": (row.get("category") or "").strip() or None,
            "price": _parse_float(row.get("price")),
            "stock": _parse_int(row.get("stock")),
            "description": (row.get("description") or "").strip() or None,
            "platform_product_id": (row.get("platform_product_id") or "").strip() or None,
            "shop_id": (row.get("shop_id") or "").strip() or None,
            "image_url": (row.get("image_url") or "").strip() or None,
            "source_url": (row.get("source_url") or "").strip() or None,
            "source_type": "csv_import",
        }
        records.append(record)

    if not records:
        raise HTTPException(status_code=400, detail="CSV 中没有有效的商品数据")

    result = product_store.bulk_create(records)
    return ProductImportResult(**result)


def _parse_float(val: Optional[str]) -> Optional[float]:
    if val is None:
        return None
    val = str(val).strip()
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _parse_int(val: Optional[str]) -> Optional[int]:
    if val is None:
        return None
    val = str(val).strip()
    if not val:
        return None
    try:
        return int(float(val))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Scrape tasks — in-memory tracking
# ---------------------------------------------------------------------------

_scrape_tasks: Dict[str, Dict[str, Any]] = {}
_scrape_lock = threading.Lock()


@router.post("/scrape")
async def scrape_products(payload: Dict[str, Any]):
    """Trigger platform product scraping.

    Product scraping reuses the product page opened by the local platform
    workbench. It must not launch a second persistent browser context with the
    same profile, otherwise Chromium/Edge profile locking can close the browser
    immediately with exitCode=21.
    """
    merchant_id = payload.get("merchant_id", "default")
    platform = payload.get("platform", "pinduoduo")

    # Validate platform via scraper registry before creating a task
    if not is_product_scraper_supported(platform):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "platform_scraper_not_supported",
                "message": f"Product scraping is not supported for platform: {platform}",
                "supported_platforms": list_supported_product_scraper_platforms(),
            },
        )

    shop_id = payload.get("shop_id")
    max_pages = payload.get("max_pages", 3)
    list_only = payload.get("list_only", False)  # 只抓列表, 不进详情

    task_id = str(uuid.uuid4())
    task_entry: Dict[str, Any] = {
        "task_id": task_id,
        "status": "pending",
        "merchant_id": merchant_id,
        "platform": platform,
        "shop_id": shop_id,
        "progress": "",
        "product_count": 0,
        "error": None,
        "list_only": list_only,
        "products": [],  # 用于 list_only 模式暂存商品数据
    }
    with _scrape_lock:
        _scrape_tasks[task_id] = task_entry

    # Run scraper in background thread so the API responds immediately
    thread = threading.Thread(
        target=_run_scrape,
        args=(task_id, merchant_id, platform, max_pages, list_only),
        daemon=True,
    )
    thread.start()

    return {
        "task_id": task_id,
        "status": "pending",
        "message": f"商品抓取任务已创建（平台: {platform}），正在后台运行",
    }


@router.get("/scrape/{task_id}/status")
async def scrape_status(task_id: str):
    """Check the status of a scrape task."""
    with _scrape_lock:
        task = _scrape_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": task.get("progress", ""),
        "product_count": task.get("product_count", 0),
        "error": task.get("error"),
        "products": task.get("products", []),
        "enriched_products": task.get("enriched_products", []),
    }


@router.post("/scrape-details")
async def scrape_product_details(payload: Dict[str, Any]):
    """Scrape detail pages for selected products.

    Receives a list of products (with platform_product_id) and enters
    each product's detail page to extract description and other fields.
    Runs asynchronously — returns a task_id to poll status.
    """
    merchant_id = payload.get("merchant_id", "default")
    platform = payload.get("platform", "pinduoduo")
    products = payload.get("products", [])
    max_detail = payload.get("max_detail", 20)

    if not products:
        raise HTTPException(status_code=400, detail="products list is empty")

    task_id = str(uuid.uuid4())
    task_entry: Dict[str, Any] = {
        "task_id": task_id,
        "status": "pending",
        "merchant_id": merchant_id,
        "platform": platform,
        "progress": "",
        "product_count": len(products),
        "error": None,
        "products": [],
        "enriched_products": [],
    }
    with _scrape_lock:
        _scrape_tasks[task_id] = task_entry

    thread = threading.Thread(
        target=_run_scrape_details,
        args=(task_id, merchant_id, platform, products, max_detail),
        daemon=True,
    )
    thread.start()

    return {
        "task_id": task_id,
        "status": "pending",
        "message": f"开始抓取 {len(products)} 个商品的详情页",
    }


def _run_scrape_details(
    task_id: str,
    merchant_id: str,
    platform: str,
    products: List[Dict[str, Any]],
    max_detail: int = 20,
) -> None:
    """Run detail scraping on the platform browser's Playwright worker thread."""
    try:
        from app.api.routes_platform_browser import _run_in_thread
        asyncio.run(
            _run_in_thread(
                _run_scrape_details_on_browser_thread,
                task_id,
                merchant_id,
                platform,
                products,
                max_detail,
            )
        )
    except Exception as exc:
        logger.exception("Detail scrape failed: %s", exc)
        _update_task(task_id, "error", error=str(exc))


def _run_scrape_details_on_browser_thread(
    task_id: str,
    merchant_id: str,
    platform: str,
    products: List[Dict[str, Any]],
    max_detail: int = 20,
) -> None:
    """Scrape detail pages for each product using the session manager's page.

    Reuses the browser already opened by the workbench — avoids profile-lock
    conflicts (exitCode=21) that happen when two Edge instances share a profile.
    """
    from app.local_agent.browser_session_manager import browser_session_manager
    import time

    # Ensure we have a products page open in the session manager
    page = browser_session_manager.ensure_page_open(platform, "products")
    if page is None:
        _update_task(task_id, "error", error="无法打开商品列表页。请先在客服工作台中打开拼多多商品页并登录。")
        return

    # Wait for list to render
    time.sleep(2)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    scraper_cls = get_product_scraper(platform)
    if scraper_cls is None:
        _update_task(task_id, "error", error=f"no scraper registered for platform: {platform}")
        return

    imported = 0
    failed = 0
    enriched = []
    scraper = None
    try:
        scraper = scraper_cls(user_data_dir="")
        # Use the session manager's page (don't create a new browser)
        # The scraper needs a reference to the page; it won't own it
        for i, p in enumerate(products[:max_detail]):
            goods_id = p.get("platform_product_id", "")
            title = p.get("title", "(unknown)")
            if not goods_id:
                enriched.append(p)
                continue

            _update_task(task_id, "running", progress=f"抓取 ({i+1}/{min(len(products), max_detail)}): {title[:20]}…")

            # Navigate directly in the session manager's page
            try:
                detail_url = f"https://mms.pinduoduo.com/goods/goods_detail?goods_id={goods_id}"
                page.goto(detail_url, wait_until="load", timeout=45000)
                time.sleep(4)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                time.sleep(2)

                # Extract detail text
                raw_text = page.evaluate("""
                    () => {
                        const main = document.querySelector('._msfe_main, ._msfe_content, #__next');
                        return main ? main.innerText.slice(0, 50000) : (document.body ? document.body.innerText.slice(0, 50000) : '');
                    }
                """)

                # Parse fields
                description = ""
                if raw_text:
                    lines = [l.strip() for l in raw_text.split("\n")]
                    for i_line, line in enumerate(lines):
                        if line == "商品描述" and i_line + 1 < len(lines):
                            description = lines[i_line + 1]
                            break
                    if not description:
                        cleaned = re.sub(r"\s+", " ", raw_text[:2000]).strip()
                        description = cleaned

                p["description"] = description

                # Import into store
                record = {
                    "merchant_id": merchant_id,
                    "platform": platform,
                    "platform_product_id": p.get("platform_product_id", ""),
                    "title": p.get("title", "(unnamed)"),
                    "price": p.get("price"),
                    "stock": p.get("stock"),
                    "sku": p.get("sku"),
                    "category": p.get("category"),
                    "image_url": p.get("image_url"),
                    "description": description,
                    "source_type": "platform_scrape",
                }
                try:
                    from app.storage.product_store import product_store
                    product_store.create(record)
                    imported += 1
                except Exception as exc:
                    logger.warning("Failed to import product %s: %s", title, exc)
                    failed += 1

            except Exception as exc:
                logger.warning("Detail scrape failed for %s: %s", title, exc)
                failed += 1

            enriched.append(p)
            time.sleep(1)

        with _scrape_lock:
            t = _scrape_tasks.get(task_id)
            if t:
                t["enriched_products"] = enriched
        _update_task(
            task_id, "completed",
            progress=f"成功导入 {imported} 个, 失败 {failed} 个" if imported else f"导入失败 {failed} 个",
            product_count=imported,
        )

    except Exception as exc:
        logger.exception("Detail scrape failed: %s", exc)
        _update_task(task_id, "error", error=str(exc))
    finally:
        try:
            if scraper is not None:
                scraper.close()
        except Exception:
            pass


# ------------------------------------------------------------------
# Background runner
# ------------------------------------------------------------------

def _run_scrape(
    task_id: str,
    merchant_id: str,
    platform: str,
    max_pages: int,
    list_only: bool = False,
) -> None:
    """Run list scraping against the already-open platform browser page."""
    try:
        from app.api.routes_platform_browser import _run_in_thread
        asyncio.run(
            _run_in_thread(
                _run_scrape_on_browser_thread,
                task_id,
                merchant_id,
                platform,
                max_pages,
                list_only,
            )
        )
    except Exception as exc:
        logger.exception("Product list scrape failed: %s", exc)
        _update_task(task_id, "error", error=str(exc))


def _run_scrape_on_browser_thread(
    task_id: str,
    merchant_id: str,
    platform: str,
    max_pages: int,
    list_only: bool = False,
) -> None:
    """Scrape the product list on the Playwright worker thread."""
    from app.local_agent.browser_session_manager import browser_session_manager

    _update_task(task_id, "running", progress="Opening product list page…")
    page = browser_session_manager.ensure_page_open(platform, "products")
    if page is None:
        _update_task(task_id, "error", error="无法打开商品列表页。请重新打开平台页面并完成登录。")
        return

    scraper_cls = get_product_scraper(platform)
    if scraper_cls is None:
        _update_task(task_id, "error", error=f"no scraper registered for platform: {platform}")
        return

    _update_task(task_id, "running", progress="Scanning products…")
    scraper = scraper_cls(user_data_dir="")
    products = scraper.scrape_existing_page(page, max_pages=max_pages, wait_after_load=5.0)
    if not products:
        current_url = getattr(page, "url", "")
        if "login" in current_url.lower():
            _update_task(task_id, "error", error="需要登录。请在浏览器窗口完成登录后重新扫描。")
        else:
            _update_task(task_id, "completed", progress="No products found", product_count=0)
        return

    if not list_only:
        _import_scraped_products(task_id, merchant_id, platform, products)
        return

    product_list = [
        {
            "platform_product_id": p.platform_product_id,
            "title": p.title,
            "price": p.price,
            "stock": p.stock,
            "sku": p.sku,
            "category": p.category,
            "description": (p.description or "")[:500],
            "image_url": p.image_url,
            "status": p.status,
        }
        for p in products
    ]
    with _scrape_lock:
        t = _scrape_tasks.get(task_id)
        if t:
            t["products"] = product_list
    _update_task(
        task_id,
        "completed",
        progress=f"Found {len(product_list)} products",
        product_count=len(product_list),
    )


def _import_scraped_products(task_id: str, merchant_id: str, platform: str, products) -> None:
    """Import scraped products into the local product store."""
    if not products:
        _update_task(task_id, "completed", progress="No products found", product_count=0)
        return

    _update_task(task_id, "running", progress=f"Importing {len(products)} products")

    imported = 0
    for p in products:
        record = {
            "merchant_id": merchant_id,
            "platform": platform,
            "platform_product_id": p.platform_product_id,
            "title": p.title,
            "price": p.price,
            "stock": p.stock,
            "sku": p.sku,
            "category": p.category,
            "image_url": p.image_url,
            "source_url": p.source_url,
            "description": p.description or None,
            "source_type": "platform_scrape",
        }
        try:
            product_store.create(record)
            imported += 1
        except Exception as exc:
            logger.warning("Failed to import product %s: %s", p.title, exc)

    _update_task(
        task_id,
        "completed",
        progress=f"Imported {imported} / {len(products)} products",
        product_count=imported,
    )


def _update_task(
    task_id: str,
    status: str,
    progress: str = "",
    product_count: int = 0,
    error: Optional[str] = None,
) -> None:
    with _scrape_lock:
        task = _scrape_tasks.get(task_id)
        if task:
            task["status"] = status
            if progress:
                task["progress"] = progress
            if product_count:
                task["product_count"] = product_count
            if error:
                task["error"] = error
