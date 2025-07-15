"""
会话管理器深度测试用例
包含各种边界条件和异常情况的测试
"""

import os
import sys
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import uuid
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from auto_session.session_manager import SessionManager, ensure_account_exists, ensure_shop_exists
from auto_session.models import SessionInfo, MessageData, TaskType, SessionState
from auto_session.database import create_database_url, get_engine, create_tables



def setup_mysql_database():
    """设置 MySQL 数据库连接"""
    database_url = create_database_url()
    engine = get_engine(database_url)
    
    # 确保表存在
    create_tables(engine)
    
    Session = sessionmaker(bind=engine)
    return Session()


def test_basic_session_creation():
    """测试基本会话创建功能"""
    print("=== 测试 1: 基本会话创建 ===")
    
    db_session = setup_mysql_database()
    session_manager = SessionManager(db_session)
    
    # 测试数据
    account_id = f"test_account_{uuid.uuid4().hex[:8]}"
    shop_id = f"test_shop_{uuid.uuid4().hex[:8]}"
    
    # 创建账号和店铺
    ensure_account_exists(db_session, account_id, "测试账号", "taobao")
    ensure_shop_exists(db_session, shop_id, "测试店铺")
    
    # 创建测试消息
    message = MessageData(
        message_id=f"msg_{uuid.uuid4().hex[:8]}",
        content="你好，我想咨询一下产品",
        from_source="shop",
        sent_at=datetime.now()
    )
    
    # 测试是否应该创建新会话
    should_create, existing_session_id = session_manager.should_create_new_session(
        account_id, shop_id, message
    )
    
    print(f"✓ 首次查询是否创建新会话: {should_create}")
    print(f"✓ 现有会话ID: {existing_session_id}")
    
    assert should_create == True, "首次应该创建新会话"
    assert existing_session_id is None, "首次不应该有现有会话ID"
    
    db_session.close()
    print("✓ 基本会话创建测试通过\n")


def test_session_timeout():
    """测试会话超时逻辑"""
    print("=== 测试 2: 会话超时逻辑 ===")
    
    db_session = setup_mysql_database()
    session_manager = SessionManager(db_session)
    
    account_id = f"timeout_account_{uuid.uuid4().hex[:8]}"
    shop_id = f"timeout_shop_{uuid.uuid4().hex[:8]}"
    
    ensure_account_exists(db_session, account_id, "超时测试账号", "taobao")
    ensure_shop_exists(db_session, shop_id, "超时测试店铺")
    
    # 创建一个会话
    session_info = SessionInfo(
        session_id=f"timeout_sess_{uuid.uuid4().hex[:8]}",
        account_id=account_id,
        shop_id=shop_id,
        task_type=TaskType.AUTO_BARGAIN,
        state=SessionState.ACTIVE,
        created_by="robot",
        priority=3
    )
    
    session_id = session_manager.create_session(session_info)
    print(f"✓ 创建会话: {session_id}")
    
    # 添加一条消息
    old_message = MessageData(
        message_id=f"msg_old_{uuid.uuid4().hex[:8]}",
        content="这是很久之前的消息",
        from_source="shop",
        sent_at=datetime.now() - timedelta(hours=2)  # 2小时前
    )
    
    session_manager.add_message_to_session(session_id, old_message)
    
    # 现在发送一条新消息，测试超时逻辑
    new_message = MessageData(
        message_id=f"msg_new_{uuid.uuid4().hex[:8]}",
        content="这是新消息",
        from_source="shop",
        sent_at=datetime.now()
    )
    
    # 测试短超时时间（5分钟）
    should_create, existing_session_id = session_manager.should_create_new_session(
        account_id, shop_id, new_message, max_inactive_minutes=5
    )
    
    print(f"✓ 超时测试（5分钟）: 应该创建新会话={should_create}")
    
    # 测试长超时时间（180分钟）
    should_create_long, existing_session_id_long = session_manager.should_create_new_session(
        account_id, shop_id, new_message, max_inactive_minutes=180
    )
    
    print(f"✓ 超时测试（180分钟）: 应该创建新会话={should_create_long}")
    
    assert should_create == True, "超过5分钟应该创建新会话"
    assert should_create_long == False, "180分钟内不应该创建新会话"
    
    db_session.close()
    print("✓ 会话超时测试通过\n")


