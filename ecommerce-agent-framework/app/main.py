"""
FastAPI Application Entry Point

This module creates and configures the FastAPI application for the e-commerce agent framework.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import API routers
from app.api.routes_chat import router as chat_router
# from app.api.routes_knowledge import router as knowledge_router  # TODO: implement later
# from app.api.routes_evaluation import router as evaluation_router  # TODO: implement later
from app.engine import engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="E-commerce Agent Framework",
    description="Intelligent customer service agent for e-commerce platforms with RAG and uncertainty detection",
    version="1.0.0"
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
# app.include_router(knowledge_router)  # TODO: implement later
# app.include_router(evaluation_router)  # TODO: implement later

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "E-commerce Agent Framework API",
        "version": "1.0.0",
        "endpoints": {
            "chat": "/api/chat/query",
            # "knowledge": "/api/knowledge/*",  # TODO
            # "evaluation": "/api/evaluation/*"  # TODO
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    status = "healthy"
    if not engine.retrievers:
        status = "initializing"
    return {"status": status}

@app.on_event("startup")
async def startup_event():
    """在应用启动时初始化引擎和商家检索器。"""
    try:
        engine.initialize()
        logger.info("Engine initialized on startup")
    except Exception as e:
        logger.exception(f"Engine initialization failed on startup: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
