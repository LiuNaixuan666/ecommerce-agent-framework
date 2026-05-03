# 🚀 快速启动指南：现在能做什么

> 你问"我现在可以尝试向智能客服提问吗"？  
> 答案是：**部分可以** 👇

---

## 📊 快速状态表

| 功能 | 能用吗 | 说明 |
|------|------|------|
| **查看系统架构** | ✅ 可以 | 所有代码已完成 |
| **运行 52 个单元测试** | ✅ 可以 | 查看测试通过情况 |
| **生成 217 个测试用例** | ✅ 可以 | 看到完整的测试数据 |
| **意图识别演示** | ✅ 可以 | 通过单元测试演示 |
| **不确定性检测演示** | ✅ 可以 | 通过单元测试演示 |
| **向 API 发送真实问题** | ⚠️ 半可以 | 框架完整，处理逻辑待集成 |
| **获得智能回答** | ❌ 不行 | 需要等待 Mar 15 |
| **问价格库存** | ❌ 不行 | 需要 SQL 数据库 + 混合路由 |

---

## 👇 5 分钟快速体验

### 第 1 步：进入项目目录

```bash
cd d:\develop_python\system\ecommerce-agent-framework
```

### 第 2 步：查看系统文件结构

```bash
# Windows PowerShell
tree /F  # 看项目的完整目录树
```

或者用 Python：
```python
import os
for root, dirs, files in os.walk('.'):
    level = root.replace('.', '').count(os.sep)
    indent = ' ' * 2 * level
    print(f'{indent}{os.path.basename(root)}/')
    sub_indent = ' ' * 2 * (level + 1)
    for file in files[:5]:  # 只显示前 5 个文件
        print(f'{sub_indent}{file}')
```

### 第 3 步：运行所有 52 个测试（3 秒钟）

```bash
python -m pytest tests/ -v --tb=short
```

**你会看到**：
```
tests/test_intent_parser.py::test_valid_response_schema PASSED     [ 2%]
tests/test_intent_parser.py::test_llm_product_inquiry PASSED       [ 4%]
...
tests/test_e2e_workflow.py::test_performance PASSED                [100%]

====== 52 passed in 1.02s ======
```

✅ **这证明了系统核心模块的完整性**

### 第 4 步：查看意图分类的工作原理

```bash
# 只运行意图解析的 13 个测试
python -m pytest tests/test_intent_parser.py -v
```

**输出示例**（你会看到这些测试通过）：
```
test_valid_response_schema     ✅ # Schema 验证成功
test_llm_product_inquiry      ✅ # 产品咨询意图识别
test_llm_policy_inquiry       ✅ # 政策咨询意图识别
test_llm_order_service        ✅ # 订单服务意图识别
test_llm_chitchat             ✅ # 闲聊意图识别
test_llm_others               ✅ # 其他意图识别
test_confidence_distribution  ✅ # 置信度分布
... (7 more)
```

### 第 5 步：查看不确定性检测的工作原理

```bash
# 运行不确定性检测的 28 个测试（最复杂的部分）
python -m pytest tests/test_uncertainty_detector.py -v
```

**这些测试验证了**：
- ✅ 检索置信度检测（5 个测试）
- ✅ 查询歧义度检测（7 个测试）
- ✅ 置信度公式计算（3 个测试）
- ✅ 不确定性判断逻辑（4 个测试）
- ✅ 澄清建议生成（3 个测试）
- 等等...

### 第 6 步：查看 Ground Truth 数据集

```bash
# 查看 217 个测试用例
python -c "
import json
with open('data/evaluation_sets/test_cases_ground_truth_extended.json') as f:
    data = json.load(f)
    print(f'总用例数: {len(data[\"cases\"])}')
    print(f'\\n分布:')
    
    # 统计意图分布
    intents = {}
    for case in data['cases']:
        intent = case['intent_label']
        intents[intent] = intents.get(intent, 0) + 1
    
    for intent, count in sorted(intents.items()):
        print(f'  {intent}: {count}')
"
```

**输出**：
```
总用例数: 217

分布:
  CHITCHAT: 27
  OTHERS: 27
  ORDER_SERVICE: 38
  POLICY_INQUIRY: 45
  PRODUCT_INQUIRY: 80
```

### 第 7 步：查看 E2E 工作流测试

```bash
# 查看完整流程的 11 个测试
python -m pytest tests/test_e2e_workflow.py -v --tb=short
```