def test_session_state_transitions():
    """测试会话状态转换"""
    print("=== 测试 3: 会话状态转换 ===")
    
    db_session = setup_mysql_database()
    session_manager = SessionManager(db_session)
    
    account_id = f"state_account_{uuid.uuid4().hex[:8]}"
    shop_id = f"state_shop_{uuid.uuid4().hex[:8]}"
    
    ensure_account_exists(db_session, account_id, "状态测试账号", "taobao")
    ensure_shop_exists(db_session, shop_id, "状态测试店铺")
    
    # 创建会话
    session_info = SessionInfo(
        session_id=f"state_sess_{uuid.uuid4().hex[:8]}",
        account_id=account_id,
        shop_id=shop_id,
        task_type=TaskType.AUTO_BARGAIN,
        state=SessionState.ACTIVE,
        created_by="robot",
        priority=3
    )
    
    session_id = session_manager.create_session(session_info)
    print(f"✓ 创建会话: {session_id}")
    
    # 获取初始状态
    initial_status = session_manager.get_session_status(account_id, shop_id)
    print(f"✓ 初始状态: {initial_status['state']}")
    
    # 测试切换到人工控制
    switch_success = session_manager.switch_session_control(
        session_id, "human", "需要转人工客服"
    )
    print(f"✓ 切换到人工控制: {switch_success}")
    
    # 检查状态变化
    human_status = session_manager.get_session_status(account_id, shop_id)
    print(f"✓ 切换后状态: {human_status['state']}")
    
    # 测试切换回机器人控制
    switch_back_success = session_manager.switch_session_control(
        session_id, "robot", "切回机器人控制"
    )
    print(f"✓ 切换回机器人控制: {switch_back_success}")
    
    # 检查最终状态
    final_status = session_manager.get_session_status(account_id, shop_id)
    print(f"✓ 最终状态: {final_status['state']}")
    
    assert initial_status['state'] == SessionState.ACTIVE, "初始状态应该是ACTIVE"
    assert human_status['state'] == SessionState.TRANSFERRED, "切换后应该是TRANSFERRED"
    assert final_status['state'] == SessionState.ACTIVE, "切换回后应该是ACTIVE"
    
    db_session.close()
    print("✓ 会话状态转换测试通过\n")


def test_concurrent_sessions():
    """测试并发会话管理"""
    print("=== 测试 4: 并发会话管理 ===")
    
    db_session = setup_mysql_database()
    cleanup_test_data(db_session)
    session_manager = SessionManager(db_session)
    
    # 创建多个账号和店铺
    num_accounts = 3
    num_shops = 2
    
    accounts = []
    shops = []
    
    for i in range(num_accounts):
        account_id = f"concurrent_account_{i}_{uuid.uuid4().hex[:8]}"
        accounts.append(account_id)
        ensure_account_exists(db_session, account_id, f"并发测试账号{i}", "taobao")
    
    for i in range(num_shops):
        shop_id = f"concurrent_shop_{i}_{uuid.uuid4().hex[:8]}"
        shops.append(shop_id)
        ensure_shop_exists(db_session, shop_id, f"并发测试店铺{i}")
    
    print(f"✓ 创建了 {num_accounts} 个账号和 {num_shops} 个店铺")
    
    # 为每个账号-店铺组合创建会话
    sessions = []
    session_counter = 0
    
    for account_id in accounts:
        for shop_id in shops:
            session_id = f"concurrent_sess_{session_counter}_{uuid.uuid4().hex[:16]}"
            session_counter += 1

            session_info = SessionInfo(
                session_id=session_id,
                account_id=account_id,
                shop_id=shop_id,
                task_type=TaskType.AUTO_BARGAIN,
                state=SessionState.ACTIVE,
                created_by="robot",
                priority=3
            )
            
            created_session_id = session_manager.create_session(session_info)
            sessions.append((created_session_id, account_id, shop_id))
    
    print(f"✓ 创建了 {len(sessions)} 个会话")
    
    # 测试每个会话的状态
    for session_id, account_id, shop_id in sessions:
        status = session_manager.get_session_status(account_id, shop_id)
        assert status['session_id'] == session_id, f"会话ID不匹配: {session_id}"
        assert status['state'] == SessionState.ACTIVE, f"会话状态不正确: {status['state']}"
    
    # 测试添加消息到所有会话
    for session_id, account_id, shop_id in sessions:
        message = MessageData(
            message_id=f"msg_{session_id}_{uuid.uuid4().hex[:8]}",
            content=f"测试消息 for {session_id}",
            from_source="shop",
            sent_at=datetime.now()
        )
        
        success = session_manager.add_message_to_session(session_id, message)
        assert success, f"添加消息失败: {session_id}"
    
    print("✓ 所有会话消息添加成功")
    
    db_session.close()
    print("✓ 并发会话管理测试通过\n")


