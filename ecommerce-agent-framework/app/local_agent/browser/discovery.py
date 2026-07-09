"""DOM selector discovery helpers for browser-backed adapters."""

from __future__ import annotations

from typing import Any, Dict


DISCOVERY_SCRIPT = r"""
() => {
  const attrNames = [
    "data-testid",
    "data-test",
    "data-qa",
    "data-message-id",
    "data-conversation-id",
    "aria-label",
    "placeholder",
    "id"
  ];

  function isVisible(el) {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== "hidden" &&
      style.display !== "none" &&
      rect.width > 0 &&
      rect.height > 0;
  }

  function cssEscape(value) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(value);
    return String(value).replace(/["\\]/g, "\\$&");
  }

  function selectorFor(el) {
    const tag = el.tagName.toLowerCase();
    for (const attr of attrNames) {
      const value = el.getAttribute(attr);
      if (!value) continue;
      if (attr === "id") return `#${cssEscape(value)}`;
      return `${tag}[${attr}="${cssEscape(value)}"]`;
    }

    const classNames = Array.from(el.classList || []).filter(Boolean).slice(0, 3);
    if (classNames.length) {
      return `${tag}.${classNames.map(cssEscape).join(".")}`;
    }

    const parent = el.parentElement;
    if (!parent) return tag;
    const siblings = Array.from(parent.children).filter((item) => item.tagName === el.tagName);
    const index = siblings.indexOf(el) + 1;
    return `${selectorFor(parent)} > ${tag}:nth-of-type(${index})`;
  }

  function textOf(el) {
    return (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
  }

  function candidate(el, reason, score = 1) {
    return {
      selector: selectorFor(el),
      tag: el.tagName.toLowerCase(),
      text: textOf(el).slice(0, 200),
      reason,
      score
    };
  }

  const all = Array.from(document.querySelectorAll("body *")).filter(isVisible);
  const inputCandidates = all
    .filter((el) => {
      const tag = el.tagName.toLowerCase();
      return tag === "textarea" ||
        (tag === "input" && !["hidden", "checkbox", "radio"].includes((el.getAttribute("type") || "text").toLowerCase())) ||
        el.getAttribute("contenteditable") === "true";
    })
    .map((el) => candidate(el, "reply_input", 8));

  const sendCandidates = all
    .filter((el) => {
      const text = textOf(el);
      const tag = el.tagName.toLowerCase();
      return ["发送", "Send", "send"].includes(text) && ["button", "div", "span", "a"].includes(tag);
    })
    .map((el) => candidate(el, "send_button", 10));

  const messageCandidates = all
    .filter((el) => {
      const text = textOf(el);
      const tag = el.tagName.toLowerCase();
      if (!text || text.length > 160) return false;
      if (["button", "input", "textarea", "svg", "path"].includes(tag)) return false;
      if (el.children.length > 4) return false;
      return true;
    })
    .map((el) => {
      const text = textOf(el);
      let score = 1;
      if (/你好|您好|在吗|stock|return|refund|订单|商品/.test(text)) score += 3;
      if (el.getAttribute("data-message-id")) score += 5;
      if (el.getAttribute("data-conversation-id")) score += 3;
      return candidate(el, "buyer_or_sent_message", score);
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 30);

  const productCandidates = all
    .filter((el) => {
      const text = textOf(el);
      if (!text || text.length > 240) return false;
      return /商品|SKU|库存|现货|¥|￥|price|stock|sku/i.test(text);
    })
    .map((el) => candidate(el, "product_context", 3))
    .slice(0, 30);

  const rootCandidates = all
    .filter((el) => {
      const text = textOf(el);
      return text.includes("发送") && (text.includes("会话") || text.includes("商品") || text.includes("订单"));
    })
    .map((el) => candidate(el, "chat_root", 4))
    .slice(0, 10);

  return {
    url: window.location.href,
    title: document.title,
    counts: {
      inputs: inputCandidates.length,
      send_buttons: sendCandidates.length,
      messages: messageCandidates.length,
      product_contexts: productCandidates.length,
      roots: rootCandidates.length
    },
    candidates: {
      root: rootCandidates,
      reply_input: inputCandidates,
      send_button: sendCandidates,
      messages: messageCandidates,
      product_fields: productCandidates
    }
  };
}
"""


def discover_selectors(page: Any) -> Dict[str, Any]:
    return page.evaluate(DISCOVERY_SCRIPT)
