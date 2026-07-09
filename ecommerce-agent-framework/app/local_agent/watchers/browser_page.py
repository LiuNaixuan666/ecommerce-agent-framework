"""Browser page watcher for web customer service pages."""

from __future__ import annotations

from datetime import datetime
import hashlib
from typing import Any, Dict, List

from app.local_agent.browser.selectors import BrowserChatSelectors
from app.local_agent.watchers.base import RawMessageEvent


class BrowserPageWatcher:
    def __init__(
        self,
        page: Any,
        platform: str,
        selectors: BrowserChatSelectors,
        default_conversation_id: str = "browser-conversation",
        latest_only: bool = True,
    ) -> None:
        self.page = page
        self.platform = platform
        self.selectors = selectors
        self.default_conversation_id = default_conversation_id
        self.latest_only = latest_only
        self.last_error: str | None = None

    def detect_app(self) -> bool:
        try:
            return self.page.locator(self.selectors.root).count() > 0
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def detect_login_status(self) -> bool:
        try:
            if self.selectors.reply_input == "__pdd_auto_reply_input__":
                return bool(self.page.evaluate(_PDD_DETECT_REPLY_INPUT))
            return self.page.locator(self.selectors.reply_input).count() > 0
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def read_events(self) -> List[RawMessageEvent]:
        events: List[RawMessageEvent] = []
        try:
            if self.selectors.buyer_messages == "__pdd_auto_buyer_messages__":
                return self._read_pdd_events()
            messages = self.page.locator(self.selectors.buyer_messages)
            total_count = messages.count()
            for index in range(total_count):
                node = messages.nth(index)
                text = node.inner_text().strip()
                if not text:
                    continue
                message_id = node.get_attribute(self.selectors.message_id_attr) or f"browser-message-{index + 1}"
                conversation_id = (
                    node.get_attribute(self.selectors.conversation_id_attr)
                    or self.default_conversation_id
                )
                events.append(
                    RawMessageEvent(
                        platform=self.platform,
                        external_conversation_id=conversation_id,
                        external_message_id=message_id,
                        text=text,
                        observed_at=datetime.now(),
                        customer_id=node.get_attribute(self.selectors.customer_id_attr),
                        customer_name=node.get_attribute(self.selectors.customer_name_attr),
                        metadata={
                            "source": "browser_page",
                            "selector": self.selectors.buyer_messages,
                            "dom_index": index,
                            "dom_count": total_count,
                            "latest_only": self.latest_only,
                        },
                    )
                )
        except Exception as exc:
            self.last_error = str(exc)
        if self.latest_only and events:
            return [events[-1]]
        return events

    def _read_pdd_events(self) -> List[RawMessageEvent]:
        raw_events = self.page.evaluate(_PDD_EXTRACT_BUYER_MESSAGES)
        events: List[RawMessageEvent] = []
        for item in raw_events or []:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            rect = item.get("rect") or {}
            digest = hashlib.sha1(
                (
                    f"{item.get('conversation_id')}|"
                    f"{rect.get('left')}|{rect.get('top')}|"
                    f"{text}"
                ).encode("utf-8")
            ).hexdigest()[:12]
            events.append(
                RawMessageEvent(
                    platform=self.platform,
                    external_conversation_id=str(item.get("conversation_id") or self.default_conversation_id),
                    external_message_id=str(item.get("message_id") or f"pdd-msg-{digest}"),
                    text=text,
                    observed_at=datetime.now(),
                    customer_name=item.get("customer_name"),
                    metadata={
                        "source": "browser_page",
                        "selector": "pdd_auto",
                        "dom_index": item.get("index"),
                        "dom_count": len(raw_events or []),
                        "latest_only": self.latest_only,
                        "rect": item.get("rect"),
                    },
                )
            )
        if self.latest_only and events:
            return [events[-1]]
        return events

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "running" if self.detect_app() else "not_detected",
            "watched_window_title": self._safe_title(),
            "last_error": self.last_error,
            "latest_only": self.latest_only,
            "current_page_url": self._safe_url(),
        }

    def _safe_title(self) -> str | None:
        try:
            title = getattr(self.page, "title")
            return title() if callable(title) else None
        except Exception as exc:
            self.last_error = str(exc)
            return None

    def _safe_url(self) -> str | None:
        try:
            url = getattr(self.page, "url")
            return url if isinstance(url, str) else (url() if callable(url) else None)
        except Exception as exc:
            self.last_error = str(exc)
            return None