def test_edge_cases():
    """测试边界条件和异常情况"""
    print("=== 测试 5: 边界条件和异常情况 ===")
    
    db_session = setup_mysql_database()
    session_manager = SessionManager(db_session)
    
    # 测试不存在的账号和店铺
    non_existent_account = f"non_existent_{uuid.uuid4().hex[:8]}"
    non_existent_shop = f"non_existent_{uuid.uuid4().hex[:8]}"
    
    message = MessageData(
        message_id=f"msg_{uuid.uuid4().hex[:8]}",
        content="测试消息",
        from_source="shop",
        sent_at=datetime.now()
    )
    
    # 测试查询不存在的会话状态
    try:
        status = session_manager.get_session_status(non_existent_account, non_existent_shop)
        print(f"✓ 不存在的会话状态: {status}")
    except Exception as e:
        print(f"✓ 处理不存在的会话异常: {e}")
    
    # 创建测试账号和店铺
    account_id = f"edge_account_{uuid.uuid4().hex[:8]}"
    shop_id = f"edge_shop_{uuid.uuid4().hex[:8]}"
    
    ensure_account_exists(db_session, account_id, "边界测试账号", "taobao")
    ensure_shop_exists(db_session, shop_id, "边界测试店铺")
    
    # 测试空消息内容
    empty_message = MessageData(
        message_id=f"empty_msg_{uuid.uuid4().hex[:8]}",
        content="",
        from_source="shop",
        sent_at=datetime.now()
    )
    
    should_create, _ = session_manager.should_create_new_session(
        account_id, shop_id, empty_message
    )
    print(f"✓ 空消息内容测试: {should_create}")
    
    # 测试极长的消息内容
    long_content = "很长的消息内容" * 1000
    long_message = MessageData(
        message_id=f"long_msg_{uuid.uuid4().hex[:8]}",
        content=long_content,
        from_source="shop",
        sent_at=datetime.now()
    )
    
    should_create_long, _ = session_manager.should_create_new_session(
        account_id, shop_id, long_message
    )
    print(f"✓ 长消息内容测试: {should_create_long}")
    
    # 测试未来时间的消息
    future_message = MessageData(
        message_id=f"future_msg_{uuid.uuid4().hex[:8]}",
        content="未来的消息",
        from_source="shop",
        sent_at=datetime.now() + timedelta(hours=1)
    )
    
    should_create_future, _ = session_manager.should_create_new_session(
        account_id, shop_id, future_message
    )
    print(f"✓ 未来时间消息测试: {should_create_future}")
    
    db_session.close()
    print("✓ 边界条件测试通过\n")


def test_performance():
    """测试性能"""
    print("=== 测试 6: 性能测试 ===")
    
    db_session = setup_mysql_database()
    session_manager = SessionManager(db_session)
    
    # 创建测试数据
    account_id = f"perf_account_{uuid.uuid4().hex[:8]}"
    shop_id = f"perf_shop_{uuid.uuid4().hex[:8]}"
    
    ensure_account_exists(db_session, account_id, "性能测试账号", "taobao")
    ensure_shop_exists(db_session, shop_id, "性能测试店铺")
    
    # 创建会话
    session_info = SessionInfo(
        session_id=f"perf_sess_{uuid.uuid4().hex[:8]}",
        account_id=account_id,
        shop_id=shop_id,
        task_type=TaskType.AUTO_BARGAIN,
        state=SessionState.ACTIVE,
        created_by="robot",
        priority=3
    )
    
    session_id = session_manager.create_session(session_info)
    
    # 测试大量消息添加的性能
    num_messages = 100
    start_time = time.time()
    
    for i in range(num_messages):
        message = MessageData(
            message_id=f"perf_msg_{i}_{uuid.uuid4().hex[:8]}",
            content=f"性能测试消息 {i}",
            from_source="shop" if i % 2 == 0 else "account",
            sent_at=datetime.now() + timedelta(seconds=i)
        )
        
        success = session_manager.add_message_to_session(session_id, message)
        assert success, f"添加消息失败: {i}"
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"✓ 添加 {num_messages} 条消息耗时: {duration:.2f} 秒")
    print(f"✓ 平均每条消息耗时: {duration/num_messages*1000:.2f} 毫秒")
    
    # 测试状态查询性能
    start_time = time.time()
    for i in range(100):
        status = session_manager.get_session_status(account_id, shop_id)
        assert status['session_id'] == session_id
    
    end_time = time.time()
    query_duration = end_time - start_time
    
    print(f"✓ 100 次状态查询耗时: {query_duration:.2f} 秒")
    print(f"✓ 平均每次查询耗时: {query_duration/100*1000:.2f} 毫秒")
    
    db_session.close()
    print("✓ 性能测试通过\n")


