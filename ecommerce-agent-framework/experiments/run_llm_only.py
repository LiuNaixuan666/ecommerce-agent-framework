"""
run_llm_only.py

对比实验 1：仅 LLM 对比基线
功能：使用大语言模型直接回答查询，不使用任何检索或知识增强
对应论文：Section 5.1 - 基线对比（LLM Only）

工作流：
  Query → LLM → Response
  
评估指标：
  - Accuracy: 是否能正确回答
  - Faithfulness: 是否有虚构内容
  - Hallucination Rate: 幻觉比率
  - Latency: 响应延迟
"""

import json
import time
import os
from typing import List, Dict
from datetime import datetime
from openai import OpenAI


class LLMOnlyBaseline:
    """仅 LLM 的基线模型"""
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
    
    def answer_query(self, query: str, merchant_context: str = None) -> Dict:
        """
        使用 LLM 直接回答查询，不使用检索
        
        Args:
            query: 用户查询
            merchant_context: （可选）商家背景信息
            
        Returns:
            {
                "response": str,
                "latency": float,
                "tokens_used": int,
                "model": str
            }
        """
        
        system_prompt = """
        You are a helpful customer service representative for an e-commerce book store.
        Answer customer queries to the best of your ability.
        """
        
        if merchant_context:
            system_prompt += f"\nContext: {merchant_context}"
        
        start_time = time.time()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            end_time = time.time()
            
            return {
                "response": response.choices[0].message.content,
                "latency": end_time - start_time,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "model": self.model,
                "status": "success"
            }
        
        except Exception as e:
            return {
                "response": f"Error: {str(e)}",
                "latency": time.time() - start_time,
                "tokens_used": 0,
                "model": self.model,
                "status": "error",
                "error": str(e)
            }


def run_llm_only_experiment(
    ground_truth_file: str,
    output_csv: str = "data/evaluation_sets/results_llm_only.csv",
    sample_size: int = None
) -> Dict:
    """
    运行仅 LLM 的对比实验
    
    Args:
        ground_truth_file: Ground Truth JSON 文件路径
        output_csv: 输出 CSV 文件路径
        sample_size: 样本大小（None 表示使用全部）
        
    Returns:
        {
            "total_cases": int,
            "accuracy": float,
            "faithfulness": float,
            "hallucination_rate": float,
            "avg_latency": float,
            "results": List[Dict]
        }
    """
    
    # 加载 Ground Truth 数据
    print(f"📖 加载 Ground Truth 数据从 {ground_truth_file}...")
    with open(ground_truth_file, 'r', encoding='utf-8') as f:
        ground_truth = json.load(f)
    
    if sample_size:
        ground_truth = ground_truth[:sample_size]
    
    print(f"✅ 加载了 {len(ground_truth)} 个测试用例\n")
    
    # 初始化模型
    baseline = LLMOnlyBaseline()
    
    # 运行实验
    results = []
    latencies = []
    
    print("🚀 开始实验...\n")
    
    for idx, test_case in enumerate(ground_truth, 1):
        query = test_case.get("question")
        merchant = test_case.get("merchant", "merchant_a")
        expected_answer = test_case.get("expected_answer", "")
        intent = test_case.get("intent_label", "UNKNOWN")
        difficulty = test_case.get("difficulty", "UNKNOWN")
        
        # 获取 LLM 回答
        result_dict = baseline.answer_query(query, merchant_context=f"You are serving {merchant}")
        response = result_dict["response"]
        latency = result_dict["latency"]
        
        # 简单的评估（在实际应用中应该更复杂）
        # 这里使用启发式评估
        accuracy = _estimate_accuracy(response, expected_answer)
        faithfulness = _estimate_faithfulness(response)
        
        latencies.append(latency)
        
        result_entry = {
            "case_id": test_case.get("id"),
            "query": query,
            "merchant": merchant,
            "intent": intent,
            "difficulty": difficulty,
            "expected_answer": expected_answer,
            "generated_response": response,
            "accuracy": accuracy,
            "faithfulness": faithfulness,
            "latency_ms": latency * 1000,
            "model": baseline.model,
            "timestamp": datetime.now().isoformat()
        }
        
        results.append(result_entry)
        
        # 打印进度
        if idx % 10 == 0:
            print(f"  [{idx}/{len(ground_truth)}] 已处理 {idx} 个用例")
    
    print(f"\n✅ 实验完成！处理了 {len(ground_truth)} 个用例\n")
    
    # 计算统计指标
    avg_accuracy = sum(r["accuracy"] for r in results) / len(results)
    avg_faithfulness = sum(r["faithfulness"] for r in results) / len(results)
    hallucination_rate = 1.0 - avg_faithfulness
    avg_latency = sum(latencies) / len(latencies)
    
    print("📊 实验结果统计：")
    print(f"  总用例数：{len(ground_truth)}")
    print(f"  平均准确度：{avg_accuracy:.2%}")
    print(f"  平均忠实度：{avg_faithfulness:.2%}")
    print(f"  幻觉率：{hallucination_rate:.2%}")
    print(f"  平均延迟：{avg_latency*1000:.2f} ms")
    
    # 保存结果
    _save_results_to_csv(results, output_csv)
    print(f"\n✅ 结果已保存到 {output_csv}")
    
    return {
        "total_cases": len(ground_truth),
        "accuracy": avg_accuracy,
        "faithfulness": avg_faithfulness,
        "hallucination_rate": hallucination_rate,
        "avg_latency": avg_latency,
        "results": results
    }


def _estimate_accuracy(response: str, expected_answer: str) -> float:
    """启发式方法评估准确度"""
    if not response or response.startswith("Error"):
        return 0.0
    
    # 简单的关键词匹配
    expected_keywords = set(expected_answer.lower().split())
    response_keywords = set(response.lower().split())
    
    if not expected_keywords:
        return 0.5
    
    overlap = len(expected_keywords & response_keywords)
    return min(overlap / len(expected_keywords), 1.0)


def _estimate_faithfulness(response: str) -> float:
    """启发式方法评估忠实度（检测虚构）"""
    if not response:
        return 0.5
    
    # 检查是否包含表示不确定性的词汇
    uncertain_indicators = ["我不确定", "我不知道", "可能", "也许", "据说", "据信"]
    
    for indicator in uncertain_indicators:
        if indicator in response:
            return 0.8  # 包含不确定性词汇，忠实度较高
    
    # 检查是否包含具体数据
    import re
    has_specific_data = bool(re.search(r'\¥\d+|价格.*\d+|库存.*\d+', response))
    
    if has_specific_data:
        return 0.9  # 包含具体数据，更可能忠实
    
    return 0.7  # 默认中等忠实度


def _save_results_to_csv(results: List[Dict], output_path: str):
    """保存结果到 CSV 文件"""
    import csv
    
    # 确保目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if not results:
        print(f"⚠️ 没有结果可保存")
        return
    
    # 获取字段名
    fieldnames = list(results[0].keys())
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


if __name__ == "__main__":
    # 运行实验
    ground_truth_path = "data/evaluation_sets/test_cases_ground_truth_extended.json"
    output_path = "data/evaluation_sets/results_llm_only.csv"
    
    print("=" * 60)
    print("🔬 对比实验 1：仅 LLM 基线")
    print("=" * 60 + "\n")
    
    # 运行实验（演示用途，仅处理 10 个样本）
    results = run_llm_only_experiment(
        ground_truth_file=ground_truth_path,
        output_csv=output_path,
        sample_size=10  # 演示用，实际应处理全部
    )
    
    print("\n" + "=" * 60)
    print("✅ 实验完成")
    print("=" * 60)
