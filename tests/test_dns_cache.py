import unittest
import time
from unittest.mock import patch
from dns_cache import DNSCache

class TestDNSCache(unittest.TestCase):
    def setUp(self):
        self.cache = DNSCache()
        
    def test_add_and_get_record(self):
        # 测试添加和获取缓存记录
        self.cache.add_record('www.example.com', '192.168.1.1', 3600)
        self.assertEqual(self.cache.get_record('www.example.com'), '192.168.1.1')
        self.assertIsNone(self.cache.get_record('nonexistent.com'))
        
    @patch('time.time')
    def test_expired_record(self, mock_time):
        # 测试过期记录处理
        mock_time.return_value = 1000  # 设置当前时间
        self.cache.add_record('www.example.com', '192.168.1.1', 3600)  # TTL 3600秒
        
        # 时间未过期
        mock_time.return_value = 2000
        self.assertEqual(self.cache.get_record('www.example.com'), '192.168.1.1')
        
        # 时间已过期
        mock_time.return_value = 5000  # 1000 + 3600 = 4600，5000 > 4600
        self.assertIsNone(self.cache.get_record('www.example.com'))
        self.assertEqual(len(self.cache), 0)  # 过期记录应被删除
        
    @patch('time.time')
    def test_clear_expired(self, mock_time):
        # 测试清理过期记录
        mock_time.return_value = 1000
        self.cache.add_record('expired.com', '10.0.0.1', 100)  # TTL 100秒
        self.cache.add_record('valid.com', '10.0.0.2', 3600)   # TTL 3600秒
        
        # 时间前进200秒，使第一个记录过期
        mock_time.return_value = 1200
        self.cache.clear_expired()
        
        # 验证过期记录被清除，有效记录保留
        self.assertIsNone(self.cache.get_record('expired.com'))
        self.assertEqual(self.cache.get_record('valid.com'), '10.0.0.2')
        self.assertEqual(len(self.cache), 1)
        
    def test_cache_length(self):
        # 测试缓存长度
        self.assertEqual(len(self.cache), 0)
        self.cache.add_record('a.com', '1.1.1.1', 3600)
        self.cache.add_record('b.com', '2.2.2.2', 3600)
        self.assertEqual(len(self.cache), 2)
        self.cache.get_record('a.com')  # 访问不影响长度
        self.assertEqual(len(self.cache), 2)

if __name__ == '__main__':
    unittest.main()