**这个测试验证了完整流程**：
```
用户查询
  ↓
意图识别 (Intent Parser)
  ↓
知识检索 (Vector DB)
  ↓
不确定性检测 (Uncertainty Detector)
  ↓
条件分支：
  ├─ 确定 → 生成回答
  └─ 不确定 → 触发澄清
```

---

## 📖 进阶体验（可选）

### 体验 1：读一读意图分类的代码

```python
# app/agent/intent_parser.py
# 看看它是如何定义 5 种意图类型的

from app.agent.intent_parser import IntentSchema

# 可用的意图类型
schema = IntentSchema()
print(schema.allowed_intents)  # ['PRODUCT_INQUIRY', 'POLICY_INQUIRY', ...]
```

### 体验 2：读一读不确定性检测的公式

```python
# app/agent/uncertainty_detector.py
# 看看这个公式是如何工作的

# 总置信度 = 检索置信度 × (1 - 歧义度) × 意图置信度
# 如果 > 0.6：安全回答
# 如果 < 0.3：需要澄清

# 例如：
retrieval_score = 0.8      # 向量库找到了很相关的文档
query_ambiguity = 0.2      # 用户的问题比较清楚
intent_confidence = 0.9    # LLM 很确定用户的意图

total_confidence = 0.8 * (1 - 0.2) * 0.9
                 = 0.8 * 0.8 * 0.9
                 = 0.576  # < 0.6，触发澄清!
```

### 体验 3：读一读测试数据的示例

```python
# data/evaluation_sets/test_cases_ground_truth_extended.json
# 看看一个完整的测试用例

import json
with open('data/evaluation_sets/test_cases_ground_truth_extended.json') as f:
    data = json.load(f)
    first_case = data['cases'][0]
    print(json.dumps(first_case, ensure_ascii=False, indent=2))
```

**输出示例**：
```json
{
  "id": "case_001",
  "question": "《Java编程思想》的作者是谁？",
  "merchant": "merchant_a",
  "expected_answer": "Bruce Eckel",
  "intent_label": "PRODUCT_INQUIRY",
  "difficulty": "EASY",
  "entities": ["Java编程思想", "作者"],
  "source_documents": ["books_catalog.csv"],
  "price_related": false,
  "inventory_related": false
}
```

---

## ⚠️ 你能看到但还不能做的

### 试了会得到"开发中"响应

```bash
# 这个 API 还没完全联通
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "merchant_a",
    "user_query": "Java编程思想这本书讲什么？"
  }'

# 返回（当前）：
{
  "merchant_id": "merchant_a",
  "user_query": "Java编程思想这本书讲什么？",
  "response_text": "[开发中] 已收到您的查询...",
  "intent": "UNKNOWN",
  "confidence": 0.0
}
```

**为什么**？ 因为 `routes_chat.py` 中的处理逻辑还在这样的注释里：
```python
# 【第 1 阶段】意图解析 (当前阶段：placeholder)
# intent_result = IntentParser.parse(user_query)
# intent_type = intent_result["intent"]
# intent_confidence = intent_result["confidence"]
```

这些 `#TODO` 会在 **Mar 15 前**被激活。

---

## 📋 完整的"能做"清单

### ✅ 我推荐你现在就做

1. **浏览文档**（5 分钟）
   ```bash
   # 打开这些文件（用记事本或编辑器）
   FILES_REFERENCE.md          # 了解每个文件的职责
   PRICE_INVENTORY_DESIGN.md   # 了解价格库存的设计
   CURRENT_STATUS.md           # 了解系统完成度
   ```

2. **运行测试**（3 分钟）
   ```bash
   pytest tests/ -v
   ```

3. **查看测试代码**（10 分钟）
   ```bash
   # 打开这些文件，看看测试的具体内容
   tests/test_intent_parser.py
   tests/test_uncertainty_detector.py
   tests/test_e2e_workflow.py
   ```

4. **查看实现代码**（15 分钟）
   ```bash
   # 打开核心实现
   app/agent/intent_parser.py
   app/agent/uncertainty_detector.py
   app/rag/vector_store.py
   ```

5. **执行数据集生成**（1 分钟）
   ```bash
   python experiments/generate_ground_truth.py
   # 输出：data/evaluation_sets/test_cases_ground_truth_extended.json
   ```

### ⏸️ 你可以做，但目前结果是样本

1. **运行基线实验**（演示版，只处理 10 个样本）
   ```bash
   python experiments/run_llm_only.py
   python experiments/run_vanilla_rag.py
   python experiments/run_agent_rag.py
   ```

