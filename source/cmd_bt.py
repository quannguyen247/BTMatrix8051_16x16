#!/usr/bin/env python3
import sys
import socket

HC05_MAC = "00:25:11:02:85:B9"
BT_PORT = 1

def main():
    # Truyền '1' để bật cầu vồng, '0' để tắt. Mặc định là '1'
    cmd = sys.argv[1] if len(sys.argv) > 1 else '1'
    
    if cmd not in ['0', '1']:
        print("Lệnh sai. Vui lòng dùng '1' (Cầu vồng) hoặc '0' (Tắt).")
        return

    print(f"[BT] Đang kết nối tới {HC05_MAC}...")
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    
    try:
        sock.connect((HC05_MAC, BT_PORT))
        print(f"[TX] Gửi lệnh: {cmd}")
        sock.send(cmd.encode('ascii'))
        
        # Đợi phản hồi 'K' từ vi điều khiển
        ack = sock.recv(1)
        if ack == b'K':
            print("[ACK] Chuyển hiệu ứng thành công! ✅")
            
    except Exception as e:
        print(f"[ERROR] Lỗi kết nối: {e}")
        
    finally:
        sock.close()

if __name__ == "__main__":
    main()