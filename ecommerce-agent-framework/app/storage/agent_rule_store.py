"""Persistent rule config store for local AI customer-service agents."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional


DEFAULT_AGENT_RULES: Dict[str, Any] = {
    "merchant_id": "default",
    "platform": "pinduoduo",
    "mode": "dry_run",
    "auto_send_low_risk": False,
    "confidence_threshold": 0.75,
    "handoff_rules": {
        "keyword": True,
        "image": True,
        "after_sale": True,
        "out_of_knowledge": True,
        "low_confidence": True,
        "timeout": True,
    },
    "sensitive_words": ["QQ", "VX", "V信", "微信", "电话", "手机号", "私下", "转账", "支付宝"],
    "handoff_keywords": ["退款", "退货", "投诉", "差评", "人工", "客服主管", "平台介入", "赔偿"],
    "timeout_seconds": 180,
    "fallback_script": "亲，请稍等，这个问题为您转接人工客服确认。",
}


class AgentRuleStore:
    def __init__(self, file_path: Optional[str] = None) -> None:
        self.file_path = file_path or os.path.join(os.getcwd(), "data", "agent_rules.json")
        self._lock = Lock()
        self._rules: Dict[str, Dict[str, Any]] = {}
        self._load()

    def get_rules(self, merchant_id: str = "default", platform: str = "pinduoduo") -> Dict[str, Any]:
        key = self._key(merchant_id, platform)
        with self._lock:
            existing = self._rules.get(key)
            if existing:
                return self._with_defaults(existing, merchant_id, platform)
            rules = self._with_defaults({}, merchant_id, platform)
            self._rules[key] = rules
            self._save_locked()
            return deepcopy(rules)

    def save_rules(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        merchant_id = payload.get("merchant_id") or "default"
        platform = payload.get("platform") or "pinduoduo"
        key = self._key(merchant_id, platform)
        with self._lock:
            merged = self._with_defaults(payload, merchant_id, platform)
            now = datetime.now().isoformat()
            existing = self._rules.get(key) or {}
            merged["created_at"] = existing.get("created_at") or now
            merged["updated_at"] = now
            self._rules[key] = merged
            self._save_locked()
            return deepcopy(merged)

    def list_rules(self, merchant_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            items = deepcopy(self._rules)
        if merchant_id:
            prefix = f"{merchant_id}:"
            items = {key: value for key, value in items.items() if key.startswith(prefix)}
        return items

    def _with_defaults(self, payload: Dict[str, Any], merchant_id: str, platform: str) -> Dict[str, Any]:
        rules = deepcopy(DEFAULT_AGENT_RULES)
        rules["merchant_id"] = merchant_id
        rules["platform"] = platform

        for key, value in payload.items():
            if key == "handoff_rules" and isinstance(value, dict):
                rules["handoff_rules"] = {**rules["handoff_rules"], **value}
            elif key in {"sensitive_words", "handoff_keywords"}:
                if isinstance(value, list) and value:
                    rules[key] = [str(item).strip() for item in value if str(item).strip()]
            elif key == "confidence_threshold":
                try:
                    rules[key] = max(0.0, min(1.0, float(value)))
                except (TypeError, ValueError):
                    pass
            elif key == "timeout_seconds":
                try:
                    rules[key] = max(30, int(value))
                except (TypeError, ValueError):
                    pass
            elif key in rules:
                rules[key] = value

        rules["mode"] = rules["mode"] if rules["mode"] in {"dry_run", "assist", "auto"} else "dry_run"
        rules["auto_send_low_risk"] = bool(rules.get("auto_send_low_risk"))
        return rules

    def _load(self) -> None:
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                self._rules = {str(key): value for key, value in data.items() if isinstance(value, dict)}
        except Exception:
            self._rules = {}

    def _save_locked(self) -> None:
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        tmp_path = f"{self.file_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(self._rules, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.file_path)

    def _key(self, merchant_id: str, platform: str) -> str:
        return f"{merchant_id or 'default'}:{platform or 'pinduoduo'}"


agent_rule_store = AgentRuleStore()
