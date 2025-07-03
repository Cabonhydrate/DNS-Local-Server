import os

class LocalDNSDatabase:
    """本地DNS数据库管理类

    该类负责加载和管理本地DNS数据库，包括白名单(IPv4和IPv6)、黑名单和ID映射功能。
    支持从文件加载DNS记录和ID转换表，并提供查询接口。
    """
    def __init__(self, db_file, logger):
        """初始化LocalDNSDatabase实例

        Args:
            db_file (str): DNS数据库文件路径
            logger (Logger): 日志记录器实例，用于记录警告和错误信息
        """
        self.db_file = db_file  # DNS数据库文件路径
        self.whitelist_ipv4 = {}  # 存储IPv4白名单记录，键为域名，值为IP地址或地址列表
        self.whitelist_ipv6 = {}  # 存储IPv6白名单记录，键为域名，值为IP地址或地址列表
        self.blacklist = {}       # 存储黑名单记录，键为域名，值为'0.0.0.0'
        self.id_mapping = {}  # 存储域名到内部ID的映射
        self.logger = logger  # 日志记录器

    def load(self):
        """从DNS数据库文件加载记录

        解析数据库文件，提取域名和对应的IP地址，分别存储到IPv4白名单、IPv6白名单或黑名单中。
        文件格式要求：每行一条记录，域名与IP地址之间用空格分隔，多个IP可用空格或逗号分隔。
        如果IP地址包含'0.0.0.0'，该域名将被加入黑名单。
        """
        with open(self.db_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:  # 跳过空行
                    continue
                parts = line.split()
                if len(parts) >= 2:  # 确保至少有域名和一个IP
                    domain = parts[0].lower()  # 统一转换为小写域名
                    # 解析IP地址，支持逗号和空格分隔的多种格式
                    ips = []
                    for part in parts[1:]:
                        ips.extend(part.split(','))
                    # 过滤空字符串并去重
                    ips = list(filter(None, ips))
                    ips = list(set(ips))  # 移除重复IP
                    
                    # 检查是否为黑名单记录
                    if '0.0.0.0' in ips:
                        self.blacklist[domain] = '0.0.0.0'
                    else:
                        # 分离IPv4和IPv6地址
                        ipv4_ips = [ip for ip in ips if ':' not in ip]
                        ipv6_ips = [ip for ip in ips if ':' in ip]
                        
                        # 存储IPv4地址（单个IP存为字符串，多个存为列表）
                        if ipv4_ips:
                            self.whitelist_ipv4[domain] = ipv4_ips if len(ipv4_ips) > 1 else ipv4_ips[0]
                        # 存储IPv6地址（单个IP存为字符串，多个存为列表）
                        if ipv6_ips:
                            self.whitelist_ipv6[domain] = ipv6_ips if len(ipv6_ips) > 1 else ipv6_ips[0]
        # 新增ID转换表加载
        self.load_id_conversion()

    def load_id_conversion(self):
        """加载域名到内部ID的转换表

        核心功能：从外部文件加载域名与内部系统ID的映射关系，用于实现DNS请求的身份标识与权限控制
        设计目的：通过独立配置文件实现域名ID映射，避免硬编码，提高系统灵活性和可维护性

        工作流程：
        1. 构建配置文件路径：自动定位与DNS数据库同目录下的'id_conversion_table.txt'
        2. 文件解析规则：
           - 忽略空行和以'#'开头的注释行
           - 有效记录格式：域名(空格)内部ID（例如：'example.com 1001'）
           - 域名自动转换为小写，确保查询时的大小写无关性
        3. 数据验证：
           - 严格检查每行是否包含且仅包含两个字段
           - 内部ID必须为整数，非整数ID会记录警告并跳过
        4. 异常处理策略：
           - 文件不存在：记录警告并禁用ID映射功能（不抛出异常）
           - 其他错误（权限问题/格式错误）：记录详细错误信息并安全退出

        数据存储：加载成功的映射关系存储在实例变量self.id_mapping（字典类型）中
        使用场景：在DNS查询处理流程中，通过域名快速查找对应的内部系统ID，用于访问控制和请求跟踪
        """
        try:
            # 构建ID转换表文件的绝对路径
            table_path = os.path.join(os.path.dirname(os.path.abspath(self.db_file)), 'id_conversion_table.txt')
            with open(table_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释行和空行
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split()
                    if len(parts) == 2:  # 确保格式正确
                        domain, internal_id = parts
                        domain = domain.lower()  # 统一转换为小写域名
                        # 尝试转换为整数ID
                        try:
                            self.id_mapping[domain] = int(internal_id)
                        except ValueError:
                            self.logger.warning(f"警告: {domain} 的ID {internal_id} 不是有效的整数")
        except FileNotFoundError:
            self.logger.warning("ID转换表文件 id_conversion_table.txt 未找到，ID映射功能已禁用")
            return
        except Exception as e:
            self.logger.error(f"加载ID转换表时发生错误: {str(e)}")
            return

    def is_in_blacklist(self, domain):
        """检查域名是否在黑名单中

        Args:
            domain (str): 要检查的域名

        Returns:
            bool: 如果域名在黑名单中则返回True，否则返回False
        """
        return domain.lower() in self.blacklist  # 统一转为小写域名进行查询

    def get_ip(self, domain):
        """获取域名对应的IP地址（兼容旧接口，IPv4优先）

        优先返回IPv4地址，如果不存在则返回IPv6地址。
        兼容旧接口设计，当只有一个IP时返回字符串，多个IP时返回列表。

        Args:
            domain (str): 要查询的域名

        Returns:
            list or str or None: IP地址列表、单个IP字符串或None（如果域名不存在）
        """
        domain = domain.lower()  # 统一转为小写域名进行查询
        ipv4 = self.whitelist_ipv4.get(domain)
        if ipv4:
            return ipv4
        return self.whitelist_ipv6.get(domain)
    
    def get_ipv4(self, domain):
        """获取域名对应的IPv4地址

        Args:
            domain (str): 要查询的域名

        Returns:
            list or str or None: IPv4地址列表、单个IP字符串或None（如果域名不存在）
        """
        return self.whitelist_ipv4.get(domain.lower())  # 统一转为小写域名进行查询
    
    def get_ipv6(self, domain):
        """获取域名对应的IPv6地址

        Args:
            domain (str): 要查询的域名

        Returns:
            list or str or None: IPv6地址列表、单个IP字符串或None（如果域名不存在）
        """
        return self.whitelist_ipv6.get(domain.lower())  # 统一转为小写域名进行查询

    def get_internal_id(self, domain):
        """获取域名对应的内部ID

        Args:
            domain (str): 要查询的域名

        Returns:
            int or None: 域名对应的内部ID，或None（如果域名不存在映射关系）
        """
        return self.id_mapping.get(domain.lower())  # 统一转为小写域名进行查询