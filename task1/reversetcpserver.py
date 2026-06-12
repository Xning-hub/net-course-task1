import socket
import struct
import time
import threading
import os
import sys

# 报文类型
TYPE_INIT = 1
TYPE_AGREE = 2
TYPE_REQ = 3
TYPE_ANS = 4

# 线程锁
LOG_LOCK = threading.Lock()

# 日志文件
LOG_FILE = "server_run_log.txt"

# 日志函数
def log_event(event):
    # 精确到毫秒
    now = time.time()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)) + f".{int(now * 1000) % 1000:03d}"
    log_line = f"[{timestamp}] {event}\n"
    LOG_LOCK.acquire()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
    finally:
        LOG_LOCK.release()


def handle_client(conn, addr):
    # 获取当前线程ID
    tid = threading.get_ident()
    print(f"【线程{tid}】新连接来自 {addr}")
    log_event(f"【线程{tid}】新连接来自 {addr}")

    try:
        # 接收 Initialization
        data = conn.recv(6)  # Type(2) + N(4)
        if len(data) < 6:
            return
        msg_type, N = struct.unpack("!HI", data)
        if msg_type != TYPE_INIT:
            log_event(f"错误：收到非初始化报文 type={msg_type}")
            return
        log_event(f"收到 Initialization，N={N}")

        # 发送 agree
        agree_pkt = struct.pack("!H", TYPE_AGREE)
        conn.sendall(agree_pkt) 
        log_event("发送 agree")

        # 循环接收 reverseRequest，处理并回复 reverseAnswer
        for i in range(N):
            # 先接收头部 (Type 2 + Length 4)
            head = conn.recv(6)
            if len(head) < 6:
                break
            msg_type, length = struct.unpack("!HI", head)
            if msg_type != TYPE_REQ:
                log_event(f"错误：期望 reverseRequest，收到 type={msg_type}")
                break

            # 接收数据块
            data = b''
            while len(data) < length:
                chunk = conn.recv(length - len(data))
                if not chunk:
                    break
                data += chunk
            if len(data) != length:
                log_event(f"警告：数据块长度不完整，期望 {length}，实际 {len(data)}")
                break

            log_event(f"收到 reverseRequest 第{i+1}块，长度={length}")

            # 反转数据（将字节串反转）
            reversed_data = data[::-1]

            # 构造 reverseAnswer：Type(2) + Length(4) + reversedData
            ans_pkt = struct.pack("!HI", TYPE_ANS, len(reversed_data)) + reversed_data
            conn.sendall(ans_pkt)
            log_event(f"发送 reverseAnswer 第{i+1}块，长度={len(reversed_data)}")

        print(f"完成与 {addr} 的通信")
        log_event(f"完成与 {addr} 的通信")

    except Exception as e:
        log_event(f"异常：{e}")
    finally:
        conn.close()

def main():
    # 命令行传参
    if len(sys.argv) != 2:
        print("用法: python server.py <port>")
        return
    port = int(sys.argv[1])
    # 创建 TCP 服务器
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('', port))
    server.listen(5)
    print(f"TCP 服务器启动，监听端口 {port}")
    log_event(f"服务器启动，监听端口 {port}")
    #循环接受新的TCP连接，为每个客户端创建一个新线程
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

if __name__ == "__main__":
    # 清空日志
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    main()