# config.py
"""
系统配置中心：统一管理 API keys、路径、模型参数、适配器配置等

使用 Pydantic BaseSettings 自动从环境变量加载，支持 .env 文件。
"""

import os
from typing import Optional, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置类"""

    # === API Keys ===
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY", description="OpenAI API Key for OpenAI LLM and embeddings")
    gemini_api_key: Optional[str] = Field(None, env="GEMINI_API_KEY", description="Google Gemini API Key for LLM generation")
    llm_provider: str = Field("openai", env="LLM_PROVIDER", description="LLM provider name (openai, gemini)")
    embedding_provider: str = Field("openai", env="EMBEDDING_PROVIDER", description="Embedding provider name (openai)")
    openai_model: str = Field("gpt-4o-mini", env="OPENAI_MODEL", description="Default OpenAI model for chat")
    gemini_model: str = Field("gemini-1.5-flash", env="GEMINI_MODEL", description="Default Gemini model for chat")
    openai_embedding_model: str = Field("text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL", description="OpenAI embedding model")

    # === 路径配置 ===
    project_root: str = Field(os.getcwd(), env="PROJECT_ROOT", description="Project root directory")
    data_root: str = Field("data", env="DATA_ROOT", description="Data directory relative to project root")
    merchants_data_root: str = Field("merchants", env="MERCHANTS_DATA_ROOT", description="Merchants data subdirectory")
    vector_store_root: str = Field("vector_store", env="VECTOR_STORE_ROOT", description="Vector store subdirectory per merchant")

    # === 知识摄取配置 ===
    chunk_size: int = Field(1000, env="CHUNK_SIZE", description="Text chunk size for document splitting")
    chunk_overlap: int = Field(200, env="CHUNK_OVERLAP", description="Overlap between chunks")
    max_documents_per_ingestion: int = Field(100, env="MAX_DOCUMENTS_PER_INGESTION", description="Max documents to process per ingestion")

    # === 检索配置 ===
    similarity_top_k: int = Field(5, env="SIMILARITY_TOP_K", description="Top K results for similarity search")
    retrieval_confidence_threshold: float = Field(0.3, env="RETRIEVAL_CONFIDENCE_THRESHOLD", description="Threshold for retrieval confidence")

    # === 不确定性检测配置 ===
    uncertainty_retrieval_threshold: float = Field(0.3, env="UNCERTAINTY_RETRIEVAL_THRESHOLD", description="Retrieval confidence threshold for uncertainty")
    uncertainty_query_threshold: float = Field(0.6, env="UNCERTAINTY_QUERY_THRESHOLD", description="Query ambiguity threshold")
    uncertainty_overall_threshold: float = Field(0.4, env="UNCERTAINTY_OVERALL_THRESHOLD", description="Overall confidence threshold")

    # === LLM 生成配置 ===
    llm_temperature: float = Field(0.3, env="LLM_TEMPERATURE", description="Temperature for LLM generation")
    llm_max_tokens: int = Field(500, env="LLM_MAX_TOKENS", description="Max tokens for LLM response")
    llm_timeout: int = Field(30, env="LLM_TIMEOUT", description="Timeout for LLM API calls (seconds)")

    # === 适配器配置 ===
    default_adapter_type: str = Field("mock", env="DEFAULT_ADAPTER_TYPE", description="Default adapter type (mock, taobao, jd, amazon, erp)")
    adapter_configs: Dict[str, Dict[str, Any]] = Field(default_factory=dict, env="ADAPTER_CONFIGS", description="Adapter-specific configurations")

    # === 服务器配置 ===
    host: str = Field("0.0.0.0", env="HOST", description="Server host")
    port: int = Field(8000, env="PORT", description="Server port")
    debug: bool = Field(False, env="DEBUG", description="Debug mode")
    cors_origins: list = Field(["http://localhost:3000", "http://localhost:8080"], env="CORS_ORIGINS", description="Allowed CORS origins")

    # === 其他 ===
    log_level: str = Field("INFO", env="LOG_LEVEL", description="Logging level")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 全局配置实例
settings = Settings()


def get_merchant_data_dir(merchant_id: str) -> str:
    """获取商家数据目录路径"""
    return os.path.join(settings.project_root, settings.data_root, settings.merchants_data_root, merchant_id)


def get_merchant_vector_store_dir(merchant_id: str) -> str:
    """获取商家向量库目录路径"""
    return os.path.join(get_merchant_data_dir(merchant_id), settings.vector_store_root)


def get_merchant_raw_docs_dir(merchant_id: str) -> str:
    """获取商家原始文档目录路径"""
    return os.path.join(get_merchant_data_dir(merchant_id), "raw_docs")


def get_merchant_products_dir(merchant_id: str) -> str:
    """获取商家产品目录路径"""
    return os.path.join(get_merchant_data_dir(merchant_id), "products")


def get_adapter_config(adapter_type: str) -> Dict[str, Any]:
    """获取适配器配置"""
    return settings.adapter_configs.get(adapter_type, {})


# 便捷函数：检查关键配置
def validate_config() -> list:
    """验证配置完整性，返回缺失的配置项列表"""
    missing = []
    provider = settings.llm_provider.lower()
    if provider == "openai" and not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if provider == "gemini" and not settings.gemini_api_key:
        missing.append("GEMINI_API_KEY")
    if settings.embedding_provider.lower() == "openai" and not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not os.path.exists(os.path.join(settings.project_root, settings.data_root)):
        missing.append("DATA_ROOT directory")
    return missing

