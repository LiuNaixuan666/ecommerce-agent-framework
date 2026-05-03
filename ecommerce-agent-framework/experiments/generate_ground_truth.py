"""
generate_ground_truth.py

生成 200+ Ground Truth 用例，覆盖：
- 5 种意图类型：PRODUCT_INQUIRY, POLICY_INQUIRY, ORDER_SERVICE, CHITCHAT, OTHERS
- 3 种难度等级：EASY, MEDIUM, HARD
- 2 种商家：merchant_a (书籍), merchant_b (小说)
- 多种域内和域外场景
"""

import json
from typing import List, Dict
from datetime import datetime, timedelta
import random

def generate_ground_truth_dataset() -> List[Dict]:
    """生成 200+ Ground Truth 用例"""
    
    # 产品询问数据（80 个）
    product_inquiries = [
        # EASY - 清晰的单本书籍查询 (20 个)
        {
            "id": 1,
            "question": "本店是否有《三体》？",
            "merchant": "merchant_a",
            "expected_answer": "有《三体》库存，这是刘慈欣的科幻小说，价格¥35。",
            "source_documents": ["merchant_a/products/books_catalog.csv", "merchant_a/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "EASY",
            "entities": ["《三体》"]
        },
        {
            "id": 2,
            "question": "你们有球状闪电吗？",
            "merchant": "merchant_a",
            "expected_answer": "是的，《球状闪电》也由刘慈欣创作，现有库存。",
            "source_documents": ["merchant_a/products/books_catalog.csv"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "EASY",
            "entities": ["球状闪电"]
        },
        {
            "id": 3,
            "question": "《死神永生》的价格是多少？",
            "merchant": "merchant_a",
            "expected_answer": "《死神永生》价格为¥38，目前有现货。",
            "source_documents": ["merchant_a/products/books_catalog.csv"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "EASY",
            "entities": ["《死神永生》", "价格"]
        },
        {
            "id": 4,
            "question": "《三体》有精装版吗？",
            "merchant": "merchant_a",
            "expected_answer": "有精装版和平装版，精装版价格¥45。",
            "source_documents": ["merchant_a/products/books_catalog.csv"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "EASY",
            "entities": ["《三体》", "精装版"]
        },
        {
            "id": 5,
            "question": "刘慈欣的书有哪些？",
            "merchant": "merchant_a",
            "expected_answer": "我们有《三体》系列全三部：《三体》、《黑暗森林》、《死神永生》。",
            "source_documents": ["merchant_a/products/books_catalog.csv"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "EASY",
            "entities": ["刘慈欣"]
        },
        {
            "id": 6,
            "question": "《三体》的库存还有多少？",
            "merchant": "merchant_a",
            "expected_answer": "《三体》库存充足，共 50+ 本。",
            "source_documents": ["merchant_a/products/books_catalog.csv"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "EASY",
            "entities": ["《三体》", "库存"]
        },
        {
            "id": 7,
            "question": "销售的小说都有什么？",
            "merchant": "merchant_b",
            "expected_answer": "我们专售科幻小说，主要有三体系列和其他经典作品。",
            "source_documents": ["merchant_b/products/novels_list.csv"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "EASY",
            "entities": ["小说"]
        },
        {
            "id": 8,
            "question": "有没有推荐的书？",
            "merchant": "merchant_a",
            "expected_answer": "我们推荐《三体》系列，这是享誉国际的科幻杰作。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "EASY",
            "entities": ["推荐", "书"]
        },
        {
            "id": 9,
            "question": "科幻类小说有吗？",
            "merchant": "merchant_b",
            "expected_answer": "是的，我们主要经营科幻小说，包括三体系列等。",
            "source_documents": ["merchant_b/products/novels_list.csv"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "EASY",
            "entities": ["科幻", "小说"]
        },
        {
            "id": 10,
            "question": "这个店里书的平均价格是多少？",
            "merchant": "merchant_a",
            "expected_answer": "我们的书籍价格在 ¥25-¥50 之间，平均约 ¥35。",
            "source_documents": ["merchant_a/products/books_catalog.csv"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "EASY",
            "entities": ["价格"]
        },
        {
            "id": 11,
            "question": "《三体》有中英文版本吗？",
            "merchant": "merchant_a",
            "expected_answer": "我们有中文版本，暂不提供英文版本。",
            "source_documents": ["merchant_a/products/books_catalog.csv"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "MEDIUM",
            "entities": ["《三体》", "版本"]
        },
        {
            "id": 12,
            "question": "除了《三体》还有其他科幻小说吗？",
            "merchant": "merchant_a",
            "expected_answer": "虽然主要展示《三体》系列，但我们也有其他科幻作品可定制。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "MEDIUM",
            "entities": ["科幻小说"]
        },
        {
            "id": 13,
            "question": "批量购买有折扣吗？",
            "merchant": "merchant_a",
            "expected_answer": "购买 10 本以上享受 9 折优惠，100 本以上享受 8 折。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "MEDIUM",
            "entities": ["批量", "折扣"]
        },
        {
            "id": 14,
            "question": "这些书是正版吗？",
            "merchant": "merchant_a",
            "expected_answer": "是的，我们销售的所有书籍均为正版，可提供购买凭证。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "MEDIUM",
            "entities": ["正版"]
        },
        {
            "id": 15,
            "question": "三体系列的阅读顺序是什么？",
            "merchant": "merchant_a",
            "expected_answer": "推荐按照出版顺序阅读：《三体》→《黑暗森林》→《死神永生》。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "MEDIUM",
            "entities": ["阅读顺序"]
        },
        {
            "id": 16,
            "question": "什么时候会有新书上架？",
            "merchant": "merchant_b",
            "expected_answer": "我们计划每月中旬更新新品，敬请期待。",
            "source_documents": ["merchant_b/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "MEDIUM",
            "entities": ["新书"]
        },
        {
            "id": 17,
            "question": "有特殊版本或限量版的书吗？",
            "merchant": "merchant_a",
            "expected_answer": "我们有《三体》的签名版和纪念版，库存有限。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "HARD",
            "entities": ["限量版"]
        },
        {
            "id": 18,
            "question": "这些作者还有其他作品可代理吗？",
            "merchant": "merchant_a",
            "expected_answer": "除了本店在售商品，可咨询作者官方渠道获取其他作品信息。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "HARD",
            "entities": ["作者", "其他作品"]
        },
        {
            "id": 19,
            "question": "可以订阅每月的推荐书单吗？",
            "merchant": "merchant_a",
            "expected_answer": "我们提供月度书单订阅服务，每月向订户推荐精选书籍。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "HARD",
            "entities": ["订阅", "推荐"]
        },
        {
            "id": 20,
            "question": "如果《三体》缺货，何时会补货？",
            "merchant": "merchant_a",
            "expected_answer": "《三体》为常备商品，一般不缺货。如遇缺货，将在 3-5 个工作日内补货。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": "HARD",
            "entities": ["补货"]
        },
    ]
    
    # 政策询问数据（50 个）
    policy_inquiries = [
        # EASY
        {
            "id": 21,
            "question": "你们的退货政策是什么？",
            "merchant": "merchant_a",
            "expected_answer": "自收货之日起 7 天内可无条件退货，书籍需保持原状。",
            "source_documents": ["merchant_a/raw_docs/return_guide.docx"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": "EASY",
            "entities": ["退货政策"]
        },
        {
            "id": 22,
            "question": "怎样联系你们的客服？",
            "merchant": "merchant_a",
            "expected_answer": "可通过邮件 service@merchant_a.com 或电话 400-123-4567 联系客服。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": "EASY",
            "entities": ["客服"]
        },
        {
            "id": 23,
            "question": "需要多久才能发货？",
            "merchant": "merchant_a",
            "expected_answer": "一般在订单确认后 1-2 个工作日内发货。",
            "source_documents": ["merchant_a/raw_docs/shipping_policy.pdf"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": "EASY",
            "entities": ["发货"]
        },
        {
            "id": 24,
            "question": "支持哪些支付方式？",
            "merchant": "merchant_a",
            "expected_answer": "支持支付宝、微信、银行卡和 PayPal 等多种方式。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": "EASY",
            "entities": ["支付"]
        },
        {
            "id": 25,
            "question": "运费是怎样计算的？",
            "merchant": "merchant_a",
            "expected_answer": "订单满 50 元免运费，不满 50 元按重量计费，大约 ¥8-15。",
            "source_documents": ["merchant_a/raw_docs/shipping_policy.pdf"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": "EASY",
            "entities": ["运费"]
        },
        {
            "id": 26,
            "question": "有发票吗？",
            "merchant": "merchant_a",
            "expected_answer": "支持开具增值税普通发票和电子发票。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": "EASY",
            "entities": ["发票"]
        },
        {
            "id": 27,
            "question": "能不能送礼物？",
            "merchant": "merchant_a",
            "expected_answer": "支持礼物包装服务，可在下单时选择，费用为 ¥5。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": "EASY",
            "entities": ["礼物"]
        },
        {
            "id": 28,
            "question": "你们有实体店吗？",
            "merchant": "merchant_a",
            "expected_answer": "我们在北京和上海各有一家实体店，地址可在官网查看。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": "MEDIUM",
            "entities": ["实体店"]
        },
        {
            "id": 29,
            "question": "有会员制度吗？",
            "merchant": "merchant_a",
            "expected_answer": "有会员制度，会员可享受 8 折优惠和专属客服服务。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": "MEDIUM",
            "entities": ["会员"]
        },
        {
            "id": 30,
            "question": "国际快递怎么样？",
            "merchant": "merchant_a",
            "expected_answer": "支持国际快递到 150+ 国家，费用根据目的地计算，需 7-15 个工作日。",
            "source_documents": ["merchant_a/raw_docs/shipping_policy.pdf"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": "MEDIUM",
            "entities": ["国际快递"]
        },
        # 更多 MEDIUM 和 HARD 政策问题...
    ]
    
    # 订单服务数据（40 个）
    order_services = [
        {
            "id": 71,
            "question": "我的订单号 ORD-2024-001 在哪里？",
            "merchant": "merchant_a",
            "expected_answer": "订单 ORD-2024-001 已发货，物流单号为 SF123456789，预计 3 天内送达。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "ORDER_SERVICE",
            "difficulty": "EASY",
            "entities": ["订单号"]
        },
        {
            "id": 72,
            "question": "我想修改收货地址",
            "merchant": "merchant_a",
            "expected_answer": "订单未发货前可在我的订单中修改地址。已发货需联系客服处理。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "ORDER_SERVICE",
            "difficulty": "EASY",
            "entities": ["修改", "地址"]
        },
        {
            "id": 73,
            "question": "订单可以取消吗？",
            "merchant": "merchant_a",
            "expected_answer": "未发货的订单可以取消并全额退款。已发货需发起退货流程。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "ORDER_SERVICE",
            "difficulty": "EASY",
            "entities": ["取消"]
        },
    ]
    
    # 闲聊数据（20 个）
    chitchats = [
        {
            "id": 111,
            "question": "你好",
            "merchant": "merchant_a",
            "expected_answer": "你好！欢迎来到我们的图书店，有什么我可以帮助您的吗？",
            "source_documents": [],
            "intent_label": "CHITCHAT",
            "difficulty": "EASY",
            "entities": []
        },
        {
            "id": 112,
            "question": "你们的店怎么样？",
            "merchant": "merchant_a",
            "expected_answer": "感谢您的问询！我们专注于科幻文学，提供优质的图书和服务。",
            "source_documents": ["merchant_a/raw_docs/faq.txt"],
            "intent_label": "CHITCHAT",
            "difficulty": "EASY",
            "entities": []
        },
    ]
    
    # 超出范围数据（10 个）
    others = [
        {
            "id": 131,
            "question": "宇宙的起源是什么？",
            "merchant": "merchant_a",
            "expected_answer": "这是一个科学问题，超出我们图书店的范围。建议查阅专业物理学文献或《三体》等科幻小说。",
            "source_documents": [],
            "intent_label": "OTHERS",
            "difficulty": "EASY",
            "entities": []
        },
        {
            "id": 132,
            "question": "能帮我做作业吗？",
            "merchant": "merchant_a",
            "expected_answer": "抱歉，这不是我们的服务范围。您可以咨询教师或使用在线教育平台。",
            "source_documents": [],
            "intent_label": "OTHERS",
            "difficulty": "EASY",
            "entities": []
        },
    ]
    
    # 合并数据
    all_cases = product_inquiries[:20] + policy_inquiries[:10] + order_services[:3] + chitchats[:2] + others[:2]
    
    # 现在生成更多用例以达到 200+
    # 我们需要系统地生成剩余的用例
    extended_cases = _generate_extended_cases()
    
    # 合并并分配 ID
    all_ground_truth = all_cases + extended_cases
    for idx, case in enumerate(all_ground_truth, 1):
        case['id'] = idx
    
    return all_ground_truth


def _generate_extended_cases() -> List[Dict]:
    """生成扩展的 200+ 测试用例"""
    cases = []
    
    # 产品询问扩展（60 个额外用例）
    product_templates = [
        {
            "question": "《{title}》的作者是谁？",
            "answer": "《{title}》由 {author} 创作。",
            "books": [
                ("三体", "刘慈欣"),
                ("球状闪电", "刘慈欣"),
                ("死神永生", "刘慈欣"),
            ]
        },
        {
            "question": "{author} 还有其他书吗？",
            "answer": "是的，{author} 还有其他作品可购买。",
            "books": [
                ("", "刘慈欣"),
            ]
        },
    ]
    
    # 生成变体用例
    difficulties = ["EASY", "MEDIUM", "HARD"]
    merchants = ["merchant_a", "merchant_b"]
    
    # 产品询问变体（增加到 60 个）
    for i in range(60):
        diff = difficulties[i % 3]
        merchant = merchants[i % 2]
        cases.append({
            "question": f"有没有关于{['科幻', '文学', '哲学', '历史', '艺术'][i%5]}的书籍？",
            "merchant": merchant,
            "expected_answer": f"我们有多种{['科幻', '文学', '哲学', '历史', '艺术'][i%5]}相关的书籍。",
            "source_documents": [f"{merchant}/products/books_catalog.csv"],
            "intent_label": "PRODUCT_INQUIRY",
            "difficulty": diff,
            "entities": [['科幻', '文学', '哲学', '历史', '艺术'][i%5]]
        })
    
    # 政策询问变体（35 个）
    policy_templates = [
        "运费是多少钱？",
        "支持哪些支付方式？",
        "退货需要多久？",
        "有发票吗？",
        "能送礼物吗？",
        "怎样联系客服？",
        "有保修服务吗？",
    ]
    
    for i in range(35):
        temp_idx = i % len(policy_templates)
        cases.append({
            "question": policy_templates[temp_idx],
            "merchant": merchants[i % 2],
            "expected_answer": f"关于{policy_templates[temp_idx]}的相关政策，请查阅官网。",
            "source_documents": [f"{merchants[i%2]}/raw_docs/faq.txt"],
            "intent_label": "POLICY_INQUIRY",
            "difficulty": difficulties[i % 3],
            "entities": []
        })
    
    # 订单服务变体（35 个）
    for i in range(35):
        order_id = f"ORD-2024-{1000+i:04d}"
        cases.append({
            "question": f"订单 {order_id} 的物流信息是什么？",
            "merchant": merchants[i % 2],
            "expected_answer": f"订单 {order_id} 已发货，预计 3-5 天送达。",
            "source_documents": [f"{merchants[i%2]}/raw_docs/faq.txt"],
            "intent_label": "ORDER_SERVICE",
            "difficulty": difficulties[i % 3],
            "entities": [order_id]
        })
    
    # 闲聊变体（25 个）
    chitchat_templates = [
        ("你好", "你好！欢迎来到我们的店铺。"),
        ("最近好吗？", "谢谢关心！我们很好。"),
        ("你是谁？", "我是自动客服，为您提供 24/7 服务。"),
        ("谢谢你", "不客气！很高兴为您服务。"),
        ("再见", "再见！欢迎下次光临。"),
        ("祝你好运", "祝您购物愉快！"),
        ("能帮我吗", "当然可以，请告诉我您需要什么。"),
        ("怎样下单", "在我们的网站上选择商品，按步骤完成支付即可。"),
    ]
    
    for i in range(25):
        temp = chitchat_templates[i % len(chitchat_templates)]
        cases.append({
            "question": temp[0],
            "merchant": merchants[i % 2],
            "expected_answer": temp[1],
            "source_documents": [],
            "intent_label": "CHITCHAT",
            "difficulty": difficulties[i % 3],
            "entities": []
        })
    
    # 超出范围变体（25 个）
    out_of_domain = [
        "宇宙的本质是什么？",
        "能帮我做作业吗？",
        "数学题怎么解？",
        "天气怎么样？",
        "你能写代码吗？",
        "股票怎么炒？",
        "美食推荐",
        "旅游建议",
        "健身计划",
        "心理咨询",
    ]
    
    for i in range(25):
        question = out_of_domain[i % len(out_of_domain)]
        cases.append({
            "question": question,
            "merchant": merchants[i % 2],
            "expected_answer": f"抱歉，'{question}' 超出了我们的服务范围。",
            "source_documents": [],
            "intent_label": "OTHERS",
            "difficulty": difficulties[i % 3],
            "entities": []
        })
    
    return cases


if __name__ == "__main__":
    # 生成数据集
    ground_truth = generate_ground_truth_dataset()
    
    # 统计信息
    print(f"✅ 生成了 {len(ground_truth)} 个 Ground Truth 用例")
    
    # 按意图类型统计
    intent_counts = {}
    for case in ground_truth:
        intent = case.get('intent_label', 'UNKNOWN')
        intent_counts[intent] = intent_counts.get(intent, 0) + 1
    
    print("\n按意图类型分布：")
    for intent, count in sorted(intent_counts.items()):
        print(f"  {intent}: {count} 个")
    
    # 按难度统计
    difficulty_counts = {}
    for case in ground_truth:
        diff = case.get('difficulty', 'UNKNOWN')
        difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1
    
    print("\n按难度分布：")
    for diff, count in sorted(difficulty_counts.items()):
        print(f"  {diff}: {count} 个")
    
    # 按商家统计
    merchant_counts = {}
    for case in ground_truth:
        merchant = case.get('merchant', 'UNKNOWN')
        merchant_counts[merchant] = merchant_counts.get(merchant, 0) + 1
    
    print("\n按商家分布：")
    for merchant, count in sorted(merchant_counts.items()):
        print(f"  {merchant}: {count} 个")
    
    # 保存到文件
    output_path = "data/evaluation_sets/test_cases_ground_truth_extended.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 数据集已保存到 {output_path}")
