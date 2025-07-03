# DNS本地服务器项目文档

## 项目概述
本项目是一个功能完善的本地DNS服务器，支持自定义域名解析规则、DNS缓存、上游服务器转发和日志记录。可用于网络调试、广告屏蔽、本地开发环境配置等场景，提供高效、可控的域名解析服务。

## 系统架构
![系统架构](https://i.imgur.com/architecture.png)（注：实际部署时请替换为架构图）

### 核心组件
1. **DNS服务器核心**（dns_server.py）：处理客户端DNS请求，协调缓存、数据库和转发器
2. **DNS转发器**（dns_relay.py）：与上游DNS服务器通信，处理本地无法解析的请求
3. **本地数据库**（dns_db.py）：存储自定义域名解析规则和黑名单
4. **DNS缓存**（dns_cache.py）：缓存解析结果，提高重复查询响应速度
5. **日志系统**（logger.py）：记录系统运行状态和请求详情
6. **主程序入口**（main.py）：协调各组件初始化和服务启动

### 组件交互流程
```
客户端请求 → DNS服务器 → 本地数据库查询 → 缓存查询 → 转发器 → 上游DNS
  ↑                                                               ↓
  └────────────────────────── 响应客户端 ───────────────────────────┘
```

## 工作流程
1. **请求接收**：服务器监听指定端口（默认53）的UDP DNS请求
2. **查询处理**：
   - 优先检查缓存，若命中且未过期则直接返回结果
   - 未命中则查询本地数据库，检查是否有自定义解析规则或黑名单
   - 本地无匹配时，通过转发器向上游DNS服务器请求
3. **响应构建**：根据查询结果构建DNS响应报文并返回给客户端
4. **结果缓存**：将新解析结果存入缓存，以便后续快速查询
5. **日志记录**：记录所有请求和响应详情，支持不同级别日志输出

## 文件说明

### 配置与数据文件
- **config.json**：系统配置文件
  ```json
  {
    "local_port": 53,          // 本地DNS服务端口
    "local_ip": "0.0.0.0",    // 监听IP地址
    "log_file": "dns_server.log", // 默认日志文件
    "database_file": "database.txt", // 本地数据库文件
    "upstream_dns": {
      "ip": "8.8.8.8",       // 上游DNS服务器IP
      "port": 53              // 上游DNS服务器端口
    },
    "cache_ttl": 3600         // 默认缓存过期时间(秒)
  }
  ```

- **database.txt**：本地域名规则数据库
  格式：`域名 类型 IP地址/黑名单标记`
  示例：
  ```
  example.com A 192.168.1.100
  ads.example.com A blackhole
  test.com CNAME www.example.com
  ```

- **id_conversion_table.txt**：内部ID转换表（保留功能）

### 核心代码文件
- **main.py**：程序入口
- **dns_server.py**：DNS服务器主逻辑
- **dns_relay.py**：DNS转发器实现
- **dns_db.py**：本地数据库管理
- **dns_cache.py**：DNS缓存实现
- **dns_message.py**：DNS报文解析与构建
- **logger.py**：日志系统实现

### 测试文件
- **tests/**：包含各模块的单元测试

## 执行流程详解
### 启动流程（python main.py）
1. **配置加载**（main.py:25-38）
   ```python
   with open('config.json', 'r') as f:
       config = json.load(f)
   ```
   - 加载配置文件，处理`FileNotFoundError`和`JSONDecodeError`异常
   - 若配置文件缺失或格式错误，抛出明确错误信息

2. **命令行参数解析**（main.py:40-45）
   ```python
   parser = argparse.ArgumentParser(description='DNS Server with logging options')
   parser.add_argument('-d', action='store_true', help='Enable INFO level logging')
   parser.add_argument('-dd', action='store_true', help='Enable DEBUG level logging')
   args = parser.parse_args()
   ```
   - 支持`-d`（INFO级别日志）和`-dd`（DEBUG级别日志）参数
   - 命令行参数优先级高于配置文件设置

3. **路径处理**（main.py:47-48）
   ```python
   project_root = Path(__file__).parent.absolute()
   ```
   - 计算项目根目录，避免相对路径依赖问题

4. **参数提取**（main.py:50-56）
   - 从配置中提取本地端口、数据库路径、上游DNS等核心参数
   - 处理本地IP地址的默认值（未配置时自动获取主机IP）

5. **日志系统初始化**（main.py:68-70）
   ```python
   logger = Logger(log_level, log_file)
   logger.info(f"Starting DNS server on {local_ip}:{local_port}")
   ```
   - **必须优先初始化**，确保其他组件可正常记录日志
   - 根据命令行参数选择日志级别和输出文件

6. **本地数据库加载**（main.py:73-76）
   ```python
   db = LocalDNSDatabase(database_file, logger)
   db.load()
   ```
   - 加载自定义域名解析规则和黑名单
   - 数据库加载失败将导致自定义规则无法生效

7. **DNS转发器初始化**（main.py:79）
   ```python
   relay = DNSRelay(local_ip, local_port, upstream_server, logger)
   ```
   - 创建与上游DNS服务器通信的转发器实例

8. **DNS服务器启动**（main.py:82-87）
   ```python
   server = DNSServer(config=config, logger=logger)
   server.start()
   ```
   - 创建服务器实例并启动服务
   - 开始监听指定端口的DNS请求

### 请求处理流程（当客户端发送DNS查询时）
1. **请求接收**（dns_server.py:DNSServer.start()）
   ```python
   sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
   sock.bind((self.local_ip, self.local_port))
   while True:
       data, addr = sock.recvfrom(512)
       self.handle_query(data, addr)
   ```
   - 创建UDP套接字并绑定到配置的IP和端口
   - 无限循环接收客户端请求并调用`handle_query`处理

2. **请求解析**（dns_server.py:DNSServer.handle_query()）
   - 调用`dns_message.parse_dns_query(data)`解析请求报文
   - 提取查询域名、类型和类别

3. **缓存查询**（dns_server.py:DNSServer.handle_query()）
   ```python
   cached_response = self.cache.get(domain, qtype)
   if cached_response and not self.cache.is_expired(domain, qtype):
       self._send_response(addr, cached_response)
       return
   ```
   - 检查缓存中是否有未过期的记录
   - 若命中缓存则直接返回结果，不进行后续处理

4. **本地数据库查询**（dns_server.py:DNSServer.handle_query()）
   ```python
   result = self.db.query(domain, qtype)
   if result:
       response = self._build_response(data, result)
       self._send_response(addr, response)
       self.cache.set(domain, qtype, response)
       return
   ```
   - 查询本地数据库中的自定义解析规则
   - 若找到匹配规则，构建响应并缓存结果

5. **上游服务器转发**（dns_server.py:DNSServer.handle_query()）
   ```python
   response = self.relay.forward_query(data)
   if response:
       self._send_response(addr, response)
       self.cache.set(domain, qtype, response)
   ```
   - 调用转发器向上游DNS服务器请求
   - 获取响应后返回给客户端并缓存结果

## 重要功能逻辑详解

### 1. DNS缓存机制（dns_cache.py）
- **实现类**：`DNSCache`
- **核心方法**：
  - `get(domain, qtype)`：查询缓存
  - `set(domain, qtype, response)`：存储缓存
  - `is_expired(domain, qtype)`：检查缓存是否过期
  - `cleanup()`：定期清理过期缓存
- **缓存策略**：
  - 基于TTL（生存时间）的过期机制
  - 采用LRU（最近最少使用）淘汰策略
  - 独立线程定期清理过期缓存

### 2. 本地数据库查询（dns_db.py）
- **实现类**：`LocalDNSDatabase`
- **核心方法**：
  - `load()`：加载数据库文件
  - `query(domain, qtype)`：查询域名规则
  - `reload()`：重新加载数据库（支持运行时更新）
- **规则匹配优先级**：
  1. 完全匹配（如`www.example.com`）
  2. 通配符匹配（如`*.example.com`）
  3. 泛域名匹配（如`example.com`）
- **黑名单处理**：返回空响应或指定的拦截IP

### 3. DNS转发逻辑（dns_relay.py）
- **实现类**：`DNSRelay`
- **核心方法**：`forward_query(data)`
- **转发策略**：
  - 支持UDP协议的DNS查询转发
  - 实现请求超时重传机制（默认重试3次）
  - 可配置的超时时间（默认5秒）
  - 异常捕获和日志记录

### 4. 日志系统（logger.py）
- **实现类**：`Logger`
- **日志级别**：DEBUG（详细调试）、INFO（运行信息）、WARNING（警告）、ERROR（错误）
- **功能特点**：
  - 同时输出到控制台和文件
  - 日志文件自动轮转（按大小）
  - 支持不同级别日志输出到不同文件
  - 详细的请求日志包含时间、客户端IP、域名、类型、响应时间等

## 使用方法
### 基本用法
1. 配置`config.json`文件，设置端口、上游DNS等参数
2. 在`database.txt`中添加自定义域名规则
3. 启动服务器：
   ```bash
   # 默认启动（INFO级别日志）
   python main.py
   
   # 详细日志模式
   python main.py -d
   
   # 调试日志模式
   python main.py -dd
   ```
4. 配置客户端DNS为服务器IP地址

### 自定义域名解析
在`database.txt`中添加记录，格式如下：
```
# 格式：域名 类型 IP地址
www.example.com A 192.168.1.100

# 黑名单（返回空响应）
ads.example.com A blackhole

# CNAME记录
test.example.com CNAME www.example.com
```

## 故障排除
1. **启动失败**：检查端口是否被占用，配置文件格式是否正确
2. **解析异常**：查看日志文件（默认在logs/目录），检查错误信息
3. **缓存问题**：可删除缓存文件或重启服务强制刷新缓存
4. **性能问题**：启用DEBUG日志，检查慢查询和频繁未命中的域名

## 扩展建议
1. 添加TCP协议支持（当前仅支持UDP）
2. 实现DNSSEC验证功能
3. 添加Web管理界面
4. 支持多上游DNS服务器和负载均衡
5. 实现更复杂的缓存策略

## 许可证
[MIT License](https://opensource.org/licenses/MIT)