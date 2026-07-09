"""Lightweight product recommendation from the local product store."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.storage.product_store import product_store


class ProductRecommender:
    """Rank locally imported products for simple buyer recommendation queries.

    This is intentionally deterministic and conservative. It does not replace
    RAG or LLM generation; it only turns the merchant's structured product data
    into evidence the workflow can safely use.
    """

    _RECOMMEND_KEYWORDS = {
        "\u63a8\u8350",  # recommend
        "\u9002\u5408",
        "\u600e\u4e48\u9009",
        "\u9009\u54ea",
        "\u54ea\u4e2a\u597d",
        "\u9884\u7b97",
        "\u4fbf\u5b9c",
        "\u8d35",
        "\u4ef7\u683c",
        "\u591a\u5c11\u94b1",
        "\u4e70\u54ea",
        "\u6709\u4ec0\u4e48",
        "\u6709\u5565",
        "\u8fd8\u6709",
        "\u522b\u7684",
        "\u5176\u4ed6",
        "\u6362\u4e00\u4e2a",
        "recommend",
        "budget",
    }

    _STOPWORDS = {
        "\u63a8\u8350",
        "\u9002\u5408",
        "\u600e\u4e48\u9009",
        "\u9009\u54ea",
        "\u54ea\u4e2a\u597d",
        "\u9884\u7b97",
        "\u4fbf\u5b9c",
        "\u4ef7\u683c",
        "\u591a\u5c11\u94b1",
        "\u4e70\u54ea",
        "\u6709\u4ec0\u4e48",
        "\u6709\u5565",
        "\u8fd8\u6709",
        "\u522b\u7684",
        "\u5176\u4ed6",
        "\u6362\u4e00\u4e2a",
        "\u4ee5\u5185",
        "\u5de6\u53f3",
        "\u4ee5\u4e0b",
        "\u4ee5\u4e0a",
        "product",
        "recommend",
        "budget",
        "price",
        "stock",
        "inventory",
    }

    def should_recommend(self, query: str) -> bool:
        lowered = (query or "").lower()
        return any(keyword in query or keyword in lowered for keyword in self._RECOMMEND_KEYWORDS)

    def recommend(
        self,
        *,
        merchant_id: str,
        query: str,
        platform: Optional[str] = None,
        shop_id: Optional[str] = None,
        limit: int = 3,
    ) -> Optional[Dict[str, Any]]:
        if not self.should_recommend(query):
            return None

        result = product_store.list(
            merchant_id=merchant_id or "default",
            platform=platform,
            shop_id=shop_id,
            limit=500,
            offset=0,
        )
        products = result.get("products", [])

        budget = self._extract_budget(query)
        terms = self._extract_terms(query)
        ranked: List[tuple[float, Dict[str, Any], List[str]]] = []

        for product in products:
            score, reasons = self._score_product(product, terms, budget)
            if score <= 0:
                continue
            ranked.append((score, product, reasons))

        ranked.sort(key=lambda item: item[0], reverse=True)
        recommendations = [
            self._serialize_product(product, reasons)
            for _, product, reasons in ranked[: max(1, limit)]
        ]
        if not recommendations:
            return None

        return {
            "recommendation_type": "product_recommendation",
            "budget": budget,
            "query_terms": terms,
            "recommendations": recommendations,
        }

    def _extract_budget(self, query: str) -> Optional[float]:
        patterns = [
            r"(?:\u9884\u7b97|\u4e0d\u8d85\u8fc7|\u4ee5\u5185|\u4ee5\u4e0b|\u4f4e\u4e8e|\u5c0f\u4e8e|\u5c11\u4e8e)\s*[\uffe5\u00a5]?\s*(\d+(?:\.\d+)?)",
            r"[\uffe5\u00a5]\s*(\d+(?:\.\d+)?)\s*(?:\u4ee5\u5185|\u4ee5\u4e0b|\u5de6\u53f3)?",
            r"(\d+(?:\.\d+)?)\s*(?:\u5143|\u5757|rmb|RMB)\s*(?:\u4ee5\u5185|\u4ee5\u4e0b|\u5de6\u53f3)?",
        ]
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    return None
        return None

    def _extract_terms(self, query: str) -> List[str]:
        terms: List[str] = []
        for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9_-]{2,}", query or ""):
            token = token.strip().lower()
            if not token or token in self._STOPWORDS:
                continue
            if re.fullmatch(r"\d+(?:\.\d+)?", token):
                continue
            terms.append(token)
        return list(dict.fromkeys(terms))[:8]

    def _score_product(
        self,
        product: Dict[str, Any],
        terms: List[str],
        budget: Optional[float],
    ) -> tuple[float, List[str]]:
        title = str(product.get("title") or "")
        category = str(product.get("category") or "")
        description = str(product.get("description") or "")
        haystack = f"{title} {category} {description}".lower()
        score = 0.0
        reasons: List[str] = []

        for term in terms:
            if term in haystack:
                score += 4.0 if term in title.lower() else 2.0
                reasons.append(f"\u5339\u914d\u9700\u6c42\uff1a{term}")

        price = self._to_float(product.get("price"))
        if budget is not None and price is not None:
            if price <= budget:
                score += 3.0
                reasons.append(f"\u4ef7\u683c {price:g} \u5728\u9884\u7b97 {budget:g} \u5185")
            else:
                over_ratio = (price - budget) / max(budget, 1.0)
                if over_ratio <= 0.15:
                    score += 0.8
                    reasons.append(f"\u4ef7\u683c {price:g} \u7565\u9ad8\u4e8e\u9884\u7b97")
                else:
                    score -= 4.0

        stock = self._to_float(product.get("stock"))
        if stock is not None and stock > 0:
            score += 1.0
            reasons.append("\u6709\u5e93\u5b58")
        elif stock == 0:
            score -= 2.0

        if not terms and budget is not None and price is not None and price <= budget:
            score += 1.0
        if not terms and budget is None:
            score += 0.5

        return score, list(dict.fromkeys(reasons))[:3]

    def _serialize_product(self, product: Dict[str, Any], reasons: List[str]) -> Dict[str, Any]:
        return {
            "product_id": product.get("id"),
            "title": product.get("title"),
            "platform": product.get("platform"),
            "shop_id": product.get("shop_id"),
            "sku": product.get("sku"),
            "price": product.get("price"),
            "stock": product.get("stock"),
            "category": product.get("category"),
            "description": product.get("description"),
            "source_url": product.get("source_url"),
            "reasons": reasons,
        }

    def _to_float(self, value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
