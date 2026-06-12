=============================================
Task2 程序运行说明
=============================================

1. 开发与运行环境
   开发语言：Python
   运行系统：
      客户端(Client)：Windows 主机系统（Host OS）
      服务端(Server)：Ubuntu 虚拟机系统（Guest OS）
      虚拟机软件：VMware Workstation
      网络模式：NAT 模式
      抓包网卡：VMnet8（用于 Wireshark 抓包验证）
   依赖：Python 标准库（socket、struct、random、time、threading 等），以及第三方库 pandas（用于 RTT 统计）

2. 程序文件清单
   udpserver.py          UDP 服务端程序
   udpclient.py          UDP 客户端程序
   server_run_log.txt    服务端自动生成的运行日志
   client_run_log.txt    客户端自动生成的运行日志
   udp_packet_capture.doc  说明文档

3. 运行规则与参数说明
   3.1 启动顺序：必须先运行服务端，再运行客户端。
   3.2 服务端启动方式
       格式：python3 udpserver.py <端口>
       示例：python3 udpserver.py 9999
       服务端监听指定端口，采用多线程模型处理每个客户端报文。
   3.3 客户端启动方式（命令行传参）
       格式：python udpclient.py <服务端IP> <服务端端口> --seed <种子>
       参数解释：
          服务端IP   ：虚拟机的 IP 地址（如 192.168.169.128）
          服务端端口 ：双方约定一致的端口号（如 9999）
          --seed     ：随机种子（可选，用于复现数据包大小生成）
       示例：python udpclient.py 192.168.169.128 9999 --seed 123

4. 核心功能流程
   4.1 连接建立：客户端发送 Type=1 连接请求（含 StudentID 字段），服务端验证后回复 Type=2 连接确认。
   4.2 数据传输：采用 GBN 协议，固定发送窗口 400 字节，每个数据包大小 40~80 字节随机。
   4.3 丢包模拟：服务端以 20% 概率随机丢弃数据包，以15%概率随机损坏包，客户端超时（300ms）后重传窗口内所有未确认包。
   4.4 确认机制：服务端支持累积确认，客户端收到确认后计算 RTT。
   4.5 结果输出：终端打印每个数据包的发送、确认、重传信息（含字节边界）；最终输出丢包率、RTT 统计量。
   4.6 日志记录：程序全程自动生成 `run_log.txt`，记录所有收发、超时、重传事件及时间戳。

5. 报文格式（自定义应用层协议，固定 10 字节头部）
   5.1 字段顺序（网络字节序）：Type(2B) + StudentID(2B) + Seq(2B) + Ack(2B) + Length(2B)
   5.2 报文类型：
       Type=1 : 连接请求（Client→Server）
       Type=2 : 连接确认（Server→Client）
       Type=3 : 数据报文（Client→Server）
       Type=4 : 确认报文（Server→Client）
   5.3 StudentID 计算：学号后 4 位（十进制）与 0x5A3C 异或。

6. 补充说明
   6.1 GBN 参数：发送窗口固定 400 字节，超时时间 300ms，总数据包数 30 个。
   6.2 丢包率：服务端自定 20% 丢包率，15%的包损坏率，客户端统计丢包率 = (总发送 - 成功接收) / 总发送 × 100%。
   6.3 RTT 统计：使用 pandas 计算最大值、最小值、平均值、标准差。
   6.4 日志与抓包：日志时间戳与 Wireshark 中 `Time of Day` 格式的时间戳相互印证。
   6.5 异常处理：对网络超时、报文解析异常等进行了基础容错处理。
