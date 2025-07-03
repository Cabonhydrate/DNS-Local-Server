
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DNS服务器主程序入口

负责协调各组件初始化、配置加载和服务启动，是整个DNS本地服务器的启动点
主要流程：
1. 加载配置文件和命令行参数（命令行参数优先级高于配置文件）
2. 初始化日志系统（必须优先初始化，确保其他组件可正常记录日志）
3. 加载本地DNS数据库（包含自定义域名解析规则和黑名单）
4. 创建DNS转发器（处理上游DNS服务器通信）和服务器实例（处理客户端请求）
5. 启动DNS服务并处理异常（确保服务崩溃时提供明确错误信息）
"""
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
from dns_cache import DNSCache

if __name__ == "__main__":
    try:
        # 加载配置文件（包含服务器端口、上游DNS、数据库路径等关键配置）
        # 配置文件缺失或格式错误将导致服务启动失败
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        # 捕获配置文件不存在异常 - 必须在项目根目录提供config.json
        raise Exception("Configuration file config.json not found")
    except json.JSONDecodeError:
        # 捕获JSON格式错误 - 检查配置文件语法是否符合JSON规范
        raise Exception("Invalid JSON format in config.json")

    # 添加命令行参数解析，支持日志级别控制
    # -d: INFO级别日志（基本运行信息）
    # -dd: DEBUG级别日志（详细调试信息，包含请求/响应内容）
    # 命令行参数优先级高于配置文件中的日志设置
    parser = argparse.ArgumentParser(description='DNS Server with logging options')
    parser.add_argument('-d', action='store_true', help='Enable INFO level logging')
    parser.add_argument('-dd', action='store_true', help='Enable DEBUG level logging')
    args = parser.parse_args()

    # 获取项目根目录（基于当前文件路径计算，确保路径一致性）
    # 避免使用相对路径导致的"工作目录依赖"问题
    project_root = Path(__file__).parent.absolute()

    # 从配置中提取核心参数
    local_port = config['local_port']          # 本地DNS服务监听端口
    database_file = config['database_file']    # 本地域名数据库文件路径
    upstream_ip = config['upstream_dns']['ip'] # 上游DNS服务器IP
    upstream_port = config['upstream_dns']['port'] # 上游DNS服务器端口
    upstream_server = (upstream_ip, upstream_port) # 上游服务器地址元组
    # 本地IP地址：优先使用配置文件中的设置，否则自动获取主机名对应的IP
    local_ip = config.get('local_ip', socket.gethostbyname(socket.gethostname()))

    # 根据命令行参数确定日志级别和输出文件
    # 日志文件路径基于项目根目录计算，确保跨环境一致性
    if args.d:
        log_level = logging.INFO
        log_file = os.path.join(project_root, "logs", "dns_server_simple.log")
    elif args.dd:
        log_level = logging.DEBUG
        log_file = os.path.join(project_root, "logs", "dns_server_detailed.log")
    else:
        log_level = logging.INFO
        log_file = os.path.join(project_root, config['log_file'])

    # 初始化日志系统（必须在其他组件之前初始化）
    # 所有后续日志输出依赖此步骤创建的logger实例
    logger = Logger(log_level, log_file)
    logger.info(f"Starting DNS server on {local_ip}:{local_port}")

    try:
        # 初始化本地DNS数据库（加载域名-IP映射和黑名单）
        # 数据库加载失败将导致自定义域名规则无法生效
        db = LocalDNSDatabase(database_file, logger)
        db.load()
        logger.info("Database loaded successfully")

        # 初始化DNS转发器（负责与上游DNS服务器通信）
        # 处理本地数据库未命中的域名查询请求
        relay = DNSRelay(local_ip, local_port, upstream_server, logger)

        cache = DNSCache(max_size=config.get('cache_size', 1000))
        # 创建并启动DNS服务器（核心服务入口）
        # 传入配置和日志实例，启动后将持续监听指定端口的DNS请求
        server = DNSServer(
            config=config,
            logger=logger,
            db=db,
            relay=relay,
            cache=cache
        )
        server.start()
    except Exception as e:
        # 捕获并记录服务启动过程中的所有异常
        # 记录后重新抛出异常，确保进程以非0状态退出，便于外部监控检测故障
        logger.error(f"Failed to start DNS server: {str(e)}")
        raise