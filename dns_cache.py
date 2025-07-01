import time
import threading

class DNSCache:
    def __init__(self, max_size=1000):
        self.cache = {}
        self.lock = threading.Lock()
        self.max_size = max_size
        self.record_order = []  # 用于FIFO淘汰策略
        
    def add_record(self, domain, ip, ttl, record_type):
        """添加域名解析记录到缓存
        
        Args:
            domain (str): 域名
            ip (str): IP地址
            ttl (int): 生存时间(秒)
            record_type (int): 记录类型(1=A记录, 28=AAAA记录)
        """
        with self.lock:
            current_time = time.time()
            expiration_time = current_time + ttl
            key = (domain, record_type)
            if key not in self.cache:
                # 如果缓存达到最大大小，删除最旧的记录
                if len(self.cache) >= self.max_size:
                    oldest_key = self.record_order.pop(0)
                    del self.cache[oldest_key]
                self.cache[key] = {
                    'ips': [],
                    'expiration': expiration_time
                }
                self.record_order.append(key)
            # 只添加新的IP地址
            if ip not in [record['ip'] for record in self.cache[key]['ips']]:
                self.cache[key]['ips'].append({
                    'ip': ip,
                    'expiration': expiration_time
                })
            # 更新过期时间为最新的IP过期时间
            if expiration_time > self.cache[key]['expiration']:
                self.cache[key]['expiration'] = expiration_time
        
    def get_record(self, domain, record_type):
        """从缓存获取域名解析记录
        
        Args:
            domain (str): 域名
            record_type (int): 记录类型(1=A记录, 28=AAAA记录)
        
        Returns:
            list: 解析的IP地址列表，如果缓存不存在或已过期则返回None
        """
        with self.lock:
            current_time = time.time()
            key = (domain, record_type)
            record = self.cache.get(key)
            if not record:
                return None
            
            # 检查过期时间
            if current_time >= record['expiration']:
                del self.cache[key]
                return None
            
            # 过滤过期的IP并保留有效IP
            valid_ips = []
            for ip_record in record['ips']:
                if current_time < ip_record['expiration']:
                    valid_ips.append(ip_record['ip'])
                
            # 如果所有IP都过期了，删除整个记录
            if not valid_ips:
                del self.cache[key]
                return None
            
            return valid_ips
        
    def clear_expired(self):
        """清除所有过期的缓存记录和过期的IP条目"""
        with self.lock:
            current_time = time.time()
            domains_to_remove = []
            
            for key, record in self.cache.items():
                # 检查过期时间
                if current_time >= record['expiration']:
                    domains_to_remove.append(key)
                    continue
                
                # 过滤过期的IP
                valid_ips = [ip_record for ip_record in record['ips'] if current_time < ip_record['expiration']]
                
                # 如果所有IP都过期，标记删除
                if not valid_ips:
                    domains_to_remove.append(key)
                else:
                    record['ips'] = valid_ips
                    # 更新过期时间为剩余IP中最远的过期时间
                    record['expiration'] = max(ip_record['expiration'] for ip_record in valid_ips)
            
            # 删除标记的记录
            for key in domains_to_remove:
                del self.cache[key]
        
    def __len__(self):
        """返回缓存中的记录数量"""
        with self.lock:
            return len(self.cache)