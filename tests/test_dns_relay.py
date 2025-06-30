import unittest
import socket
from unittest.mock import patch, Mock
from dns_relay import DNSRelay

class TestDNSRelay(unittest.TestCase):
    def setUp(self):
        # 创建测试用的日志模拟对象
        self.logger = Mock()
        self.logger.warning = Mock()
        self.logger.error = Mock()
        
        # 创建DNSRelay实例
        self.relay = DNSRelay(
            local_ip='127.0.0.1',
            local_port=53,
            upstream_server=('8.8.8.8', 53),
            logger=self.logger
        )

    @patch('socket.socket')
    def test_forward_query_success(self, mock_socket):
        # 测试成功转发查询
        # 准备测试数据
        query_data = b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x07example\x03com\x00\x00\x01\x00\x01'
        mock_response = b'\x12\x34\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00\x03www\x07example\x03com\x00\x00\x01\x00\x01\xc0\x0c\x00\x01\x00\x01\x00\x00\x0e\x10\x00\x04\xc0\xa8\x01\x01'
        
        # 配置socket模拟
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.recvfrom.return_value = (mock_response, ('8.8.8.8', 53))
        
        # 执行测试
        result = self.relay.forward_query(query_data)
        
        # 验证结果
        self.assertEqual(result, mock_response)
        mock_sock.sendto.assert_called_once_with(query_data, ('8.8.8.8', 53))
        mock_sock.close.assert_called_once()
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    @patch('socket.socket')
    def test_forward_query_timeout(self, mock_socket):
        # 测试上游服务器超时
        query_data = b'test_query_data'
        
        # 配置socket模拟以引发超时
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.recvfrom.side_effect = socket.timeout
        
        # 执行测试
        result = self.relay.forward_query(query_data)
        
        # 验证结果
        self.assertIsNone(result)
        self.logger.warning.assert_called_once_with('Upstream DNS server timeout')
        mock_sock.close.assert_called_once()

    @patch('socket.socket')
    def test_forward_query_exception(self, mock_socket):
        # 测试转发过程中的异常处理
        query_data = b'test_query_data'
        
        # 配置socket模拟以引发异常
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        mock_sock.sendto.side_effect = Exception('Network error')
        
        # 执行测试
        result = self.relay.forward_query(query_data)
        
        # 验证结果
        self.assertIsNone(result)
        self.logger.error.assert_called_once()
        mock_sock.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()