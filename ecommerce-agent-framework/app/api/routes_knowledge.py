"""
知识管理 API 路由：文档上传、摄取管理、状态查询

对应工作流：
  Upload Files → Store Temporarily → Trigger Ingestion → Monitor Progress → Vector Store Ready
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from typing import List, Optional, Dict
import logging
import os
import uuid
import json
from datetime import datetime
import asyncio
from pathlib import Path

from app.models.schemas import (
    KnowledgeUploadResponse,
    IngestionStatusResponse,
    IngestionStartRequest,
    IngestionStartResponse,
)
from app.knowledge.ingestion import ingest_merchant_documents
from app.config import settings
from app.storage.storage_manager import storage_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
UPLOAD_STAGING_DIR = os.path.join(os.getcwd(), "data", "uploads_staging")


def _ensure_staging_dir():
    """确保临时上传目录存在"""
    os.makedirs(UPLOAD_STAGING_DIR, exist_ok=True)


def _get_merchant_upload_dir(merchant_id: str) -> str:
    """获取商家的临时上传目录"""
    path = os.path.join(UPLOAD_STAGING_DIR, merchant_id)
    os.makedirs(path, exist_ok=True)
    return path


def _get_merchant_raw_docs_dir(merchant_id: str) -> str:
    """获取商家的原始文档目录"""
    return os.path.join(os.getcwd(), "data", "merchants", merchant_id, "raw_docs")


# ==================== 后台摄取任务 ====================

async def _background_ingest_task(upload_id: str, merchant_id: str, upload_dir: str):
    """
    后台摄取任务：处理上传的文件并写入向量库

    流程：
    1. 等待所有文件上传完成
    2. 将文件从临时目录移到商家原始文档目录
    3. 调用 ingestion.ingest_merchant_documents()
    4. 更新任务状态
    """
    try:
        # 获取任务数据
        task = storage_manager.get_ingestion_task(upload_id)
        if not task:
            logger.error(f"Task {upload_id} not found in storage")
            return

        # 更新状态为处理中
        storage_manager.update_ingestion_task(upload_id, {
            "status": "processing",
            "updated_at": datetime.now().isoformat()
        })

        logger.info(f"Starting background ingestion for upload_id={upload_id}, merchant_id={merchant_id}")

        # 检查临时上传目录是否有文件
        if not os.path.exists(upload_dir):
            storage_manager.update_ingestion_task(upload_id, {
                "status": "failed",
                "error_message": "上传目录不存在",
                "updated_at": datetime.now().isoformat()
            })
            logger.warning(f"Upload directory not found: {upload_dir}")
            return

        files_in_upload = os.listdir(upload_dir)
        if not files_in_upload:
            storage_manager.update_ingestion_task(upload_id, {
                "status": "failed",
                "error_message": "没有上传任何文件",
                "updated_at": datetime.now().isoformat()
            })
            logger.warning(f"No files in upload directory: {upload_dir}")
            return

        # 获取原始文档目录并创建它
        raw_docs_dir = _get_merchant_raw_docs_dir(merchant_id)
        os.makedirs(raw_docs_dir, exist_ok=True)

        # 将文件从临时目录复制到原始文档目录
        for file_name in files_in_upload:
            src = os.path.join(upload_dir, file_name)
            dst = os.path.join(raw_docs_dir, file_name)

            if os.path.isfile(src):
                try:
                    # 简单的文件复制（在实际场景中可能需要更复杂的处理）
                    import shutil
                    shutil.copy2(src, dst)
                    logger.info(f"Copied file: {file_name} to {raw_docs_dir}")
                except Exception as e:
                    logger.warning(f"Failed to copy file {file_name}: {e}")

        # 调用摄取函数
        logger.info(f"Calling ingest_merchant_documents for merchant_id={merchant_id}")
        result = ingest_merchant_documents(
            merchant_id=merchant_id,
            merchant_dir=os.path.join(os.getcwd(), "data", "merchants", merchant_id),
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        logger.info(f"Ingestion result: {result}")

        # 更新任务状态
        if result.get("status") == "ok":
            storage_manager.update_ingestion_task(upload_id, {
                "status": "completed",
                "documents_processed": result.get("documents", 0),
                "chunks_created": result.get("chunks", 0),
                "progress_percentage": 100,
                "updated_at": datetime.now().isoformat()
            })
        else:
            storage_manager.update_ingestion_task(upload_id, {
                "status": "failed",
                "error_message": result.get("detail", "摄取失败"),
                "updated_at": datetime.now().isoformat()
            })

        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(upload_dir)
            logger.info(f"Cleaned up staging directory: {upload_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up staging directory: {e}")

        logger.info(f"Ingestion task completed for upload_id={upload_id}")

    except Exception as e:
        logger.exception(f"Error in background ingestion task: {e}")
        storage_manager.update_ingestion_task(upload_id, {
            "status": "failed",
            "error_message": str(e),
            "updated_at": datetime.now().isoformat()
        })


# ==================== API 端点 ====================

@router.post("/upload", response_model=KnowledgeUploadResponse)
async def upload_knowledge(
    merchant_id: str,
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
) -> KnowledgeUploadResponse:
    """
    上传商家知识库文档
    
    支持的文件格式：
    - .txt (纯文本)
    - .pdf (PDF 文档)
    - .docx (Word 文档)
    - .csv (CSV 表格)
    - .md (Markdown)
    
    Args:
        merchant_id: 商家 ID
        files: 上传的文件列表
        background_tasks: FastAPI 后台任务管理器
    
    Returns:
        上传响应，包含上传 ID 和状态
    """
    try:
        logger.info(f"Received upload request for merchant_id={merchant_id}, files={len(files)}")
        
        # 验证输入
        if not merchant_id:
            raise HTTPException(status_code=400, detail="merchant_id 不能为空")
        
        if not files:
            raise HTTPException(status_code=400, detail="至少需要上传一个文件")
        
        if len(files) > 50:
            raise HTTPException(status_code=400, detail="单次最多上传 50 个文件")
        
        # 生成上传任务 ID
        upload_id = str(uuid.uuid4())
        
        # 创建临时上传目录
        upload_dir = _get_merchant_upload_dir(merchant_id)
        
        # 保存文件
        saved_files = 0
        for file in files:
            # 验证文件名
            if not file.filename:
                continue
            
            # 检查文件扩展名
            allowed_extensions = {".txt", ".pdf", ".docx", ".csv", ".md", ".doc"}
            file_ext = os.path.splitext(file.filename)[1].lower()
            
            if file_ext not in allowed_extensions:
                logger.warning(f"Skipping file with unsupported extension: {file.filename}")
                continue
            
            # 保存文件到临时目录
            file_path = os.path.join(upload_dir, file.filename)
            
            try:
                content = await file.read()
                with open(file_path, "wb") as f:
                    f.write(content)
                saved_files += 1
                logger.info(f"Saved file: {file.filename} to {upload_dir}")
            except Exception as e:
                logger.warning(f"Failed to save file {file.filename}: {e}")
        
        if saved_files == 0:
            raise HTTPException(status_code=400, detail="没有可用的文件被保存")
        
        # 记录上传任务
        task_data = {
            "upload_id": upload_id,
            "merchant_id": merchant_id,
            "status": "pending",
            "files_received": saved_files,
            "documents_processed": 0,
            "chunks_created": 0,
            "progress_percentage": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "error_message": None,
            "files": [file.filename for file in files if file.filename]
        }

        storage_manager.save_ingestion_task(task_data)
        
        # 添加后台任务（自动触发摄取）
        if background_tasks:
            background_tasks.add_task(
                _background_ingest_task,
                upload_id=upload_id,
                merchant_id=merchant_id,
                upload_dir=upload_dir,
            )
        
        logger.info(f"Upload task created: upload_id={upload_id}, saved_files={saved_files}")
        
        return KnowledgeUploadResponse(
            merchant_id=merchant_id,
            status="pending",
            files_received=saved_files,
            upload_id=upload_id,
            message=f"成功接收 {saved_files} 个文件，已加入摄取队列",
        )
    
    except HTTPException as e:
        logger.warning(f"Upload validation failed: {e.detail}")
        raise
    except Exception as e:
        logger.exception(f"Error in upload_knowledge: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/status/{upload_id}", response_model=IngestionStatusResponse)
async def get_ingestion_status(upload_id: str) -> IngestionStatusResponse:
    """
    查询摄取任务状态

    Args:
        upload_id: 上传任务 ID

    Returns:
        摄取状态详情
    """
    try:
        logger.info(f"Querying status for upload_id={upload_id}")

        task = storage_manager.get_ingestion_task(upload_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"找不到上传任务: {upload_id}")

        return IngestionStatusResponse(
            merchant_id=task["merchant_id"],
            upload_id=upload_id,
            status=task["status"],
            documents_processed=task.get("documents_processed", 0),
            chunks_created=task.get("chunks_created", 0),
            vector_store_size=task.get("chunks_created", 0),  # 简化为块数
            progress_percentage=task.get("progress_percentage", 0),
            error_message=task.get("error_message"),
        )
    
    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"Error in get_ingestion_status: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/ingest", response_model=IngestionStartResponse)
async def start_ingestion(
    request: IngestionStartRequest,
    background_tasks: BackgroundTasks = None,
) -> IngestionStartResponse:
    """
    手动触发摄取（如果不想自动摄取）

    Args:
        request: 摄取请求（包含 merchant_id 和 upload_id）
        background_tasks: 后台任务管理器

    Returns:
        摄取启动响应
    """
    try:
        merchant_id = request.merchant_id
        upload_id = request.upload_id

        logger.info(f"Manual ingest request: upload_id={upload_id}, merchant_id={merchant_id}")

        task = storage_manager.get_ingestion_task(upload_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"找不到上传任务: {upload_id}")

        # 检查任务状态
        if task["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"只能摄取 pending 状态的任务，当前状态: {task['status']}"
            )

        # 获取上传目录
        upload_dir = _get_merchant_upload_dir(merchant_id)

        # 添加后台任务
        if background_tasks:
            background_tasks.add_task(
                _background_ingest_task,
                upload_id=upload_id,
                merchant_id=merchant_id,
                upload_dir=upload_dir,
            )

        logger.info(f"Ingestion started for upload_id={upload_id}")

        return IngestionStartResponse(
            merchant_id=merchant_id,
            upload_id=upload_id,
            status="processing",
            message="摄取已启动，请稍后查询状态",
        )

    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"Error in start_ingestion: {e}")
        raise HTTPException(status_code=500, detail=f"启动摄取失败: {str(e)}")


@router.get("/list-uploads")
async def list_uploads(merchant_id: Optional[str] = None) -> dict:
    """
    列出所有摄取任务

    Args:
        merchant_id: 可选的商家 ID 筛选

    Returns:
        任务列表
    """
    try:
        tasks = storage_manager.list_ingestion_tasks(merchant_id)

        result = []
        for task in tasks:
            result.append({
                "upload_id": task["upload_id"],
                "merchant_id": task["merchant_id"],
                "status": task["status"],
                "files_received": task.get("files_received", 0),
                "documents_processed": task.get("documents_processed", 0),
                "chunks_created": task.get("chunks_created", 0),
                "progress_percentage": task.get("progress_percentage", 0),
                "created_at": task.get("created_at"),
                "updated_at": task.get("updated_at"),
            })
        
        return {
            "total": len(result),
            "tasks": result,
        }
    
    except Exception as e:
        logger.exception(f"Error in list_uploads: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/health")
async def knowledge_health():
    """知识管理模块健康检查"""
    try:
        # 获取存储统计信息
        stats = storage_manager.get_stats()

        # 计算活跃任务数
        tasks = storage_manager.list_ingestion_tasks()
        active_tasks = len([t for t in tasks if t["status"] in ["pending", "processing"]])

        return {
            "status": "healthy",
            "module": "knowledge",
            "active_tasks": active_tasks,
            "total_tasks": len(tasks),
            "storage": stats
        }
    except Exception as e:
        logger.exception(f"Error in knowledge_health: {e}")
        return {
            "status": "unhealthy",
            "module": "knowledge",
            "error": str(e)
        }


# 确保临时目录存在
_ensure_staging_dir()
