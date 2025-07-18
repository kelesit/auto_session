"""
往Redis里添加测试数据
用于测试外部发送器的功能
"""

import redis
import json
import uuid
from datetime import datetime
import sys
import os

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.auto_session.config import Config


def create_redis_client():
    """创建Redis客户端"""
    try:
        return redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            password=Config.REDIS_PASSWORD,
            decode_responses=True
        )
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        return None
    

if __name__ == "__main__":
    # 创建Redis客户端
    redis_client = create_redis_client()
    if not redis_client:
        sys.exit(1)

    queue_key = 'level3'
    redis_task_id = 5563
    redis_client.lpush(queue_key, str(redis_task_id))