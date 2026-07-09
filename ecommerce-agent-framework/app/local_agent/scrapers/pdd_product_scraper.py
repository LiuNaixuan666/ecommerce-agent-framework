"""
PDD (Pinduoduo) product scraper — 从商品列表 → 商品详情 全流程抓取.

策略:
  Phase 1: 打开商品列表页 → 从 DOM 提取所有商品基本信息
  Phase 2: 逐个进入商品详情页 → 提取完整商品信息
  Phase 3: 返回结构化数据

Usage::

    python -m app.local_agent.run_pdd_scraper \\
        --user-data-dir ../../data/browser_profiles/pdd_edge \\
        --output products.json

    python -m app.local_agent.run_pdd_scraper \\
        --user-data-dir ../../data/browser_profiles/pdd_edge \\
        --headed --list-only
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ===================================================================
# 数据模型
# ===================================================================

@dataclass
class PddProduct:
    """A single product scraped from PDD."""
    platform_product_id: str
    title: str
    price: Optional[float] = None
    stock: Optional[int] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    sales_volume: Optional[int] = None
    status: Optional[str] = None
    description: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


# ===================================================================
# DOM 提取脚本 (列表页)
# ===================================================================

_EXTRACT_FROM_LIST = r"""
() => {
  const result = { rows: [], method: 'fallback', pageInfo: {} };
  result.pageInfo.url = window.location.href;
  result.pageInfo.title = document.title;

  function readRows(rows, headers, method) {
    const items = [];
    for (const row of rows) {
      if (row.querySelector('[class*="TB_pgt"]')) continue;
      const cells = Array.from(row.querySelectorAll('td, [class*="TB_td"]'));
      if (cells.length < 2) continue;

      const allText = (row.innerText || '').trim();
      const links = Array.from(row.querySelectorAll('a')).map(a => a.href || '');
      const idMatch =
        allText.match(/ID[：:]?\s*(\d{6,})/) ||
        links.join('\n').match(/[?&]goods_id=(\d{6,})/) ||
        links.join('\n').match(/[?&]id=(\d{6,})/);

      const hasImage = !!row.querySelector('img');
      if (!idMatch && !hasImage && allText.length < 20) continue;
      if (allText.includes('暂无数据') || allText.includes('没有数据')) continue;

      const item = { cells: [], headers: headers };
      cells.forEach((cell, idx) => {
        const img = cell.querySelector('img');
        item.cells.push({
          index: idx,
          text: (cell.innerText || '').trim(),
          header: headers[idx] || '',
          hasCheckbox: !!cell.querySelector('input[type="checkbox"]'),
          hasImage: !!img,
          imgSrc: img ? (img.src || '') : '',
          links: Array.from(cell.querySelectorAll('a')).map(a => a.href || ''),
        });
      });

      if (idMatch) item.goodsId = idMatch[1];
      items.push(item);
    }

    if (items.length > 0) {
      result.method = method;
      result.rows = items;
      result.pageInfo.rowsFound = items.length;
      return true;
    }
    return false;
  }

  // Current PDD goods list: normal table with headers like 商品信息 / 价格(元) / 总库存.
  const tables = Array.from(document.querySelectorAll('table'));
  for (const table of tables) {
    const headers = Array.from(table.querySelectorAll('thead th, thead [role="columnheader"]'))
      .map(th => (th.innerText || '').trim());
    const headerText = headers.join('|');
    if (!/商品信息|商品名称|价格|库存|销量/.test(headerText)) continue;

    const rows = Array.from(table.querySelectorAll('tbody tr')).filter(row => {
      return row.querySelectorAll('td').length >= 2;
    });
    if (readRows(rows, headers, 'html_table')) return JSON.stringify(result);
  }

  // Older PDD virtual table implementation.
  const tbRows = Array.from(document.querySelectorAll(
    '[class*="TB_tr"]:not(thead [class*="TB_tr"]):not([class*="TB_thead"])'
  ));
  const headerRow = document.querySelector('[class*="TB_thead"] [class*="TB_tr"], thead [class*="TB_tr"]');
  const tbHeaders = [];
  if (headerRow) {
    headerRow.querySelectorAll('th, [class*="TB_th"]').forEach(th => {
      tbHeaders.push((th.innerText || '').trim());
    });
  }
  readRows(tbRows, tbHeaders, 'TB_table');
  return JSON.stringify(result);
}
"""

# ===================================================================
# Scraper
# ===================================================================

class PddProductScraper:
    """Scrapes products from PDD merchant backend — list + detail pages."""

    GOODS_LIST_URL = "https://mms.pinduoduo.com/goods/goods_list"
    GOODS_DETAIL_URL = "https://mms.pinduoduo.com/goods/goods_detail?goods_id={}&page_num=12"

    def __init__(self, user_data_dir: str = "", page_url: str = "",
                 browser_channel: str = "msedge") -> None:
        self.user_data_dir = user_data_dir
        self.page_url = page_url or self.GOODS_LIST_URL
        self.browser_channel = browser_channel
        self._page = None
        self._context = None
        self._playwright_obj = None

    # ------------------------------------------------------------------
    # 浏览器生命周期
    # ------------------------------------------------------------------

    def _launch(self, headless: bool = True):
        if self._page is not None:
            return self._page
        from playwright.sync_api import sync_playwright
        self._playwright_obj = sync_playwright()
        pw = self._playwright_obj.__enter__()
        launch_opts = {
            "headless": headless, "channel": self.browser_channel,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if self.user_data_dir and os.path.isdir(self.user_data_dir):
            self._context = pw.chromium.launch_persistent_context(self.user_data_dir, **launch_opts)
        else:
            import tempfile
            tmp = os.path.join(tempfile.gettempdir(), f"pdd_{int(time.time())}")
            os.makedirs(tmp, exist_ok=True)
            self._context = pw.chromium.launch_persistent_context(tmp, **launch_opts)
        self._page = (self._context.pages or [self._context.new_page()])[0]
        return self._page

    def close(self):
        for obj in ('_context', '_playwright_obj'):
            try:
                if getattr(self, obj, None) is not None:
                    if obj == '_context':
                        self._context.close()
                    else:
                        self._playwright_obj.__exit__(None, None, None)
            except Exception:
                pass
        self._page = None
        self._context = None
        self._playwright_obj = None

    def navigate_to_list(self, headless: bool = True, timeout: float = 60.0) -> bool:
        page = self._launch(headless=headless)
        logger.info("导航到商品列表: %s", self.page_url)
        try:
            page.goto(self.page_url, wait_until="load", timeout=int(timeout * 1000))
        except Exception as exc:
            logger.warning("导航超时: %s", exc)
        time.sleep(3)
        from urllib.parse import urlparse
        if urlparse(page.url).path.rstrip("/") == "/login":
            logger.warning("检测到登录页!")
            return False
        try:
            page.wait_for_selector('[class*="TB_outerWrapper"], .goods-list', timeout=15000)
        except Exception:
            pass
        return True

    # ==============================================================
    # 列表页提取
    # ==============================================================

    def extract_list(self) -> List[Dict[str, Any]]:
        """从列表页 DOM 提取所有商品的基本信息。"""
        logger.info("正在从列表页提取商品数据...")
        time.sleep(3)
        raw = self._page.evaluate(_EXTRACT_FROM_LIST)
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as exc:
            logger.warning("DOM 提取失败: %s", exc)
            return []

        if data.get("rows"):
            logger.info("DOM 提取: 找到 %d 行", len(data["rows"]))
            return self._parse_table_rows(data["rows"])
        logger.warning("未找到商品数据")
        return []

    def _parse_table_rows(self, rows: List[Dict]) -> List[Dict[str, Any]]:
        """解析 PDD 商品表格行。"""
        products = []
        for row in rows:
            cells = row.get("cells", [])
            if not cells or len(cells) < 3:
                continue
            p: Dict[str, Any] = {
                "platform_product_id": "", "title": "", "price": None,
                "stock": None, "image_url": None, "sales_volume": None,
                "status": None, "source_url": "", "sku": "",
                "raw_cells": cells,
            }
            for cell in cells:
                idx = cell.get("index", -1)
                text = cell.get("text", "")
                header = cell.get("header", "").lower()
                lines = [l.strip() for l in text.split("\n") if l.strip()]

                if idx == 1 or "商品信息" in header or "商品名称" in header:
                    title_candidates = [l for l in lines
                                        if not l.startswith("ID:") and not l.startswith("商品编码:")
                                        and len(l) > 4]
                    if title_candidates:
                        p["title"] = title_candidates[0]
                    for l in lines:
                        m = re.search(r"ID[：:]?\s*(\d{8,})", l)
                        if m:
                            p["platform_product_id"] = m.group(1)
                    for l in lines:
                        m = re.search(r"商品编码[：:]?\s*(.+)", l)
                        if m:
                            p["sku"] = m.group(1).strip()
                    if cell.get("hasImage") and cell.get("imgSrc"):
                        p["image_url"] = cell["imgSrc"]
                    for link in cell.get("links", []):
                        if "goods" in link or "goods_id=" in link:
                            p["source_url"] = link
                            break
                elif "价格" in header or idx == 2:
                    for l in lines:
                        pr = self._parse_price(l)
                        if pr is not None:
                            p["price"] = pr; break
                elif "库存" in header or idx == 3:
                    for l in lines:
                        s = self._parse_int(l)
                        if s is not None:
                            p["stock"] = s; break
                elif "销量" in header or idx == 5:
                    for l in lines:
                        v = self._parse_int(l)
                        if v is not None:
                            p["sales_volume"] = v; break
                elif idx == 8 and "创建" in header:
                    for l in lines:
                        if l in ("销售中", "已下架", "已售罄", "预售"):
                            p["status"] = l

            if not p["platform_product_id"]:
                p["platform_product_id"] = row.get("goodsId", "")
            if p["title"] or p["platform_product_id"]:
                products.append(p)
        return products

    # ==============================================================
    # 详情页抓取
    # ==============================================================

    def scrape_detail_page(self, goods_id: str) -> Optional[Dict[str, Any]]:
        """导航到商品详情页, 提取结构化信息。"""
        logger.info("正在为商品 %s 获取详情数据...", goods_id)
        url = self.GOODS_DETAIL_URL.format(goods_id)
        logger.info("导航到: %s", url)
        try:
            self._page.goto(url, wait_until="load", timeout=45000)
            time.sleep(5)
            try:
                self._page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            time.sleep(3)
        except Exception as exc:
            logger.warning("导航失败: %s", exc)
            return None

        logger.info("详情页: %s", self._page.url)

        # 提取内容
        fields, images, raw_text = self._extract_detail_fields()

        # 返回列表页
        try:
            self._page.goto(self.GOODS_LIST_URL, wait_until="load", timeout=30000)
            time.sleep(2)
        except Exception:
            pass

        return {
            "goods_id": goods_id,
            "fields": fields,
            "images": images,
            "raw_text": raw_text[:3000],
        }

    def _extract_detail_fields(self):
        """从详情页提取结构化字段。"""
        raw = self._page.evaluate(r"""
            () => {
                const result = { text: '', images: [], inputs: [] };
                result.url = window.location.href;
                result.title = document.title;
                const main = document.querySelector('._msfe_main, ._msfe_content, #__next');
                result.text = main ? main.innerText.slice(0, 50000)
                                   : (document.body ? document.body.innerText.slice(0, 50000) : '');
                document.querySelectorAll('input:not([type="hidden"]), select, textarea').forEach(el => {
                    try {
                        const name = el.name || el.id || '';
                        const val = (el.value || '').slice(0, 200);
                        if (name || val) result.inputs.push({ name: name.slice(0, 50), value: val });
                    } catch(e) {}
                });
                document.querySelectorAll('img').forEach(img => {
                    if (img.width > 100 && img.src && !img.src.includes('logo') &&
                        !img.src.includes('funimg') && !img.src.includes('commimg') &&
                        !img.src.includes('genimg') && !img.src.includes('promotion') &&
                        !img.src.includes('pfile')) {
                        result.images.push({ src: img.src, w: img.width, h: img.height });
                    }
                });
                return JSON.stringify(result, null, 2);
            }
        """)
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {}

        text = data.get("text", "")
        images = data.get("images", [])
        fields = self._parse_detail_text(text)

        return fields, images, text

    @staticmethod
    def _parse_detail_text(text: str) -> Dict[str, str]:
        """从详情页文本中结构化解析字段。"""
        fields = {}
        if not text:
            return fields
        lines = text.split("\n")
        lines = [l.strip() for l in lines]

        for i, line in enumerate(lines):
            # 下一行取值 (适用于 "商品标题" "商品描述" 等独占一行key的场景)
            if line == "商品标题" and i + 1 < len(lines):
                fields["商品标题"] = lines[i + 1]
            elif line == "商品描述" and i + 1 < len(lines):
                fields["商品描述"] = lines[i + 1]
            elif line == "商品编码" and i + 1 < len(lines):
                fields["商品编码"] = lines[i + 1]
            elif line == "商品分类" and i + 1 < len(lines):
                fields["商品分类"] = lines[i + 1]
            elif line == "商品类型" and i + 1 < len(lines):
                fields["商品类型"] = lines[i + 1]
            elif line == "承诺发货时间" and i + 1 < len(lines):
                fields["承诺发货时间"] = lines[i + 1]
            elif line == "运费模板" and i + 1 < len(lines):
                fields["运费模板"] = lines[i + 1]
            elif line == "库存扣减方式" and i + 1 < len(lines):
                fields["库存扣减方式"] = lines[i + 1]
            elif line == "拼单要求" and i + 1 < len(lines):
                fields["拼单要求"] = lines[i + 1]
            elif line == "商品参考价" and i + 1 < len(lines):
                fields["商品参考价"] = lines[i + 1]

            # 布尔字段
            for bf in ("是否二手", "是否保密发货", "是否定制", "是否预售"):
                if line == bf and i + 1 < len(lines):
                    fields[bf] = lines[i + 1]

            # 从行内提取 (格式 "key value")
            if "：" in line:
                parts = line.split("：", 1)
                k, v = parts[0].strip(), parts[1].strip()
                if k and v and len(k) < 40 and len(v) < 200:
                    fields[k] = v

            # 价格库存表
            if "拼单价" in line and i + 1 < len(lines):
                next_parts = lines[i + 1].split("\t")
                if len(next_parts) >= 4:
                    fields["库存"] = next_parts[0]
                    fields["拼单价"] = next_parts[1]
                    fields["单买价"] = next_parts[2]

            # 满件折扣
            if "折" in line and "折后" in line and "满" in line:
                fields["满件折扣"] = line.strip()

            # 商品参考价
            if "商品参考价" in line:
                val = line.replace("商品参考价", "").strip()
                if val:
                    fields["商品参考价"] = val

        return {k: v for k, v in fields.items() if v}

    # ==============================================================
    # 批量详情抓取
    # ==============================================================

    def scrape_all_details(self, products: List[Dict[str, Any]], max_detail: int = 100) -> List[Dict[str, Any]]:
        enriched = []
        for i, p in enumerate(products):
            goods_id = p.get("platform_product_id", "")
            if not goods_id:
                enriched.append(p)
                continue
            if i >= max_detail:
                # Still include the product, just skip detail-page scraping
                enriched.append(p)
                continue
            detail = self.scrape_detail_page(goods_id)
            if detail:
                p["detail_info"] = detail
                # Extract a clean description from the detail text
                raw_text = (detail.get("raw_text") or "")
                fields = (detail.get("fields") or {})
                if fields.get("商品描述"):
                    p["description"] = fields["商品描述"]
                elif fields.get("商品标题"):
                    # Fallback: use raw text but cleaned up
                    cleaned = re.sub(r"\s+", " ", raw_text[:2000]).strip()
                    p["description"] = cleaned
            enriched.append(p)
        return enriched

    # ==============================================================
    # 主入口
    # ==============================================================

    def scrape(self, headless: bool = True, max_pages: int = 3,
               wait_after_load: float = 5.0, list_only: bool = False) -> List[PddProduct]:
        ok = self.navigate_to_list(headless=headless)
        if not ok:
            self.close(); return []
        if wait_after_load > 0:
            time.sleep(wait_after_load)

        raw_products = self.extract_list()
        if not raw_products:
            try:
                self._page.screenshot(path="tmp/pdd_list_debug.png")
            except Exception:
                pass
            self.close(); return []

        logger.info("列表页共提取到 %d 个商品", len(raw_products))
        products = [self._dict_to_product(p) for p in raw_products]

        if not list_only and products:
            logger.info("开始抓取详情页...")
            enriched = self.scrape_all_details([p.__dict__ for p in products])
            products = [self._dict_to_product(d) for d in enriched]

        self.close()
        return products

    def scrape_existing_page(self, page, max_pages=3, wait_after_load=5.0) -> List[PddProduct]:
        self._page = page; self._context = None; self._playwright_obj = None

        # 先导航到商品列表页 (当前页面可能是登录页/客服页/首页)
        try:
            logger.info("Navigating to goods list: %s", self.GOODS_LIST_URL)
            page.goto(self.GOODS_LIST_URL, wait_until="load", timeout=45000)
        except Exception as exc:
            logger.warning("Navigation failed: %s", exc)

        # 等待 SPA 渲染商品表格
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        if wait_after_load > 0:
            time.sleep(wait_after_load)

        # 检查当前 URL 和标题, 截调试图
        current_url = page.url
        current_title = page.title()
        logger.info("After navigation: url=%s title=%s", current_url, current_title)
        try:
            os.makedirs("tmp", exist_ok=True)
            page.screenshot(path="tmp/pdd_list_debug.png")
            logger.info("Debug screenshot saved to tmp/pdd_list_debug.png")
        except Exception as exc:
            logger.warning("Screenshot failed: %s", exc)

        # 确认是否真的到了商品列表页
        if "/goods" not in current_url and "/login" in current_url:
            logger.warning("Redirected to login page! Cannot extract products.")
            return []

        raw = self.extract_list()
        logger.info("extract_list returned %d items", len(raw))
        if not raw:
            logger.warning("No products extracted. URL=%s, title=%s", current_url, current_title)
        return [self._dict_to_product(p) for p in raw]

    def _dict_to_product(self, d: Dict) -> PddProduct:
        return PddProduct(
            platform_product_id=str(d.get("platform_product_id") or ""),
            title=str(d.get("title") or "(未命名)"),
            price=self._parse_price(d.get("price")),
            stock=self._parse_int(d.get("stock")),
            sku=str(d.get("sku") or ""),
            image_url=str(d.get("image_url") or ""),
            source_url=str(d.get("source_url") or ""),
            sales_volume=self._parse_int(d.get("sales_volume")),
            status=str(d.get("status") or ""),
            description=str(d.get("description") or ""),
            detail=d.get("detail_info"),
            raw_data=d,
        )

    @staticmethod
    def _parse_price(val):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        cleaned = re.sub(r"[¥￥,，\s元]", "", str(val))
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_int(val):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return int(val)
        cleaned = str(val).replace(",", "").replace("件", "").strip()
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None
