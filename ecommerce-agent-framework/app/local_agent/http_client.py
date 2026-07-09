"""Small HTTP client used by the self-built Local Agent."""

from __future__ import annotations

import json
from typing import Any, Dict
from urllib import request


class LocalBackendClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def post_rpa_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post_json("/api/chat/rpa/message", payload)

    def post_send_result(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post_json("/api/chat/rpa/send-result", payload)

    def post_heartbeat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post_json("/api/local-agent/heartbeat", payload)

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            text = response.read().decode("utf-8")
        if not text:
            return {}
        return json.loads(text)
