"""
FastAPI接口层

提供会话管理的REST API接口
支持：
1. 会话任务创建
2. 会话状态查询
3. 任务状态更新
4. 消息批处理
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from .utils.tools import extract_account_id_from_raw_message_list
from .database import create_database_url, get_engine
from .models import TaskType, SessionState, MessageData, RawMessage
from .session_manager import SessionManager, ensure_account_exists, ensure_shop_exists
from .session_task_manager import SessionTaskManager
from sqlalchemy.orm import sessionmaker

# 创建FastAPI应用
app = FastAPI(
    title="Auto Session API",
    description="智能会话管理系统API",
    version="1.0.0"
)

# 数据库会话工厂
database_url = create_database_url()
engine = get_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 依赖注入：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 请求模型
class SessionTaskCreateRequest(BaseModel):
    """创建会话任务请求"""
    account_id: str = Field(..., description="账号ID")
    shop_id: str = Field(..., description="店铺ID")
    shop_name: str = Field(..., description="店铺名称")
    task_type: TaskType = Field(..., description="任务类型")
    external_task_id: str = Field(..., description="外部任务ID")
    send_content: str = Field(..., description="发送内容")
    platform: str = Field("淘天", description="平台类型")
    level: str = Field('level3', description="优先级")
    send_url: Optional[str] = Field(None, description="发送URL")
    max_inactive_minutes: int = Field(120, description="最大非活跃时间(分钟)")


class SessionTaskCompleteRequest(BaseModel):
    """完成会话任务请求"""
    success: bool = Field(..., description="是否成功")
    error_message: Optional[str] = Field(None, description="错误消息")


class MessageBatchRequest(BaseModel):
    """批量消息处理请求"""
    shop_name: str = Field(..., description="店铺名称")
    messages: List[Dict[str, Any]] = Field(..., description="消息列表")
    platform: str = Field("淘天", description="平台类型")
    max_inactive_minutes: int = Field(120, description="最大非活跃时间(分钟)")


# 响应模型
class ApiResponse(BaseModel):
    """API响应基类"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None

class SessionTaskResponse(BaseModel):
    """会话任务响应"""
    session_id: str
    external_task_id: str
    task_type: str
    status: Dict[str, Any]

