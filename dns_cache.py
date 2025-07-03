import time
import threading

class DNSCache:
    """DNS缓存管理类

    该类实现了DNS解析记录的缓存功能，支持添加记录、查询记录和清除过期记录。
    采用FIFO(先进先出)淘汰策略管理缓存大小，确保缓存不会无限增长。
    使用线程锁保证多线程环境下的安全访问。
    """
    def __init__(self, max_size=1000):
        """初始化DNSCache实例

        Args:
            max_size (int): 缓存的最大记录数，超过此数量时将使用FIFO策略淘汰旧记录
        """
        self.cache = {}  # 存储DNS缓存记录，键为(domain, record_type)元组，值为包含IP列表和过期时间的字典
        self.lock = threading.Lock()  # 线程锁，确保多线程安全
        self.max_size = max_size  # 缓存最大记录数
        self.record_order = []  # 记录插入顺序，用于FIFO淘汰策略
        
    def add_record(self, domain, ip, ttl, record_type):
        """添加域名解析记录到缓存

        将域名解析记录存储到缓存中，并处理缓存大小限制和过期时间。
        如果相同域名和记录类型的记录已存在，则只添加新的IP地址，并更新过期时间。

        Args:
            domain (str): 域名，例如 'www.example.com'
            ip (str): IP地址，例如 '192.168.1.1' 或 '2001:db8::1'
            ttl (int): 生存时间(秒)，记录在缓存中保留的时间
            record_type (int): 记录类型，1表示A记录(IPv4)，28表示AAAA记录(IPv6)
        """
        with self.lock:  # 获取线程锁，确保多线程安全
            current_time = time.time()  # 获取当前时间戳
            expiration_time = current_time + ttl  # 计算记录过期时间
            key = (domain, record_type)  # 构建缓存键，由域名和记录类型组成

            # 如果记录不存在，则创建新记录
            if key not in self.cache:
                # 检查缓存是否已满，如果已满则删除最旧的记录
                if len(self.cache) >= self.max_size:
                    oldest_key = self.record_order.pop(0)  # 从记录顺序列表中移除最旧的键
                    del self.cache[oldest_key]  # 从缓存中删除最旧的记录
                
                # 初始化新的缓存记录
                self.cache[key] = {
                    'ips': [],  # 存储该域名和记录类型对应的IP列表
                    'expiration': expiration_time  # 记录的过期时间
                }
                self.record_order.append(key)  # 将新记录添加到顺序列表中

            # 检查IP是否已存在，如果不存在则添加
            existing_ips = [record['ip'] for record in self.cache[key]['ips']]
            if ip not in existing_ips:
                self.cache[key]['ips'].append({
                    'ip': ip,
                    'expiration': expiration_time
                })

            # 更新记录的过期时间为最新IP的过期时间
            if expiration_time > self.cache[key]['expiration']:
                self.cache[key]['expiration'] = expiration_time
        
    def get_record(self, domain, record_type):
        """从缓存获取域名解析记录

        根据域名和记录类型查询缓存，如果记录存在且未过期，则返回有效的IP地址列表。
        如果记录不存在、已过期或所有IP都已过期，则返回None。

        Args:
            domain (str): 要查询的域名
            record_type (int): 记录类型，1表示A记录(IPv4)，28表示AAAA记录(IPv6)

        Returns:
            list: 有效的IP地址列表，如果记录不存在或已过期则返回None
        """
        with self.lock:  # 获取线程锁，确保多线程安全
            current_time = time.time()  # 获取当前时间戳
            key = (domain, record_type)  # 构建缓存键
            record = self.cache.get(key)  # 从缓存中获取记录

            # 如果记录不存在，返回None
            if not record:
                return None
            
            # 检查记录是否已过期，如果已过期则删除记录并返回None
            if current_time >= record['expiration']:
                del self.cache[key]
                return None
            
            # 过滤过期的IP地址，只保留有效的IP
            valid_ips = []
            for ip_record in record['ips']:
                if current_time < ip_record['expiration']:
                    valid_ips.append(ip_record['ip'])
                
            # 如果所有IP都已过期，删除记录并返回None
            if not valid_ips:
                del self.cache[key]
                return None
            
            return valid_ips  # 返回有效的IP地址列表
        
    def clear_expired(self):
        """清除所有过期的缓存记录和过期的IP条目

        遍历缓存中的所有记录，删除已过期的记录和记录中已过期的IP地址。
        如果一个记录中的所有IP都已过期，则删除整个记录。
        对于部分IP过期的记录，更新记录的过期时间为剩余IP中最远的过期时间。
        """
        with self.lock:  # 获取线程锁，确保多线程安全
            current_time = time.time()  # 获取当前时间戳
            domains_to_remove = []  # 存储需要删除的记录键
            
            # 遍历所有缓存记录
            for key, record in self.cache.items():
                # 检查记录是否已过期
                if current_time >= record['expiration']:
                    domains_to_remove.append(key)  # 标记为需要删除
                    continue
                
                # 过滤过期的IP地址
                valid_ips = [ip_record for ip_record in record['ips'] if current_time < ip_record['expiration']]
                
                # 如果所有IP都已过期，标记记录为需要删除
                if not valid_ips:
                    domains_to_remove.append(key)
                else:
                    # 更新记录中的IP列表为有效IP
                    record['ips'] = valid_ips
                    # 更新记录的过期时间为剩余IP中最远的过期时间
                    record['expiration'] = max(ip_record['expiration'] for ip_record in valid_ips)
            
            # 删除所有标记为需要删除的记录
            for key in domains_to_remove:
                del self.cache[key]
        
    def __len__(self):
        """返回缓存中的记录数量

        Returns:
            int: 当前缓存中的记录总数
        """
        with self.lock:  # 获取线程锁，确保多线程安全
            return len(self.cache)  # 返回缓存记录的数量