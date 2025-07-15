"""
创建数据库表脚本
基于设计文档创建完整的表结构
"""

from auto_session.database import Base, create_database_url, get_engine


def create_all_tables():
    """创建所有数据库表"""
    print("正在连接数据库...")
    database_url = create_database_url()
    engine = get_engine(database_url)
    
    print("正在创建表结构...")
    try:
        Base.metadata.create_all(engine)
        print("所有表结构创建成功！")
        print("\n已创建的表：")
        for table_name in Base.metadata.tables.keys():
            print(f"  - {table_name}")
        
        print("\n表结构详情：")
        print("- accounts: 账号表")
        print("- shops: 店铺表") 
        print("- sessions: 会话表（核心表，包含转交支持）")
        print("- messages: 消息表")
        print("- session_transfers: 会话转交记录表")
        print("- external_tasks: 外部任务关联表")
        print("- session_operations: 会话操作日志表")
        
        return True
        
    except Exception as e:
        print(f"创建表结构失败: {e}")
        return False
    finally:
        engine.dispose()
        print("数据库连接已关闭。")


def recreate_all_tables():
    """删除并重建所有表"""
    print("⚠️  警告：这将删除所有现有数据！")
    confirm = input("确定要继续吗？(yes/no): ")
    
    if confirm.lower() != 'yes':
        print("操作已取消。")
        return False
    
    print("正在连接数据库...")
    database_url = create_database_url()
    engine = get_engine(database_url)
    
    try:
        print("正在删除现有表...")
        Base.metadata.drop_all(engine)
        
        print("正在创建新表...")
        Base.metadata.create_all(engine)
        
        print("表重建完成！")
        return True
        
    except Exception as e:
        print(f"重建表失败: {e}")
        return False
    finally:
        engine.dispose()


if __name__ == "__main__":
    success = recreate_all_tables()
    if success:
        print("\n✅ 脚本执行成功，数据库表创建完毕！")
    else:
        print("\n❌ 脚本执行失败，请检查错误信息。")