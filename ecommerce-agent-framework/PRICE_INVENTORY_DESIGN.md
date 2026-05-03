# 💰 [深度解析] 价格与库存查询：向量库 vs 实时数据库设计

> 你的问题触及了 e-commerce RAG 系统的**核心架构困境**——如何在语义智能和数据准确性之间取舍。

## 📖 问题回顾

**你的理解完全正确**：
> "价格和库存浮动很大，问这些问题的时候是不是需要在别的地方查询"

**回答**：✅ **是的！** 这正是系统需要采用**混合架构**的核心原因。

---

## 🔍 第一部分：为什么不能把价格/库存放向量库里？

### 1️⃣ **向量库的本质是什么？**

向量库（如 ChromaDB）的核心功能是**语义相似性搜索**：

```
原始文本 → 嵌入模型 → 向量表示 → 余弦相似度 → 排序返回
```

**示例**：
```
用户问：「这本书现在多少钱？」

向量库做的事：
1. 把这句话转成向量
2. 在数据库中找"语义最接近"的文本块
3. 可能返回：
   - "《Java编程思想》是经典编程书籍，由 Bruce Eckel 著，..."
   - "本书涵盖 Java 核心特性，适合初级程序员..."
   - "价格：899 元（此价格来自摄取时的 CSV）"
```

**问题出现**：
- 用户问的是 **实时价格**
- 向量库返回的是 **历史价格**（可能已过期）

---

### 2️⃣ **具体的业务场景问题**

#### 场景 A：库存实时性
```
时间线：

[T0 = 2026年2月1日] 文档摄取
- CSV: 书籍 ID=101, 库存=50 本
- 向量库存储了这个数据

[T1 = 2026年2月10日] 用户询问
- 用户问：「《Java编程思想》还有货吗？」
- 向量库返回：「有 50 本」
- 实际情况：已售出 48 本，剩 2 本！
- ❌ 客户下单后收到缺货通知 → 体验极差
```

#### 场景 B：价格竞争
```
电商平台竞争激烈，价格每天变化：

[京东] 《Java编程思想》：899 元
[Amazon] 《Java编程思想》：799 元
[你的小店] 《Java编程思想》：899 元（需要降价以竞争）

如果向量库里存的是 899 元的快照：
- 聊天机器人告诉客户：899 元
- 实际官网价格：699 元（你刚刚改的）
- ❌ 用户看到聊天和官网价格不一致 → 信任度下降
```

---

### 3️⃣ **向量库对数值型数据的"失效"**

向量化的核心逻辑是**距离度量**：

```python
# 假设我们向量化价格数字
price_text = "899"  # 字符串形式

# 嵌入后的向量表示
embedding = embed_model.encode("899")  # 比如 [0.12, 0.34, ...., -0.56]

# 问题：
# embed("899") 和 embed("999") 的距离 
# 可能 = embed("899") 和 embed("青苹果") 的距离！

# 为什么？因为向量是基于"文本上下文"产生的，不是"数值大小"
```

**比喻**：
- 向量库问：「这段文字的'语义'是什么？」✅ 做得好
- 向量库问：「899 和 999 差多少？」❌ 不擅长

---

### 4️⃣ **实时更新的数据库设计**

如果你想存储可变的数据，应该用：

| 数据库类型 | 适合的场景 | 不适合的场景 |
|----------|----------|----------|
| **向量库** (ChromaDB) | 文本内容、产品描述、政策文档 | 价格、库存、订单状态 |
| **SQL 数据库** (PostgreSQL) | 精确查询、事务、实时更新 | 语义搜索、模糊匹配 |
| **缓存** (Redis) | 热点数据、实时计数 | 持久存储 |

**为什么**：
- **SQL**：支持 `WHERE price > 800` 这样的精确范围查询
- **Redis**：一读一写的速度 < 1ms，完全实时
- **向量库**：擅长 `find_similar_to("优惠的编程书")`

---

## ✅ 第二部分：如何设计混合架构？

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    用户查询入口                             │
│              "Java编程思想现在多少钱？"                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
   【1】意图识别                  【2】关键词提取
   Intent Parser              Keyword Extraction
   输出：PRODUCT_INQUIRY      输出：["价格", "Java编程思想"]
        │                          │
        └──────────────┬───────────┘
                       ▼
        【3】路由决策（Router）
        ┌──────────────────────────┐
        │ 检查关键词                 │
        │ if "价格" or "多少钱":    │
        │    → 转向 SQL 查询        │
        │ elif "内容" or "讲什么":  │
        │    → 转向向量库查询       │
        │ else:                     │
        │    → 混合查询             │
        └──────────────────────────┘
             │          │          │
    ┌────────▼──┐    ┌─▼───────┐  └────┬──────────┐
    │ SQL 查询  │    │向量库   │      │混合查询   │
    │(实时精确) │    │(语义)   │      │           │
    └────────┬──┘    └─┬───────┘      └────┬──────┘
             │         │                   │
    ┌────────▼─────────▼──────────────────▼────────┐
    │              响应生成 (LLM)                    │
    │   "《Java编程思想》现在 699 元，库存 12 本"  │
    └─────────────────────────────────────────────┘
