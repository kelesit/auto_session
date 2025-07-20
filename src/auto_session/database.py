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
    Column,
    DECIMAL
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

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
    account_name: Mapped[str] = mapped_column(String(100), nullable=True)
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
        String(50), unique=True, nullable=True, index=True
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
    shop_name: Mapped[str] = mapped_column(
        String(50), ForeignKey("shops.shop_name"), nullable=False
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
        Index('idx_account_shop_state', 'account_id', 'shop_name', 'state'),
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

class DBSessionTask(Base):
    """会话任务表"""
    __tablename__ = "session_tasks"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_task_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="外部任务类型"
    )
    external_task_id: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="外部任务ID"
    )
    task_created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="任务创建时间"    )
    task_finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="任务完成时间"
    )
    task_status: Mapped[str] = mapped_column(
        Integer, nullable=False, comment="任务状态，0: 未开始, 1: 已完成, 2: 跳过"
    )
    send_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="发送内容"
    )
    session_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sessions.session_id"), nullable=False, comment="关联会话ID"
    )

    __table___args__ = (
        Index('idx_session_id', 'session_id'),
    )


# ======= 上游任务 =======
## 不可随意修改，必须与上游系统保持一致
class DBBargainTask(Base):
    """砍价任务表"""
    __tablename__ = 'bargain_task'
    # 基本属性
    # cpmaso 信息
    ## 交易详情
    cpmaso_trade_id = Column(Integer,primary_key=True, nullable=False, comment='交易记录ID')
    trade_status = Column(Integer, nullable=False, default=0, comment='交易状态 0: 新交易，待付款 1:已提交，待审核')
    trade_no = Column(String(64), nullable=False, comment='交易号')
    trade_platform_order_id = Column(String(64), nullable=False, comment='交易平台订单号')
    buy_no = Column(Integer, nullable=False, comment='采购单号')
    add_time = Column(DateTime, nullable=True, comment='添加时间')
    cpmaso_account = Column(String(256), nullable=True,comment='CPMASO指派人员和账号')
    store_id = Column(Integer, nullable=False, comment='店铺ID')
    platform = Column(String(64), nullable=False, comment='交易平台')
    
    ## 订单商品详情信息
    product_main_id = Column(String(256), nullable=True, comment='货源主单号')
    product_sub_id = Column(String(256), nullable=True, comment='货源子单号')
    buy_id = Column(String(256), nullable=True, comment='采购ID')
    buy_person = Column(String(256), nullable=True, comment='采购人')
    shop_name = Column(String(256), nullable=True, comment='店铺名称')
    product_price = Column(DECIMAL(10, 2), nullable=True, comment='商品原价')
    logistics_price = Column(DECIMAL(10, 2), nullable=True, comment='物流价格')
    original_price = Column(DECIMAL(10, 2), nullable=True, comment='原始价格,商品原价+物流价格')

    # 任务状态
    update_time = Column(DateTime, nullable=False, default=datetime.now, comment='更新时间')
    task_status = Column(Integer, nullable=False, default=0, comment='任务状态 0:未开始 1:进行中 2:已完成 3:已取消')
    last_offer_price = Column(DECIMAL(10, 2), nullable=True, comment='最新报价')
    final_price = Column(DECIMAL(10, 2), nullable=True, comment='最终成交价=最新报价+物流价格')
    upload_cpmaso = Column(Integer, nullable=False, default=0, comment='是否上传到CPMASO 0:未上传 1:已上传')

    # 关联对话任务属性
    last_chat_id = Column(Integer, nullable=True, comment='最后对话ID')





def create_database_url(
    host: str = "",
    port: int = 3306,
    username: str = "",
    password: str = "",
    database: str = "",
    charset: str = "",
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

def get_db_session():
    """获取数据库会话"""
    engine = get_engine(create_database_url())
    Session = sessionmaker(bind=engine)
    return Session()