"""
FastAPI Application Entry Point

This module creates and configures the FastAPI application for the e-commerce agent framework.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import API routers
from app.api.routes_chat import router as chat_router
from app.api.routes_knowledge import router as knowledge_router
from app.api.routes_extension import router as extension_router
from app.api.routes_local_agent import router as local_agent_router
from app.api.routes_platform import router as platform_router
from app.api.routes_products import router as products_router
from app.api.routes_agent_rules import router as agent_rules_router
from app.api.routes_handoff import router as handoff_router
# from app.api.routes_evaluation import router as evaluation_router  # TODO: implement later
from app.api.routes_platform_browser import router as platform_browser_router
from app.engine import engine
from app.storage.storage_manager import storage_manager
from app.connectors.chat_manager import chat_manager
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _build_platform_configs():
    platform_configs = {}

    if settings.xiaohongshu_app_id and settings.xiaohongshu_app_secret:
        platform_configs["xiaohongshu"] = {
            "app_id": settings.xiaohongshu_app_id,
            "app_secret": settings.xiaohongshu_app_secret,
            "webhook_token": settings.xiaohongshu_webhook_token,
            "merchant_id": settings.xiaohongshu_merchant_id,
            "api_base_url": settings.xiaohongshu_api_base_url,
            "listen_mode": "both",
        }

    if settings.taobao_app_key and settings.taobao_app_secret:
        platform_configs["taobao"] = {
            "app_key": settings.taobao_app_key,
            "app_secret": settings.taobao_app_secret,
            "session_key": settings.taobao_session_key,
        }

    if settings.jd_app_key and settings.jd_app_secret:
        platform_configs["jd"] = {
            "app_key": settings.jd_app_key,
            "app_secret": settings.jd_app_secret,
        }

    return platform_configs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting up E-commerce Agent Framework...")

    platform_configs = _build_platform_configs()
    if platform_configs:
        success = await chat_manager.initialize(platform_configs)
        if success:
            await chat_manager.start()
            logger.info("Chat manager started with platforms: %s", list(platform_configs))
        else:
            logger.warning("Failed to start chat manager")
    else:
        logger.info("No platform configurations found, chat manager not started")

    try:
        engine.initialize()
        logger.info("Engine initialized on startup")
        storage_stats = storage_manager.get_stats()
        logger.info("Storage manager initialized: %s", storage_stats)
    except Exception:
        logger.exception("Initialization failed on startup")

    try:
        yield
    finally:
        logger.info("Shutting down E-commerce Agent Framework...")
        await chat_manager.stop()
        logger.info("Chat manager stopped")


# Create FastAPI application
app = FastAPI(
    title="E-commerce Agent Framework",
    description="Intelligent customer service agent for e-commerce platforms with RAG and uncertainty detection",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(extension_router)
app.include_router(local_agent_router)
app.include_router(platform_router)
app.include_router(products_router)
app.include_router(agent_rules_router)
app.include_router(handoff_router)
app.include_router(platform_browser_router)
# app.include_router(evaluation_router)  # TODO: implement later

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "E-commerce Agent Framework API",
        "version": "1.0.0",
        "description": "Intelligent customer service agent with RAG, multi-turn conversations, and document management",
        "endpoints": {
            "chat": {
                "query": "POST /api/chat/query - 发送查询（支持多轮对话）",
                "history": "GET /api/chat/conversations/{conversation_id}/history - 获取会话历史",
                "info": "GET /api/chat/conversations/{conversation_id} - 获取会话信息",
                "close": "POST /api/chat/conversations/{conversation_id}/close - 关闭会话",
                "list": "GET /api/chat/conversations - 列出所有会话",
                "health": "GET /api/chat/health - 聊天模块健康检查",
            },
            "knowledge": {
                "upload": "POST /api/knowledge/upload - 上传文档",
                "status": "GET /api/knowledge/status/{upload_id} - 查询摄取状态",
                "ingest": "POST /api/knowledge/ingest - 手动触发摄取",
                "list": "GET /api/knowledge/list-uploads - 列出所有上传任务",
                "health": "GET /api/knowledge/health - 知识管理模块健康检查",
            }
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint - 系统整体健康状态"""
    status = "healthy"
    components = {
        "engine": "unknown",
        "chat": "healthy",
        "knowledge": "healthy",
        "storage": "unknown"
    }

    if not engine.retrievers:
        status = "initializing"
        components["engine"] = "initializing"
    else:
        components["engine"] = "healthy"

    # 检查存储状态
    try:
        storage_stats = storage_manager.get_stats()
        if storage_stats.get("session_storage", {}).get("status") == "connected" or \
           storage_stats.get("ingestion_storage", {}).get("status") == "connected":
            components["storage"] = "healthy"
        elif storage_stats.get("session_storage", {}).get("status") == "disconnected" and \
             storage_stats.get("ingestion_storage", {}).get("status") == "disconnected":
            components["storage"] = "memory_fallback"
        else:
            components["storage"] = "partial"
    except Exception as e:
        logger.warning(f"Storage health check failed: {e}")
        components["storage"] = "error"

    return {
        "status": status,
        "components": components,
        "version": "1.0.0",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
