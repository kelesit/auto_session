"""
会话管理器 - 核心业务逻辑

实现两个核心功能：
1. 判断新聊天记录是否应该创建新会话还是加入现有会话
2. 判断某个店铺-账号组合是否可以创建新的机器人会话
"""

from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .database import DBAccount, DBMessage, DBSession, DBShop
from .models import MessageData, SessionInfo, SessionState, TaskType, ProcessResult
from .tools import send_notification

ACCOUNT_NICK_NAME_LIST = [
    't-2217567810350-0',  # 示例账号昵称
    # 可以添加更多账号昵称
]

class SessionManager:
    """会话管理器"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def process_message_batch(
        self,
        messages: list[MessageData],
        account_id: str,
        shop_id: Optional[str],
        shop_name: str,
        max_inactive_minutes: int = 30,
    ):
        """
        批量处理消息 - 核心功能
        Args:
            messages: 消息列表
            account_id: 账号ID
            shop_id: 店铺ID
            max_inactive_minutes: 最大非活跃时间（分钟）
        Returns:
            ProcessResult: 处理结果
        """
        result = ProcessResult()

        try:
            # 预处理消息，过滤掉无效或重复的消息
            processed_messages = self._preprocess_messages(messages)
            result.processed_messages = len(processed_messages)
            result.skipped_messages = len(messages) - result.processed_messages


            should_create, existing_session_id = self.should_create_new_session(
                account_id, shop_id, processed_messages, max_inactive_minutes
            )
            if should_create:
                # 创建新会话
                session_id = self.create_session(
                    SessionInfo(
                        session_id=self._generate_session_id(),
                        account_id=account_id,
                        shop_id=shop_id,
                        task_type=TaskType.MANUAL_URGENT,   # 会话类型为人工
                        state=SessionState.TRANSFERRED,
                        created_by="human",
                        priority=1,  # 默认优先级
                        message_count=0,  # 初始为0，添加消息时会更新
                    )
                )
                result.active_session_id = session_id
                
                # 将消息添加到新创建的会话
                for msg in processed_messages:
                    self.add_message_to_session(session_id, msg)
                
                print(f"✓ 创建新会话: {session_id}")
                send_notification(messages, shop_id,shop_name, account_id)

            else:
                existing_session = self._get_session(existing_session_id)
                if existing_session:
                    # 添加消息到现有会话
                    print(f"添加消息到现有会话: {existing_session_id}")
                    for msg in processed_messages:
                        self.add_message_to_session(existing_session.session_id, msg)

                    # 更新会话统计信息（不重复计数，因为add_message_to_session已经增加了）
                    existing_session.last_activity = datetime.now()
                    result.active_session_id = existing_session.session_id

                    if existing_session.state == SessionState.TRANSFERRED:
                        # 如果现有会话是人工处理状态
                        send_notification(messages, shop_id,shop_name, account_id)
                        result.session_operations = ["加入现有的人工会话"]

                    else:
                        # 如果是机器人会话(ACTIVE状态)
                        # 解析消息，判断是否有人工介入
                        if self._check_human_intervention(processed_messages, existing_session.account_id):
                            print(f"✓ 检测到人工介入，转交会话: {existing_session_id}")
                            if not self.switch_session_control(
                                existing_session.session_id, "human", "检测到人工介入"
                            ):
                                # 转交失败
                                result.errors = [f"会话{existing_session.session_id}转人工失败"]
                            else:
                                result.session_operations = ["转交给人工处理"]
                                send_notification(messages, shop_id,shop_name, account_id)

                        else:
                            # 没有人工介入，继续处理机器人任务
                            print(f"✓ 继续处理机器人会话: {existing_session_id}")
                            result.session_operations = ["继续处理机器人会话"]

                else:
                    result.errors = [f"无法找到现有会话: {existing_session_id}"]
                    print(f"错误: 无法找到现有会话: {existing_session_id}")
            return result
        except Exception as e:
            result.errors = [str(e)]
            print(f"处理消息批次失败: {e}")
            return result



    def _check_human_intervention(self, messages: List[MessageData], account_id) -> bool:
        """检查是否有人工介入的消息
        检查账号的消息中是否有来自人工的消息
        账号发的消息 
        机器人发的消息会用'hi'开头
        """
        for msg in messages:
            # 检查消息是否来自账号且内容不以 'hi' 开头
            if msg.from_source == "account" and not msg.content.startswith('hi'):
                # 检查账号昵称是否在允许的列表中
                if msg.sender in ACCOUNT_NICK_NAME_LIST:
                    print(f"检测到人工介入消息: {msg.content} 来自账号: {msg.sender}")
                    return True
                
        return False




    def _preprocess_messages(self, messages: List[MessageData]):
        """
        预处理消息，过滤掉无效或重复的消息
        Args:
            messages: 消息列表
        Returns:
            List[MessageData]: 预处理后的消息列表
        """
        if not messages:
            return []
        
        message_ids = [msg.message_id for msg in messages]

        # 查询已存在的消息
        existing_messages = self.db.query(DBMessage.message_id).filter(
            DBMessage.message_id.in_(message_ids)
        ).all()
        existing_message_ids = {msg.message_id for msg in existing_messages}

        return [msg for msg in messages if msg.message_id not in existing_message_ids]

            

    def should_create_new_session(
        self,
        account_id: str,
        shop_id: Optional[str],
        new_messages: List[MessageData],
        max_inactive_minutes: int = 30,
    ) -> tuple[bool, str | None]:
        """
        判断是否应该创建新会话

        Args:
            account_id: 账号ID
            shop_id: 店铺ID
            new_message: 新消息信息
            max_inactive_minutes: 最大非活跃时间（分钟）

        Returns:
            tuple[bool, Optional[str], Optional[str]]: (是否创建新会话, 现有会话ID或None)
        """
        if not shop_id:
            # 如果没有店铺ID，直接创建新会话
            return True, None

        # 查找该账号-店铺组合的唯一活跃会话(ACTIVE或TRANSFERRED状态)
        active_session = self._find_active_session(account_id, shop_id)

        # 没有活跃会话，创建新会话
        if not active_session:
            return True, None
        
        # 检查会话是否超时
        time_since_last_activity = datetime.now() - active_session.last_activity
        if time_since_last_activity > timedelta(minutes=max_inactive_minutes):
            # 会话超时，创建新会话
            active_session.state = SessionState.TIMEOUT
            return True, None
        
        # 有活跃会话且未超时，加入现有会话
        return False, active_session.session_id
    
    def create_session(self, session_info: SessionInfo) -> str:
        """
        创建新会话
        自动完成该 账号-店铺组合 下的所有现有活跃会话

        Args:
            session_info: 会话信息

        Returns:
            str: 新创建的会话ID
        """
        # 先完成该账号-店铺组合下的所有现有活跃会话
        self._complete_existing_sessions(session_info.account_id, session_info.shop_id)

        new_session = DBSession(
            session_id=session_info.session_id,
            account_id=session_info.account_id,
            shop_id=session_info.shop_id,
            task_type=session_info.task_type,
            state=session_info.state,
            created_by=session_info.created_by,
            priority=session_info.priority,
            external_task_id=session_info.external_task_id,
            message_count=session_info.message_count,
            created_at=session_info.created_at or datetime.now(),
            last_activity=session_info.last_activity or datetime.now(),
        )
        self.db.add(new_session)
        self.db.commit()
        return new_session.session_id
    
    def add_message_to_session(
        self, session_id: str, message: MessageData
    ):
        """
        向会话添加消息

        Args:
            session_id: 会话ID
            message: 消息信息
        """
        session = self._get_session(session_id)
        if not session:
            return False
        
        new_message = DBMessage(
            message_id=message.message_id,
            session_id=session_id,
            content=message.content,
            from_source=message.from_source,
            sent_at=message.sent_at,
            # platform_data=message.platform_data,
        )
        self.db.add(new_message)

        session.message_count += 1
        session.last_activity = message.sent_at
        if session.state == SessionState.PENDING:
            # 只有当会话是 PENDING 状态时才激活
            session.state = SessionState.ACTIVE


        self.db.commit()
        return True
    
    def switch_session_control(
        self, session_id: str, new_owner: str, reason: str | None = None
    ):
        """
        切换会话控制权（机器人 <-> 人工）

        Args:
            session_id: 会话ID
            new_owner: 新的控制者 ("robot" 或 "human")
            reason: 切换原因

        Returns:
            bool: 是否切换成功
        """
        session = self._get_session(session_id)
        if not session:
            return False

        # 更新会话状态
        session.created_by = new_owner

        if new_owner == "human":
            session.state = SessionState.TRANSFERRED
            session.transferred_at = datetime.now()
        else:
            session.state = SessionState.ACTIVE

        session.last_activity = datetime.now()

        self.db.commit()
        return True
    
    def get_session_status(self, account_id: str, shop_id: str) -> dict:
        """
        获取账号-店铺组合的会话状态

        Args:
            account_id: 账号ID
            shop_id: 店铺ID

        Returns:
            dict: 会话状态信息
        """
        active_session = self._find_active_session(account_id, shop_id)
        if not active_session:
            return {
                "has_active_session": False,
                "session_id": None,
                "state": None,
                "created_by": None,
                "message_count": 0,
                "last_activity": None,
            }
        return {
            "has_active_session": True,
            "session_id": active_session.session_id,
            "state": active_session.state.value,
            "created_by": active_session.created_by,
            "task_type": active_session.task_type.value,
            "message_count": active_session.message_count,
            "last_activity": active_session.last_activity,
        }
    
    def _find_active_session(self, account_id: str, shop_id: str) -> DBSession | None:
        """
        查找该账号-店铺组合的唯一活跃会话
        """
        return (
            self.db.query(DBSession)
            .filter(
                DBSession.account_id == account_id,
                DBSession.shop_id == shop_id,
                DBSession.state.in_([SessionState.ACTIVE, SessionState.TRANSFERRED]),
            )
            .order_by(DBSession.last_activity.desc())
            .first()
        )
    
    def _complete_existing_sessions(self, account_id: str, shop_id: str):
        """
        完成该账号-店铺组合下的所有现有活跃会话
        确保只有一个活跃会话的约束
        """
        active_states = [SessionState.ACTIVE, SessionState.TRANSFERRED]
        existing_sessions = (
            self.db.query(DBSession)
            .filter(
                DBSession.account_id == account_id,
                DBSession.shop_id == shop_id,
                DBSession.state.in_(active_states),
            )
            .all()
        )
        for session in existing_sessions:
            session.state = SessionState.COMPLETED
            session.last_activity = datetime.now()

        if existing_sessions:
            self.db.commit()


    def _get_session(self, session_id: str) -> DBSession | None:
        """
        获取会话信息
        """
        return (self.db.query(DBSession)
            .filter(DBSession.session_id == session_id)
            .first()
        )
    
    def _generate_session_id(self) -> str:
        """生成会话ID"""
        from uuid import uuid4

        return f"sess_{uuid4().hex[:12]}"
    

def create_session_manager(db_session: Session) -> SessionManager:
    """创建会话管理器实例"""
    return SessionManager(db_session)


def ensure_account_exists(db_session: Session, account_id: str, account_name: str, platform: str = "default"):
    """确保账号存在"""
    existing = (
        db_session.query(DBAccount)
        .filter(DBAccount.account_id == account_id)
        .first()
    )
    if not existing:
        account = DBAccount(
            account_id=account_id,
            account_name=account_name,
            is_active=True,
            created_at=datetime.now(),
            platform=platform,  # 默认平台
        )
        db_session.add(account)
        db_session.commit()


def ensure_shop_exists(db_session: Session, shop_id: str, shop_name: str):
    """确保店铺存在"""
    existing = db_session.query(DBShop).filter(DBShop.shop_id == shop_id).first()
    if not existing:
        shop = DBShop(
            shop_id=shop_id,
            shop_name=shop_name,
            created_at=datetime.now(),
        )
        db_session.add(shop)
        db_session.commit()
