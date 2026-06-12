import socket
import struct
import time
import random
import sys
import os
import threading

TYPE_INIT = 1
TYPE_AGREE = 2
TYPE_REQ = 3
TYPE_ANS = 4

#区分不同线程，改动了日志名
start_time = time.strftime("%Y%m%d_%H%M%S")
LOG_FILE = f"client_run_log_{start_time}.txt"
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

# 读取文件
def read_file(filepath):
    with open(filepath, 'rb') as f:
        return f.read()

# 分块函数
def generate_chunk_lengths(total_size, Lmin, Lmax, seed=None):
    if seed is not None:
        random.seed(seed)
    chunks = []
    remaining = total_size
    while remaining > 0:
        # 剩余不足最小块长，直接作为最后一块
        if remaining < Lmin:
            chunks.append(remaining)
            break
        # [Lmin, Lmax) 
        length = random.randrange(Lmin, Lmax)
        # 防止随机数大于剩余字节，因为不传入随机种子的时候，系统会随机分配种子
        if length > remaining:
            length = remaining
        chunks.append(length)
        remaining -= length
    return chunks

def main():
    # 命令行传参
    if len(sys.argv) < 6:
        print("用法: python reversetcpclient.py <serverIP> <serverPort> <filePath> <Lmin> <Lmax> [--seed <seed>]")
        return

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    file_path = sys.argv[3]
    Lmin = int(sys.argv[4])
    Lmax = int(sys.argv[5])
    seed = None
    if "--seed" in sys.argv:
        idx = sys.argv.index("--seed")
        if idx + 1 < len(sys.argv):
            seed = int(sys.argv[idx + 1])

    # 读取文件并生成分块
    if not os.path.exists(file_path):
        print(f"文件 {file_path} 不存在")
        return

    file_data = read_file(file_path)
    total_size = len(file_data)
    print(f"文件大小: {total_size} 字节")

    chunk_lengths = generate_chunk_lengths(total_size, Lmin, Lmax, seed)
    N = len(chunk_lengths)
    print(f"分块数 N = {N}")
    print(f"各块长度: {chunk_lengths}")

    # 连接服务器
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, server_port))
    print(f"连接到服务器 {server_ip}:{server_port}")
    log_event(f"连接到服务器 {server_ip}:{server_port}")

    # 发送 Initialization
    init_pkt = struct.pack("!HI", TYPE_INIT, N)
    sock.sendall(init_pkt)
    log_event(f"发送 Initialization，N={N}")

    # 接收 agree
    agree_data = sock.recv(2)
    if len(agree_data) == 2:
        msg_type = struct.unpack("!H", agree_data)[0]
        if msg_type != TYPE_AGREE:
            print("错误：服务器未返回 agree")
            sock.close()
            return
        log_event("收到 agree")
    else:
        print("错误：未收到 agree")
        sock.close()
        return

    # 收集所有反转后的数据（按原始块顺序暂存）
    chunks_reversed = []
    offset = 0
    for i, length in enumerate(chunk_lengths):
        chunk = file_data[offset:offset+length]
        offset += length

        # 发送 reverseRequest
        req_pkt = struct.pack("!HI", TYPE_REQ, length) + chunk
        sock.sendall(req_pkt)
        log_event(f"发送 reverseRequest 第{i+1}块，长度={length}")

        # 接收 reverseAnswer
        head = sock.recv(6)
        if len(head) < 6:
            print(f"错误：接收 reverseAnswer 头部失败，跳过当前块")
            continue
        msg_type, ans_len = struct.unpack("!HI", head)
        if msg_type != TYPE_ANS:
            print(f"错误：期望 reverseAnswer，收到 type={msg_type}，跳过当前块")
            continue

        ans_data = b''
        while len(ans_data) < ans_len:
            chunk = sock.recv(ans_len - len(ans_data))
            if not chunk:
                break
            ans_data += chunk
        if len(ans_data) != ans_len:
            print(f"错误：接收数据不完整，跳过当前块")
            continue

        # 存储到列表（按原始块顺序）
        chunks_reversed.append(ans_data)

        # 命令行打印
        reversed_text = ans_data.decode('utf-8', errors='ignore')
        print(f"第{i+1}块：{reversed_text}")
        log_event(f"收到 reverseAnswer 第{i+1}块，长度={ans_len}，内容={reversed_text}")

    # 将存储的反转块按逆序拼接，得到整体反转
    reversed_all = b''.join(reversed(chunks_reversed))
    output_filename = "reversed_output.txt"
    with open(output_filename, "wb") as f:
        f.write(reversed_all)
    print(f"\n所有反转数据已保存到文件: {output_filename}")
    log_event(f"所有反转数据已保存到文件: {output_filename}")

    sock.close()
    print("传输完成")
    log_event("传输完成")

if __name__ == "__main__":
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    main()