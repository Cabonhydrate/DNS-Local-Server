
import os
import socket
from logger import Logger
from dns_server import DNSServer
from dns_relay import DNSRelay
from dns_db import LocalDNSDatabase

if __name__ == "__main__":
    # 获取本地IP地址
    local_ip = socket.gethostbyname(socket.gethostname())
    local_port = 53 

    # 初始化日志系统
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dns_server.log')
    logger = Logger(log_path)
    logger.info(f"Starting DNS server on {local_ip}:{local_port}")

    try:
        # 初始化数据库
        db = LocalDNSDatabase('database.txt')
        db.load()
        logger.info("Database loaded successfully")

        # 初始化DNS转发器
        relay = DNSRelay(local_ip, local_port, ('8.8.8.8', 53), logger)

        # 创建并启动DNS服务器
        server = DNSServer(
            local_ip=local_ip,
            local_port=local_port,
            upstream_server=('8.8.8.8', 53),
            db_file='database.txt',
            logger=logger
        )
        server.start()
    except Exception as e:
        logger.error(f"Failed to start DNS server: {str(e)}")
        raise