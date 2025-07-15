"""
数据库模型
基于设计文档实现完整的会话管理和消息存储
支持会话转交、任务关联、操作日志等功能
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import(
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
    create_engine,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .models import TaskType, SessionState, TransferStatus, UrgencyLevel


class Base(DeclarativeBase):
    """基础模型类，所有模型继承自此类"""
    pass

class DBAccount(Base):
    """账号表"""
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)

    # 关联关系
    sessions: Mapped[list["DBSession"]] = relationship(
        "DBSession", back_populates="account"
    )

class DBShop(Base):
    """店铺表"""
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    shop_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # 关联关系    
    sessions: Mapped[list["DBSession"]] = relationship(
        "DBSession", back_populates="shop"
    )

class DBSession(Base):
    """会话表 - 核心表"""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("accounts.account_id"), nullable=False
    )
    shop_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("shops.shop_id"), nullable=False
    )

    # 会话核心信息
    task_type: Mapped[TaskType] = mapped_column(SQLEnum(TaskType), nullable=False)
    state: Mapped[SessionState] = mapped_column(SQLEnum(SessionState), nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "robot" or "human"

    # 新增字段 - 支持转交和任务管理
    priority: Mapped[int] = mapped_column(Integer, default=3)
    external_task_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # 统计信息
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    timeout_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 转交相关字段
    transferred_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    transfer_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 索引优化
    __table_args__ = (
        # 使用 SQLAlchemy 的 Index 对象
        Index('idx_account_shop_state', 'account_id', 'shop_id', 'state'),
        Index('idx_last_activity', 'last_activity'),
        Index('idx_external_task_id', 'external_task_id'),
        Index('idx_priority_state', 'priority', 'state'),
    )

    # 关联关系
    account: Mapped["DBAccount"] = relationship("DBAccount", back_populates="sessions")
    shop: Mapped["DBShop"] = relationship("DBShop", back_populates="sessions")
    messages: Mapped[list["DBMessage"]] = relationship(
        "DBMessage", back_populates="session", cascade="all, delete-orphan"
    )
    transfers: Mapped[list["DBSessionTransfer"]] = relationship(
        "DBSessionTransfer", back_populates="session", cascade="all, delete-orphan"
    )
    external_task: Mapped[Optional["DBExternalTask"]] = relationship(
        "DBExternalTask", back_populates="session", uselist=False
    )
    operations: Mapped[list["DBSessionOperation"]] = relationship(
        "DBSessionOperation", back_populates="session", cascade="all, delete-orphan"
    )

class DBMessage(Base):
    """消息表 - 存储会话中的消息"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sessions.session_id"), nullable=False
    )
    message_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # 消息内容
    content: Mapped[str] = mapped_column(Text, nullable=False)
    from_source: Mapped[str] = mapped_column(String(20), nullable=False)  # "shop" or "account"
    
    # 时间戳
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # 关联关系
    session: Mapped["DBSession"] = relationship("DBSession", back_populates="messages")


class DBSessionTransfer(Base):
    """会话转交记录表"""
    
    __tablename__ = "session_transfers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sessions.session_id"), nullable=False
    )
    
    # 转交信息
    from_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "robot" or "human"
    to_type: Mapped[str] = mapped_column(String(20), nullable=False)    # "robot" or "human"
    transfer_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transfer_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 操作者信息
    transferred_by: Mapped[str] = mapped_column(String(50), nullable=False)
    transferred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    accepted_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 状态和优先级
    status: Mapped[TransferStatus] = mapped_column(SQLEnum(TransferStatus), default=TransferStatus.PENDING)
    urgency_level: Mapped[UrgencyLevel] = mapped_column(SQLEnum(UrgencyLevel), default=UrgencyLevel.MEDIUM)
    
    # 索引
    __table_args__ = (
        Index('idx_session_id', 'session_id'),
        Index('idx_transferred_at', 'transferred_at'),
        Index('idx_status', 'status'),
    )
    
    # 关联关系
    session: Mapped["DBSession"] = relationship("DBSession", back_populates="transfers")


class DBExternalTask(Base):
    """外部任务关联表"""
    
    __tablename__ = "external_tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("sessions.session_id"), nullable=True
    )
    
    # 任务信息
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'bargain', 'follow_up', 'custom'
    task_status: Mapped[str] = mapped_column(String(20), default='pending')  # 'pending', 'running', 'completed', 'failed', 'transferred'
    task_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 索引
    __table_args__ = (
        Index('idx_task_id', 'task_id'),
        Index('idx_session_id', 'session_id'),
    )
    
    # 关联关系
    session: Mapped[Optional["DBSession"]] = relationship("DBSession", back_populates="external_task")


class DBSessionOperation(Base):
    """会话操作日志表"""
    
    __tablename__ = "session_operations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sessions.session_id"), nullable=False
    )
    
    # 操作信息
    operation_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'create', 'pause', 'resume', 'transfer', 'complete', 'cancel'
    operator_id: Mapped[str] = mapped_column(String(50), nullable=False)
    operator_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'robot', 'human', 'system'
    operation_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    operation_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # 索引
    __table_args__ = (
        Index('idx_session_id', 'session_id'),
        Index('idx_operation_at', 'operation_at'),
    )
    
    # 关联关系
    session: Mapped["DBSession"] = relationship("DBSession", back_populates="operations")

def create_database_url(
    host: str = "192.168.100.33",
    port: int = 3306,
    username: str = "zhenggantian",
    password: str = "123456",
    database: str = "mdm",
    charset: str = "utf8mb4",
) -> str:
    """创建 MySQL 数据库连接 URL"""
    return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}?charset={charset}"

def create_tables(engine):
    """创建所有数据库表"""
    Base.metadata.create_all(engine)

def get_engine(database_url: str):
    """获取数据库引擎"""
    return create_engine(
        database_url,
        echo=False,  # 设置为 True 可以看到 SQL 查询日志
        pool_pre_ping=True,  # 连接池预检查
        pool_recycle=3600,  # 连接回收时间（秒）
    )