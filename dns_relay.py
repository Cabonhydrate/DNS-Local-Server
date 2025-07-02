import socket
import struct
import time

class DNSRelay:
    def __init__(self, local_ip, local_port, upstream_server, logger):
        self.local_ip = local_ip
        self.local_port = local_port
        self.upstream_server = upstream_server
        self.logger = logger

    def forward_query(self, query_data, max_retries=2, retry_delay=1):
        retries = 0
        while retries <= max_retries:
            try:
                # 创建UDP套接字
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(5)  # 添加5秒超时
                self.logger.debug(f"Forwarding query to upstream server {self.upstream_server}")
                sock.sendto(query_data, self.upstream_server)
                try:
                    response, _ = sock.recvfrom(512)
                    self.logger.debug(f"Received response from upstream server (size: {len(response)} bytes)")
                    sock.close()
                    return response
                except socket.timeout:
                    self.logger.warning(f"Upstream DNS server timeout, retrying {retries + 1}/{max_retries + 1}")
                    retries += 1
                    if retries <= max_retries:
                        time.sleep(retry_delay)
                        self.logger.debug(f"Waiting {retry_delay}s before retry {retries}")
                    sock.close()
            except Exception as e:
                self.logger.error(f"Error forwarding query: {e}")
                return None
        self.logger.error(f"All {max_retries + 1} attempts failed")
        return None