import struct
import socket

class DNSHeader:
    def __init__(self):
        """初始化DNS头部字段

        DNS头部共12字节，结构如下(RFC1035 4.1.1节):
        0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                      ID                       |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE   |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    QDCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    ANCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    NSCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        |                    ARCOUNT                    |
        +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
        """
        # DNS头部核心字段(RFC1035 4.1.1节)
        self.transaction_id = None  # 2字节：事务ID，客户端生成的唯一标识符，服务器响应时需原样返回
                                    # 用途：匹配请求与响应，确保客户端能将响应与对应的请求关联
        self.flags = None           # 2字节：标志位集合，包含16个二进制位，用于表示消息的各种属性
                                    # 结构：QR(1位) + Opcode(4位) + AA(1位) + TC(1位) + RD(1位) + RA(1位) + Z(3位) + RCODE(4位)
        self.qdcount = 0            # 2字节：问题计数(Question Count)，指明消息中Question部分的条目数量
                                    # 用途：告知接收方需要解析的问题数量，服务器通常会为每个问题提供一个回答
        self.ancount = 0            # 2字节：回答计数(Answer Count)，指明Answer部分包含的资源记录数量
                                    # 用途：告知接收方有多少条回答记录，客户端根据此值解析对应数量的资源记录
        self.nscount = 0            # 2字节：授权计数(Name Server Count)，指明Authority部分包含的资源记录数量
                                    # 用途：提供权威名称服务器信息，通常在域名解析需要进一步查询时使用
        self.arcount = 0            # 2字节：附加计数(Additional Count)，指明Additional部分包含的资源记录数量
                                    # 用途：提供额外的辅助信息，如权威服务器的IP地址，减少客户端后续查询
        
        # 标志位分解字段(从flags中解析得到)
        self.qr = 0                 # 1位：查询/响应标志(Query/Response)
                                    # 取值：0=查询消息(客户端发送)，1=响应消息(服务器返回)
        self.opcode = 0             # 4位：操作码(Operation Code)，定义DNS消息的类型
                                    # 标准取值：0=标准查询(QUERY)，1=反向查询(IQUERY)，2=服务器状态查询(STATUS)
                                    # 扩展取值：3-15为保留值，用于未来扩展
        self.aa = 0                 # 1位：授权回答标志(Authoritative Answer)，仅在响应中有效
                                    # 取值：1=响应来自权威服务器，0=非权威回答(如缓存结果)
        self.tc = 0                 # 1位：截断标志(Truncated Response)
                                    # 取值：1=消息长度超过512字节被截断，客户端需使用TCP重试(默认UDP限制)
        self.rd = 0                 # 1位：递归期望(Recursion Desired)
                                    # 取值：1=客户端希望服务器进行递归查询，0=客户端希望服务器进行迭代查询
        self.ra = 0                 # 1位：递归可用(Recursion Available)，仅在响应中有效
                                    # 取值：1=服务器支持递归查询，0=服务器不支持递归
        self.z = 0                  # 3位：保留字段(Reserved)，必须设置为0，用于未来扩展
        self.rcode = 0              # 4位：响应码(Response Code)，表示查询的处理结果
                                    # 常见取值：0=无错误(NoError)，3=域名不存在(NXDomain)，5=拒绝(Refused)
                                    # 完整取值见RFC1035 4.1.1节和后续扩展文档

    @classmethod
    def parse(cls, data):
        """从字节数据解析DNS头部

        Args:
            data (bytes): 完整的DNS消息字节数据

        Returns:
            DNSHeader: 解析后的DNSHeader对象

        Raises:
            ValueError: 当数据长度小于12字节时抛出
        """
        if len(data) < 12:
            raise ValueError("DNS消息长度不足，头部需要至少12字节")
        
        header = cls()
        # 解析头部（前12字节），使用网络字节序(!)和无符号短整型(H)
        # 格式字符串含义: !表示网络字节序(大端序),6个H表示6个2字节无符号整数
        header_data = struct.unpack('!HHHHHH', data[:12])
        header.transaction_id = header_data[0]  # ID字段
        header.flags = header_data[1]           # 标志字段
        header.qdcount = header_data[2]         # 问题计数
        header.ancount = header_data[3]         # 回答计数
        header.nscount = header_data[4]         # 授权计数
        header.arcount = header_data[5]         # 附加计数
        
        # 解析标志位字段(2字节=16位)
        # 按位运算提取各个子字段，参考RFC1035 4.1.1节
        header.qr = (header.flags >> 15) & 0x01          # 第15位(最高位)
        header.opcode = (header.flags >> 11) & 0x0F       # 第11-14位(4位)
        header.aa = (header.flags >> 10) & 0x01           # 第10位
        header.tc = (header.flags >> 9) & 0x01            # 第9位
        header.rd = (header.flags >> 8) & 0x01            # 第8位
        header.ra = (header.flags >> 7) & 0x01            # 第7位
        header.z = (header.flags >> 4) & 0x07             # 第4-6位(3位)
        header.rcode = header.flags & 0x0F                # 第0-3位(4位)
        
        return header


