"""In-memory product store with optional JSON persistence.

Follows the same pattern as RpaRuntimeStore — process-local storage
that can later be migrated to SQLite/PostgreSQL.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


DEFAULT_PRODUCT_STORE_PATH = os.path.join(
    os.getcwd(), "data", "products", "product_store.json"
)


class ProductStore:
    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._products: Dict[str, Dict[str, Any]] = {}  # keyed by product id
        self._persist_path = persist_path or DEFAULT_PRODUCT_STORE_PATH
        self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        product_id = str(uuid.uuid4())
        record = {
            "id": product_id,
            "created_at": now,
            "updated_at": now,
            **data,
        }
        self._products[product_id] = record
        self._save()
        return record

    def get(self, product_id: str) -> Optional[Dict[str, Any]]:
        return self._products.get(product_id)

    def update(self, product_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        record = self._products.get(product_id)
        if not record:
            return None
        record.update(data)
        record["updated_at"] = datetime.now().isoformat()
        self._save()
        return record

    def delete(self, product_id: str) -> bool:
        if product_id in self._products:
            del self._products[product_id]
            self._save()
            return True
        return False

    def list(
        self,
        merchant_id: Optional[str] = None,
        platform: Optional[str] = None,
        shop_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        items = list(self._products.values())
        if merchant_id:
            items = [p for p in items if p.get("merchant_id") == merchant_id]
        if platform:
            items = [p for p in items if p.get("platform") == platform]
        if shop_id:
            items = [p for p in items if p.get("shop_id") in {None, "", shop_id}]
        # Sort by created_at descending
        items.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        total = len(items)
        page = items[offset : offset + limit]
        return {"total": total, "products": page}

    def bulk_create(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        imported = 0
        skipped = 0
        errors: List[str] = []
        for i, record in enumerate(records):
            try:
                # Check duplicate by platform + platform_product_id or sku
                platform = record.get("platform")
                pid = record.get("platform_product_id")
                sku = record.get("sku")
                dup = None
                for existing in self._products.values():
                    if platform and pid and existing.get("platform") == platform and existing.get("platform_product_id") == pid:
                        dup = existing
                        break
                    if platform and sku and existing.get("platform") == platform and existing.get("sku") == sku:
                        dup = existing
                        break
                if dup:
                    # Update instead of skip
                    self.update(dup["id"], record)
                    imported += 1
                else:
                    self.create(record)
                    imported += 1
            except Exception as exc:
                errors.append(f"Row {i}: {exc}")
                skipped += 1
        self._save()
        return {"imported_count": imported, "skipped_count": skipped, "errors": errors}

    # ------------------------------------------------------------------
    # Context-based matching (used by workflow to match page_context)
    # ------------------------------------------------------------------

    def find_by_context(
        self,
        merchant_id: str,
        platform: str | None = None,
        product_id: str | None = None,
        platform_product_id: str | None = None,
        sku: str | None = None,
        title: str | None = None,
        shop_id: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a product record matching the given context clues.

        Matching priority (returns on first match):
        1.  Local ``product_id``
        2.  ``platform + platform_product_id``
        3.  ``platform + sku``
        4.  ``platform + title`` exact match (after normalization)
        5.  ``platform + title`` normalised-contains match

        Returns ``None`` when nothing matches.
        """
        if merchant_id:
            candidates = [
                p for p in self._products.values()
                if p.get("merchant_id") == merchant_id
            ]
        else:
            candidates = list(self._products.values())
        if shop_id:
            candidates = [p for p in candidates if p.get("shop_id") in {None, "", shop_id}]

        # 1. product_id
        if product_id:
            for p in candidates:
                if p.get("id") == product_id:
                    return p

        if not platform:
            return None

        platform_candidates = [p for p in candidates if p.get("platform") == platform]

        # 2. platform_product_id
        if platform_product_id:
            for p in platform_candidates:
                if p.get("platform_product_id") == platform_product_id:
                    return p

        # 3. sku
        if sku:
            for p in platform_candidates:
                if p.get("sku") and p["sku"] == sku:
                    return p

        # 4. title exact (normalized)
        if title:
            norm_title = _normalize_text(title)
            for p in platform_candidates:
                p_title = _normalize_text(p.get("title", ""))
                if p_title == norm_title:
                    return p

            # 5. title normalized contains
            for p in platform_candidates:
                p_title = _normalize_text(p.get("title", ""))
                if norm_title and p_title and norm_title in p_title:
                    return p

        return None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_file(self) -> str:
        return self._persist_path

    def _save(self) -> None:
        path = self._persist_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(list(self._products.values()), f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        path = self._persist_file()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                for item in items:
                    pid = item.get("id")
                    if pid:
                        self._products[pid] = item
            except (json.JSONDecodeError, OSError):
                pass


# Module-level singleton
product_store = ProductStore()


def _normalize_text(value: str | None) -> str:
    """Strip whitespace and lower-case for fuzzy matching."""
    return re.sub(r"\s+", "", (value or "")).lower()
