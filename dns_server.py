import socket
from dns_message import DNSMessage, DNSHeader
from dns_db import LocalDNSDatabase
from dns_relay import DNSRelay

class DNSServer:
    def __init__(self, local_ip, local_port, upstream_server, db_file):
        self.local_ip = local_ip
        self.local_port = local_port
        self.upstream_server = upstream_server
        self.db = LocalDNSDatabase(db_file)
        self.relay = DNSRelay(local_ip, local_port, upstream_server)

    def start(self):
        self.db.load()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.local_ip, self.local_port))
        print(f"DNS server started on {self.local_ip}:{self.local_port}")
        while True:
            data, addr = sock.recvfrom(512)
            self.handle_query(data, addr, sock)

    def handle_query(self, data, addr, sock):
        dns_msg = DNSMessage.parse(data)
        domain = self.extract_domain(dns_msg)  # 需要实现提取域名的逻辑

        if self.db.is_in_blacklist(domain):
            response = self.build_blacklist_response(dns_msg)
            sock.sendto(response, addr)
        else:
            ip = self.db.get_ip(domain)
            if ip:
                response = self.build_whitelist_response(dns_msg, ip, domain)
                sock.sendto(response, addr)
            else:
                # 转发查询并获取上游服务器响应
                response_data = self.relay.forward_query(data)
                if response_data:
                    sock.sendto(response_data, addr)
                else:
                    # 上游服务器无响应，返回服务器错误
                    error_response = self.build_error_response(dns_msg, rcode=2)
                    sock.sendto(error_response, addr)

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

    def build_whitelist_response(self, dns_msg, ip, domain):
        """构建白名单响应(返回查询到的IP地址和内部ID)

        Args:
            dns_msg (DNSMessage): 原始请求DNS消息对象
            ip (str): 要返回的IP地址
            domain (str): 查询的域名

        Returns:
            bytes: 构建好的DNS响应数据
        """
        # 构建A记录资源记录
        a_record = {
            'name': dns_msg.questions[0][0],  # 查询域名
            'type': 1,                         # A记录类型
            'class': 1,                        # IN互联网类
            'ttl': 300,                        # 5分钟缓存时间
            'rdata': socket.inet_aton(ip)      # IP地址转换为网络字节序
        }
        
        answers = [a_record]
        
        # 添加内部ID的TXT记录
        internal_id = self.db.get_internal_id(domain)
        if internal_id is not None:
            txt_record = DNSMessage.build_txt_record(
                name=dns_msg.questions[0][0],
                ttl=300,
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