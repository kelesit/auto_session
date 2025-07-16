"""
消息处理功能测试
测试 SessionManager 的 process_message_batch 方法
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from auto_session.database import create_database_url, get_engine, create_tables, DBSession, DBMessage, DBAccount, DBShop
from auto_session.session_manager import SessionManager, ensure_account_exists, ensure_shop_exists
from auto_session.models import MessageData, SessionState, TaskType


def setup_mysql_database():
    """设置 MySQL 数据库连接"""
    database_url = create_database_url()
    engine = get_engine(database_url)
    
    # 确保表存在
    create_tables(engine)
    
    Session = sessionmaker(bind=engine)
    return Session()


def cleanup_message_test_data(db_session):
    """清理消息测试数据"""
    try:
        # 按正确的顺序删除数据（子表到父表）
        
        # 1. 删除消息（子表）
        db_session.query(DBMessage).filter(
            DBMessage.session_id.like('msg_test_%') |
            DBMessage.session_id.like('robot_sess_%') |
            DBMessage.session_id.like('old_sess_%') |
            DBMessage.session_id.like('sess_%')
        ).delete(synchronize_session='fetch')
        
        # 2. 删除会话（子表）
        db_session.query(DBSession).filter(
            DBSession.session_id.like('msg_test_%') |
            DBSession.session_id.like('robot_sess_%') |
            DBSession.session_id.like('old_sess_%') |
            DBSession.session_id.like('sess_%')
        ).delete(synchronize_session='fetch')
        
        # 3. 删除账号（父表）
        db_session.query(DBAccount).filter(
            DBAccount.account_id.like('msg_test_%')
        ).delete(synchronize_session='fetch')
        
        # 4. 删除店铺（父表）
        db_session.query(DBShop).filter(
            DBShop.shop_id.like('msg_test_%')
        ).delete(synchronize_session='fetch')
        
        db_session.commit()
        print("✓ 消息测试数据清理完成")
    except Exception as e:
        print(f"清理数据时出错: {e}")
        db_session.rollback()


def test_create_new_session_with_messages():
    """测试创建新会话并处理消息"""
    print("=== 测试 1: 创建新会话并处理消息 ===")
    
    db_session = setup_mysql_database()
    cleanup_message_test_data(db_session)
    
    try:
        session_manager = SessionManager(db_session)
        
        # 准备测试数据
        account_id = f"msg_test_account_{uuid.uuid4().hex[:8]}"
        shop_id = f"msg_test_shop_{uuid.uuid4().hex[:8]}"
        shop_name = f"测试店铺_{uuid.uuid4().hex[:8]}"
        
        # 创建账号和店铺
        ensure_account_exists(db_session, account_id, "消息测试账号", "taobao")
        ensure_shop_exists(db_session, shop_id, shop_name)
        
        # 创建测试消息
        messages = [
            MessageData(
                message_id=f"msg_{i}_{uuid.uuid4().hex[:8]}",
                content=f"测试消息内容 {i}",
                from_source="shop",
                sent_at=datetime.now() + timedelta(seconds=i),
                sender="customer_user"
            )
            for i in range(3)
        ]
        
        print(f"✓ 准备了 {len(messages)} 条测试消息")
        
        # 处理消息批次
        result = session_manager.process_message_batch(
            messages=messages,
            account_id=account_id,
            shop_id=shop_id,
            shop_name=shop_name,
            max_inactive_minutes=30
        )
        
        print(f"✓ 处理结果: {result}")
        
        # 验证结果
        assert result.processed_messages == len(messages), f"处理消息数量不正确: {result.processed_messages}"
        assert result.skipped_messages == 0, f"跳过消息数量不正确: {result.skipped_messages}"
        assert result.active_session_id is not None, "应该创建新会话"
        assert len(result.errors) == 0, f"不应该有错误: {result.errors}"
        
        # 验证会话状态
        session_status = session_manager.get_session_status(account_id, shop_id)
        assert session_status['has_active_session'] == True, "应该有活跃会话"
        assert session_status['state'] == SessionState.TRANSFERRED.value, "新会话应该是TRANSFERRED状态"
        assert session_status['created_by'] == "human", "应该是人工创建"
        
        # 验证消息已保存
        saved_messages = db_session.query(DBMessage).filter(
            DBMessage.session_id == result.active_session_id
        ).all()
        assert len(saved_messages) == len(messages), f"保存的消息数量不正确: {len(saved_messages)}"
        
        print("✓ 创建新会话并处理消息测试通过\n")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db_session.close()


def test_add_messages_to_existing_session():
    """测试向现有会话添加消息"""
    print("=== 测试 2: 向现有会话添加消息 ===")
    
    db_session = setup_mysql_database()
    cleanup_message_test_data(db_session)
    
    try:
        session_manager = SessionManager(db_session)
        
        # 准备测试数据
        account_id = f"msg_test_account_{uuid.uuid4().hex[:8]}"
        shop_id = f"msg_test_shop_{uuid.uuid4().hex[:8]}"
        shop_name = f"测试店铺_{uuid.uuid4().hex[:8]}"
        
        # 创建账号和店铺
        ensure_account_exists(db_session, account_id, "消息测试账号", "taobao")
        ensure_shop_exists(db_session, shop_id, shop_name)
        
        # 第一批消息 - 创建会话
        first_messages = [
            MessageData(
                message_id=f"first_msg_{i}_{uuid.uuid4().hex[:8]}",
                content=f"第一批消息 {i}",
                from_source="shop",
                sent_at=datetime.now() + timedelta(seconds=i),
                sender="customer_user"
            )
            for i in range(2)
        ]
        
        result1 = session_manager.process_message_batch(
            messages=first_messages,
            account_id=account_id,
            shop_id=shop_id,
            shop_name=shop_name
        )
        
        print(f"✓ 第一批消息处理完成，创建会话: {result1.active_session_id}")
        
        # 第二批消息 - 添加到现有会话
        second_messages = [
            MessageData(
                message_id=f"second_msg_{i}_{uuid.uuid4().hex[:8]}",
                content=f"第二批消息 {i}",
                from_source="shop", 
                sent_at=datetime.now() + timedelta(seconds=i + 10),
                sender="customer_user"
            )
            for i in range(2)
        ]
        
        result2 = session_manager.process_message_batch(
            messages=second_messages,
            account_id=account_id,
            shop_id=shop_id,
            shop_name=shop_name
        )
        
        print(f"✓ 第二批消息处理完成，使用现有会话: {result2.active_session_id}")
        
        # 验证结果
        assert result1.active_session_id == result2.active_session_id, "应该使用同一个会话"
        assert result2.processed_messages == len(second_messages), "第二批消息处理数量不正确"
        
        # 验证会话中的消息总数
        session_status = session_manager.get_session_status(account_id, shop_id)
        total_messages = db_session.query(DBMessage).filter(
            DBMessage.session_id == result1.active_session_id
        ).count()
        
        expected_total = len(first_messages) + len(second_messages)
        assert total_messages == expected_total, f"消息总数不正确: {total_messages}, 期望: {expected_total}"
        
        print("✓ 向现有会话添加消息测试通过\n")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db_session.close()


def test_human_intervention_detection():
    """测试人工介入检测"""
    print("=== 测试 3: 人工介入检测 ===")
    
    db_session = setup_mysql_database()
    cleanup_message_test_data(db_session)
    
    try:
        session_manager = SessionManager(db_session)
        
        # 准备测试数据
        account_id = f"msg_test_account_{uuid.uuid4().hex[:8]}"
        shop_id = f"msg_test_shop_{uuid.uuid4().hex[:8]}"
        shop_name = f"测试店铺_{uuid.uuid4().hex[:8]}"
        
        # 创建账号和店铺
        ensure_account_exists(db_session, account_id, "消息测试账号", "taobao")
        ensure_shop_exists(db_session, shop_id, shop_name)
        
        # 先创建一个机器人会话
        from auto_session.models import SessionInfo
        robot_session = SessionInfo(
            session_id=f"robot_sess_{uuid.uuid4().hex[:8]}",
            account_id=account_id,
            shop_id=shop_id,
            task_type=TaskType.AUTO_BARGAIN,
            state=SessionState.ACTIVE,
            created_by="robot",
            priority=3
        )
        
        session_id = session_manager.create_session(robot_session)
        print(f"✓ 创建机器人会话: {session_id}")
        
        # 发送包含人工介入的消息
        human_messages = [
            MessageData(
                message_id=f"human_msg_{uuid.uuid4().hex[:8]}",
                content="人工客服回复：您好，我来帮您处理",  # 不以'hi'开头
                from_source="account",
                sent_at=datetime.now(),
                sender="t-2217567810350-0"  # 在ACCOUNT_NICK_NAME_LIST中
            )
        ]
        
        result = session_manager.process_message_batch(
            messages=human_messages,
            account_id=account_id,
            shop_id=shop_id,
            shop_name=shop_name
        )
        
        print(f"✓ 处理人工介入消息: {result}")
        
        # 验证会话状态已切换为TRANSFERRED
        session_status = session_manager.get_session_status(account_id, shop_id)
        assert session_status['state'] == SessionState.TRANSFERRED.value, "会话应该切换为TRANSFERRED状态"
        assert session_status['created_by'] == "human", "会话应该切换为人工控制"
        
        print("✓ 人工介入检测测试通过\n")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db_session.close()


def test_robot_message_no_intervention():
    """测试机器人消息不触发人工介入"""
    print("=== 测试 4: 机器人消息不触发人工介入 ===")
    
    db_session = setup_mysql_database()
    cleanup_message_test_data(db_session)
    
    try:
        session_manager = SessionManager(db_session)
        
        # 准备测试数据
        account_id = f"msg_test_account_{uuid.uuid4().hex[:8]}"
        shop_id = f"msg_test_shop_{uuid.uuid4().hex[:8]}"
        shop_name = f"测试店铺_{uuid.uuid4().hex[:8]}"
        
        # 创建账号和店铺
        ensure_account_exists(db_session, account_id, "消息测试账号", "taobao")
        ensure_shop_exists(db_session, shop_id, shop_name)
        
        # 先创建一个机器人会话
        from auto_session.models import SessionInfo
        robot_session = SessionInfo(
            session_id=f"robot_sess_{uuid.uuid4().hex[:8]}",
            account_id=account_id,
            shop_id=shop_id,
            task_type=TaskType.AUTO_BARGAIN,
            state=SessionState.ACTIVE,
            created_by="robot",
            priority=3
        )
        
        session_id = session_manager.create_session(robot_session)
        print(f"✓ 创建机器人会话: {session_id}")
        
        # 发送机器人消息（以'hi'开头）
        robot_messages = [
            MessageData(
                message_id=f"robot_msg_{uuid.uuid4().hex[:8]}",
                content="hi，这是机器人回复",  # 以'hi'开头
                from_source="account",
                sent_at=datetime.now(),
                sender="t-2217567810350-0"
            )
        ]
        
        result = session_manager.process_message_batch(
            messages=robot_messages,
            account_id=account_id,
            shop_id=shop_id,
            shop_name=shop_name
        )
        
        print(f"✓ 处理机器人消息: {result}")
        
        # 验证会话状态仍然是ACTIVE
        session_status = session_manager.get_session_status(account_id, shop_id)
        assert session_status['state'] == SessionState.ACTIVE.value, "会话应该保持ACTIVE状态"
        assert session_status['created_by'] == "robot", "会话应该保持机器人控制"
        
        print("✓ 机器人消息不触发人工介入测试通过\n")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db_session.close()


def test_duplicate_message_handling():
    """测试重复消息处理"""
    print("=== 测试 5: 重复消息处理 ===")
    
    db_session = setup_mysql_database()
    cleanup_message_test_data(db_session)
    
    try:
        session_manager = SessionManager(db_session)
        
        # 准备测试数据
        account_id = f"msg_test_account_{uuid.uuid4().hex[:8]}"
        shop_id = f"msg_test_shop_{uuid.uuid4().hex[:8]}"
        shop_name = f"测试店铺_{uuid.uuid4().hex[:8]}"
        
        # 创建账号和店铺
        ensure_account_exists(db_session, account_id, "消息测试账号", "taobao")
        ensure_shop_exists(db_session, shop_id, shop_name)
        
        # 创建测试消息
        duplicate_message_id = f"duplicate_msg_{uuid.uuid4().hex[:8]}"
        messages = [
            MessageData(
                message_id=duplicate_message_id,
                content="重复消息内容",
                from_source="shop",
                sent_at=datetime.now(),
                sender="customer_user"
            )
        ]
        
        # 第一次处理
        result1 = session_manager.process_message_batch(
            messages=messages,
            account_id=account_id,
            shop_id=shop_id,
            shop_name=shop_name
        )
        
        print(f"✓ 第一次处理: {result1}")
        
        # 第二次处理相同消息
        result2 = session_manager.process_message_batch(
            messages=messages,
            account_id=account_id,
            shop_id=shop_id,
            shop_name=shop_name
        )
        
        print(f"✓ 第二次处理: {result2}")
        
        # 验证重复消息被跳过
        assert result1.processed_messages == 1, "第一次应该处理1条消息"
        assert result1.skipped_messages == 0, "第一次应该跳过0条消息"
        assert result2.processed_messages == 0, "第二次应该处理0条消息"
        assert result2.skipped_messages == 1, "第二次应该跳过1条消息"
        
        # 验证数据库中只有一条消息
        saved_messages = db_session.query(DBMessage).filter(
            DBMessage.message_id == duplicate_message_id
        ).count()
        assert saved_messages == 1, f"数据库中应该只有1条消息，实际: {saved_messages}"
        
        print("✓ 重复消息处理测试通过\n")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db_session.close()


def test_session_timeout():
    """测试会话超时处理"""
    print("=== 测试 6: 会话超时处理 ===")
    
    db_session = setup_mysql_database()
    cleanup_message_test_data(db_session)
    
    try:
        session_manager = SessionManager(db_session)
        
        # 准备测试数据
        account_id = f"msg_test_account_{uuid.uuid4().hex[:8]}"
        shop_id = f"msg_test_shop_{uuid.uuid4().hex[:8]}"
        shop_name = f"测试店铺_{uuid.uuid4().hex[:8]}"
        
        # 创建账号和店铺
        ensure_account_exists(db_session, account_id, "消息测试账号", "taobao")
        ensure_shop_exists(db_session, shop_id, shop_name)
        
        # 创建一个过期的会话
        from auto_session.models import SessionInfo
        old_session = SessionInfo(
            session_id=f"old_sess_{uuid.uuid4().hex[:8]}",
            account_id=account_id,
            shop_id=shop_id,
            task_type=TaskType.AUTO_BARGAIN,
            state=SessionState.ACTIVE,
            created_by="robot",
            priority=3,
            last_activity=datetime.now() - timedelta(hours=2)  # 2小时前
        )
        
        old_session_id = session_manager.create_session(old_session)
        
        # 手动设置会话的最后活动时间
        old_session_obj = session_manager._get_session(old_session_id)
        old_session_obj.last_activity = datetime.now() - timedelta(hours=2)
        db_session.commit()
        
        print(f"✓ 创建过期会话: {old_session_id}")
        
        # 发送新消息，应该创建新会话
        new_messages = [
            MessageData(
                message_id=f"new_msg_{uuid.uuid4().hex[:8]}",
                content="新消息内容",
                from_source="shop",
                sent_at=datetime.now(),
                sender="customer_user"
            )
        ]
        
        result = session_manager.process_message_batch(
            messages=new_messages,
            account_id=account_id,
            shop_id=shop_id,
            shop_name=shop_name,
            max_inactive_minutes=30  # 30分钟超时
        )
        
        print(f"✓ 处理新消息: {result}")
        
        # 验证创建了新会话
        assert result.active_session_id != old_session_id, "应该创建新会话"
        
        # 验证旧会话状态变为TIMEOUT
        old_session_obj = session_manager._get_session(old_session_id)
        assert old_session_obj.state == SessionState.TIMEOUT, "旧会话应该变为TIMEOUT状态"
        
        print("✓ 会话超时处理测试通过\n")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db_session.close()


def run_all_message_tests():
    """运行所有消息处理测试"""
    print("=== 开始消息处理功能测试 ===\n")
    
    test_functions = [
        test_create_new_session_with_messages,
        test_add_messages_to_existing_session,
        test_human_intervention_detection,
        test_robot_message_no_intervention,
        test_duplicate_message_handling,
        test_session_timeout
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} 失败: {e}")
            failed += 1
    
    print(f"=== 消息处理测试完成 ===")
    print(f"✓ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"总计: {passed + failed}")


if __name__ == "__main__":
    run_all_message_tests()
