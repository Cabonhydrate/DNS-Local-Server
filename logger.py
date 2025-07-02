import datetime
import logging
import os
from logging.handlers import RotatingFileHandler

class Logger:
    def __init__(self, log_level=logging.INFO, log_file=None):
        self.log_level = log_level
        self.logger = logging.getLogger('DNSLogger')
        self.logger.setLevel(log_level)
        self.logger.propagate = False  # 防止日志重复传播到root logger
        
        self.log_file = log_file
        
        # 确保日志文件路径为绝对路径
        if not os.path.isabs(self.log_file):
            self.log_file = os.path.join(os.getcwd(), self.log_file)
        
        # 确保日志目录存在
        log_dir = os.path.dirname(self.log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # 移除现有处理器以避免重复日志
        if self.logger.handlers:
            self.logger.handlers = []
        
        # 创建文件处理器 - 使用RotatingFileHandler实现日志轮转
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=1024*1024*5,  # 5MB
            backupCount=5,          # 最多保留5个备份
            encoding='utf-8'
        )
        file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def debug(self, message):
        self.logger.debug(message)