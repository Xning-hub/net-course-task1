=============================================
Task1 程序运行说明
=============================================

1. 开发与运行环境
   开发语言：Python 
   运行系统：
      客户端(Client)：Windows 主机系统（Host OS）
      服务端(Server)：Ubuntu 虚拟机系统（Guest OS）
      虚拟机软件：VMware Workstation
      网络模式：NAT 模式
      抓包网卡：VMnet8（用于 Wireshark 抓包验证）
   依赖：Python 标准库（socket、struct、random、time、threading 等，无第三方库依赖）

2. 程序文件清单
   reversetcpserver.py          TCP 服务端程序
   reversetcpclient.py          TCP 客户端程序
   server_run_log.txt           服务端自动生成的运行日志
   client_run_log_20260612_092014.txt  客户端1 自动生成的运行日志（时间戳区分）
   client_run_log_20260612_091945.txt  客户端2 自动生成的运行日志（时间戳区分）
   test.txt                     待传输的原始 ASCII 英文文本文件
   reversed_output.txt          客户端最终生成的全局反转文本文件

3. 运行规则与参数说明
   3.1 启动顺序：必须先运行服务端，再运行客户端。
   3.2 服务端启动方式
       格式：python reversetcpserver.py <端口>
       示例：python reversetcpserver.py 8888
       服务端监听指定端口，支持多线程并发处理多个客户端连接。
   3.3 客户端启动方式（命令行传参）
       格式：python reversetcpclient.py <服务端IP> <服务端端口> <文件路径> <Lmin> <Lmax> --seed <种子>
       参数解释：
          服务端IP   ：虚拟机的 IP 地址（如 192.168.169.128）
          服务端端口 ：双方约定一致的端口号（如 8888）
          文件路径   ：待传输的 ASCII 文件路径（如 test.txt）
          Lmin       ：单块数据最小长度（如 50）
          Lmax       ：单块数据最大长度（不包含，如 100）
          --seed     ：随机种子（必选，用于复现分块结果，如 42）
       示例：python reversetcpclient.py 192.168.169.128 8888 test.txt 50 100 --seed 42

4. 核心功能流程
   4.1 预处理：客户端读取本地原始文件，按照 `[Lmin, Lmax)` 区间随机生成分块长度，计算总块数 N。
   4.2 初始化阶段：客户端发送 Type=1 的 Initialization 报文，携带总分块数 N。
   4.3 协商阶段：服务端回复 Type=2 的 Agree 报文，确认建立交互。
   4.4 循环交互：客户端逐块发送 Type=3 reverseRequest 报文；服务端反转数据后，返回 Type=4 reverseAnswer 报文。
   4.5 结果输出：客户端每接收一块反转数据，终端打印“第 x 块：反转文本”；全部传输完成后，生成 `reversed_output.txt`（原始文件的整体反转）。
   4.6 日志记录：程序全程自动生成 `run_log.txt`，记录所有报文收发事件与精确到毫秒的时间戳。

5. 报文格式（自定义应用层协议）
   5.1 Initialization 报文（客户端→服务端，Type=1）
       字段：Type(2B) + 总分块数 N(4B)
   5.2 Agree 报文（服务端→客户端，Type=2）
       字段：Type(2B)
   5.3 reverseRequest 报文（客户端→服务端，Type=3）
       字段：Type(2B) + 数据长度 Length(4B) + 原始数据 Data
   5.4 reverseAnswer 报文（服务端→客户端，Type=4）
       字段：Type(2B) + 反转数据长度 Length(4B) + 反转数据 reverseData

6. 补充说明
   6.1 分块规则：除最后一块外，所有数据块长度在 `[Lmin, Lmax)` 内随机；最后一块为剩余全部数据。
   6.2 并发能力：服务端采用多线程模型（`threading.Thread`），可同时处理 2 个及以上客户端请求。日志中可见不同线程 ID。
   6.3 并发验证：同时运行两个客户端（例如 09:19:45 和 09:20:14 两个不同时间戳的日志），服务端日志显示它们由不同线程处理。
   6.4 日志与抓包：日志时间戳与 Wireshark 中显示为 `Time of Day` 格式的时间戳相互印证。
   6.5 异常处理：对文件读取、网络断开、报文解析异常进行了基础容错处理。
