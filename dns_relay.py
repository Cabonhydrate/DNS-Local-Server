import socket
import struct
import time

class DNSRelay:
    """DNS中继器类，负责将本地DNS查询转发至上游DNS服务器并返回响应

    实现了带重试机制的DNS查询转发功能，支持超时处理和错误记录，
    是本地DNS服务器与外部DNS服务器之间的桥梁组件。
    """
    def __init__(self, local_ip, local_port, upstream_server, logger):
        """初始化DNSRelay实例

        Args:
            local_ip (str): 本地DNS服务器IP地址，用于标识本地服务端点
            local_port (int): 本地DNS服务器端口号，通常为53
            upstream_server (tuple): 上游DNS服务器地址元组，格式为(ip, port)
                例如：('8.8.8.8', 53)表示Google公共DNS服务器
            logger (Logger): 日志记录器实例，用于记录中继过程中的调试、警告和错误信息
        """
        self.local_ip = local_ip          # 本地服务器IP
        self.local_port = local_port      # 本地服务器端口
        self.upstream_server = upstream_server  # 上游DNS服务器地址
        self.logger = logger              # 日志记录器

    def forward_query(self, query_data, max_retries=2, retry_delay=1):
        """将DNS查询转发至上游服务器并获取响应

        实现带重试机制的DNS查询转发，处理网络超时和异常情况，确保查询可靠性。
        使用UDP协议与上游DNS服务器通信，遵循DNS协议规范(RFC1035)。

        Args:
            query_data (bytes): 原始DNS查询消息字节数据
            max_retries (int): 最大重试次数，包含首次尝试
                               默认为2，表示最多尝试3次(1次初始+2次重试)
            retry_delay (int/float): 重试间隔时间(秒)，默认为1秒

        Returns:
            bytes or None: 上游服务器返回的DNS响应字节数据；若所有尝试失败则返回None

        Note:
            - UDP套接字超时时间固定为5秒，符合DNS协议推荐值
            - 最大响应长度限制为512字节(UDP协议标准限制)
            - 异常情况下会记录错误日志并立即返回None，不进行重试
        """
        retries = 0
        # 重试循环：最多尝试max_retries+1次(包含初始尝试)
        while retries <= max_retries:
            try:
                # 创建UDP套接字(AF_INET: IPv4, SOCK_DGRAM: UDP)
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # 设置SO_REUSEADDR选项允许端口重用，避免连接关闭后端口占用
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(5)  # 设置5秒超时，防止无限期等待
                self.logger.debug(f"转发查询至上游服务器 {self.upstream_server}")
                # 发送DNS查询数据到上游服务器
                sock.sendto(query_data, self.upstream_server)
                try:
                    # 接收响应(最大512字节，DNS UDP消息标准长度)
                    response, _ = sock.recvfrom(512)
                    self.logger.debug(f"从上游服务器接收响应 (大小: {len(response)} 字节)")
                    sock.close()
                    return response
                except socket.timeout:
                    # 处理接收超时情况
                    self.logger.warning(f"上游DNS服务器超时，正在重试 {retries + 1}/{max_retries + 1}")
                    retries += 1
                    if retries <= max_retries:
                        # 重试前等待指定时间，避免网络拥塞
                        time.sleep(retry_delay)
                        self.logger.debug(f"重试前等待 {retry_delay}秒 (重试次数: {retries})")
                    sock.close()
            except Exception as e:
                # 捕获其他异常(如网络错误)并记录
                self.logger.error(f"转发查询时发生错误: {e}")
                return None
        # 所有重试尝试失败
        self.logger.error(f"所有 {max_retries + 1} 次尝试均失败")
        return None