```

---

### 系统组件详解

#### 🔹 组件 1：Router（路由决策器）

```python
# 设计思路：通过关键词和意图联合判断

class QueryRouter:
    def __init__(self):
        # 价格相关关键词
        self.price_keywords = {'价格', '多少钱', '怎么卖', '价格走势', '便宜', '打折', '成本'}
        # 库存相关关键词
        self.inventory_keywords = {'库存', '有货', '缺货', '补货', '数量', '还剩'}
        # 政策相关关键词
        self.policy_keywords = {'退货', '售后', '发货', '保修', '换货', '运费'}
        # 订单相关关键词
        self.order_keywords = {'订单', '物流', '配送', '签收', '取消订单'}
    
    def decide_source(self, user_query, intent, merchant_id):
        """
        返回数据源：sql_price, sql_inventory, vector_db, hybrid
        """
        keywords = self.extract_keywords(user_query)
        
        # 规则 1：价格查询 → SQL
        if any(kw in keywords for kw in self.price_keywords):
            return 'sql_price'
        
        # 规则 2：库存查询 → SQL（因为需要实时）
        if any(kw in keywords for kw in self.inventory_keywords):
            return 'sql_inventory'
        
        # 规则 3：政策/订单 → 向量库（这些是相对静态的）
        if any(kw in keywords for kw in self.policy_keywords):
            return 'vector_db'
        
        # 规则 4：产品描述/内容 → 向量库
        if intent == 'PRODUCT_INQUIRY':
            return 'vector_db'
        
        # 规则 5：复杂查询 → 混合
        if len(keywords) > 3:
            return 'hybrid'
        
        # 默认 → 向量库
        return 'vector_db'
```

#### 🔹 组件 2：SQL 查询器（实时数据）

```python
# 完全不同于向量库的思路

import sqlite3
from typing import Optional

class PriceInventoryDB:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
    
    def get_product_price(self, merchant_id: str, title: str) -> Optional[dict]:
        """
        精确查询：给定书名，返回实时价格
        """
        query = """
        SELECT id, title, price, stock, last_updated
        FROM products
        WHERE merchant_id = ? AND title = ?
        LIMIT 1
        """
        result = self.cursor.execute(query, (merchant_id, title)).fetchone()
        
        if result:
            return {
                'id': result[0],
                'title': result[1],
                'price': result[2],  # 实时！
                'stock': result[3],  # 实时！
                'last_updated': result[4]
            }
        return None
    
    def get_product_by_fuzzy_match(self, merchant_id: str, partial_title: str):
        """
        模糊匹配：用户可能输入 "Java编程" 而不是 "Java编程思想"
        """
        query = """
        SELECT id, title, price, stock
        FROM products
        WHERE merchant_id = ? AND title LIKE ?
        ORDER BY LENGTH(title) ASC
        LIMIT 5
        """
        # 用 LIKE 和通配符
        results = self.cursor.execute(
            query, 
            (merchant_id, f"%{partial_title}%")
        ).fetchall()
        
        return [
            {'id': r[0], 'title': r[1], 'price': r[2], 'stock': r[3]}
            for r in results
        ]
    
    def update_price(self, product_id: str, new_price: float):
        """
        实时更新价格（秒级生效）
        """
        query = "UPDATE products SET price = ?, last_updated = NOW() WHERE id = ?"
        self.cursor.execute(query, (new_price, product_id))
        self.conn.commit()
```

#### 🔹 组件 3：混合查询（语义 + 实时）

```python
class HybridRetriever:
    def __init__(self, vector_db, price_db, router):
        self.vector_db = vector_db
        self.price_db = price_db
        self.router = router
    
    async def retrieve(self, user_query: str, merchant_id: str):
        """
        混合查询：结合向量库和 SQL，给出最完整的答案
        """
        # 第 1 步：决定数据源
        source = self.router.decide_source(user_query, merchant_id)
        
        # 第 2 步：从对应的数据源查询
        if source == 'sql_price':
            # 提取书名（NER 或实体识别）
            book_title = extract_entity(user_query, entity_type='PRODUCT')
            price_info = self.price_db.get_product_price(merchant_id, book_title)
            return {
                'type': 'price',
                'data': price_info,
                'source': 'sql_real_time'
            }
        
        elif source == 'vector_db':
            # 从向量库查询（语义）
            results = await self.vector_db.query(
                embedding=embed(user_query),
                merchant_id=merchant_id,
                n_results=3
            )
            return {
                'type': 'semantic',
                'data': results,
                'source': 'vector_store'
            }
        
        elif source == 'hybrid':
            # 同时查询两个源
            book_title = extract_entity(user_query, entity_type='PRODUCT')
            
            # 并行查询（加速）
            price_task = asyncio.create_task(
                self.price_db.get_product_price_async(merchant_id, book_title)
            )
            semantic_task = asyncio.create_task(
                self.vector_db.query(embed(user_query), merchant_id)
            )
            
            price_data, semantic_data = await asyncio.gather(
                price_task, semantic_task
            )
            
            return {
                'type': 'hybrid',
                'price_data': price_data,
                'semantic_data': semantic_data,
                'sources': ['sql_real_time', 'vector_store']
            }
