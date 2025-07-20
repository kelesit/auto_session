"""
配置文件
"""

import os
from dataclasses import dataclass, field
from typing import List

@dataclass
class Config:
    """应用配置"""
    
    # 数据库配置
    DATABASE_HOST: str = ""
    DATABASE_PORT: int = ""
    DATABASE_USER: str = ""
    DATABASE_PASSWORD: str = ""
    DATABASE_NAME: str = ""
    DATABASE_CHARSET: str = ""
    
    # Redis配置
    REDIS_HOST: str = "192.168.100.44"
    REDIS_PORT: int = 7379
    REDIS_DB: int = 4
    REDIS_PASSWORD: str = "123456"
    
    # 应用配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    # 业务配置
    DEFAULT_SESSION_TIMEOUT: int = 1800  # 30分钟
    MAX_CONCURRENT_SESSIONS: int = 10
    MAX_INACTIVE_MINUTES: int = 120  # 2小时
    

    ### 淘天
    # 账号昵称列表（用于消息处理）
    ACCOUNT_NICK_NAMES: List[str] = field(default_factory=lambda: [
        't-2217567810350-0',    # 
        't-2220262859798-0',    # 

        't-2217640538887-0',    # 
        
        't-2217525684881-0',   # 
        't-2217644064498-0',   # 
        't-2217655997959-0',    # 
        't-2217683614335-0',    # 
        't-2217720464839-0',    # 
        # 可以添加更多账号昵称
    ])
    
    def __post_init__(self):
        # 确保列表不为空
        if not self.ACCOUNT_NICK_NAMES:
            self.ACCOUNT_NICK_NAMES = [
                't-2217567810350-0',
                # 可以添加更多账号昵称
            ]
    
    @classmethod
    def from_env(cls):
        """从环境变量创建配置"""
        return cls(
            DATABASE_HOST=os.getenv("DATABASE_HOST", ""),
            DATABASE_PORT=int(os.getenv("DATABASE_PORT", "")),
            DATABASE_USER=os.getenv("DATABASE_USER", ""),
            DATABASE_PASSWORD=os.getenv("DATABASE_PASSWORD", ""),
            DATABASE_NAME=os.getenv("DATABASE_NAME", ""),
            DATABASE_CHARSET=os.getenv("DATABASE_CHARSET", ""),
            
            REDIS_HOST=os.getenv("REDIS_HOST", "192.168.100.44"),
            REDIS_PORT=int(os.getenv("REDIS_PORT", "7379")),
            REDIS_DB=int(os.getenv("REDIS_DB", "4")),
            REDIS_PASSWORD=os.getenv("REDIS_PASSWORD", "123456"),
            
            API_HOST=os.getenv("API_HOST", "0.0.0.0"),
            API_PORT=int(os.getenv("API_PORT", "8000")),
            DEBUG=os.getenv("DEBUG", "True").lower() == "true",
            
            DEFAULT_SESSION_TIMEOUT=int(os.getenv("DEFAULT_SESSION_TIMEOUT", "1800")),
            MAX_CONCURRENT_SESSIONS=int(os.getenv("MAX_CONCURRENT_SESSIONS", "10")),
            MAX_INACTIVE_MINUTES=int(os.getenv("MAX_INACTIVE_MINUTES", "120")),
        )

# 全局配置实例
config = Config.from_env()
