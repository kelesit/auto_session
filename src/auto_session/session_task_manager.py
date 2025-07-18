"""
会话任务管理器

负责管理会话任务的创建、状态更新和完成
主要功能：
1. 创建会话任务 - 为上游系统创建会话任务
2. 更新任务状态 - 更新任务执行状态
3. 完成会话任务 - 标记任务完成并处理结果
4. Redis集成 - 与下游RPA系统通信
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️  Redis库未安装，Redis功能将被禁用")

from .database import DBSession, DBSessionTask, DBAccount, DBShop
from .models import (
    TaskType, SessionState, SessionInfo, SessionCreationResult, 
    MessageData, ProcessResult
)
from .session_manager import SessionManager
from .config import Config
from .utils.tools import get_send_info_by_external_task

LEVEL_LIST = ["level5", "level4", "level3", "level2", "level1"] # 级别越高越优先

class SessionTaskManager:
    """会话任务管理器"""
    
    def __init__(self, db_session: Session, redis_client: Optional[Any] = None):
        self.db = db_session
        self.session_manager = SessionManager(db_session)
        self.redis_client = redis_client or self._create_redis_client()
        
    def _create_redis_client(self) -> Optional[Any]:
        """创建Redis客户端"""
        if not REDIS_AVAILABLE:
            return None
            
        try:
            # 这里可以从配置文件读取Redis配置
            return redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                password=Config.REDIS_PASSWORD,
                decode_responses=True
            )
        except Exception as e:
            print(f"⚠️  Redis连接失败: {e}")
            return None
    
    def create_session_task(
        self,
        task_type: TaskType,
        external_task_id: str,
        account_id: str,
        shop_name: str,
        send_content: str,
        level: str = "level3",  # LEVEL_LIST = ["level5", "level4", "level3", "level2", "level1"]
        max_inactive_minutes: int = 120
    ) -> SessionCreationResult:
        """
        创建会话任务
        
        Args:
            account_id: 账号ID
            shop_name: 店铺名称
            task_type: 任务类型
            external_task_id: 外部任务ID
            send_content: 发送内容
            send_url: 发送URL
            level: 发送级别
            max_inactive_minutes: 最大非活跃时间
            
        Returns:
            SessionCreationResult: 创建结果
        """
        try:
            # 1. 检查是否可以创建会话
            availability = self.session_manager.can_create_robot_session(
                account_id=account_id,
                shop_name=shop_name,
                task_type=task_type,
                max_inactive_minutes=max_inactive_minutes
            )
            
            if not availability.available:
                return SessionCreationResult(
                    success=False,
                    error_code="UNAVAILABLE",
                    error_message=availability.error_message,
                    conflict_session_id=availability.current_session_id
                )
            
            # 2. 创建会话
            session_result = self.session_manager.create_robot_session(
                account_id=account_id,
                shop_name=shop_name,
                task_type=task_type,
                external_task_id=external_task_id,
                max_inactive_minutes=max_inactive_minutes
            )
            
            if not session_result.success:
                return session_result
            
            # 3. 创建会话任务
            session_task = DBSessionTask(
                external_task_type=task_type.value,
                external_task_id=external_task_id,
                task_created_at=datetime.now(),
                task_status=0,  # 0: 未开始
                send_content=send_content,
                session_id=session_result.session_id
            )
            
            self.db.add(session_task)
            self.db.commit()
            
            # 4. 发布任务到Redis队列
            redis_task_id = session_task.id
            
            redis_sucess = self._publish_task_to_redis(level, redis_task_id)
            if not redis_sucess:
                return SessionCreationResult(
                    success=False,
                    error_code="REDIS_PUBLISH_FAILED",
                    error_message="发布任务到Redis失败"
                )
            
            return SessionCreationResult(
                success=True,
                session_id=session_result.session_id,
                error_code=None,
                error_message=None
            )
            
        except Exception as e:
            self.db.rollback()
            return SessionCreationResult(
                success=False,
                error_code="CREATE_FAILED",
                error_message=f"创建会话任务失败: {str(e)}"
            )
    
    def update_task_status(
        self,
        session_id: str,
        status: int,
        external_task_id: Optional[str] = None
    ) -> bool:
        """
        更新任务状态
        
        Args:
            session_id: 会话ID
            status: 任务状态 (0: 未开始, 1: 已完成, 2: 跳过)
            external_task_id: 外部任务ID（可选）
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 查找任务记录
            query = self.db.query(DBSessionTask).filter(
                DBSessionTask.session_id == session_id
            )
            
            if external_task_id:
                query = query.filter(DBSessionTask.external_task_id == external_task_id)
            
            task = query.first()
            
            if not task:
                print(f"未找到会话任务: session_id={session_id}, external_task_id={external_task_id}")
                return False
            
            # 更新任务状态
            task.task_status = status
            if status == 1:  # 已完成
                task.task_finished_at = datetime.now()
            
            self.db.commit()
            
            print(f"✓ 任务状态已更新: session_id={session_id}, status={status}")
            return True
            
        except Exception as e:
            self.db.rollback()
            print(f"更新任务状态失败: {e}")
            return False
    
    def complete_session_task(
        self,
        session_id: str,
        success: bool,
        error_message: Optional[str] = None
    ) -> bool:
        """
        完成会话任务
        
        Args:
            session_task_id: 会话任务ID
            success: 是否成功
            error_message: 错误消息
            
        Returns:
            bool: 完成是否成功
        """
        try:
            # 1. 更新会话任务状态
            status = 1 if success else 2  # 1: 已完成, 2: 跳过/失败
            if not self.update_task_status(session_id, status):
                return False
            
            # 2. 更新会话状态
            session = self.db.query(DBSession).filter(
                DBSession.session_id == session_id
            ).first()
            
            if session:
                if success:
                    session.state = SessionState.ACTIVE
                else:
                    session.state = SessionState.CANCELLED
                    
                session.last_activity = datetime.now()
                self.db.commit()
            
            
            # 4. 记录完成日志
            completion_info = {
                "session_id": session_id,
                "success": success,
                "completed_at": datetime.now().isoformat(),
                "error_message": error_message
            }
            
            print(f"✓ 会话任务完成: {json.dumps(completion_info, ensure_ascii=False, indent=2)}")
            return True
            
        except Exception as e:
            self.db.rollback()
            print(f"完成会话任务失败: {e}")
            return False
    
    def get_next_redis_task(self):
        """
        获取下一个redis任务id（直接从Redis队列pop）
        """
        if not self.redis_client:
            print("⚠️  Redis未连接，无法获取任务")
            return None
        try:
            # 按优先级顺序尝试获取任务
            for level in LEVEL_LIST:  # ["level5", "level4", "level3", "level2", "level1"]
                # 从队列中弹出任务ID
                task_id = self.redis_client.rpop(level)
                if task_id:
                    print(f"✓ 获取到任务: {task_id} from {level}")
                    return task_id
                
            print("❌ 没有可用任务")
            return None
        except Exception as e:
            print(f"获取Redis任务失败: {e}")
            return None

    def get_send_info_by_redis_id(self, redis_task_id: str) -> Optional[Dict[str, Any]]:
        """
        根据Redis任务ID获取发送消息和url以及商家信息
        提供给影刀APP进行发送消息操作
        
        Args:
            redis_task_id: Redis任务ID
            
        Returns:
            Optional[Dict]: 包含发送内容、URL和商家信息的字典
        """
        try:
            # 从数据库中查询任务信息
            session_task = self.db.query(DBSessionTask).filter(
                DBSessionTask.id == redis_task_id
            ).first()
            
            if not session_task:
                print(f"❌ 未找到会话任务: {redis_task_id}")
                return {"msg": "未找到会话任务", "send_url": "", "send_content": ""}
            
            external_task_id = session_task.external_task_id
            external_task_type = session_task.external_task_type
            if not external_task_id or not external_task_type:
                print(f"❌ 会话任务缺少必要信息: {redis_task_id}")
                return {"msg": "会话任务缺少必要信息", "send_url": "", "send_content": ""}
            
            send_content = session_task.send_content

            send_url, shopname = get_send_info_by_external_task(
                task_type=external_task_type,
                external_task_id=external_task_id,
                db_session=self.db
            )


            return {
                "send_content": send_content,
                "send_url": send_url,
                "shop_name": shopname,
            }
            
        except Exception as e:
            print(f"获取会话任务失败: {e}")
            return None

    def get_task_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict: 任务状态信息
        """
        try:
            # 从数据库获取任务信息
            task = self.db.query(DBSessionTask).filter(
                DBSessionTask.session_id == session_id
            ).first()
            
            if not task:
                return None
            
            # 从数据库获取会话信息
            session = self.db.query(DBSession).filter(
                DBSession.session_id == session_id
            ).first()
            
            if not session:
                return None
            
            return {
                "session_id": session_id,
                "external_task_id": task.external_task_id,
                "task_type": task.external_task_type,
                "task_status": task.task_status,
                "session_state": session.state.value,
                "created_at": task.task_created_at.isoformat(),
                "finished_at": task.task_finished_at.isoformat() if task.task_finished_at else None,
                "send_content": task.send_content,
                "account_id": session.account_id,
                "priority": session.priority,
                "message_count": session.message_count,
                "last_activity": session.last_activity.isoformat()
            }
            
        except Exception as e:
            print(f"获取任务状态失败: {e}")
            return None
    
    def _publish_task_to_redis(self, level: str, redis_task_id: Dict[str, Any]):
        """发布任务到Redis队列"""
        if not self.redis_client:
            print("⚠️  Redis未连接，跳过任务发布")
            return False
            
        try:
            # 发布到任务队列
            queue_key = level
            self.redis_client.lpush(queue_key, str(redis_task_id))
            print(f"✓ 任务已发布到Redis: {redis_task_id}")
            return True
            
            
        except Exception as e:
            print(f"发布任务到Redis失败: {e}")
            return False

    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取待处理任务列表
        
        Args:
            limit: 返回任务数量限制
            
        Returns:
            List[Dict]: 待处理任务列表
        """
        try:
            # 查询待处理的会话任务
            tasks = self.db.query(DBSessionTask).filter(
                DBSessionTask.task_status == 0  # 0: 未开始
            ).order_by(DBSessionTask.task_created_at.desc()).limit(limit).all()
            
            result = []
            for task in tasks:
                # 获取对应的会话信息
                session = self.db.query(DBSession).filter(
                    DBSession.session_id == task.session_id
                ).first()
                
                if session:
                    task_info = {
                        "task_id": task.id,
                        "session_id": task.session_id,
                        "external_task_id": task.external_task_id,
                        "task_type": task.external_task_type,
                        "task_status": task.task_status,
                        "send_content": task.send_content,
                        "created_at": task.task_created_at.isoformat(),
                        "account_id": session.account_id,
                        "shop_id": session.shop_id,
                        "session_state": session.state.value,
                        "priority": session.priority
                    }
                    result.append(task_info)
            
            return result
            
        except Exception as e:
            print(f"获取待处理任务失败: {e}")
            return []