
import os
import socket
import json
import argparse
import logging
from pathlib import Path
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

    # 添加参数解析
    parser = argparse.ArgumentParser(description='DNS Server with logging options')
    parser.add_argument('-d', action='store_true', help='Enable INFO level logging')
    parser.add_argument('-dd', action='store_true', help='Enable DEBUG level logging')
    args = parser.parse_args()

    # 获取项目根目录
    project_root = Path(__file__).parent.absolute()

    # 获取配置值
    local_port = config['local_port']
    database_file = config['database_file']
    upstream_ip = config['upstream_dns']['ip']
    upstream_port = config['upstream_dns']['port']
    upstream_server = (upstream_ip, upstream_port)
    local_ip = config.get('local_ip', socket.gethostbyname(socket.gethostname()))

    # 确定日志级别和文件名
    if args.d:
        log_level = logging.INFO
        log_file = os.path.join(project_root, "logs", "dns_server_simple.log")
    elif args.dd:
        log_level = logging.DEBUG
        log_file = os.path.join(project_root, "logs", "dns_server_detailed.log")
    else:
        log_level = logging.INFO
        log_file = os.path.join(project_root, config['log_file'])

    # 初始化日志系统
    logger = Logger(log_level, log_file)
    logger.info(f"Starting DNS server on {local_ip}:{local_port}")

    try:

        # 初始化数据库
        db = LocalDNSDatabase(database_file, logger)
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