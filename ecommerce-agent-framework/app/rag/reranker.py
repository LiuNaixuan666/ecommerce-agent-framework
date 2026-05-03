from typing import List, Tuple


class Reranker:
    """可选的检索结果重排序器。"""

    def rerank(self, results: List[Tuple[dict, float]], query: str) -> List[Tuple[dict, float]]:
        """当前默认直接返回现有结果，保留扩展点。"""
        return results