2. **查看 API 框架**（还不能真正使用）
   ```bash
   # 打开文件并阅读
   app/api/routes_chat.py
   ```

### ❌ 暂时不能做

1. **获取真实的聊天回答** → 等 Mar 15
2. **问价格库存问题** → 等 Apr（需要 SQL 集成）
3. **进行多轮对话** → 等 Apr（状态管理待实装）
4. **在生产环境部署** → 等 Jun（需要完整的对标数据）

---

## 🎯 时间表：什么时候能做完整的体验

```
现在（2 月 24 日）
├─ ✅ 查看代码 & 测试
├─ ✅ 理解系统设计
└─ ✅ 学习算法原理

    ↓

Mar 15 前的某个时间
├─ ✅ API 能接收问题
├─ ✅ 系统能识别意图
├─ ✅ 系统能进行不确定性判断
└─ ❌ 但还是不能处理价格库存

    ↓

Apr 20 前
├─ ✅ 价格库存的混合查询
├─ ✅ 多轮对话支持
└─ ✅ 澄清功能就绪

    ↓

Jun 1
├─ ✅ 完整系统上线
├─ ✅ 基准对标完成
└─ ✅ 可以部署到生产环境
```

---

## 💬 关于你的问题："我能问价格库存吗？"

**现状**：❌ 不能

**理由**：
- 向量库擅长"语义搜索"（"这本书讲什么？" → 检索描述）
- 价格库存需要"精确实时查询"（"这本书多少钱？" → SQL 查询）
- 两个系统需要通过"混合路由器"联接

**何时能**：Apr 20 左右

**如何做**：
1. 建立 SQL 数据库（已有设计文档）
2. 实装"路由器"（认出"价格"关键词，转向 SQL）
3. 新增"混合检索"层（同时用向量库 + SQL）
4. 在测试中验证（更新 217 个用例中的价格相关问题）

**详细设计**：见 [PRICE_INVENTORY_DESIGN.md](PRICE_INVENTORY_DESIGN.md) ⭐

---

## 🔗 推荐的阅读顺序

1. **了解全景** → [CURRENT_STATUS.md](CURRENT_STATUS.md) （你在这儿）
2. **了解文件** → [FILES_REFERENCE.md](FILES_REFERENCE.md) ⭐
3. **了解设计** → [PRICE_INVENTORY_DESIGN.md](PRICE_INVENTORY_DESIGN.md) ⭐⭐
4. **了解细节** → [PHASE1_SUMMARY.md](PHASE1_SUMMARY.md)

---

## 📞 快速问答

**Q: "为什么我现在不能直接问问题？"**  
A: 因为 routes_chat.py 中的处理逻辑还在代码注释里（`#TODO`），需要 Mar 15 前激活。

**Q: "既然代码都写好了，为什么不能用？"**  
A: 写好了，但没有**集成**到 API 中。就像你有一把刀和砧板，但还没接上厨房一样。

**Q: "我能自己把 #TODO 改成实际代码吗？"**  
A: 可以尝试！这是很好的学习机会。不过建议等到 Mar 中旬之后再做，因为到时候会有完整的集成指导。

**Q: "测试通过意味着系统完整了吗？"**  
A: 意味着核心**模块**完整了。但系统完整还需要把这些模块**联接**起来（API 集成、工作流编排）。

**Q: "那什么时候能想用就用？"**  
A: Jun 1 之后。现在是"部件完整，总装进行中"的状态。

---

## 🎓 如果你想深入学习

### 推荐代码阅读顺序

1. **易**：`app/models/schemas.py` - 看数据结构定义
2. **中等**：`app/agent/intent_parser.py` - 看 5 种意图如何定义
3. **中等**：`app/agent/uncertainty_detector.py` - 看置信度公式
4. **难**：`app/rag/vector_store.py` - 看商家隔离如何实现
5. **难**：`tests/test_e2e_workflow.py` - 看完整流程的单元测试

### 推荐测试阅读顺序

1. `tests/test_intent_parser.py` （简单，只是 mock LLM）
2. `tests/test_uncertainty_detector.py` （中等，涉及公式计算）
3. `tests/test_e2e_workflow.py` （复杂，涉及完整流程）

---

**最后更新**：2026 年 2 月 24 日  
**版本**：1.0  
**下一次更新**：Mar 15（API 集成完成时）