_PDD_DETECT_REPLY_INPUT = r"""
() => {
  const selectors = [
    'textarea',
    'input:not([type="hidden"])',
    '[contenteditable="true"]',
    '#replyTextarea',
    '.reply-input',
    '[class*="reply"] [contenteditable="true"]'
  ];
  if (selectors.some(sel => document.querySelector(sel))) return true;
  return Array.from(document.querySelectorAll('button, div, span')).some(el => {
    const text = (el.innerText || '').trim();
    return text === '发送';
  });
}
"""


_PDD_EXTRACT_BUYER_MESSAGES = r"""
() => {
  const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1600;
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 900;
  const centerMinX = viewportWidth * 0.22;
  const centerMaxX = viewportWidth * 0.70;
  const buyerMaxX = viewportWidth * 0.48;
  const minY = 260;
  const maxY = viewportHeight - 260;
  const rejectTexts = [
    '今日接待', '全部会话', '待办任务', '加载更多会话', '当前用户来自', '商品详情页',
    '机器人', '主账号', '自动回复', '消费者多次触发相同答案', '转移会话',
    '商品推荐', '最新订单', '快捷回复', '服务助手', '发送', '邀请关注', '邀请下单',
    '小额打款', '已读', '接待中', '查看', '耐心准则', '耐心', '准则',
    '隐私号', '文字聊天', '语音', '沟通中', '客服在线接待中', '手机消息通知'
  ];

  function bubbleFor(el) {
    let node = el;
    for (let depth = 0; node && depth < 5; depth += 1, node = node.parentElement) {
      const rect = node.getBoundingClientRect();
      const style = window.getComputedStyle(node);
      const bg = style.backgroundColor || '';
      const radius = parseFloat(style.borderRadius || '0') || 0;
      const centerX = rect.left + rect.width / 2;
      const hasBubbleBg = bg && !['rgba(0, 0, 0, 0)', 'transparent'].includes(bg);
      if (
        hasBubbleBg &&
        radius >= 2 &&
        rect.width >= 20 &&
        rect.width <= 420 &&
        rect.height >= 18 &&
        rect.height <= 180 &&
        centerX >= centerMinX &&
        centerX <= buyerMaxX
      ) {
        return { node, rect };
      }
    }
    return null;
  }

  function visible(el, rect) {
    const style = window.getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none' &&
      rect.width > 8 && rect.height > 8 && rect.top >= minY && rect.bottom <= maxY;
  }

  function isLeafText(el) {
    const text = (el.innerText || '').trim();
    if (!text || text.length > 300) return false;
    if (rejectTexts.some(item => text.includes(item))) return false;
    const uiRejectPattern = /(\u7ea0\u9519|\u81ea\u52a8\u56de\u590d|\u4e0b\u4e00\u6b65|\u673a\u5668\u4eba|\u4e3b\u8d26\u53f7|\u590d\u5236|\u67e5\u770b|\u5df2\u8bfb|\u63a5\u5f85\u4e2d|\u6062\u590d\u63a5\u5f85|\u6682\u505c\u63a5\u5f85|\u670d\u52a1\u7528\u8bed|\u4e86\u89e3\u66f4\u591a)/;
    if (uiRejectPattern.test(text)) return false;
    if (/^-/.test(text)) return false;
    if (/[：:]\s*$/.test(text)) return false;
    if (/^\d{1,3}$/.test(text)) return false;
    if (/^\d+(\.\d+)?\s*(%|元)?$/.test(text)) return false;
    const childTextCount = Array.from(el.children || []).filter(child => (child.innerText || '').trim()).length;
    return childTextCount <= 1;
  }

  const candidates = [];
  const elements = Array.from(document.querySelectorAll('div, span, p'));
  elements.forEach((el, index) => {
    const text = (el.innerText || '').trim();
    if (!isLeafText(el)) return;
    const bubble = bubbleFor(el);
    if (!bubble) return;
    const rect = bubble.rect;
    if (!visible(el, rect)) return;
    if (rect.height < 20) return;
    if (rect.width > 260 && rect.height < 30) return;
    const centerX = rect.left + rect.width / 2;
    if (centerX < centerMinX || centerX > centerMaxX) return;
    if (centerX > buyerMaxX) return;
    if (text.includes('\n') && text.split('\n').length > 3) return;
    candidates.push({
      index,
      text,
      message_id: el.getAttribute('data-message-id') || el.getAttribute('data-id') || null,
      conversation_id: el.getAttribute('data-conversation-id') || location.hash || location.pathname,
      customer_name: null,
      rect: {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      }
    });
  });

  const deduped = [];
  const seen = new Set();
  for (const item of candidates.sort((a, b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left)) {
    const key = `${item.text}|${item.rect.top}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
  }
  return deduped.slice(-20);
}
"""

