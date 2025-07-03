import socket
from concurrent.futures import ThreadPoolExecutor
from dns_message import DNSMessage, DNSHeader
from dns_db import LocalDNSDatabase
from dns_relay import DNSRelay
from dns_cache import DNSCache

class DNSServer:
    def __init__(self, config, logger):
        # 配置参数验证
        required_keys = ['local_ip', 'local_port', 'upstream_dns', 'database_file']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")
        if not isinstance(config['upstream_dns'], dict) or 'ip' not in config['upstream_dns'] or 'port' not in config['upstream_dns']:
            raise ValueError("Upstream DNS configuration must be a dict with 'ip' and 'port'")
        self.local_ip = config['local_ip']
        self.local_port = config['local_port']
        self.upstream_server = (config['upstream_dns']['ip'], config['upstream_dns']['port'])
        self.default_ttl = config.get('default_ttl', 300)
        self.db = LocalDNSDatabase(config['database_file'], logger)
        self.logger = logger
        self.relay = DNSRelay(self.local_ip, self.local_port, self.upstream_server, logger)
        self.cache = DNSCache(max_size=config.get('cache_size', 1000))
        # 启动缓存清理线程
        def start_cache_cleaner():
            import time
            while True:
                self.cache.clear_expired()
                time.sleep(60)  # 每60秒清理一次过期缓存
        import threading
        cleaner_thread = threading.Thread(target=start_cache_cleaner, daemon=True)
        cleaner_thread.start()

    def start(self):
        # 清空日志文件
        log_path = self.logger.log_file
        try:
            with open(log_path, 'w') as f:
                pass  # 以写入模式打开文件会截断内容
        except Exception as e:
            self.logger.error(f"Failed to clear log file: {e}")
        self.db.load()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.local_ip, self.local_port))
        sock.settimeout(5)  # 添加超时设置
        self.logger.info(f"DNS server started on {self.local_ip}:{self.local_port}")
        
        # 创建线程池，设置最大工作线程数为10
        with ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                try:
                    data, addr = sock.recvfrom(512)
                    # 提交请求处理任务到线程池
                    executor.submit(self.handle_query, data, addr, sock)
                except ConnectionResetError:
                    self.logger.warning("客户端连接被重置")
                except socket.timeout:
                    continue  # 超时不处理，继续等待新请求
                except Exception as e:
                    self.logger.error(f"发生错误: {e}")

    def handle_query(self, data, addr, sock):
        try:
            self.logger.info(f"Received DNS query from {addr}")
            self.logger.debug(f"Query data: {data.hex()}")
            dns_msg = DNSMessage.parse(data)
            domain = self.extract_domain(dns_msg)  # 需要实现提取域名的逻辑
            if not domain:
                self.logger.error("Received DNS query with empty domain")
                return
            # 获取并记录域名内部ID
            domain_id = self.db.get_internal_id(domain)
            if domain_id:
                self.logger.debug(f"Domain {domain} mapped to internal ID: {domain_id}")
            else:
                self.logger.debug(f"No internal ID found for domain: {domain}")
            qtype = dns_msg.questions[0][1] if dns_msg.questions else 1
            self.logger.debug(f"Extracted domain: {domain}, query type: {qtype}")
            self.logger.info(f"Processing query for domain: {domain}, type: {qtype}")
        except Exception as e:
            self.logger.error(f"Failed to parse DNS query: {e}")
            # 发送格式错误响应
            error_response = self.build_error_response(dns_msg, rcode=1)
            try:
                sock.sendto(error_response, addr)
            except Exception as send_err:
                self.logger.error(f"Failed to send error response: {send_err}")
            return

        if self.db.is_in_blacklist(domain):
            self.logger.warning(f"Domain {domain} is in blacklist")
            response = self.build_blacklist_response(dns_msg)
            try:
                sock.sendto(response, addr)
                return  # 发送后立即返回，避免继续转发
            except ConnectionResetError:
                self.logger.warning(f"发送黑名单响应到 {addr} 时连接被重置")
            except Exception as e:
                self.logger.error(f"发送黑名单响应错误: {e}")
                return  # 发送失败后终止处理
        else:
            # 根据查询类型获取对应版本的IP地址
            if qtype == 28:
                ips = self.db.get_ipv6(domain)
            elif qtype == 1:
                ips = self.db.get_ipv4(domain)
            else:
                ips = []
            if ips:
                # 如果是单个IP字符串，转换为列表
                if isinstance(ips, str):
                    ips = [ips]
                self.logger.debug(f"Found {len(ips)} IPs for {domain} in local database")
                self.logger.info(f"Domain {domain} found in local database: {ips}")
                response = self.build_whitelist_response(dns_msg, ips, domain)
                try:
                    sock.sendto(response, addr)
                    return  # 发送后立即返回，避免继续转发
                except ConnectionResetError:
                    self.logger.warning(f"发送白名单响应到 {addr} 时连接被重置")
                except Exception as e:
                    self.logger.error(f"发送白名单响应错误: {e}")
            else:
                # 检查缓存
                cached_ips = self.cache.get_record(domain, qtype)
                self.logger.debug(f"Cache lookup for {domain} (type {qtype}): {'hit' if cached_ips else 'miss'}")
                if cached_ips:
                    self.logger.debug(f"Cache hit for {domain}, type {qtype}: {cached_ips}")
                    self.logger.info(f"Domain {domain} found in cache: {cached_ips}")
                    response = self.build_whitelist_response(dns_msg, cached_ips, domain)
                    try:
                        sock.sendto(response, addr)
                    except ConnectionResetError:
                        self.logger.warning(f"发送缓存响应到 {addr} 时连接被重置")
                    except Exception as e:
                        self.logger.error(f"发送缓存响应错误: {e}")
                    return
                # 缓存未命中，转发到上游服务器
            self.logger.info(f"Domain {domain} not in local database or cache, forwarding to upstream server")
            # 转发查询并获取上游服务器响应
            response_data = self.relay.forward_query(data)
            if response_data:
                # 解析上游响应，提取IP和TTL存入缓存
                try:
                    upstream_response = DNSMessage.parse(response_data)
                    # 遍历回答记录，查找A记录
                    # 收集所有A记录
                    a_records = []
                    for answer in upstream_response.answers:
                        # 处理A记录(IPv4)和AAAA记录(IPv6)
                        if answer['type'] == 1:  # A记录
                            ip = socket.inet_ntoa(answer['rdata'])
                            ttl = answer['ttl']
                            a_records.append((ip, ttl))
                            self.cache.add_record(domain, ip, ttl, 1)
                            self.logger.debug(f"Added cache record: {domain} -> {ip} (TTL: {ttl}s)")
                            self.logger.info(f"Added IPv4 {domain} -> {ip} to cache with TTL {ttl}s")
                        elif answer['type'] == 28:  # AAAA记录
                            ip = socket.inet_ntop(socket.AF_INET6, answer['rdata'])
                            ttl = answer['ttl']
                            self.cache.add_record(domain, ip, ttl, 28)
                            self.logger.info(f"Added IPv6 {domain} -> {ip} to cache with TTL {ttl}s")
                    
                    # 如果没有A记录，记录警告
                    if not a_records:
                        self.logger.warning(f"No A records found for {domain} in upstream response")
                except Exception as e:
                    self.logger.error(f"Failed to parse upstream response for caching: {e}")
                try:
                    sock.sendto(response_data, addr)
                except ConnectionResetError:
                    self.logger.warning(f"发送上游响应到 {addr} 时连接被重置")
                except Exception as e:
                    self.logger.error(f"发送上游响应错误: {e}")
            else:
                # 上游服务器无响应，返回服务器错误
                error_response = self.build_error_response(dns_msg, rcode=2)
                try:
                    sock.sendto(error_response, addr)
                except ConnectionResetError:
                    self.logger.warning(f"发送错误响应到 {addr} 时连接被重置")
                except Exception as e:
                    self.logger.error(f"发送错误响应错误: {e}")

    def extract_domain(self, dns_msg):
        """从DNS消息中提取第一个问题的域名

        Args:
            dns_msg (DNSMessage): 已解析的DNS消息对象

        Returns:
            str: 提取的域名字符串，如"example.com"
        """
        if dns_msg.questions and len(dns_msg.questions) > 0:
            # 移除域名末尾可能存在的点以匹配数据库格式
            domain = dns_msg.get_question_domain(0).rstrip('.').lower()
            return domain
        return ""

    def _create_response_header(self, request_header, rcode=0):
        """创建响应消息头

        Args:
            request_header (DNSHeader): 请求消息头对象
            rcode (int): 响应码(0=无错误,3=域名不存在)

        Returns:
            DNSHeader: 构建好的响应消息头对象
        """
        response_header = DNSHeader()
        response_header.transaction_id = request_header.transaction_id
        response_header.qr = 1  # 响应标志
        response_header.opcode = request_header.opcode
        response_header.aa = 1  # 授权回答
        response_header.tc = 0
        response_header.rd = request_header.rd  # 保持请求的递归期望
        response_header.ra = 1  # 支持递归
        response_header.z = 0
        response_header.rcode = rcode
        response_header.qdcount = request_header.qdcount
        response_header.ancount = 0
        response_header.nscount = 0
        response_header.arcount = 0
        
        # 计算flags值
        response_header.flags = (response_header.qr << 15) | \
                               (response_header.opcode << 11) | \
                               (response_header.aa << 10) | \
                               (response_header.tc << 9) | \
                               (response_header.rd << 8) | \
                               (response_header.ra << 7) | \
                               (response_header.z << 4) | \
                               response_header.rcode
        
        return response_header

    def build_error_response(self, dns_msg, rcode=2):
        """构建错误响应

        Args:
            dns_msg (DNSMessage): 原始请求DNS消息对象
            rcode (int): 响应码(2=服务器失败, 3=域名不存在)

        Returns:
            bytes: 构建好的DNS响应数据
        """
        response_header = self._create_response_header(dns_msg.header, rcode=rcode)
        return dns_msg.build_response(
            header=response_header,
            answers=[]
        )

    def build_blacklist_response(self, dns_msg):
        """构建黑名单响应(返回域名不存在错误)

        Args:
            dns_msg (DNSMessage): 原始请求DNS消息对象

        Returns:
            bytes: 构建好的DNS响应数据
        """
        # 创建响应头(设置域名不存在错误)
        response_header = self._create_response_header(dns_msg.header, rcode=3)

        # 构建并返回完整响应
        return dns_msg.build_response(
            header=response_header,
            answers=[]  # 黑名单响应无回答记录
        )

    def build_whitelist_response(self, dns_msg, ips, domain):
        """构建白名单响应(返回查询到的IP地址列表和内部ID)

        Args:
            dns_msg (DNSMessage): 原始请求DNS消息对象
            ips (list): 要返回的IP地址列表
            domain (str): 查询的域名

        Returns:
            bytes: 构建好的DNS响应数据
        """
        # 获取查询类型
        qtype = dns_msg.questions[0][1] if dns_msg.questions else 1
        answers = []
        for ip in ips:
            # 根据查询类型返回A记录(IPv4)或AAAA记录(IPv6)
            try:
                # 尝试解析为IPv4
                socket.inet_pton(socket.AF_INET, ip)
                record_type = 1
                rdata = socket.inet_aton(ip)
            except OSError:
                try:
                    # 尝试解析为IPv6
                    socket.inet_pton(socket.AF_INET6, ip)
                    record_type = 28
                    rdata = socket.inet_pton(socket.AF_INET6, ip)
                except OSError:
                    # 无效的IP地址
                    self.logger.error(f"Invalid IP address: {ip} for domain {domain}")
                continue
            record = {
                'name': dns_msg.questions[0][0],  # 查询域名
                'type': record_type,              # 记录类型
                'class': 1,                        # IN互联网类
                'ttl': self.default_ttl,           # 使用配置的TTL
                'rdata': rdata                     # IP地址转换为网络字节序
            }
            answers.append(record)
        
        # 添加内部ID的TXT记录
        internal_id = self.db.get_internal_id(domain)
        if internal_id is not None:
            txt_record = DNSMessage.build_txt_record(
                name=dns_msg.questions[0][0],
                ttl=self.default_ttl,
                text=f"internal-id:{internal_id}"
            )
            answers.append(txt_record)

        # 构建响应标志位
        # 创建响应头
        response_header = self._create_response_header(dns_msg.header)
        response_header.ancount = len(answers)  # 设置回答数

        # 构建并返回完整响应
        return dns_msg.build_response(
            header=response_header,
            answers=answers
        )