def test_data_integrity():
    """测试数据完整性"""
    print("=== 测试 7: 数据完整性 ===")
    
    db_session = setup_mysql_database()
    session_manager = SessionManager(db_session)
    
    account_id = f"integrity_account_{uuid.uuid4().hex[:8]}"
    shop_id = f"integrity_shop_{uuid.uuid4().hex[:8]}"
    
    ensure_account_exists(db_session, account_id, "完整性测试账号", "taobao")
    ensure_shop_exists(db_session, shop_id, "完整性测试店铺")
    
    # 创建会话
    session_info = SessionInfo(
        session_id=f"integrity_sess_{uuid.uuid4().hex[:8]}",
        account_id=account_id,
        shop_id=shop_id,
        task_type=TaskType.AUTO_BARGAIN,
        state=SessionState.ACTIVE,
        created_by="robot",
        priority=3
    )
    
    session_id = session_manager.create_session(session_info)
    
    # 添加消息并验证计数
    messages_to_add = 10
    for i in range(messages_to_add):
        message = MessageData(
            message_id=f"integrity_msg_{i}_{uuid.uuid4().hex[:8]}",
            content=f"完整性测试消息 {i}",
            from_source="shop",
            sent_at=datetime.now() + timedelta(seconds=i)
        )
        
        session_manager.add_message_to_session(session_id, message)
    
    # 验证消息计数
    status = session_manager.get_session_status(account_id, shop_id)
    print(f"✓ 会话消息计数: {status.get('message_count', 0)}")
    
    # 验证最后活动时间更新
    last_activity = status.get('last_activity')
    print(f"✓ 最后活动时间: {last_activity}")
    
    assert isinstance(last_activity, datetime), "最后活动时间应该是datetime对象"
    
    # 测试会话状态一致性
    initial_state = status['state']
    
    # 切换状态
    session_manager.switch_session_control(session_id, "human", "测试状态切换")
    
    # 验证状态变化
    new_status = session_manager.get_session_status(account_id, shop_id)
    new_state = new_status['state']
    
    assert new_state != initial_state, "状态应该已经改变"
    assert new_state == SessionState.TRANSFERRED, "新状态应该是HUMAN_TAKEOVER"
    
    print(f"✓ 状态变化验证: {initial_state} -> {new_state}")
    
    db_session.close()
    print("✓ 数据完整性测试通过\n")


def run_all_tests():
    """运行所有测试"""
    print("=== 开始深度测试会话管理器 ===\n")
    
    test_functions = [
        test_basic_session_creation,
        test_session_timeout,
        test_session_state_transitions,
        test_concurrent_sessions,
        test_edge_cases,
        test_performance,
        test_data_integrity
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"=== 测试完成 ===")
    print(f"✓ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"总计: {passed + failed}")

def cleanup_test_data(db_session):
    """清理测试数据"""
    try:
        # 删除测试相关的会话
        db_session.execute(
            text("DELETE FROM sessions WHERE session_id LIKE 'concurrent_sess%' OR session_id LIKE 'sess_%'")
        )
        # 删除测试相关的消息
        db_session.execute(
            text("DELETE FROM messages WHERE session_id LIKE 'concurrent_sess%' OR session_id LIKE 'sess_%'")
        )
        # 删除测试相关的账号
        db_session.execute(
            text("DELETE FROM accounts WHERE account_id LIKE 'concurrent_account%' OR account_id LIKE 'test_account%'")
        )
        # 删除测试相关的店铺
        db_session.execute(
            text("DELETE FROM shops WHERE shop_id LIKE 'concurrent_shop%' OR shop_id LIKE 'test_shop%'")
        )
        db_session.commit()
        print("✓ 测试数据清理完成")
    except Exception as e:
        print(f"清理数据时出错: {e}")
        db_session.rollback()


if __name__ == "__main__":
    run_all_tests()
