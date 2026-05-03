from typing import List
from pydantic import BaseModel, Field
from app.llm.factory import get_llm
from app.llm.openai_client import OpenAIClient
import json


# 定义意图识别的输出结构（用于论文展示你的 Schema 设计）
class IntentSchema(BaseModel):
    intent_label: str = Field(description="One of: PRODUCT_INQUIRY, POLICY_INQUIRY, ORDER_SERVICE, CHITCHAT, OTHERS")
    detected_entities: List[str] = Field(description="Extract book titles, authors, or order IDs mentioned.")
    confidence_score: float = Field(description="Confidence from 0.0 to 1.0")
    reasoning: str = Field(description="Brief reason for this classification")


class IntentParser:
    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    def parse(self, user_query: str) -> IntentSchema:
        system_prompt = """
        You are a high-precision Intent Classifier for a Book E-commerce platform.
        Your task is to analyze the user's query and categorize it into one of the following:
        1. PRODUCT_INQUIRY: Asking about book details, availability, or price.
        2. POLICY_INQUIRY: Asking about shipping, returns, or shop rules.
        3. ORDER_SERVICE: Checking order status, changing address, or complaints.
        4. CHITCHAT: Greetings or general talk.
        5. OTHERS: Ambiguous or out-of-scope queries.

        Output MUST be in valid JSON format.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Query: '{user_query}'"}
        ]

        kwargs = {}
        if isinstance(self.llm, OpenAIClient):
            kwargs["response_format"] = {"type": "json_object"}

        try:
            raw_content = self.llm.chat(messages, **kwargs)
            parsed_data = json.loads(raw_content)
            return IntentSchema(**parsed_data)
        except Exception as e:
            return IntentSchema(
                intent_label="OTHERS",
                detected_entities=[],
                confidence_score=0.0,
                reasoning=f"Error parsing: {str(e)}"
            )


if __name__ == "__main__":
    parser = IntentParser()
    result = parser.parse("这本《三体》现在有现货吗？几天能发货？")
    print(f"Intent: {result.intent_label}")
    print(f"Entities: {result.detected_entities}")
    print(f"Reasoning: {result.reasoning}")