# 人工客服回复捕捉功能设计

## 功能概述
AI自动分析人工客服的回复，识别未覆盖在知识库中的新问题，并建议添加到问答模板。

## 核心组件

### 1. 回复分析器 (app/agent/response_analyzer.py)
```python
class ResponseAnalyzer:
    def analyze_human_response(self, user_query: str, human_response: str) -> Dict:
        """
        分析人工客服回复
        返回: {
            "is_new_pattern": bool,
            "suggested_question": str,
            "suggested_answer": str,
            "confidence": float,
            "category": str
        }
        """
```

### 2. 新问答建议存储
```python
# 数据结构
suggested_qa = {
    "suggestion_id": "sug_123",
    "merchant_id": "merchant_a",
    "user_query": "如何修改收货地址？",
    "human_response": "您可以在订单详情页点击修改地址...",
    "ai_analysis": {
        "is_new": true,
        "category": "订单管理",
        "confidence": 0.85
    },
    "status": "pending",  # pending, approved, rejected
    "created_at": "2024-01-01T10:00:00Z",
    "reviewed_by": null
}
```

### 3. 商家审核界面
- 列表显示待审核的建议
- 支持一键添加/拒绝
- 分类管理建议

## 工作流程

### 1. 消息监听
- 监听平台消息流
- 识别人工客服回复

### 2. 智能分析
- 对比现有知识库
- 判断是否为新问题模式
- 生成建议的问答对

### 3. 质量过滤
- 相似度检查 (避免重复)
- 回复质量评估
- 敏感内容过滤

### 4. 商家通知
- 实时推送新建议
- 批量审核功能
- 统计报表

## 实施步骤
1. 实现回复分析器
2. 添加建议存储和管理
3. 创建商家审核界面
4. 集成到消息处理流程