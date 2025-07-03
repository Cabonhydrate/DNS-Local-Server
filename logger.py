import datetime
import logging
import os
from logging.handlers import RotatingFileHandler

class Logger:
    """日志处理类，提供文件日志和控制台日志的统一管理

    支持日志轮转、日志级别控制、同时输出到文件和控制台
    自动处理日志目录创建和路径规范化

    示例:
        >>> logger = Logger(log_level=logging.DEBUG, log_file='logs/dns_server.log')
        >>> logger.info('DNS服务器启动成功')
        >>> logger.error('解析请求失败')
    """
    def __init__(self, log_level=logging.INFO, log_file=None):
        """初始化日志处理器

        Args:
            log_level (int): 日志级别，默认为logging.INFO
            log_file (str): 日志文件路径，None表示不输出到文件
        """
        self.log_level = log_level
        self.logger = logging.getLogger('DNSLogger')
        self.logger.setLevel(log_level)
        # 禁用日志传播，防止被root logger重复处理导致日志重复输出
        self.logger.propagate = False
        
        self.log_file = log_file
        
        # 确保日志文件路径为绝对路径，避免相对路径依赖工作目录
        if not os.path.isabs(self.log_file):
            self.log_file = os.path.join(os.getcwd(), self.log_file)
        
        # 确保日志目录存在，不存在则创建（exist_ok=True避免目录已存在时抛出异常）
        log_dir = os.path.dirname(self.log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # 移除现有处理器以避免重复日志输出（例如多次实例化时）
        if self.logger.handlers:
            self.logger.handlers = []
        
        # 创建文件处理器 - 使用RotatingFileHandler实现日志轮转
        # 选择轮转策略而非FileHandler，防止单个日志文件过大难以管理
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=1024*1024*5,  # 5MB - 单个日志文件最大大小
            backupCount=5,          # 最多保留5个备份日志文件
            encoding='utf-8'        # 使用UTF-8编码确保中文日志正常显示
        )
        # 文件日志格式包含时间戳，便于问题追溯和审计
        file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # 添加控制台处理器，用于开发环境实时查看日志
        console_handler = logging.StreamHandler()
        # 控制台日志简化格式，突出关键信息便于快速调试
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def info(self, message):
        """记录INFO级别的日志

        用于记录正常的运行状态信息，如服务启动、配置加载等

        Args:
            message (str): 日志消息内容
        """
        self.logger.info(message)

    def warning(self, message):
        """记录WARNING级别的日志

        用于记录可能的异常情况，但不影响服务继续运行

        Args:
            message (str): 日志消息内容
        """
        self.logger.warning(message)

    def error(self, message):
        """记录ERROR级别的日志

        用于记录错误信息，通常表示功能无法正常执行

        Args:
            message (str): 日志消息内容
        """
        self.logger.error(message)

    def debug(self, message):
        """记录DEBUG级别的日志

        用于开发阶段记录详细调试信息，生产环境通常禁用

        Args:
            message (str): 日志消息内容
        """
        self.logger.debug(message)