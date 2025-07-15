"""
数据模型

基于设计文档的完整数据模型定义，支持：
1. 会话生命周期管理
2. 会话转交机制
3. 消息处理
4. 任务关联
"""

from enum import Enum
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


class TaskType(str, Enum):
    """任务类型"""
    # 人工会话
    MANUAL_CUSTOMER_SERVICE = "manual_customer_service"
    MANUAL_COMPLAINT = "manual_complaint"
    MANUAL_URGENT = "manual_urgent"
    
    # 机器人会话
    AUTO_BARGAIN = "auto_bargain"
    AUTO_FOLLOW_UP = "auto_follow_up"


class SessionState(str, Enum):
    """会话状态"""
    PENDING = "pending"          # 等待激活
    ACTIVE = "active"            # 激活
    COMPLETED = "completed"      # 完成
    TRANSFERRED = "transferred"  # 转交人工
    PAUSED = "paused"           # 暂停
    CANCELLED = "cancelled"      # 取消
    TIMEOUT = "timeout"         # 超时


class TransferStatus(str, Enum):
    """转交状态"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class UrgencyLevel(str, Enum):
    """紧急程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Priority(int, Enum):
    """优先级"""
    EMERGENCY = 1    # 紧急 - MANUAL_URGENT
    HIGH = 2         # 高 - MANUAL_CUSTOMER_SERVICE, MANUAL_COMPLAINT
    MEDIUM = 3       # 中 - AUTO_BARGAIN
    LOW = 4          # 低 - AUTO_FOLLOW_UP


@dataclass
class SessionInfo:
    """会话信息"""
    session_id: str
    account_id: str
    shop_id: str
    task_type: TaskType
    state: SessionState
    created_by: str  # "robot" or "human"
    priority: int = 3
    external_task_id: Optional[str] = None
    message_count: int = 0
    created_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    timeout_at: Optional[datetime] = None
    transferred_at: Optional[datetime] = None
    transfer_reason: Optional[str] = None


class RawMessage:
    """原始消息数据
    {
    'shopname': '精品浴缸店', 
    'messages': [
        {
            'id': '3587452118761.PNM', 
            'nick': 't-2217567810350-0', 
            'time':'2025-07-03 10:45:16', 
            'content': '平台交易号:2807802123905538788,您好，请问订单的发货时间能否确定？07 
    月06日前可以发货吗? 如果近期无法确定我们只能申请退款处理。'
        }, 
        {
            'id': '3595269819313.PNM', 
            'nick': 'tb5637469_2011', 
            'time': '2025-07-03 10:45:34', 
            'content': '可以的，今天发'
        }
        ]
    }
    """
    shop_name: str
    messages: List[Dict[str, Any]]  # 每条消息包含 id, nick, time, content



@dataclass
class MessageData:
    """消息数据
    {
        'id': '3557925002486.PNM', 
        'nick': 't-2217567810350-0', 
        'time': '2025-06-11 14: 41: 58', 
        'content': '平台交易号: 2603865144931538788,你好，请问最快什么时候发货，6月14日前可以发货吗？'
    }"""
    message_id: str
    content: str
    from_source: str  # "shop" or "account"
    sent_at: datetime
    
    sender: Optional[str] = None  # 发送者昵称
    platform_data: Optional[Dict[str, Any]] = None


@dataclass
class SessionCreationResult:
    """会话创建结果"""
    success: bool
    session_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    conflict_session_id: Optional[str] = None


@dataclass
class TransferResult:
    """转交结果"""
    success: bool
    transfer_id: Optional[str] = None
    estimated_wait_time: Optional[int] = None  # 分钟
    error_message: Optional[str] = None
    notification_sent: bool = False


@dataclass
class AvailabilityResult:
    """可用性检查结果"""
    available: bool
    current_session_id: Optional[str] = None
    current_session_type: Optional[TaskType] = None
    estimated_available_at: Optional[datetime] = None


@dataclass
class ProcessResult:
    """消息处理结果"""
    processed_messages: int = 0
    skipped_messages: int = 0
    active_session_id: Optional[str] = None
    session_operations: List[str, Any] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.session_operations is None:
            self.session_operations = []
        if self.errors is None:
            self.errors = []


@dataclass
class TransferData:
    """转交数据"""
    session_id: str
    from_type: str  # "robot" or "human"
    to_type: str    # "robot" or "human"
    transfer_reason: str
    transfer_data: Dict[str, Any]
    transferred_by: str
    urgency_level: UrgencyLevel = UrgencyLevel.MEDIUM


# 任务类型到优先级的映射
TASK_TYPE_PRIORITY = {
    TaskType.MANUAL_URGENT: Priority.EMERGENCY,
    TaskType.MANUAL_CUSTOMER_SERVICE: Priority.HIGH,
    TaskType.MANUAL_COMPLAINT: Priority.HIGH,
    TaskType.AUTO_BARGAIN: Priority.MEDIUM,
    TaskType.AUTO_FOLLOW_UP: Priority.LOW,
}


def get_task_priority(task_type: TaskType) -> int:
    """获取任务类型的优先级"""
    return TASK_TYPE_PRIORITY.get(task_type, Priority.LOW).value


def is_human_task(task_type: TaskType) -> bool:
    """判断是否为人工任务"""
    return task_type.value.startswith('manual_')


def is_robot_task(task_type: TaskType) -> bool:
    """判断是否为机器人任务"""
    return task_type.value.startswith('auto_')