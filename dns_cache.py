import time

class DNSCache:
    def __init__(self):
        self.cache = {}
        
    def add_record(self, domain, ip, ttl):
        """添加域名解析记录到缓存
        
        Args:
            domain (str): 域名
            ip (str): IP地址
            ttl (int): 生存时间(秒)
        """
        expiration_time = time.time() + ttl
        self.cache[domain] = {
            'ip': ip,
            'expiration': expiration_time
        }
        
    def get_record(self, domain):
        """从缓存获取域名解析记录
        
        Args:
            domain (str): 域名
        
        Returns:
            str: 解析的IP地址，如果缓存不存在或已过期则返回None
        """
        record = self.cache.get(domain)
        if not record:
            return None
        
        # 检查记录是否过期
        if time.time() < record['expiration']:
            return record['ip']
        else:
            # 删除过期记录
            del self.cache[domain]
            return None
        
    def clear_expired(self):
        """清除所有过期的缓存记录"""
        current_time = time.time()
        expired_domains = [domain for domain, record in self.cache.items() if record['expiration'] < current_time]
        for domain in expired_domains:
            del self.cache[domain]
        
    def __len__(self):
        """返回缓存中的记录数量"""
        return len(self.cache)