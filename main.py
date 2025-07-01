
import os
import socket
import json
from logger import Logger
from dns_server import DNSServer
from dns_relay import DNSRelay
from dns_db import LocalDNSDatabase

if __name__ == "__main__":
    try:
        # 加载配置文件
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        raise Exception("Configuration file config.json not found")
    except json.JSONDecodeError:
        raise Exception("Invalid JSON format in config.json")

    # 获取配置值
    local_port = config['local_port']
    log_file = config['log_file']
    database_file = config['database_file']
    upstream_ip = config['upstream_dns']['ip']
    upstream_port = config['upstream_dns']['port']
    upstream_server = (upstream_ip, upstream_port)
    local_ip = config.get('local_ip', socket.gethostbyname(socket.gethostname()))

    # 初始化日志系统
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_file)
    logger = Logger(log_path)
    logger.info(f"Starting DNS server on {local_ip}:{local_port}")

    try:

        # 初始化数据库
        db = LocalDNSDatabase(database_file)
        db.load()
        logger.info("Database loaded successfully")

        # 初始化DNS转发器
        relay = DNSRelay(local_ip, local_port, upstream_server, logger)

        # 创建并启动DNS服务器
        server = DNSServer(
            local_ip=local_ip,
            local_port=local_port,
            upstream_server=upstream_server,
            db_file=database_file,
            logger=logger
        )
        server.start()
    except Exception as e:
        logger.error(f"Failed to start DNS server: {str(e)}")
        raise