class DNSMessage:
    """DNS消息类，包含完整的DNS消息结构

    DNS消息结构(RFC1035 4.1节):
    +---------------------+
    |        Header       |  # 12字节，已解析为DNSHeader对象
    +---------------------+
    |       Question      |  # 问题部分，包含查询域名、类型和类
    +---------------------+
    |        Answer       |  # 回答部分，包含资源记录
    +---------------------+
    |      Authority      |  # 授权部分，包含权威名称服务器
    +---------------------+
    |     Additional      |  # 附加部分，包含额外信息
    +---------------------+
    """
    def __init__(self, data):
        """初始化DNS消息

        Args:
            data (bytes): 原始DNS消息字节数据
        """
        self.data = data                # 原始消息数据
        self.header = None              # DNSHeader对象：已解析的头部信息
        self.questions = []             # 问题列表：每个元素是元组(qname（域名）, qtype, qclass)
        self.answers = []               # 回答资源记录列表
        self.authority = []             # 授权资源记录列表
        self.additional = []            # 附加资源记录列表

    def get_question_domain(self, index=0):
        """获取指定索引的问题部分的域名

        Args:
            index (int): 问题索引，默认为0，之所以会有这个index是因为一个请求可能有多个问题

        Returns:
            str: 问题域名，如果索引无效则返回空字符串
        """
        if 0 <= index < len(self.questions):
            return self.questions[index][0]
        return ""

    @staticmethod
    def parse(data):
        """从字节数据解析完整DNS消息

        Args:
            data (bytes): 原始DNS消息字节数据

        Returns:
            DNSMessage: 解析后的DNSMessage对象

        Raises:
            ValueError: 当数据长度小于12字节时抛出
        """
        msg = DNSMessage(data)
        if len(data) < 12:
            raise ValueError("DNS消息长度不足，头部需要至少12字节")
        
        # 解析头部
        msg.header = DNSHeader.parse(data)
        
        # 解析问题部分(RFC1035 4.1.2节)
        offset = 12  # 头部占用12字节，问题部分从偏移12开始
        # 根据头部的qdcount字段确定问题数量
        for _ in range(msg.header.qdcount):
            # 解析域名
            qname, offset = DNSMessage._parse_name(data, offset)
            # 解析查询类型和查询类(各2字节)
            qtype, qclass = struct.unpack('!HH', data[offset:offset+4])
            offset +=4
            # 添加到问题列表
            # qtype: 查询类型(1=A记录,2=NS记录,5=CNAME等)
            # qclass: 查询类(1=IN互联网地址)
            msg.questions.append((qname, qtype, qclass))
        
        # 解析回答部分
        for _ in range(msg.header.ancount):
            name, offset = DNSMessage._parse_name(data, offset)
            type_code, cls = struct.unpack('!HH', data[offset:offset+4])
            offset += 4
            ttl = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            rdlength = struct.unpack('!H', data[offset:offset+2])[0]
            offset += 2
            rdata = data[offset:offset+rdlength]
            offset += rdlength
            msg.answers.append({
                'name': name,
                'type': type_code,
                'class': cls,
                'ttl': ttl,
                'rdata': rdata
            })
        
        # 解析授权部分
        for _ in range(msg.header.nscount):
            name, offset = DNSMessage._parse_name(data, offset)
            type_code, cls = struct.unpack('!HH', data[offset:offset+4])
            offset += 4
            ttl = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            rdlength = struct.unpack('!H', data[offset:offset+2])[0]
            offset += 2
            rdata = data[offset:offset+rdlength]
            offset += rdlength
            msg.authority.append({
                'name': name,
                'type': type_code,
                'class': cls,
                'ttl': ttl,
                'rdata': rdata
            })
        
        # 解析附加部分
        for _ in range(msg.header.arcount):
            name, offset = DNSMessage._parse_name(data, offset)
            type_code, cls = struct.unpack('!HH', data[offset:offset+4])
            offset += 4
            ttl = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            rdlength = struct.unpack('!H', data[offset:offset+2])[0]
            offset += 2
            rdata = data[offset:offset+rdlength]
            offset += rdlength
            msg.additional.append({
                'name': name,
                'type': type_code,
                'class': cls,
                'ttl': ttl,
                'rdata': rdata
            })
        
        return msg
    
    @staticmethod
    def _parse_name(data, offset):
        """解析DNS域名（支持压缩格式）

        DNS域名格式(RFC1035 3.1节):
        由一系列标签组成，每个标签以长度字节开头(0-63)，最后以0字节结束
        压缩格式使用指针(最高两位为1)指向消息中已出现的域名，避免重复

        Args:
            data (bytes): 原始DNS消息字节数据
            offset (int): 当前解析偏移量

        Returns:
            tuple: (域名字符串, 新偏移量)
        """
        name_parts = []
        while True:
            # 读取标签长度字节
            length = data[offset]
            
            # 0字节表示域名结束(RFC1035 3.1节)
            if length == 0:
                offset += 1
                break
            
            # 检查是否是指针(最高两位为1: 0xC0 = 11000000)
            # DNS压缩格式使用指针避免重复域名，指针占2字节，最高两位为11表示指针
            if (length & 0xC0) == 0xC0:
                # 指针计算：取第一个字节低6位和第二个字节组成14位偏移量
                # 0x3F是掩码，保留低6位：00111111
                pointer = ((length & 0x3F) << 8) | data[offset + 1]
                offset += 2  # 指针占用2字节
                # 递归解析指针指向的域名
                sub_name, _ = DNSMessage._parse_name(data, pointer)
                name_parts.append(sub_name)
                break
            
            # 普通标签处理(长度0-63)
            # 标签格式：[长度字节(1字节)][标签内容(n字节)]
            offset += 1  # 跳过长度字节
            # 读取标签内容并解码为ASCII(RFC1035要求域名使用ASCII编码)
            label = data[offset:offset + length].decode('ascii')
            name_parts.append(label)
            offset += length  # 移动到下一个标签
        
        # 连接所有标签，形成完整域名
        return '.'.join(name_parts), offset

    def build_response(self, header, answers):
        """构建DNS响应消息

        根据DNS请求消息和提供的回答资源记录，构建完整的DNS响应消息字节数据
        响应消息结构遵循RFC1035 4.1节规范，包含头部、问题部分和回答部分

        Args:
            header (DNSHeader): 响应消息头对象，需设置正确的标志位和计数字段
            answers (list): 回答资源记录列表，每个元素为包含以下键的字典:
                - name (str): 域名
                - type (int): 资源记录类型码(如1=A记录,16=TXT记录)
                - class (int): 类别码(通常为1表示IN类)
                - ttl (int): 生存时间(秒)
                - rdata (bytes): 资源数据字节

        Returns:
            bytes: 构建好的DNS响应字节数据，可直接通过网络发送

        Note:
            此实现目前仅包含头部、问题部分和回答部分，未包含授权和附加部分
            问题部分直接复用请求中的问题部分，避免重复解析和编码
        """
        # 构建响应头部
        # 头部格式: !HHHHHH (ID, 标志, QDCOUNT, ANCOUNT, NSCOUNT, ARCOUNT)
        header_data = struct.pack('!HHHHHH',
                                 header.transaction_id,
                                 header.flags,
                                 header.qdcount,
                                 len(answers),
                                 header.nscount,
                                 header.arcount)
        
        # 构建问题部分（直接复用请求中的问题部分）
        question_section = self.data[12:12 + self._get_question_section_length()]
        
        # 构建答案部分
        answer_section = b''
        for ans in answers:
            # 资源记录格式: 域名(压缩格式) + 类型 + 类 + TTL + 数据长度 + 数据
            answer_section += self._encode_name(ans['name'])
            answer_section += struct.pack('!HHIH',
                                      ans['type'],
                                      ans['class'],
                                      ans['ttl'],
                                      len(ans['rdata']))
            answer_section += ans['rdata']
        
        # 组合完整响应
        response = header_data + question_section + answer_section
        return response
    
    def _get_question_section_length(self):
        """计算问题部分的总长度

        通过遍历所有问题条目，计算每个问题的DNS编码长度并求和
        问题部分格式(RFC1035 4.1.2节): [域名][类型(2字节)][类(2字节)]

        Returns:
            int: 问题部分的总字节数，用于构建响应时定位回答部分的起始位置
        """
        length = 0
        for qname, qtype, qclass in self.questions:
            # 域名长度(包括标签长度字节和结尾0字节) + 4字节(qtype+qclass)
            length += self._get_domain_length(qname) + 4
        return length
    
    def _encode_name(self, domain):
        """将域名编码为DNS格式(RFC1035 3.1节)

        DNS域名编码规则：
        1. 域名由多个标签组成，标签间用点分隔
        2. 每个标签编码为[长度字节(1字节)][标签内容(n字节)]
        3. 域名以0字节结束
        4. 不支持域名压缩(本实现仅生成未压缩域名)

        Args:
            domain (str): 域名字符串(如"example.com")，空字符串表示根域名

        Returns:
            bytes: DNS格式的域名字节数据

        Example:
            domain="www.example.com" → 编码后为\x03www\x07example\x03com\x00
        """
        if not domain:
            return b'\x00'
        encoded = b''
        for label in domain.split('.'):
            encoded += bytes([len(label)]) + label.encode('ascii')
        encoded += b'\x00'
        return encoded

    def _get_domain_length(self, domain):
        """计算域名的DNS编码长度

        Args:
            domain (str): 域名字符串(如"example.com")

        Returns:
            int: DNS编码后的长度(包括结尾0字节)
        """
        if not domain:
            return 1  # 仅包含结尾0字节
        length = 0
        for label in domain.split('.'):
            length += len(label) + 1  # 标签长度字节 + 标签内容
        length += 1  # 结尾0字节
        return length

    @staticmethod
    def build_txt_record(name, ttl, text):
        """构建TXT资源记录(RFC1035 3.3.14节)

        用于输出合规的TXT记录

        Args:
            name (str): 域名，TXT记录关联的域名
            ttl (int): 生存时间(秒)，表示记录在缓存中的保留时间
            text (str): TXT记录内容，将被编码为单个字符串段

        Returns:
            dict: TXT资源记录字典，可直接用于build_response方法的answers参数

        Note:
            本实现仅支持单个字符串段的TXT记录，如需多段需扩展rdata生成逻辑
            TXT记录类型码为16，类别码固定为1(IN类)
        """
        # TXT记录的rdata格式: 长度字节 + 文本内容
        rdata = bytes([len(text)]) + text.encode('ascii')
        return {
            'name': name,
            'type': 16,  # TXT记录类型码
            'class': 1,   # IN类
            'ttl': ttl,
            'rdata': rdata
        }