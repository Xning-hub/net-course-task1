import socket
import struct
import random
import time
import os
import threading
import sys

# 自定义协议常量
TYPE_CONN_REQ = 1    # 连接请求
TYPE_CONN_ACK = 2    # 连接确认
TYPE_DATA = 3        # 数据报文
TYPE_ACK = 4         # 确认报文

STUDENT_ID_MASK = 0x5A3C
LOSS_RATE = 0.2      # 20% 丢包率
CORRUPT_RATE = 0.15  # 15% 包损坏率
LOG_FILE = "server_run_log.txt"

# 日志锁：多线程并发写日志防错乱
LOG_LOCK = threading.Lock()
# 客户端状态字典 + 读写锁：(ip,port) -> (期望序号, 绑定学号)
client_state = {}
state_lock = threading.Lock()

# 日志函数
def log_event(event):
    """毫秒级日志 + 线程锁"""
    now = time.time()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)) + f".{int(now * 1000) % 1000:03d}"
    log_line = f"[{timestamp}] {event}\n"
    LOG_LOCK.acquire()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
    finally:
        LOG_LOCK.release()

# 验证学号是否合法
def validate_student_id(stu_id):
    # 验证 stu_id ^ 0x5A3C 是否为 0-9999 整数
    val = stu_id ^ STUDENT_ID_MASK
    return 0 <= val <= 9999

#服务器处理每个报文的函数，由多线程调用
def handle_client_packet(data, addr, server_sock):
    """子线程：处理单个客户端报文"""
    if len(data) < 10:
        return

    # 首部设计，解析固定10字节头部
    msg_type, stu_id, seq, ack, length = struct.unpack("!HHHHH", data[:10])
    # 校验长度合法性
    if length < 0 or 10 + length > len(data):
        return
    payload = data[10:10+length] if length > 0 else b''

    # 1. 连接请求
    if msg_type == TYPE_CONN_REQ:
        if not validate_student_id(stu_id):
            print(f"来自 {addr} 的连接请求被拒绝：无效 StudentID {stu_id}")
            log_event(f"拒绝连接 {addr}：无效 StudentID")
            return
        print(f"收到连接请求，来自 {addr}，StudentID 验证通过")
        log_event(f"收到连接请求，来自 {addr}，StudentID 验证通过")

        # 初始化该客户端状态
        with state_lock:
            client_state[addr] = (1, stu_id)

        # 回复连接确认
        resp = struct.pack("!HHHHH", TYPE_CONN_ACK, stu_id, 0, 0, 0)
        server_sock.sendto(resp, addr)
        return

    # 2. 数据报文 GBN 处理
    if msg_type == TYPE_DATA:
        # 检查客户端是否已建立连接
        with state_lock:
            if addr not in client_state:
                print(f"客户端 {addr} 未建立连接，丢弃报文")
                log_event(f"客户端 {addr} 未建立连接，丢弃报文")
                return
            expected_seq, bind_stu_id = client_state[addr]

        # 校验学号一致性
        if stu_id != bind_stu_id:
            log_event(f"客户端 {addr} 学号不匹配，丢弃报文")
            return

        # 模拟丢包
        if random.random() < LOSS_RATE:
            print(f"模拟丢包：来自 {addr} seq={seq} 丢弃")
            log_event(f"模拟丢包：来自 {addr} seq={seq}")
            return

        # 模拟包损坏
        if random.random() < CORRUPT_RATE:
            print(f"模拟包损坏：来自 {addr} seq={seq}")
            log_event(f"模拟包损坏：来自 {addr} seq={seq}")
            return

        # 序号正常：按序接收
        if seq == expected_seq:
            print(f"收到数据 seq={seq}, len={length}")
            log_event(f"收到数据 seq={seq}, len={length}")
            # 更新期望序号
            with state_lock:
                client_state[addr] = (expected_seq + 1, bind_stu_id)
            # 累积确认
            ack_pkt = struct.pack("!HHHHH", TYPE_ACK, stu_id, 0, seq, 0)
            server_sock.sendto(ack_pkt, addr)
        else:
            # 乱序/重复包，回复上一次确认
            print(f"收到乱序 seq={seq}, 期望 {expected_seq}，发送重复确认")
            log_event(f"收到乱序 seq={seq}, 期望 {expected_seq}")
            ack_pkt = struct.pack("!HHHHH", TYPE_ACK, stu_id, 0, expected_seq - 1, 0)
            server_sock.sendto(ack_pkt, addr)
        return

    # 3. 未知报文
    else:
        print(f"未知报文类型 {msg_type} 来自 {addr}")
        log_event(f"未知报文类型 {msg_type} 来自 {addr}")

def main():
    # 命令行参数校验
    if len(sys.argv) != 2:
        print("用法: python3 udpserver.py <port>")
        print("示例: python3 udpserver.py 9999")
        return

    try:
        port = int(sys.argv[1])
    except ValueError:
        print("错误：端口必须是数字")
        return

    # 端口合法范围校验
    if port < 1024 or port > 65535:
        print("错误：端口范围必须在 1024 ~ 65535 之间")
        return

    # 创建UDP服务器
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(('', port))
    print(f"UDP 多线程服务器启动，监听端口 {port}")
    log_event(f"UDP 多线程服务器启动，监听端口 {port}")

    # 循环接收UDP数据包
    while True:
        data, addr = server.recvfrom(4096)
        t = threading.Thread(target=handle_client_packet, args=(data, addr, server))
        t.daemon = True
        t.start()

if __name__ == "__main__":
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    main()