# config.py
"""
系统配置中心：统一管理 API keys、路径、模型参数、适配器配置等

使用 Pydantic BaseSettings 自动从环境变量加载，支持 .env 文件。
"""

import os
from typing import Optional, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置类"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === API Keys ===
    openai_api_key: Optional[str] = Field(None, description="OpenAI API Key for OpenAI LLM and embeddings")
    gemini_api_key: Optional[str] = Field(None, description="Google Gemini API Key for LLM generation")
    llm_provider: str = Field("openai", description="LLM provider name (openai, gemini)")
    embedding_provider: str = Field("local", description="Embedding provider name (local, openai)")
    openai_model: str = Field("gpt-4o-mini", description="Default OpenAI model for chat")
    gemini_model: str = Field("gemini-1.5-flash", description="Default Gemini model for chat")
    openai_embedding_model: str = Field("text-embedding-3-small", description="OpenAI embedding model")

    # === 路径配置 ===
    project_root: str = Field(os.getcwd(), description="Project root directory")
    data_root: str = Field("data", description="Data directory relative to project root")
    merchants_data_root: str = Field("merchants", description="Merchants data subdirectory")
    vector_store_root: str = Field("vector_store", description="Vector store subdirectory per merchant")

    # === 知识摄取配置 ===
    chunk_size: int = Field(1000, description="Text chunk size for document splitting")
    chunk_overlap: int = Field(200, description="Overlap between chunks")
    max_documents_per_ingestion: int = Field(100, description="Max documents to process per ingestion")

    # === 检索配置 ===
    similarity_top_k: int = Field(5, description="Top K results for similarity search")
    retrieval_confidence_threshold: float = Field(0.3, description="Threshold for retrieval confidence")

    # === 不确定性检测配置 ===
    uncertainty_retrieval_threshold: float = Field(0.3, description="Retrieval confidence threshold for uncertainty")
    uncertainty_query_threshold: float = Field(0.6, description="Query ambiguity threshold")
    uncertainty_overall_threshold: float = Field(0.4, description="Overall confidence threshold")

    # === 自动发送风控配置 ===
    auto_send_min_confidence: float = Field(
        0.5,
        description="Minimum workflow confidence required before auto sending",
    )
    auto_send_allow_medium_risk: bool = Field(
        False,
        description="Whether medium-risk replies may be auto-sent when all other checks pass",
    )

    # === LLM 生成配置 ===
    llm_temperature: float = Field(0.3, description="Temperature for LLM generation")
    llm_max_tokens: int = Field(500, description="Max tokens for LLM response")
    llm_timeout: int = Field(30, description="Timeout for LLM API calls (seconds)")

    # === 数据库配置 ===
    # Redis 配置（会话存储）
    redis_host: str = Field("localhost", description="Redis server host")
    redis_port: int = Field(6379, description="Redis server port")
    redis_db: int = Field(0, description="Redis database number")
    redis_password: Optional[str] = Field(None, description="Redis password")
    redis_session_ttl: int = Field(86400, description="Session TTL in seconds (24 hours)")

    # PostgreSQL 配置（摄取任务存储）
    postgres_host: str = Field("localhost", description="PostgreSQL server host")
    postgres_port: int = Field(5432, description="PostgreSQL server port")
    postgres_db: str = Field("ecommerce_agent", description="PostgreSQL database name")
    postgres_user: str = Field("postgres", description="PostgreSQL username")
    postgres_password: str = Field("password", description="PostgreSQL password")

    # 存储后端选择
    storage_backend: str = Field("memory", description="Storage backend: memory, redis, postgres")
    session_storage: str = Field(
        "memory",
        description="Session storage: memory, redis, postgres, hybrid",
    )
    ingestion_storage: str = Field("memory", description="Ingestion storage: memory, postgres")

    # === 适配器配置 ===
    default_adapter_type: str = Field("mock", description="Default adapter type (mock, taobao, jd, amazon, erp)")

    # 平台聊天适配器配置
    chat_adapters: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Chat adapter configurations per platform")

    # 小红书配置
    xiaohongshu_app_id: Optional[str] = Field(None, description="Xiaohongshu App ID")
    xiaohongshu_app_secret: Optional[str] = Field(None, description="Xiaohongshu App Secret")
    xiaohongshu_webhook_token: Optional[str] = Field(None, description="Xiaohongshu Webhook Token")
    xiaohongshu_merchant_id: Optional[str] = Field(None, description="Xiaohongshu Merchant ID")
    xiaohongshu_api_base_url: str = Field("https://api.xiaohongshu.com", description="Xiaohongshu API Base URL")

    # 淘宝配置
    taobao_app_key: Optional[str] = Field(None, description="Taobao App Key")
    taobao_app_secret: Optional[str] = Field(None, description="Taobao App Secret")
    taobao_session_key: Optional[str] = Field(None, description="Taobao Session Key")

    # 京东配置
    jd_app_key: Optional[str] = Field(None, description="JD App Key")
    jd_app_secret: Optional[str] = Field(None, description="JD App Secret")

    adapter_configs: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Adapter-specific configurations")

    # === 服务器配置 ===
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    debug: bool = Field(False, description="Debug mode")
    cors_origins: list = Field(["http://localhost:3000", "http://localhost:8080"], description="Allowed CORS origins")

    # === 其他 ===
    log_level: str = Field("INFO", description="Logging level")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "no", "off"}:
                return False
            if normalized in {"debug", "dev", "development", "true", "1", "yes", "on"}:
                return True
        return value

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

