import datetime
import logging
import os

class Logger:
    def __init__(self, log_file="dns_server.log"):
        self.logger = logging.getLogger('DNSLogger')
        self.logger.setLevel(logging.INFO)
        
        # 确保日志目录存在
        if not os.path.isabs(log_file):
            if not os.path.exists("logs"):
                os.makedirs("logs")
            self.log_path = os.path.join("logs", log_file)
        else:
            self.log_path = log_file
        
        # 移除现有处理器以避免重复日志
        if self.logger.handlers:
            self.logger.handlers = []
        
        # 创建文件处理器
        file_handler = logging.FileHandler(self.log_path)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def info(self, message):
        self.logger.info(message)
        self._flush_handlers()

    def warning(self, message):
        self.logger.warning(message)
        self._flush_handlers()

    def error(self, message):
        self.logger.error(message)
        self._flush_handlers()

    def debug(self, message):
        self.logger.debug(message)
        self._flush_handlers()

    def _flush_handlers(self):
        for handler in self.logger.handlers:
            handler.flush()