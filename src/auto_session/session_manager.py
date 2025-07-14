"""
会话管理器 - 核心业务逻辑

实现两个核心功能：
1. 判断新聊天记录是否应该创建新会话还是加入现有会话
2. 判断某个店铺-账号组合是否可以创建新的机器人会话
"""


from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .database import DBAccount, DBMessage, DBSession, DBShop
from .models import MessageData, SessionInfo, SessionState, TaskType

class SessionManager:
    """会话管理器"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def should_create_new_session(
        self,
        account_id: str,
        shop_id: str,
        new_message: MessageData,
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
            tuple[bool, Optional[str]]: (是否创建新会话, 现有会话ID或None)
        """
        # 查找该账号-店铺组合的唯一活跃会话
        active_session = self._find_active_session(account_id, shop_id)

        # 没有活跃会话，创建新会话
        if not active_session:
            return True, None
        
        # 检查会话是否超时
        time_since_last_activity = datetime.now() - active_session.last_activity
        if time_since_last_activity > timedelta(minutes=max_inactive_minutes):
            # 会话超时，创建新会话
            return True, None
        
        # 检查会话状态
        if active_session.state == SessionState.COMPLETED:
            # 已完成的会话，创建新会话
            return True, None
        
        # 加入现有会话
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
        session.last_activity = datetime.now()

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
            session.state = SessionState.MANUAL
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
                DBSession.state.in_([SessionState.ACTIVE]),
            )
            .order_by(DBSession.last_activity.desc())
            .first()
        )
    
    def _complete_existing_sessions(self, account_id: str, shop_id: str):
        """
        完成该账号-店铺组合下的所有现有活跃会话
        确保只有一个活跃会话的约束
        """
        active_states = [SessionState.ACTIVE]
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


def ensure_account_exists(db_session: Session, account_id: str, account_name: str):
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
