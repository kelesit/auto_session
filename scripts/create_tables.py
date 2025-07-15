"""
创建数据库表脚本
基于设计文档创建完整的表结构
"""
from sqlalchemy import create_engine, text

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


def upgrade_existing_database():
    """为现有数据库添加 unique 约束和索引"""
    
    database_url = create_database_url()
    engine = get_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # 添加索引
            result = conn.execute(text("""
                SELECT shop_name, COUNT(*) as count 
                FROM shops 
                GROUP BY shop_name 
                HAVING COUNT(*) > 1
            """))

            duplicates = result.fetchall()
            if duplicates:
                print("⚠️  发现重复的店铺名称：")
                for row in duplicates:
                    print(f"  - '{row[0]}' 出现 {row[1]} 次")
                
                print("\n请先处理重复数据，然后再运行此脚本。")
                return False
            
            # 添加唯一约束
            print("添加 shop_name 的唯一约束...")
            conn.execute(text("ALTER TABLE shops ADD CONSTRAINT uk_shop_name UNIQUE (shop_name)"))
            
            try:
                conn.execute(text("CREATE INDEX idx_shop_name ON shops(shop_name)"))
            except Exception as e:
                if "already exists" in str(e).lower():
                    print("索引已存在，跳过...")
                else:
                    raise
            
            conn.commit()
            print("✅ 唯一约束和索引添加成功！")
            return True
    except Exception as e:
        print(f"升级数据库失败: {e}")
        return False
    finally:
        engine.dispose()



if __name__ == "__main__":
    upgrade_existing_database()
    # success = recreate_all_tables()
    # if success:
    #     print("\n✅ 脚本执行成功，数据库表创建完毕！")
    # else:
    #     print("\n❌ 脚本执行失败，请检查错误信息。")