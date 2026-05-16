import logging
from typing import Optional, List
from app.llm.factory import get_llm
from app.config import settings


class ResponseGenerator:
    def __init__(self, llm=None):
        self.llm = llm or get_llm()
        self.logger = logging.getLogger(__name__)

    async def generate_grounded_response(
        self,
        user_query: str,
        retrieval_results: dict,
        merchant_id: str,
    ) -> str:
        """基于检索知识和结构化信息生成回答。"""
        try:
            context_parts = []
            structured_data = retrieval_results.get("structured_data")
            if structured_data:
                context_parts.append("=== 结构化数据 ===")
                context_parts.append(self._format_structured_data(structured_data))

            documents = retrieval_results.get("documents", [])
            if documents:
                context_parts.append("=== 相关文档 ===")
                for i, doc in enumerate(documents[:3]):
                    context_parts.append(f"文档 {i+1}: {doc['content']}")
                    if doc.get("source"):
                        context_parts.append(f"来源: {doc['source']}")

            context_text = "\n\n".join(context_parts)
            system_prompt = f"""
            你是一个专业的电商客服助手。请基于提供的上下文信息回答用户问题。

            回答要求：
            1. 必须基于上下文信息回答，不得编造信息
            2. 如果上下文中有结构化数据（价格、库存等），优先使用这些准确数据
            3. 引用文档内容时，要标注来源
            4. 如果问题无法从上下文中完全回答，要明确说明
            5. 回答要友好、专业、有帮助

            上下文信息：
            {context_text}
            """

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"用户问题：{user_query}"}
            ]

            try:
                response_text = self.llm.chat(
                    messages,
                    max_tokens=settings.llm_max_tokens,
                    temperature=settings.llm_temperature,
                )
                return response_text.strip()
            except Exception as e:
                self.logger.warning(f"LLM generation failed: {e}")

            return self._generate_mock_response(user_query, structured_data, documents)

        except Exception as e:
            self.logger.exception(f"Error generating response: {e}")
            return f"抱歉，暂时无法生成回答。请稍后重试。错误：{str(e)}"

    async def generate_grounded_response_with_confidence(
        self,
        user_query: str,
        retrieval_results: dict,
        merchant_id: str,
    ) -> tuple:
        """生成回答并请求模型给出自评置信度，返回 (response_text, self_confidence)。"""
        try:
            # 复用 generate_grounded_response 的上下文构造
            context_parts = []
            structured_data = retrieval_results.get("structured_data")
            if structured_data:
                context_parts.append("=== 结构化数据 ===")
                context_parts.append(self._format_structured_data(structured_data))

            documents = retrieval_results.get("documents", [])
            if documents:
                context_parts.append("=== 相关文档 ===")
                for i, doc in enumerate(documents[:3]):
                    context_parts.append(f"文档 {i+1}: {doc['content']}")
                    if doc.get("source"):
                        context_parts.append(f"来源: {doc['source']}")

            context_text = "\n\n".join(context_parts)
            system_prompt = f"""
            你是一个专业的电商客服助手。请基于提供的上下文信息回答用户问题。

            要求：
            1) 先给出清晰、基于上下文的回答。
            2) 然后以严格的 JSON 格式返回模型对自己回答的置信度评分（字段名为 self_confidence，范围 0.0-1.0）。
               最终输出应为一个 JSON 对象，形如：{"{"}answer": "...", "self_confidence": 0.85{"}"}

            上下文信息：
            {context_text}
            """

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"用户问题：{user_query}"}
            ]

            try:
                raw = self.llm.chat(
                    messages,
                    max_tokens=settings.llm_max_tokens,
                    temperature=max(0.0, min(0.3, settings.llm_temperature)),
                )
                text = raw.strip()

                # 尝试解析 JSON
                import json, re

                try:
                    payload = json.loads(text)
                    answer = payload.get("answer") or payload.get("response") or ""
                    confidence = float(payload.get("self_confidence", 1.0))
                    return answer.strip(), max(0.0, min(1.0, confidence))
                except Exception:
                    # 尝试从文本末尾提取 JSON 对象
                    m = re.search(r"\{.*\}\s*$", text, re.S)
                    if m:
                        try:
                            payload = json.loads(m.group(0))
                            answer = text[:m.start()].strip()
                            confidence = float(payload.get("self_confidence", 1.0))
                            return answer, max(0.0, min(1.0, confidence))
                        except Exception:
                            pass

                    # 退化方案：没有 JSON，尝试从文本中找到类似数字
                    num = re.search(r"self_confidence\D*(0?\.\d+|1(?:\.0+)?)", text, re.I)
                    if num:
                        try:
                            confidence = float(num.group(1))
                            # 答案为剔除置信字段的文本
                            answer = re.sub(r"self_confidence\D*(0?\.\d+|1(?:\.0+)?)", "", text, flags=re.I).strip()
                            return answer, max(0.0, min(1.0, confidence))
                        except Exception:
                            pass

                # 最后退回：无置信度信息，返回文本并默认置信为 0.5
                return text, 0.5
            except Exception as e:
                self.logger.warning(f"LLM generation (with confidence) failed: {e}")

            return self._generate_mock_response(user_query, structured_data, documents), 0.5

        except Exception as e:
            self.logger.exception(f"Error generating response with confidence: {e}")
            return f"抱歉，暂时无法生成回答。请稍后重试。错误：{str(e)}", 0.0

    def _format_structured_data(self, data: dict) -> str:
        lines = []
        if "product_name" in data:
            lines.append(f"产品：{data['product_name']}")

        if "price" in data and data["price"]:
            price_info = data["price"]
            lines.append(f"价格：{price_info.get('price', '未知')} {price_info.get('currency', 'CNY')}")

        if "inventory" in data and data["inventory"]:
            inv_info = data["inventory"]
            status_map = {
                "in_stock": "有货",
                "low_stock": "库存紧张",
                "out_of_stock": "缺货"
            }
            status = status_map.get(inv_info.get("status", "unknown"), "未知")
            quantity = inv_info.get("quantity", "未知")
            lines.append(f"库存：{quantity} 件 ({status})")

        if "order_id" in data:
            lines.append(f"订单号：{data['order_id']}")

        if "status" in data and data["status"]:
            status_info = data["status"]
            status = status_info.get("status", "未知")
            tracking = status_info.get("tracking_number", "")
            delivery = status_info.get("estimated_delivery", "")
            lines.append(f"订单状态：{status}")
            if tracking:
                lines.append(f"快递单号：{tracking}")
            if delivery:
                lines.append(f"预计送达：{delivery}")

        if "shipping" in data and data["shipping"]:
            ship_info = data["shipping"]
            carrier = ship_info.get("carrier", "")
            cost = ship_info.get("shipping_cost", "")
            if carrier:
                lines.append(f"快递公司：{carrier}")
            if cost:
                lines.append(f"运费：{cost} 元")

        return "\n".join(lines)

    def _generate_mock_response(self, user_query: str, structured_data: Optional[dict], documents: list) -> str:
        if structured_data:
            parts = ["依据系统中的结构化信息："]
            parts.append(self._format_structured_data(structured_data))
            parts.append("\n如果您需要更多细节，请告诉我。")
            return "\n".join(parts)

        if documents:
            summary = "; \n".join([f"来自{doc.get('source', 'unknown')}的内容：{doc['content']}" for doc in documents[:2]])
            return f"我在相关文档中找到了以下信息：\n{summary}\n如果这些信息仍不能完全回答您的问题，请提供更多细节。"

        return "抱歉，我暂时无法直接回答这个问题。请提供更多上下文信息，例如商品名称或订单号。"

