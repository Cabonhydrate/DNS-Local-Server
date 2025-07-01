import os

class LocalDNSDatabase:
    def __init__(self, db_file):
        self.db_file = db_file
        self.whitelist_ipv4 = {}  # 存储IPv4地址
        self.whitelist_ipv6 = {}  # 存储IPv6地址
        self.blacklist = {}
        self.id_mapping = {}  # 新增ID映射字典

    def load(self):
        with open(self.db_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[0]
                    # 解析IP地址，支持逗号和空格分隔
                    ips = []
                    for part in parts[1:]:
                        ips.extend(part.split(','))
                    # 过滤空字符串并去重
                    ips = list(filter(None, ips))
                    ips = list(set(ips))
                    
                    if '0.0.0.0' in ips:
                        self.blacklist[domain] = '0.0.0.0'
                    else:
                        # 分离IPv4和IPv6地址
                        ipv4_ips = [ip for ip in ips if ':' not in ip]
                        ipv6_ips = [ip for ip in ips if ':' in ip]
                        
                        if ipv4_ips:
                            self.whitelist_ipv4[domain] = ipv4_ips if len(ipv4_ips) > 1 else ipv4_ips[0]
                        if ipv6_ips:
                            self.whitelist_ipv6[domain] = ipv6_ips if len(ipv6_ips) > 1 else ipv6_ips[0]
        # 新增ID转换表加载
        self.load_id_conversion()

    def load_id_conversion(self):
        """加载ID转换表"""
        try:
            # 使用绝对路径打开ID转换表文件
            table_path = os.path.join(os.path.dirname(os.path.abspath(self.db_file)), 'id_conversion_table.txt')
            with open(table_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释和空行
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split()
                    if len(parts) == 2:
                        domain, internal_id = parts
                        # 尝试转换为整数ID
                        try:
                            self.id_mapping[domain] = int(internal_id)
                        except ValueError:
                            print(f"警告: {domain} 的ID {internal_id} 不是有效的整数")
        except FileNotFoundError:
            print("警告: ID转换表文件 id_conversion_table.txt 未找到")

    def is_in_blacklist(self, domain):
        return domain in self.blacklist

    def get_ip(self, domain):
        """获取域名对应的IP地址列表(兼容旧接口，IPv4优先)
        
        Returns:
            list or str or None: IP地址列表、单个IP字符串或None
        """
        ipv4 = self.whitelist_ipv4.get(domain)
        if ipv4:
            return ipv4
        return self.whitelist_ipv6.get(domain)
    
    def get_ipv4(self, domain):
        """获取域名对应的IPv4地址列表
        
        Returns:
            list or str or None: IPv4地址列表、单个IP字符串或None
        """
        return self.whitelist_ipv4.get(domain)
    
    def get_ipv6(self, domain):
        """获取域名对应的IPv6地址列表
        
        Returns:
            list or str or None: IPv6地址列表、单个IP字符串或None
        """        
        return self.whitelist_ipv6.get(domain)

    # 新增获取内部ID的方法
    def get_internal_id(self, domain):
        """获取域名对应的内部ID"""
        return self.id_mapping.get(domain)