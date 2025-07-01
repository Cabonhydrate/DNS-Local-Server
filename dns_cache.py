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
        current_time = time.time()
        expiration_time = current_time + ttl
        if domain not in self.cache:
            self.cache[domain] = {
                'ips': [],
                'expiration': expiration_time
            }
        # 只添加新的IP地址
        if ip not in [record['ip'] for record in self.cache[domain]['ips']]:
            self.cache[domain]['ips'].append({
                'ip': ip,
                'expiration': expiration_time
            })
        # 更新域名级别的过期时间为最新的IP过期时间
        if expiration_time > self.cache[domain]['expiration']:
            self.cache[domain]['expiration'] = expiration_time
        
    def get_record(self, domain):
        """从缓存获取域名解析记录
        
        Args:
            domain (str): 域名
        
        Returns:
            list: 解析的IP地址列表，如果缓存不存在或已过期则返回None
        """
        current_time = time.time()
        record = self.cache.get(domain)
        if not record:
            return None
        
        # 检查域名级别的过期时间
        if current_time >= record['expiration']:
            del self.cache[domain]
            return None
        
        # 过滤过期的IP并保留有效IP
        valid_ips = []
        for ip_record in record['ips']:
            if current_time < ip_record['expiration']:
                valid_ips.append(ip_record['ip'])
            
        # 如果所有IP都过期了，删除整个记录
        if not valid_ips:
            del self.cache[domain]
            return None
        
        return valid_ips
        
    def clear_expired(self):
        """清除所有过期的缓存记录和过期的IP条目"""
        current_time = time.time()
        domains_to_remove = []
        
        for domain, record in self.cache.items():
            # 检查域名级别的过期
            if current_time >= record['expiration']:
                domains_to_remove.append(domain)
                continue
            
            # 过滤过期的IP
            valid_ips = [ip_record for ip_record in record['ips'] if current_time < ip_record['expiration']]
            
            # 如果所有IP都过期，标记域名删除
            if not valid_ips:
                domains_to_remove.append(domain)
            else:
                record['ips'] = valid_ips
                # 更新域名过期时间为剩余IP中最远的过期时间
                record['expiration'] = max(ip_record['expiration'] for ip_record in valid_ips)
        
        # 删除标记的域名
        for domain in domains_to_remove:
            del self.cache[domain]
        
    def __len__(self):
        """返回缓存中的记录数量"""
        return len(self.cache)