import os

class LocalDNSDatabase:
    def __init__(self, db_file):
        self.db_file = db_file
        self.whitelist = {}
        self.blacklist = {}
        self.id_mapping = {}  # 新增ID映射字典

    def load(self):
        with open(self.db_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    domain = parts[0]
                    ip = parts[1]
                    if ip == '0.0.0.0':
                        self.blacklist[domain] = ip
                    else:
                        self.whitelist[domain] = ip
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
        return self.whitelist.get(domain)

    # 新增获取内部ID的方法
    def get_internal_id(self, domain):
        """获取域名对应的内部ID"""
        return self.id_mapping.get(domain)