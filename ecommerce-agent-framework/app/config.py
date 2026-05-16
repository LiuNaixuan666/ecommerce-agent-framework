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

    # === 数据库配置 ===
    # Redis 配置（会话存储）
    redis_host: str = Field("localhost", env="REDIS_HOST", description="Redis server host")
    redis_port: int = Field(6379, env="REDIS_PORT", description="Redis server port")
    redis_db: int = Field(0, env="REDIS_DB", description="Redis database number")
    redis_password: Optional[str] = Field(None, env="REDIS_PASSWORD", description="Redis password")
    redis_session_ttl: int = Field(86400, env="REDIS_SESSION_TTL", description="Session TTL in seconds (24 hours)")

    # PostgreSQL 配置（摄取任务存储）
    postgres_host: str = Field("localhost", env="POSTGRES_HOST", description="PostgreSQL server host")
    postgres_port: int = Field(5432, env="POSTGRES_PORT", description="PostgreSQL server port")
    postgres_db: str = Field("ecommerce_agent", env="POSTGRES_DB", description="PostgreSQL database name")
    postgres_user: str = Field("postgres", env="POSTGRES_USER", description="PostgreSQL username")
    postgres_password: str = Field("password", env="POSTGRES_PASSWORD", description="PostgreSQL password")

    # 存储后端选择
    storage_backend: str = Field("memory", env="STORAGE_BACKEND", description="Storage backend: memory, redis, postgres")
    session_storage: str = Field("memory", env="SESSION_STORAGE", description="Session storage: memory, redis")
    ingestion_storage: str = Field("memory", env="INGESTION_STORAGE", description="Ingestion storage: memory, postgres")

    # === 适配器配置 ===
    default_adapter_type: str = Field("mock", env="DEFAULT_ADAPTER_TYPE", description="Default adapter type (mock, taobao, jd, amazon, erp)")

    # 平台聊天适配器配置
    chat_adapters: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Chat adapter configurations per platform")

    # 小红书配置
    xiaohongshu_app_id: Optional[str] = Field(None, env="XIAOHONGSHU_APP_ID", description="Xiaohongshu App ID")
    xiaohongshu_app_secret: Optional[str] = Field(None, env="XIAOHONGSHU_APP_SECRET", description="Xiaohongshu App Secret")
    xiaohongshu_webhook_token: Optional[str] = Field(None, env="XIAOHONGSHU_WEBHOOK_TOKEN", description="Xiaohongshu Webhook Token")
    xiaohongshu_merchant_id: Optional[str] = Field(None, env="XIAOHONGSHU_MERCHANT_ID", description="Xiaohongshu Merchant ID")
    xiaohongshu_api_base_url: str = Field("https://api.xiaohongshu.com", env="XIAOHONGSHU_API_BASE_URL", description="Xiaohongshu API Base URL")

    # 淘宝配置
    taobao_app_key: Optional[str] = Field(None, env="TAOBAO_APP_KEY", description="Taobao App Key")
    taobao_app_secret: Optional[str] = Field(None, env="TAOBAO_APP_SECRET", description="Taobao App Secret")
    taobao_session_key: Optional[str] = Field(None, env="TAOBAO_SESSION_KEY", description="Taobao Session Key")

    # 京东配置
    jd_app_key: Optional[str] = Field(None, env="JD_APP_KEY", description="JD App Key")
    jd_app_secret: Optional[str] = Field(None, env="JD_APP_SECRET", description="JD App Secret")

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

