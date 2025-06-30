import unittest
import struct
from dns_message import DNSHeader, DNSMessage

class TestDNSHeader(unittest.TestCase):
    def test_header_parsing(self):
        # 测试DNS头部解析功能
        # 构造符合RFC1035标准的DNS头部数据
        header_data = struct.pack('!HHHHHH',
            0x1234,  # Transaction ID
            0x8180,  # Flags (QR=1, Opcode=0, AA=0, TC=0, RD=1, RA=1, Z=0, RCODE=0)
            1,       # QDCOUNT
            2,       # ANCOUNT
            3,       # NSCOUNT
            4        # ARCOUNT
        )
        header = DNSHeader.parse(header_data)
        
        # 验证基本字段解析
        self.assertEqual(header.transaction_id, 0x1234)
        self.assertEqual(header.qdcount, 1)
        self.assertEqual(header.ancount, 2)
        self.assertEqual(header.nscount, 3)
        self.assertEqual(header.arcount, 4)
        
        # 验证标志位解析
        self.assertEqual(header.qr, 1)        # 响应消息
        self.assertEqual(header.opcode, 0)     # 标准查询
        self.assertEqual(header.aa, 0)         # 非权威回答
        self.assertEqual(header.tc, 0)         # 未截断
        self.assertEqual(header.rd, 1)         # 期望递归
        self.assertEqual(header.ra, 1)         # 递归可用
        self.assertEqual(header.z, 0)          # 保留字段
        self.assertEqual(header.rcode, 0)      # 无错误

    def test_header_parsing_short_data(self):
        # 测试不完整头部数据的错误处理
        with self.assertRaises(ValueError):
            DNSHeader.parse(b'\x00' * 11)  # 只有11字节，少于头部所需的12字节

class TestDNSMessage(unittest.TestCase):
    def test_parse_question_section(self):
        # 构造包含问题部分的DNS消息
        # 头部(12字节) + 问题部分(域名+类型+类)
        # 域名格式: 3www7example3com0 (www.example.com)
        question_data = b'\x03www\x07example\x03com\x00'  # 域名
        question_data += struct.pack('!HH', 1, 1)  # QTYPE=A记录, QCLASS=IN
        
        # 完整消息数据
        full_data = struct.pack('!HHHHHH', 0x5678, 0x0100, 1, 0, 0, 0) + question_data
        
        # 解析消息
        message = DNSMessage.parse(full_data)
        
        # 验证问题部分解析
        self.assertEqual(len(message.questions), 1)
        qname, qtype, qclass = message.questions[0]
        self.assertEqual(qname, 'www.example.com')
        self.assertEqual(qtype, 1)  # A记录类型
        self.assertEqual(qclass, 1)  # IN类

    def test_parse_name_with_compression(self):
        # 测试带压缩指针的域名解析 (RFC1035 4.1.4节)
        # 构造包含压缩指针的域名数据: www.example.com -> example.com (指针指向0xC00C)
        data = b'\x03www\xC0\x0C'  # 0xC00C表示指针指向偏移量12处
        
        # 创建完整消息数据，确保偏移量12处有example.com的定义
        full_data = b'\x00' * 12  # 头部12字节
        full_data += b'\x07example\x03com\x00'  # example.com的完整定义
        full_data += data  # 带压缩指针的域名
        
        # 解析域名
        name, offset = DNSMessage._parse_name(full_data, 12 + len(b'\x07example\x03com\x00'))
        self.assertEqual(name, 'www.example.com')

if __name__ == '__main__':
    unittest.main()