import cv2
import socket
import numpy as np
import time
import sys

# ==========================================
# CẤU HÌNH HỆ THỐNG
# ==========================================
VIDEO_FILE = "sample.mp4"         # Tên file video Bad Apple của ông
BT_MAC     = "00:25:11:02:85:B9"  # MAC chuẩn của ông
PORT       = 1
MATRIX_W   = 16
MATRIX_H   = 16
NUM_LEDS   = MATRIX_W * MATRIX_H
FRAME_SIZE = NUM_LEDS * 3
IS_ZIGZAG  = True                 # Mạch hàn zíc-zắc

# ==========================================
# CÁC HÀM XỬ LÝ (CORE)
# ==========================================
def convert_to_ws2812b_buffer(matrix_2d):
    """Băm ma trận pixel 16x16 thành dải 768 bytes GRB Zíc-zắc"""
    buffer_1d = bytearray(FRAME_SIZE)
    for y in range(MATRIX_H):
        for x in range(MATRIX_W):
            actual_x = x if not IS_ZIGZAG else (x if y % 2 == 0 else MATRIX_W - 1 - x)
            idx = (y * MATRIX_W + actual_x) * 3
            
            # Đọc RGB từ mảng numpy (Opencv xuất ra là RGB nếu đã convert)
            r, g, b = matrix_2d[y, x]
            
            buffer_1d[idx]     = g
            buffer_1d[idx + 1] = r
            buffer_1d[idx + 2] = b
    return bytes(buffer_1d)

def print_terminal_preview(matrix_2d, is_first_frame):
    """
    In preview ra Terminal dùng ANSI Escape Code.
    Trick ăn tiền: Di chuyển con trỏ chuột lên trên 16 dòng để in đè (Không bị cuộn màn hình)
    """
    if not is_first_frame:
        sys.stdout.write(f"\033[{MATRIX_H}A") # Đẩy con trỏ lên trên MATRIX_H dòng
    
    for y in range(MATRIX_H):
        row_str = ""
        for x in range(MATRIX_W):
            r, g, b = matrix_2d[y, x]
            # \x1b[48;2;R;G;Bm là mã màu nền ANSI 24-bit
            row_str += f"\x1b[48;2;{r};{g};{b}m  \x1b[0m"
        sys.stdout.write(row_str + "\n")
    sys.stdout.flush()

# ==========================================
# KHỞI TẠO KẾT NỐI
# ==========================================
print(f"[*] Đang kết nối Bluetooth tới {BT_MAC}...")
try:
    bt_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    bt_sock.connect((BT_MAC, PORT))
    bt_sock.settimeout(1.0) # Đợi chữ K tối đa 1 giây
    print("[+] Kết nối Bluetooth thành công!")
except Exception as e:
    print(f"[-] Lỗi kết nối Bluetooth: {e}")
    sys.exit()

cap = cv2.VideoCapture(VIDEO_FILE)
if not cap.isOpened():
    print(f"[-] LỖI: Không đọc được file {VIDEO_FILE}!")
    sys.exit()

# Lấy thông số Video gốc
fps = cap.get(cv2.CAP_PROP_FPS)
if fps == 0: fps = 30
frame_delay = 1.0 / fps

print(f"[*] Đang nạp {VIDEO_FILE} ({fps} FPS). BẤM RESET TRÊN BOARD ĐỂ BẮT ĐẦU!!!")
time.sleep(1) # Dừng 1 xíu cho ông chuẩn bị tư thế bấm Reset =))

# ==========================================
# VÒNG LẶP PLAY VIDEO
# ==========================================
is_first_frame = True
frame_count = 0
start_time = time.time()

try:
    while cap.isOpened():
        # Đoạn này dùng để đồng bộ thời gian thực (giữ cho video không bị chạy chậm lại)
        # Tính toán frame nào đang cần được phát tại thời điểm hiện tại
        elapsed_time = time.time() - start_time
        target_frame_idx = int(elapsed_time * fps)
        
        # Nhảy đến đúng frame cần phát (Bỏ qua các frame bị trễ do nghẽn Bluetooth)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_idx)
        
        ret, frame = cap.read()
        if not ret:
            print("\n\n[+] HẾT PHIM!")
            break

        # Đổi màu từ BGR sang RGB và thu nhỏ về 16x16
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_16x16 = cv2.resize(frame_rgb, (MATRIX_W, MATRIX_H), interpolation=cv2.INTER_AREA)

        # 1. In Preview Terminal
        print_terminal_preview(frame_16x16, is_first_frame)
        is_first_frame = False

        # 2. Đóng gói Data
        payload = convert_to_ws2812b_buffer(frame_16x16)

        # 3. Giao tiếp với Mạch (Chờ 'K' -> Bắn Data)
        try:
            ack = bt_sock.recv(1024)
            if b'K' in ack:
                bt_sock.send(payload)
        except socket.timeout:
            # Nếu nghẽn không thấy 'K', tự nhồi data phá kẹt
            bt_sock.send(payload)

        frame_count += 1
        
        # In thêm 1 dòng text nhỏ xíu đè ở trên cùng để theo dõi
        sys.stdout.write(f"\033[{MATRIX_H+1}A\r[+] Đang phát: Frame {target_frame_idx} | Đã xuất LED: {frame_count} frames\n\033[{MATRIX_H}B")
        sys.stdout.flush()

except KeyboardInterrupt:
    print("\n\n[*] Đã dừng bằng tay.")
finally:
    try: bt_sock.close() 
    except: pass
    cap.release()
    # In thêm vài dòng trống để terminal không bị lem màu
    print("\n" * (MATRIX_H + 2))
    print("[*] Đã ngắt kết nối an toàn.")