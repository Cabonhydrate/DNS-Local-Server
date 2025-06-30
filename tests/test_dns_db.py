import unittest
import os
import tempfile
from dns_db import LocalDNSDatabase

class TestLocalDNSDatabase(unittest.TestCase):
    def setUp(self):
        # 创建临时测试文件
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'database.txt')
        self.id_path = os.path.join(self.temp_dir.name, 'id_conversion_table.txt')
        
        # 创建测试数据库文件
        with open(self.db_path, 'w') as f:
            f.write('www.example.com 192.168.1.1\n')
            f.write('mail.example.com 192.168.1.2\n')
            f.write('blocked.com 0.0.0.0\n')  # 黑名单条目
            f.write('invalid.line\n')  # 无效格式行
        
        # 创建测试ID转换表
        with open(self.id_path, 'w') as f:
            f.write('# 这是注释行\n')
            f.write('www.example.com 1001\n')
            f.write('mail.example.com 1002\n')
            f.write('invalid.id abc\n')  # 无效ID格式

    def tearDown(self):
        # 清理临时目录
        self.temp_dir.cleanup()

    def test_load_database(self):
        # 测试数据库加载功能
        db = LocalDNSDatabase(self.db_path)
        db.load()
        
        # 验证白名单加载
        self.assertEqual(db.get_ip('www.example.com'), '192.168.1.1')
        self.assertEqual(db.get_ip('mail.example.com'), '192.168.1.2')
        
        # 验证黑名单加载
        self.assertTrue(db.is_in_blacklist('blocked.com'))
        self.assertFalse(db.is_in_blacklist('www.example.com'))
        
        # 验证无效行被忽略
        self.assertIsNone(db.get_ip('invalid.line'))

    def test_id_mapping(self):
        # 测试ID转换表功能
        db = LocalDNSDatabase(self.db_path)
        db.load()
        
        # 验证有效ID映射
        self.assertEqual(db.get_internal_id('www.example.com'), 1001)
        self.assertEqual(db.get_internal_id('mail.example.com'), 1002)
        
        # 验证无效ID被忽略
        self.assertIsNone(db.get_internal_id('invalid.id'))
        
        # 验证不存在的域名返回None
        self.assertIsNone(db.get_internal_id('nonexistent.com'))

    def test_missing_id_file(self):
        # 测试ID转换表文件不存在的情况
        # 删除ID文件
        os.remove(self.id_path)
        
        db = LocalDNSDatabase(self.db_path)
        db.load()  # 不应抛出异常
        self.assertEqual(len(db.id_mapping), 0)

if __name__ == '__main__':
    unittest.main()