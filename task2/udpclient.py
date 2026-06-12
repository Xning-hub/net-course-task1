import socket
import struct
import time
import random
import sys
import os
import threading 
import pandas as pd

# 协议常量
TYPE_CONN_REQ = 1
TYPE_CONN_ACK = 2
TYPE_DATA = 3
TYPE_ACK = 4

STUDENT_ID_MASK = 0x5A3C
WINDOW_SIZE = 400      # 固定发送窗口 400 字节
MIN_CHUNK = 40
MAX_CHUNK = 80
TIMEOUT = 0.3          # 300ms
TOTAL_PACKETS = 30     # 要发送的数据包数量

LOG_FILE = "client_run_log.txt"
LOG_LOCK = threading.Lock() 

# 日志函数
def log_event(event):
    now = time.time()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)) + f".{int(now * 1000) % 1000:03d}"
    log_line = f"[{timestamp}] {event}\n"
    LOG_LOCK.acquire()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
    finally:
        LOG_LOCK.release()

# StudentID字段
def compute_student_id(sid_str):
    """学号后4位异或 0x5A3C"""
    last4 = int(sid_str[-4:])
    return last4 ^ STUDENT_ID_MASK

def main():
    # 命令行传参
    total_all_sent = 0     
    if len(sys.argv) < 3:
        print("用法: python udpclient.py <serverIP> <serverPort> [--seed <seed>]")
        return

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    seed = None
    if "--seed" in sys.argv:
        idx = sys.argv.index("--seed")
        if idx + 1 < len(sys.argv):
            seed = int(sys.argv[idx + 1])

    # 学号
    student_id = "240501220"
    stu_field = compute_student_id(student_id)
    print(f"StudentID 字段值: {stu_field}")

    # 随机种子（用于生成报文大小）
    if seed is not None:
        random.seed(seed)

    # 创建Socket并设置超时
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)

    # 连接建立
    # 发送连接请求
    conn_req = struct.pack("!HHHHH", TYPE_CONN_REQ, stu_field, 0, 0, 0)
    sock.sendto(conn_req, (server_ip, server_port))
    log_event(f"发送连接请求，StudentID={stu_field}")
    print(f"发送连接请求，StudentID={stu_field}")

    # 等待连接确认
    try:
        data, _ = sock.recvfrom(1024)
        if len(data) >= 10:
            msg_type, stu_resp, _, _, _ = struct.unpack("!HHHHH", data[:10])
            if msg_type == TYPE_CONN_ACK and stu_resp == stu_field:
                print("连接建立成功")
                log_event("收到连接确认，连接建立成功")
            else:
                print("连接确认报文无效")
                log_event("连接确认报文无效")
                return
        else:
            print("收到无效报文")
            return
    except socket.timeout:
        print("连接建立超时")
        log_event("连接建立超时")
        return
    except Exception as e:  
        print(f"连接异常：{e}")
        log_event(f"连接异常：{e}")
        return

    # 数据传输（GBN）
    # 生成随机字节串作为数据，长度随机
        # 1. 预生成所有数据包 + 记录每个包长度
        # 生成数据：共 TOTAL_PACKETS 个数据包，每个数据包大小 40~80 字节随机
    packets = []
    packet_len_list = []
    packet_boundary = []  # 存储每个包 (编号n, 起始x, 结束y)
    offset = 0            # 字节偏移，从0开始计数

    for i in range(TOTAL_PACKETS):
        size = random.randint(MIN_CHUNK, MAX_CHUNK)
        data = bytes([random.randint(32, 126) for _ in range(size)])
        packets.append(data)
        packet_len_list.append(size)

        # 记录当前包字节边界
        pkt_num = i + 1
        start_byte = offset
        end_byte = offset + size - 1
        packet_boundary.append( (pkt_num, start_byte, end_byte) )
        offset += size

    # 开始发送模拟 GBN
    base = 0          # 最早未被确认的序列号(数组下标，从0开始)
    next_seq = 0      # 下一个要发送的包下标
    acked = [False] * TOTAL_PACKETS
    rtt_list = []
    sent_time = [0.0] * TOTAL_PACKETS

    # 主循环，直到所有包被确认
    while base < TOTAL_PACKETS:
        # 计算：当前窗口内 已发送未确认 的总字节数
        current_window_bytes = 0
        for idx in range(base, next_seq):
            if not acked[idx]:
                current_window_bytes += packet_len_list[idx]

        # 窗口未满 && 还有包没发 ，继续发包
        while next_seq < TOTAL_PACKETS and current_window_bytes < WINDOW_SIZE:
            data = packets[next_seq]
            pkt_len = packet_len_list[next_seq]
            seq = next_seq + 1  # 报文序列号从1开始

            # 取出当前包编号、字节边界
            n, x, y = packet_boundary[next_seq]

            header = struct.pack("!HHHHH", TYPE_DATA, stu_field, seq, 0, pkt_len)
            pkt = header + data
            sock.sendto(pkt, (server_ip, server_port))
            total_all_sent += 1
            sent_time[next_seq] = time.time()

            # 打印
            print(f"第 {n} 个（第 {x}~{y} 字节）client 端已经发送")
            log_event(f"发送第{seq}个数据包 (seq={seq}), 长度={pkt_len}")

            current_window_bytes += pkt_len
            next_seq += 1

        # 等待确认或超时
        try:
            data, _ = sock.recvfrom(1024)
            if len(data) < 10:
                continue
            msg_type, stu_resp, _, ack_seq, _ = struct.unpack("!HHHHH", data[:10])
            # 增加ACK序号范围校验，防止越界
            if msg_type == TYPE_ACK and stu_resp == stu_field and 0 <= ack_seq <= TOTAL_PACKETS:
                if ack_seq > base:   # 只有确认了新的包才更新窗口
                    for i in range(base, ack_seq):
                        if not acked[i]:
                            acked[i] = True
                            rtt = (time.time() - sent_time[i]) * 1000
                            rtt_list.append(rtt)
                            n, x, y = packet_boundary[i]
                            print(f"第 {n} 个（第 {x}~{y} 字节）server 端已经收到，RTT 是 {rtt:.2f} ms")
                            log_event(f"收到第{i+1}个包确认, seq={i+1}, RTT={rtt:.2f}ms")
                    base = ack_seq
    # 如果 ack_seq <= base，则忽略（不更新窗口）
        except socket.timeout:
            # GBN 超时：重传 base ~ next_seq-1 所有未确认包
                        # GBN 超时：重传 base ~ next_seq-1 所有未确认包
            print("超时，重传窗口内所有数据包")
            log_event("超时，重传窗口内所有数据包")
            for i in range(base, next_seq):
                if not acked[i]:
                    data = packets[i]
                    pkt_len = packet_len_list[i]
                    seq = i + 1

                    # 取出边界信息
                    n, x, y = packet_boundary[i]

                    header = struct.pack("!HHHHH", TYPE_DATA, stu_field, seq, 0, pkt_len)
                    pkt = header + data
                    sock.sendto(pkt, (server_ip, server_port))
                    total_all_sent += 1
                    sent_time[i] = time.time()

                    # 打印
                    print(f"重传第 {n} 个（第 {x}~{y} 字节）数据包")
                    log_event(f"重传第{seq}个数据包 (seq={seq})")
           
    # 所有包确认完成
    print("所有数据包发送并确认完毕")
    log_event("所有数据包发送并确认完毕")

    # 统计信息
    print(f"实际发送总包数(含重传): {total_all_sent}")
    print(f"成功接收包数: {TOTAL_PACKETS}")

    # 没有让30丢包率 = (总发送 - 成功接收) / 总发送 * 100%
    if total_all_sent == 0:
        loss_rate = 0.0
    else:
        loss_rate = (total_all_sent - TOTAL_PACKETS) / total_all_sent * 100
    print(f"丢包率: {loss_rate:.2f}%")

    # 使用 pandas 计算 RTT 统计量
    if rtt_list:
        df = pd.DataFrame({'RTT': rtt_list})
        max_rtt = df['RTT'].max()
        min_rtt = df['RTT'].min()
        avg_rtt = df['RTT'].mean()
        stdev_rtt = df['RTT'].std()
        print(f"最大 RTT: {max_rtt:.2f}ms")
        print(f"最小 RTT: {min_rtt:.2f}ms")
        print(f"平均 RTT: {avg_rtt:.2f}ms")
        print(f"RTT 标准差: {stdev_rtt:.2f}ms")
        log_event(f"统计 (pandas): maxRTT={max_rtt:.2f}, minRTT={min_rtt:.2f}, avgRTT={avg_rtt:.2f}, std={stdev_rtt:.2f}")
    else:
        print("没有有效的 RTT 数据")

    sock.close()

if __name__ == "__main__":
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    main()