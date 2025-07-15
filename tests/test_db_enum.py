"""
调试枚举值存储问题
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from auto_session.database import create_database_url, get_engine, create_tables, DBSession
from auto_session.session_manager import SessionManager, ensure_account_exists, ensure_shop_exists
from auto_session.models import SessionInfo, TaskType, SessionState
from sqlalchemy.orm import sessionmaker

def debug_enum_storage():
    """调试枚举值存储"""
    print("=== 调试枚举值存储 ===\n")
    
    # 设置数据库
    database_url = create_database_url()
    engine = get_engine(database_url)
    create_tables(engine)
    
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    try:
        # 创建测试数据
        account_id = "debug_account_001"
        shop_id = "debug_shop_001"
        
        ensure_account_exists(db_session, account_id, "调试账号", "taobao")
        ensure_shop_exists(db_session, shop_id, "调试店铺")
        
        # 创建会话信息
        session_info = SessionInfo(
            session_id="debug_session_001",
            account_id=account_id,
            shop_id=shop_id,
            task_type=TaskType.AUTO_BARGAIN,
            state=SessionState.ACTIVE,
            created_by="robot",
            priority=3,
            message_count=0
        )
        
        print(f"创建会话前的枚举值:")
        print(f"  task_type: {session_info.task_type} (类型: {type(session_info.task_type)})")
        print(f"  state: {session_info.state} (类型: {type(session_info.state)})")
        
        # 创建会话管理器
        session_manager = SessionManager(db_session)
        
        # 创建会话
        session_id = session_manager.create_session(session_info)
        print(f"\n✓ 会话创建成功: {session_id}")
        
        # 直接查询数据库验证
        db_session_obj = db_session.query(DBSession).filter(
            DBSession.session_id == session_id
        ).first()
        
        if db_session_obj:
            print(f"\n数据库中的枚举值:")
            print(f"  task_type: {db_session_obj.task_type} (类型: {type(db_session_obj.task_type)})")
            print(f"  state: {db_session_obj.state} (类型: {type(db_session_obj.state)})")
        else:
            print("❌ 数据库中没有找到会话记录")
        
        # 测试状态获取
        status = session_manager.get_session_status(account_id, shop_id)
        print(f"\n通过会话管理器获取的状态:")
        for key, value in status.items():
            print(f"  {key}: {value} (类型: {type(value)})")
        
    except Exception as e:
        print(f"调试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db_session.close()

if __name__ == "__main__":
    debug_enum_storage()