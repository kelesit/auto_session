#!/usr/bin/env python3
"""
快速启动脚本
自动设置环境并启动API服务
"""

import os
import sys
import subprocess
import time

def check_redis():
    """检查Redis是否运行"""
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, db=0)
        client.ping()
        print("✓ Redis连接正常")
        return True
    except ImportError:
        print("⚠️  Redis库未安装，将跳过Redis功能")
        return False
    except Exception:
        print("⚠️  Redis未运行，将跳过Redis功能")
        return False

def check_database():
    """检查数据库连接"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        from auto_session.database import create_database_url, get_engine
        
        database_url = create_database_url()
        engine = get_engine(database_url)
        
        # 尝试连接
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        
        print("✓ 数据库连接正常")
        return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False

def create_tables():
    """创建数据库表"""
    try:
        print("正在创建数据库表...")
        result = subprocess.run([sys.executable, "scripts/create_tables.py"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ 数据库表创建成功")
            return True
        else:
            print(f"✗ 数据库表创建失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 创建数据库表时出错: {e}")
        return False

def install_dependencies():
    """安装依赖"""
    print("正在检查依赖...")
    try:
        # 检查是否有uv
        result = subprocess.run(["uv", "--version"], capture_output=True)
        if result.returncode == 0:
            print("使用uv安装依赖...")
            subprocess.run(["uv", "install"], check=True)
        else:
            print("使用pip安装依赖...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
        
        print("✓ 依赖安装成功")
        return True
    except Exception as e:
        print(f"✗ 依赖安装失败: {e}")
        return False

def start_api():
    """启动API服务"""
    print("正在启动API服务...")
    try:
        # 启动API服务
        subprocess.run([sys.executable, "run_api.py"])
    except KeyboardInterrupt:
        print("\n✓ API服务已停止")
    except Exception as e:
        print(f"✗ 启动API服务失败: {e}")

def main():
    """主函数"""
    print("Auto Session 快速启动")
    print("=" * 50)
    
    # 1. 安装依赖
    if not install_dependencies():
        return
    
    # 2. 检查数据库连接
    if not check_database():
        print("请检查数据库配置和连接")
        return
    
    # 3. 创建数据库表
    if not create_tables():
        return
    
    # 4. 检查Redis（可选）
    check_redis()
    
    # 5. 启动API服务
    print("\n准备启动API服务...")
    print("API地址: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    print("按 Ctrl+C 停止服务")
    print("-" * 50)
    
    time.sleep(2)
    start_api()

if __name__ == "__main__":
    main()