# Override the first PDD extractor with a broader heuristic. The PDD page's
# class names are unstable, so this uses geometry plus text filtering instead
# of brittle CSS selectors.
_PDD_EXTRACT_BUYER_MESSAGES = r"""
() => {
  const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1600;
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 900;
  const centerMinX = viewportWidth * 0.22;
  const centerMaxX = viewportWidth * 0.70;
  const buyerMaxX = viewportWidth * 0.58;
  const minY = 300;
  const maxY = viewportHeight - 120;
  const rejectTexts = [
    '今日接待', '全部会话', '待办任务', '加载更多会话', '当前用户来自', '商品详情页',
    '机器人未找到对应的回复', '点击添加', '消费者多次触发相同答案', '转移会话',
    '商品推荐', '最新订单', '快捷回复', '服务助手', '发送', '邀请关注', '邀请下单',
    '小额打款', '已读', '接待中', '查看', '尊重准则', '耐心准则', '同理心准则',
    '隐私号', '文字聊天', '语音', '沟通中', '客服在线接待中', '手机消息通知',
    '恢复接待', '立即恢复接待', '暂停接待', '机器人', '主账号',
    '本店铺体验分', '同排行', '去开启', '今天不再提示', '以上数据', '部分数据',
    '提示', '预览说明书', '客服用语', '了解更多', '必须体现', '禁止', '规则'
  ];

  function visible(el, rect) {
    const style = window.getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none' &&
      rect.width > 8 && rect.height > 8 &&
      rect.top >= minY && rect.bottom <= maxY &&
      rect.left >= centerMinX && rect.left <= centerMaxX;
  }

  function isMessageText(el) {
    const text = (el.innerText || '').trim();
    if (!text || text.length > 80) return false;
    if (text.length <= 1) return false;
    if (rejectTexts.some(item => text.includes(item))) return false;
    const uiRejectPattern = /(\u7ea0\u9519|\u81ea\u52a8\u56de\u590d|\u4e0b\u4e00\u6b65|\u673a\u5668\u4eba|\u4e3b\u8d26\u53f7|\u590d\u5236|\u67e5\u770b|\u5df2\u8bfb|\u63a5\u5f85\u4e2d|\u6062\u590d\u63a5\u5f85|\u6682\u505c\u63a5\u5f85|\u670d\u52a1\u7528\u8bed|\u4e86\u89e3\u66f4\u591a)/;
    if (uiRejectPattern.test(text)) return false;
    if (/^-/.test(text)) return false;
    if (/[：:]\s*$/.test(text)) return false;
    if (/^\d{1,3}$/.test(text)) return false;
    if (/^\d+(\.\d+)?\s*(%|元|人|条)?$/.test(text)) return false;
    if (/^\d{4}年\d{2}月\d{2}日/.test(text)) return false;
    if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(text)) return false;
    if (/^https?:\/\//.test(text)) return false;
    if (text.includes('\n') && text.split('\n').filter(Boolean).length > 2) return false;
    const childTexts = Array.from(el.children || []).map(child => (child.innerText || '').trim()).filter(Boolean);
    if (childTexts.some(childText => childText === text)) return false;
    return childTexts.length <= 1;
  }

  function messageBoxFor(el) {
    let best = null;
    for (let node = el, depth = 0; node && depth < 5; depth += 1, node = node.parentElement) {
      const rect = node.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      if (
        rect.width >= 16 &&
        rect.width <= 520 &&
        rect.height >= 14 &&
        rect.height <= 180 &&
        centerX >= centerMinX &&
        centerX <= buyerMaxX &&
        rect.top >= minY &&
        rect.bottom <= maxY
      ) {
        best = rect;
      }
    }
    return best || el.getBoundingClientRect();
  }

  const candidates = [];
  const elements = Array.from(document.querySelectorAll('div, span, p, pre'));
  elements.forEach((el, index) => {
    const text = (el.innerText || '').trim();
    if (!isMessageText(el)) return;
    const rect = messageBoxFor(el);
    if (!visible(el, rect)) return;
    if (rect.height < 20) return;
    if (rect.width > 260 && rect.height < 30) return;
    const centerX = rect.left + rect.width / 2;
    if (centerX < centerMinX || centerX > centerMaxX || centerX > buyerMaxX) return;
    candidates.push({
      index,
      text,
      message_id: el.getAttribute('data-message-id') || el.getAttribute('data-id') || null,
      conversation_id: el.getAttribute('data-conversation-id') || location.hash || location.pathname,
      customer_name: null,
      rect: {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      }
    });
  });

  const deduped = [];
  const seen = new Set();
  for (const item of candidates.sort((a, b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left)) {
    const key = `${item.text}|${item.rect.top}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
  }
  return deduped.slice(-20);
}
"""