# API路由
@app.get("/")
async def root():
    """根路径"""
    return {"message": "Auto Session API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# 创建会话任务
@app.post("/api/sessions/create", response_model=ApiResponse)
async def create_session_task(
    request: SessionTaskCreateRequest,
    db: Session = Depends(get_db)
):
    """创建会话任务"""
    try:
        # 确保账号和店铺存在
        ensure_account_exists(db, request.account_id, f"账号_{request.account_id}", request.platform)
        ensure_shop_exists(db, request.shop_name, request.shop_id)
        
        # 创建任务管理器
        task_manager = SessionTaskManager(db)
        
        # 创建会话任务
        result = task_manager.create_session_task(
            task_type=request.task_type,
            external_task_id=request.external_task_id,
            account_id=request.account_id,
            shop_name=request.shop_name,
            send_content=request.send_content,
            level=request.level,
            max_inactive_minutes=request.max_inactive_minutes
        )
        
        if result.success:
            return ApiResponse(
                success=True,
                message="会话任务创建成功",
                data={
                    "session_id": result.session_id,
                    "external_task_id": request.external_task_id,
                    "task_type": request.task_type.value,
                    "created_at": datetime.now().isoformat()
                }
            )
        else:
            return ApiResponse(
                success=False,
                message=result.error_message,
                error_code=result.error_code,
                data={
                    "conflict_session_id": result.conflict_session_id
                } if result.conflict_session_id else None
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话任务失败: {str(e)}")


# 完成会话任务
@app.post("/api/sessions/{session_id}/complete", response_model=ApiResponse)
async def complete_session_task(
    session_id: str,
    request: SessionTaskCompleteRequest,
    db: Session = Depends(get_db)
):
    """完成会话任务"""
    try:
        task_manager = SessionTaskManager(db)
        success = task_manager.complete_session_task(
            session_id=session_id,
            success=request.success,
            error_message=request.error_message
        )
        
        if success:
            return ApiResponse(
                success=True,
                message="会话任务完成成功",
                data={
                    "session_id": session_id,
                    "success": request.success,
                    "completed_at": datetime.now().isoformat()
                }
            )
        else:
            return ApiResponse(
                success=False,
                message="会话任务完成失败",
                error_code="COMPLETE_FAILED"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"完成会话任务失败: {str(e)}")


# 获取下一个redis任务
@app.get("/api/tasks/next_id", response_model=ApiResponse)
async def get_next_task(
    db: Session = Depends(get_db)
):
    """获取下一个redis任务ID"""
    try:
        task_manager = SessionTaskManager(db)
        task_id = task_manager.get_next_redis_task()

        if task_id is None:
            return ApiResponse(
                success=False,
                message="当前没有待处理的任务",
                data={"task_id": None}
            )
        
        return ApiResponse(
            success=True,
            message="获取任务成功",
            data={
                "task_id": task_id,
                "timestamp": datetime.now().isoformat()
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取下一个任务失败: {str(e)}")

# 获取redis任务关联的会话任务
@app.get("/api/tasks/{task_id}/send_info", response_model=ApiResponse)
async def get_send_info_by_task_id(
    task_id: str,
    db: Session = Depends(get_db)
):
    """根据redis任务ID获取发送信息"""
    try:
        task_manager = SessionTaskManager(db)
        send_info = task_manager.get_send_info_by_redis_id(task_id)
        if send_info is None:
            return ApiResponse(
                success=False,
                message="未找到对应的发送信息",
                error_code="TASK_NOT_FOUND"
            )
        return ApiResponse(
            success=True,
            message="获取发送信息成功",
            data=send_info
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取发送信息失败: {str(e)}")


# 上传批量消息
@app.post("/api/messages/batch", response_model=ApiResponse)
async def process_message_batch(
    request: MessageBatchRequest,
    db: Session = Depends(get_db)
):
    """批量处理消息"""
    try:
        account_id = extract_account_id_from_raw_message_list(request.platform, request.messages)

        # 确保账号和店铺存在
        ensure_account_exists(db, account_id, f"账号_{account_id}", request.platform)
        ensure_shop_exists(db, request.shop_name)
        
        # 转换消息格式
        messages = []
        for msg_data in request.messages:
            # 将字典转换为MessageData
            sender = msg_data.get('nick')
            from_source = "account" if sender==account_id else "shop"
            send_at = msg_data.get('time', datetime.now())
            if isinstance(send_at, str):
                # 如果时间是字符串，尝试解析
                try:
                    send_at = datetime.fromisoformat(send_at.replace('Z', '+00:00'))
                except:
                    send_at = datetime.now()
            messages.append(MessageData(
                message_id=msg_data.get("id"),
                content=msg_data.get("content", ""),
                sender=sender,
                from_source=from_source,
                sent_at=send_at
            ))
        
        # 创建会话管理器
        session_manager = SessionManager(db)
        
        # 处理消息批次
        result = session_manager.process_message_batch(
            messages=messages,
            account_id=account_id,
            shop_name=request.shop_name,
            max_inactive_minutes=request.max_inactive_minutes
        )
        
        return ApiResponse(
            success=True,
            message="消息批处理成功",
            data={
                "processed_messages": result.processed_messages,
                "skipped_messages": result.skipped_messages,
                "active_session_id": result.active_session_id,
                "session_operations": result.session_operations,
                "errors": result.errors
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量处理消息失败: {str(e)}")


# 暂时用不着的api
@app.get("/api/sessions/{session_id}/status", response_model=ApiResponse)
async def get_session_status(
    session_id: str,
    db: Session = Depends(get_db)
):
    """获取会话状态"""
    try:
        task_manager = SessionTaskManager(db)
        status = task_manager.get_task_status(session_id)
        
        if status:
            return ApiResponse(
                success=True,
                message="获取会话状态成功",
                data=status
            )
        else:
            return ApiResponse(
                success=False,
                message="会话不存在",
                error_code="SESSION_NOT_FOUND"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话状态失败: {str(e)}")


@app.get("/api/tasks/pending", response_model=ApiResponse)
async def get_pending_tasks(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取待处理任务"""
    try:
        task_manager = SessionTaskManager(db)
        tasks = task_manager.get_pending_tasks(limit=limit)
        
        return ApiResponse(
            success=True,
            message="获取待处理任务成功",
            data={
                "tasks": tasks,
                "count": len(tasks),
                "limit": limit
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取待处理任务失败: {str(e)}")


# 错误处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_code": "HTTP_ERROR"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "内部服务器错误",
            "error_code": "INTERNAL_ERROR"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
