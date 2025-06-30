import socket
import struct

class DNSRelay:
    def __init__(self, local_ip, local_port, upstream_server):
        self.local_ip = local_ip
        self.local_port = local_port
        self.upstream_server = upstream_server

    def forward_query(self, query_data):
        try:
            # 创建UDP套接字
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)  # 添加5秒超时
            sock.sendto(query_data, self.upstream_server)
            try:
                response, _ = sock.recvfrom(512)
            except socket.timeout:
                print("Upstream DNS server timeout")
                return None
            sock.close()
            return response
        except Exception as e:
            print(f"Error forwarding query: {e}")
            return None