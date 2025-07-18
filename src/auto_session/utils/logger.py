import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


class SafeRotatingFileHandler(RotatingFileHandler):
    """安全的文件滚动处理器，解决Windows文件被占用问题"""
    
    def doRollover(self):
        """
        执行文件滚动，处理Windows文件占用问题
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # 尝试多次重命名文件
        for i in range(1, self.backupCount + 1):
            sfn = self.rotation_filename(f"{self.baseFilename}.{i}")
            if os.path.exists(sfn):
                try:
                    os.remove(sfn)
                except (OSError, PermissionError):
                    # 如果无法删除，跳过
                    continue
        
        # 重命名当前文件
        dfn = self.rotation_filename(f"{self.baseFilename}.1")
        try:
            if os.path.exists(self.baseFilename):
                os.rename(self.baseFilename, dfn)
        except (OSError, PermissionError):
            # 如果重命名失败，创建新文件
            pass
        
        # 重新打开日志文件
        if not self.delay:
            self.stream = self._open()


class LoggerConfig:
    """日志配置管理类"""

    def __init__(self, 
                 log_name="followup",
                 log_level=logging.INFO,
                 log_dir="logs",
                 max_bytes=10*1024*1024,  # 10MB
                 backup_count=5,
                 console_output=True):
        """
        初始化日志配置
        Args:
            log_name: 日志名称
            log_level: 日志级别
            log_dir: 日志目录
            max_bytes: 单个日志文件最大大小
            backup_count: 备份文件数量
            console_output: 是否输出到控制台
        """
        self.log_name = log_name
        self.log_level = log_level
        self.log_dir = log_dir
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.console_output = console_output
        
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
        
    def setup_logger(self, logger_name=None):
        """
        设置并返回logger对象
        Args:
            logger_name: logger名称，默认使用调用模块的名称
        Returns:
            logging.Logger: 配置好的logger对象
        """

        # 使用传入的名称或默认名称
        if logger_name is None:
            logger_name = self.log_name

        # 获取logger对象
        logger = logging.getLogger(logger_name)

        # 如果logger已经配置过，直接返回
        if logger.handlers:
            return logger
        
        logger.setLevel(self.log_level)

        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        
        # 文件处理器 - 按大小滚动
        log_file = os.path.join(self.log_dir, f"{self.log_name}.log")
        file_handler = SafeRotatingFileHandler(
            log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 错误日志单独记录
        error_log_file = os.path.join(self.log_dir, f"{self.log_name}_error.log")
        error_handler = SafeRotatingFileHandler(
            error_log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)

        # 控制台处理器
        if self.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self.log_level)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        # 防止向上传播到根logger
        logger.propagate = False

        return logger
    
    def setup_daily_logger(self, logger_name=None):
        """
        设置按日期滚动的logger
        Args:
            logger_name: logger名称
        Returns:
            logging.Logger: 配置好的logger对象
        """
        if logger_name is None:
            logger_name = self.log_name
            
        logger = logging.getLogger(logger_name)
        
        if logger.handlers:
            return logger
            
        logger.setLevel(self.log_level)
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        
        # 按日期滚动的文件处理器
        log_file = os.path.join(self.log_dir, f"{self.log_name}.log")
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=30,  # 保留30天的日志
            encoding='utf-8'
        )
        file_handler.suffix = "%Y-%m-%d"
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 控制台处理器
        if self.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self.log_level)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        logger.propagate = False
        
        return logger
    
# 创建全局logger配置实例
logger_config = LoggerConfig(
    log_name="auto session",
    log_level=logging.INFO,
    log_dir="logs",
    console_output=True
)

# 获取默认logger的便捷函数
def get_logger(name=None):
    """获取logger对象的便捷函数"""
    return logger_config.setup_logger(name or __name__)

# 获取按日期滚动的logger
def get_daily_logger(name=None):
    """获取按日期滚动的logger对象"""
    return logger_config.setup_daily_logger(name or __name__)