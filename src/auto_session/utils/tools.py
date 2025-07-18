from sqlalchemy.orm import Session
from typing import Any, Callable, List, Optional
import functools
import time
import random

from ..models import RawMessage, MessageData
from ..database import DBBargainTask, get_db_session
from ..external.taotian import get_order_info_tw, get_send_url_tw
from .logger import get_logger
logger = get_logger(__name__)


def api_retry(max_retries: int = 3, base_delay: float = 1, backoff_factor: float = 2):
    """
    API调用重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        backoff_factor: 退避因子，每次重试延迟时间的倍数
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    last_exception = e
                    error_msg = str(e)

                    if attempt < max_retries - 1:
                        wait_time = base_delay * (backoff_factor ** attempt)
                        logger.warning(f"{func.__name__} API调用失败，等待 {wait_time:.1f} 秒后重试 (第{attempt+1}/{max_retries}次): {error_msg}")
                        time.sleep(wait_time + random.uniform(0.5, 1.5))
                        continue
                    break
            logger.error(f"{func.__name__} API调用失败，所有重试均未成功: {last_exception}")
            raise last_exception
        return wrapper
    return decorator


@api_retry(max_retries=3, base_delay=1, backoff_factor=2)
def send_notification(messages, shop_name, account_id):
    """
    发送通知给指定的账号
    """
    print(f"\n🔔 ===== 消息通知 =====")
    print(f"📧 接收账号: {account_id}")
    print(f"🏪 店铺信息: {shop_name}")
    print(f"📝 消息数量: {len(messages)} 条")
    print(f"📄 消息详情:")
    
    for i, msg in enumerate(messages, 1):
        print(f"  {i}. {msg}")
    
    print(f"========================\n")



def get_send_info_for_bargain(task_id, db_session: Session=None):
    """获取砍价任务的发送内容和URL"""
    if db_session is None:
        db_session = get_db_session()
        should_close = True
    else:
        should_close = False

    # 查询砍价任务
    try:
        bargain_task = db_session.query(DBBargainTask).filter(DBBargainTask.id == task_id).first()
        if not bargain_task:
            print(f"❌ 未找到砍价任务: {task_id}")
            return None, None
    finally:
        if should_close:
            db_session.close()

    shop_name = bargain_task.shop_name
    platform = bargain_task.platform
    if platform == "淘天":
        order_info_tw_resp = get_order_info_tw(bargain_task.trade_platform_order_id)
        if not order_info_tw_resp.get('success'):
            print(f"❌ 获取订单信息失败: {order_info_tw_resp.get('message', '未知错误')}")
            return None, None
        order_info = order_info_tw_resp['data']
        bizId = order_info['purchase_orders'][0]['outer_purchase_id']
        sub_user_id = order_info['purchase_orders'][0]['sub_user_id']
        
        send_url_tw_resp = get_send_url_tw(bizId, sub_user_id)
        if not send_url_tw_resp.get('success'):
            print(f"❌ 获取发送URL失败: {send_url_tw_resp.get('message', '未知错误')}, bizId: {bizId}, sub_user_id: {sub_user_id}")
            return None, None
        send_url = send_url_tw_resp['data']['send_url']
        
        if not send_url:
            print(f"❌ 获取发送URL失败: {bizId}, {sub_user_id}")
            return None, None
        return send_url, shop_name
    
    else:
        print(f"❌ 不支持的平台: {platform}")
        return None, None
    

def get_send_info_by_external_task(task_type, task_id, db_session: Session=None):
    """
    获取发送详情
    Args:
        task_type: 任务类型
        external_task_id: 外部任务ID
        db_session: 可选的数据库会话，如果不提供则新建
        
    Returns:
        tuple: (send_url, shop_name)
    """
    if db_session is None:
        db_session = get_db_session()
        should_close = True
    else:
        should_close = False

    try:
        if task_type == "auto_bargain":
            return get_send_info_for_bargain(task_id, db_session)
        else:
            print(f"❌ 未知任务类型: {task_type}")
            return None, None
    finally:
        if should_close:
            db_session.close()



def extract_account_id_from_raw_message_list_tw(messages) -> str:
    """
    从淘天消息列表中提取己方账号ID
    通常以t-开头的ID为己方账号ID
    Args:
        messages: 消息列表（可以是RawMessage对象或字典）
        
    Returns:
        str: 账号ID
    """
    for msg in messages:
        # 处理字典格式的消息
        if isinstance(msg, dict):
            nick = msg.get('nick')
        else:
            # 处理RawMessage对象
            nick = msg.nick
            
        if nick and nick.startswith("t-"):
            account_id = nick
            print(f"✅ 提取到淘天账号ID: {account_id}")
            return account_id
    print("❌ 未找到淘天账号ID")
    return "未知账号"



def extract_account_id_from_raw_message_list(platform: str, messages) -> str:
    """
    从消息中提取账号ID
    Args:
        platform: 平台类型
        messages: 消息列表（可以是RawMessage对象或字典）
        
    Returns:
        str: 账号ID
    """
    if not messages:
        return "未知账号"
    if platform == "淘天":
        return extract_account_id_from_raw_message_list_tw(messages)
    else:
        return "非淘天平台，无法提取账号ID"
    
    