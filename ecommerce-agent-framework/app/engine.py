# engine.py
"""
系统引擎：负责初始化和协调所有核心组件

提供统一的接口来构建 IntentParser、VectorStore、Retriever 等实例。
"""

from typing import Dict, Any, Optional
from app.config import settings
from app.agent.intent_parser import IntentParser
from app.agent.uncertainty_detector import UncertaintyDetector
from app.agent.response_generator import ResponseGenerator
from app.rag.vector_store import VectorStore
from app.rag.retriever import Retriever
from app.rag.embedder import Embedder
from app.connectors.base import get_platform_adapter, MerchantDataAdapter, mock_adapter


class Engine:
    """系统引擎类"""

    def __init__(self):
        self.intent_parser: Optional[IntentParser] = None
        self.uncertainty_detector: Optional[UncertaintyDetector] = None
        self.response_generator: Optional[ResponseGenerator] = None
        self.vector_stores: Dict[str, VectorStore] = {}
        self.retrievers: Dict[str, Retriever] = {}
        self.embedder: Optional[Embedder] = None
        self.adapters: Dict[str, MerchantDataAdapter] = {}

    def initialize(self):
        """初始化所有组件"""
        # 初始化 Embedder
        self.embedder = Embedder()

        # 初始化 IntentParser
        self.intent_parser = IntentParser()

        # 初始化 UncertaintyDetector
        self.uncertainty_detector = UncertaintyDetector()

        # 初始化 ResponseGenerator
        self.response_generator = ResponseGenerator()

        # 为每个商家初始化 VectorStore 和 Retriever
        for merchant_id in self._get_merchant_ids():
            self._initialize_merchant_components(merchant_id)

        # 初始化适配器
        self._initialize_adapters()

        print("Engine initialized successfully")

    def _get_merchant_ids(self) -> list:
        """获取所有商家ID"""
        import os
        merchants_dir = os.path.join(settings.project_root, settings.data_root, settings.merchants_data_root)
        if os.path.exists(merchants_dir):
            return [d for d in os.listdir(merchants_dir) if os.path.isdir(os.path.join(merchants_dir, d))]
        return []

    def _initialize_merchant_components(self, merchant_id: str):
        """为指定商家初始化组件"""
        # VectorStore
        vector_store = VectorStore(
            merchant_id=merchant_id,
            embeddings=self.embedder.client
        )
        self.vector_stores[merchant_id] = vector_store

        # Retriever
        retriever = Retriever(
            merchant_id=merchant_id,
            embedder=self.embedder,
            top_k=settings.similarity_top_k
        )
        self.retrievers[merchant_id] = retriever

    def _initialize_adapters(self):
        """初始化适配器"""
        for merchant_id in self._get_merchant_ids():
            if settings.default_adapter_type == 'mock':
                adapter = mock_adapter
            else:
                adapter = get_platform_adapter(settings.default_adapter_type)
            self.adapters[merchant_id] = adapter

    def get_intent_parser(self) -> IntentParser:
        """获取意图解析器"""
        if not self.intent_parser:
            raise RuntimeError("Engine not initialized")
        return self.intent_parser

    def get_uncertainty_detector(self) -> UncertaintyDetector:
        """获取不确定性检测器"""
        if not self.uncertainty_detector:
            raise RuntimeError("Engine not initialized")
        return self.uncertainty_detector

    def get_response_generator(self) -> ResponseGenerator:
        """获取响应生成器"""
        if not self.response_generator:
            raise RuntimeError("Engine not initialized")
        return self.response_generator

    def get_retriever(self, merchant_id: str) -> Retriever:
        """获取指定商家的检索器"""
        if merchant_id not in self.retrievers:
            raise ValueError(f"No retriever for merchant {merchant_id}")
        return self.retrievers[merchant_id]

    def get_adapter(self, merchant_id: str) -> MerchantDataAdapter:
        """获取指定商家的适配器"""
        if merchant_id not in self.adapters:
            raise ValueError(f"No adapter for merchant {merchant_id}")
        return self.adapters[merchant_id]

    def get_vector_store(self, merchant_id: str) -> VectorStore:
        """获取指定商家的向量库"""
        if merchant_id not in self.vector_stores:
            raise ValueError(f"No vector store for merchant {merchant_id}")
        return self.vector_stores[merchant_id]


# 全局引擎实例
engine = Engine()