```

---

## 🏗️ 第三部分：项目中具体的实现路线

### 当前状态

| 组件 | 状态 | 备注 |
|------|------|------|
| **向量库** (ChromaDB) | ✅ 100% | merchant_a 和 merchant_b 已隔离 |
| **Router** | 🔴 0% | 需要实装 |
| **SQL 数据库** | 🔴 0% | 需要初始化（建议用 SQLite） |
| **混合检索层** | 🔴 0% | 需要编写和测试 |
| **API 集成** | 🔄 30% | routes_chat.py 框架已有，待集成 |

### 建议实现顺序（优先级）

#### Phase 1（Mar 15）- 高优先级
1. ✅ **建立 SQL Schema**
   ```sql
   CREATE TABLE products (
       id TEXT PRIMARY KEY,
       merchant_id TEXT,
       title TEXT,
       price REAL,
       stock INT,
       last_updated TIMESTAMP,
       FOREIGN KEY (merchant_id) REFERENCES merchants(id)
   );
   
   CREATE INDEX idx_merchant_title ON products(merchant_id, title);
   ```

2. ✅ **实现 Router（关键词路由）**
   - 提取价格/库存关键词
   - 提取产品实体名称
   - 决定数据源

3. ✅ **集成到 routes_chat.py**
   ```python
   @router.post("/query")
   async def chat_query(request: ChatRequest):
       # 第 1 步：意图识别
       intent = IntentParser.parse(request.user_query)
       
       # 第 2 步：路由决策（新增）
       source = router.decide_source(request.user_query, intent)
       
       # 第 3 步：获取数据
       if source == 'sql_price':
           data = price_db.query_price(...)
       else:
           data = vector_db.query(...)
       
       # 第 4 步：生成回答
       return generate_response(data, intent)
   ```

#### Phase 2（Apr 20）- 中优先级
1. **实现完整的模糊匹配**（用户可能输入错误的产品名）
2. **添加缓存层**（Redis）以加速重复查询
3. **实现价格/库存更新 API**

#### Phase 3（May 1+）- 集成测试
1. 编写新的测试用例（包含价格问题）
2. 在 217 个 Ground Truth 用例中添加 50+ 个价格/库存相关的问题
3. 运行对比实验

---

## 📊 你错过的技术细节（vendor 相关）

你提到"merc拼错了"，我猜你是想说 **"Merchant"**：

**Merchant** = 商家（在我们的系统中）

```python
# 系统中的"商家"概念

merchant_a = 商家 A（比如"中关村图书店"）
merchant_b = 商家 B（比如"线上书城"）

# 数据隔离
data/merchants/merchant_a/products/books.csv
data/merchants/merchant_b/products/novels.csv

# 向量库隔离
ChromaDB collection: "merchant_a"
ChromaDB collection: "merchant_b"

# SQL 隔离
SELECT * FROM products WHERE merchant_id = 'merchant_a'
```

**为什么需要商家隔离**？
- 多个商家共用一个系统
- 但彼此数据必须看不到
- 每个商家有自己的产品库、价格、政策

---

## 🎯 总结：你现在应该做什么

### 1️⃣ 理解核心设计
- ✅ 你已经理解了向量库的局限性（很好！）
- ✅ 识别了价格/库存的实时需求

### 2️⃣ 下一步建议
- 📝 在 `experiments/test_cases_ground_truth_extended.json` 中查看已有的测试用例
- 📝 观察 `tests/test_e2e_workflow.py` 中是否已有价格查询的测试
- 💻 如果有兴趣，可以先抽取一部分 `products/books_catalog.csv` 数据，建立 SQLite 原型

### 3️⃣ Mar 15 前的准备
- 不需要你立即实现；我会在集成 routes_chat.py 时处理
- 但理解这个设计能帮助你在 code review 时提出建议

---

## 📚 参考资源

- [ChromaDB 文档](https://docs.trychroma.com/) - 向量库用法
- [SQLite 教程](https://www.sqlitetutorial.net/) - 实时数据存储
- [RAG System Design](https://arxiv.org/abs/2407.16125) - 学术背景

---

**文档作者**：系统架构团队  
**最后更新**：2026 年 2 月 24 日  
**版本**：1.0
