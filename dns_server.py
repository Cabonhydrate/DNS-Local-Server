import socket
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from dns_message import DNSMessage, DNSHeader
from dns_db import LocalDNSDatabase
from dns_relay import DNSRelay
from dns_cache import DNSCache

class DNSServer:
    """DNS服务器核心类，负责接收和处理DNS查询请求

    该类集成了本地数据库查询、缓存管理和上游服务器转发功能，
    实现了一个完整的DNS服务器处理流程，包括请求解析、本地数据查询、
    缓存检查、上游转发和响应构建等功能。

    Attributes:
        local_ip (str): 本地服务器IP地址
        local_port (int): 本地服务器端口
        upstream_server (tuple): 上游DNS服务器地址和端口
        default_ttl (int): 默认TTL值(秒)
        db (LocalDNSDatabase): 本地DNS数据库实例
        logger (Logger): 日志记录器实例
        relay (DNSRelay): DNS中继器实例，用于转发请求到上游服务器
        cache (DNSCache): DNS缓存实例，用于存储查询结果
    """
    def __init__(self, config, logger, db, relay, cache):
        # 配置参数验证：确保启动服务器所需的关键配置项存在且格式正确
        # 验证逻辑：
        # 1. 检查必填配置项是否齐全
        # 2. 验证上游DNS服务器配置格式
        required_keys = ['local_ip', 'local_port', 'upstream_dns', 'database_file']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")
        # 上游DNS配置必须包含'ip'和'port'字段
        if not isinstance(config['upstream_dns'], dict) or 'ip' not in config['upstream_dns'] or 'port' not in config['upstream_dns']:
            raise ValueError("Upstream DNS configuration must be a dict with 'ip' and 'port'")
        self.local_ip = config['local_ip']
        self.local_port = config['local_port']
        self.upstream_server = (config['upstream_dns']['ip'], config['upstream_dns']['port'])
        self.default_ttl = config.get('default_ttl', 300)
        self.db = db
        self.logger = logger
        self.relay = relay
        self.cache = cache
        # 启动缓存清理线程
        # 功能：定期清理过期的DNS缓存记录，防止缓存无限增长
        # 实现：创建一个后台守护线程，每60秒调用一次cache.clear_expired()
        def start_cache_cleaner():
            while True:
                self.cache.clear_expired()
                time.sleep(60)  # 每60秒清理一次过期缓存
        # 创建守护线程：当主线程退出时自动结束，避免资源泄漏
        cleaner_thread = threading.Thread(target=start_cache_cleaner, daemon=True)
        cleaner_thread.start()

    def start(self):
        """启动DNS服务器并开始监听DNS查询请求

        该方法执行以下操作：
        1. 清空日志文件
        2. 加载本地DNS数据库
        3. 创建UDP socket并绑定到本地地址和端口
        4. 使用线程池处理接收到的DNS查询请求，支持并发处理

        服务器将持续运行，直到被手动终止。每个查询请求会被提交到线程池处理，
        以支持高并发查询。
        """
        # 清空日志文件：在服务器启动时重置日志，避免日志文件过大
        log_path = self.logger.log_file
        try:
            with open(log_path, 'w') as f:
                pass  # 以写入模式打开文件会截断内容，达到清空效果
        except Exception as e:
            self.logger.error(f"Failed to clear log file: {e}")
        # 加载本地DNS数据库：从配置的数据库文件中加载域名-IP映射关系
        # 创建UDP套接字
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.local_ip, self.local_port))
        sock.settimeout(5)  # 添加超时设置

        
        # 创建线程池，设置最大工作线程数为10
        # 选择依据：根据DNS查询的平均处理时间和预期并发量设定，10个线程可满足普通场景需求
        # 使用with语句确保线程池在服务器停止时正确关闭
        #with语句用于创建一个上下文管理器，确保资源在使用完毕后能够被正确释放，无论是否发生异常。
        #用客服的例子来理解
        with ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                try:
                    # 接收DNS查询数据，缓冲区大小512字节(符合DNS协议标准)
                    data, addr = sock.recvfrom(512)
                    # 提交请求处理任务到线程池，实现异步处理，避免阻塞主线程
                    executor.submit(self.handle_query, data, addr, sock)
                except ConnectionResetError:
                    self.logger.warning("客户端连接被重置")
                except socket.timeout:
                    continue  # 超时不处理，继续等待新请求
                except Exception as e:
                    self.logger.error(f"发生错误: {e}")  # 捕获其他所有异常，确保服务器稳定运行

    def handle_query(self, data, addr, sock):
        """处理接收到的DNS查询请求

        该方法是DNS查询处理的核心逻辑，执行以下步骤：
        1. 解析接收到的DNS查询数据
        2. 提取查询域名和查询类型
        3. 检查域名是否在黑名单中
        4. 若在白名单中，从本地数据库返回结果
        5. 若不在本地数据库，检查缓存
        6. 若缓存未命中，转发请求到上游DNS服务器
        7. 构建并发送响应给客户端

        Args:
            data (bytes): 接收到的DNS查询数据
            addr (tuple): 客户端地址，格式为(ip, port)
            sock (socket.socket): 用于发送响应的UDP socket
        """
        try:
            self.logger.info(f"Received DNS query from {addr}")
            self.logger.debug(f"Query data: {data.hex()}")
            dns_msg = DNSMessage.parse(data)
            domain = self.extract_domain(dns_msg)  # 提取域名
            if not domain:
                self.logger.error("Received DNS query with empty domain")
                return
            # 获取并记录域名内部ID
            domain_id = self.db.get_internal_id(domain)
            if domain_id:
                self.logger.debug(f"Domain {domain} mapped to internal ID: {domain_id}")
            else:
                self.logger.debug(f"No internal ID found for domain: {domain}")
            #指定查询的记录类型 默认，ipv4的话值为1  ipv6的话值为28   
            #取当前请求的第一个查询
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
            # 根据查询类型获取对应版本的IP地址
            # 查询类型参考：
            # - 1: A记录(IPv4)
            # - 28: AAAA记录(IPv6)
            # - 其他类型暂不支持，返回空列表
            if qtype == 28:
                ips = self.db.get_ipv6(domain)
            elif qtype == 1:
                ips = self.db.get_ipv4(domain)
            else:
                ips = []
            if ips:
                # 数据格式统一：确保ips始终为列表类型，即使只有一个IP
                if isinstance(ips, str):
                    ips = [ips]  # 将单个IP字符串转换为单元素列表
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
            #后进行缓存查询：数据库是静态的，先查反而更快。
            #规则优先，方便我测试
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
                    # 解析上游响应，提取IP和TTL存入缓存
                    # 遍历所有回答记录，处理A(IPv4)和AAAA(IPv6)类型
                    a_records = []
                    for answer in upstream_response.answers:
                        # A记录(IPv4)处理
                        if answer['type'] == 1:  # A记录
                            # 将网络字节序转换为点分十进制IP
                            ip = socket.inet_ntoa(answer['rdata'])
                            ttl = answer['ttl']
                            a_records.append((ip, ttl))
                            # 添加到缓存，类型1表示A记录
                            self.cache.add_record(domain, ip, ttl, 1)
                            self.logger.debug(f"Added cache record: {domain} -> {ip} (TTL: {ttl}s)")
                            self.logger.info(f"Added IPv4 {domain} -> {ip} to cache with TTL {ttl}s")
                        # AAAA记录(IPv6)处理
                        elif answer['type'] == 28:  # AAAA记录
                            # 将网络字节序转换为IPv6字符串
                            ip = socket.inet_ntop(socket.AF_INET6, answer['rdata'])
                            ttl = answer['ttl']
                            # 添加到缓存，类型28表示AAAA记录
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

        从DNS查询消息的问题部分提取第一个问题的域名，并进行标准化处理，
        移除末尾的点并转换为小写，以统一格式匹配本地数据库。

        Args:
            dns_msg (DNSMessage): 已解析的DNS消息对象

        Returns:
            str: 提取的域名字符串，如"example.com"；若没有问题部分则返回空字符串
        """
        if dns_msg.questions and len(dns_msg.questions) > 0:
            # 移除域名末尾可能存在的点以匹配数据库格式
            domain = dns_msg.get_question_domain(0).rstrip('.').lower()
            return domain
        return ""

    def _create_response_header(self, request_header, rcode=0):
        """创建DNS响应消息头

        根据请求消息头和响应码构建响应消息头，设置响应标志位，
        包括响应标志(QR=1)、授权回答(AA=1)、递归可用(RA=1)等。

        Args:
            request_header (DNSHeader): 请求消息头对象
            rcode (int): 响应码，默认为0(无错误)，常用值包括：
                         0: 无错误
                         1: 格式错误
                         2: 服务器失败
                         3: 域名不存在

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
        
        # 计算flags值,左移然后进行”或“操作来构建
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
        """构建DNS错误响应

        根据指定的响应码构建错误响应，包含正确的消息头但不包含回答记录。
        常用于处理解析错误、服务器故障等异常情况。

        Args:
            dns_msg (DNSMessage): 原始请求DNS消息对象
            rcode (int): 响应码，默认为2(服务器失败)，常用值包括：
                         2: 服务器失败
                         3: 域名不存在

        Returns:
            bytes: 构建好的DNS响应数据
        """
        response_header = self._create_response_header(dns_msg.header, rcode=rcode)
        return dns_msg.build_response(
            header=response_header,
            answers=[]
        )

    def build_blacklist_response(self, dns_msg):
        """构建黑名单域名响应

        对于在黑名单中的域名，返回域名不存在错误(rcode=3)，
        阻止客户端访问被屏蔽的域名。

        Args:
            dns_msg (DNSMessage): 原始请求DNS消息对象

        Returns:
            bytes: 构建好的DNS响应数据，包含域名不存在错误
        """
        # 创建响应头(设置域名不存在错误)
        response_header = self._create_response_header(dns_msg.header, rcode=3)

        # 构建并返回完整响应
        return dns_msg.build_response(
            header=response_header,
            answers=[]  # 黑名单响应无回答记录
        )

    def build_whitelist_response(self, dns_msg, ips, domain):
        """构建白名单域名响应

        为白名单域名构建包含IP地址记录的DNS响应，支持IPv4(A记录)和IPv6(AAAA记录)，
        并添加包含内部ID的TXT记录，便于跟踪和管理域名。

        Args:
            dns_msg (DNSMessage): 原始请求DNS消息对象
            ips (list): 要返回的IP地址列表，可以包含IPv4和IPv6地址
            domain (str): 查询的域名

        Returns:
            bytes: 构建好的DNS响应数据，包含IP记录和可选的TXT记录
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
        
        # 添加内部ID的TXT记录：为便于域名管理，附加自定义TXT记录
            # TXT记录格式："internal-id:{id}"，其中{id}为数据库中的域名内部标识
            internal_id = self.db.get_internal_id(domain)
            if internal_id is not None:
                txt_record = DNSMessage.build_txt_record(
                    name=dns_msg.questions[0][0],
                    ttl=self.default_ttl,
                    text=f"internal-id:{internal_id}"
                )
                answers.append(txt_record)  # 将TXT记录添加到响应中

        # 构建响应标志位
        # 创建响应头
        response_header = self._create_response_header(dns_msg.header)
        response_header.ancount = len(answers)  # 设置回答数

        # 构建并返回完整响应
        return dns_msg.build_response(
            header=response_header,
            answers=answers
        )