#!/usr/bin/env python3
"""
send.py — Gửi ảnh tĩnh 16×16 tới CH552T LED Matrix qua Bluetooth Native Socket
==========================================================================
Đã loại bỏ PyBluez, sử dụng socket chuẩn của Windows/Linux.
Chỉ cần cài: pip install Pillow
==========================================================================
"""

import sys
import os
import time
import socket

# ── Pillow (Thư viện xử lý ảnh duy nhất cần thiết) ────────────────────────
try:
    from PIL import Image
except ImportError:
    sys.exit("[ERROR] Cần cài Pillow:  pip install Pillow")

# ══════════════════════════════════════════════════════════════════════════
#  ❶  CẤU HÌNH HỆ THỐNG
# ══════════════════════════════════════════════════════════════════════════

# --- Chế độ BLUETOOTH NATIVE ----------------------------------------------
HC05_MAC  = "00:25:11:02:85:B9"   # Đã fix đúng MAC của ông
BT_PORT   = 1                     # RFCOMM channel, HC-05 mặc định = 1

# --- Chung ------------------------------------------------------------------
IMAGE_FILE = "sample.png"          # Ảnh mặc định nếu không truyền argument
MATRIX_W   = 16                    # Chiều rộng ma trận
MATRIX_H   = 16                    # Chiều cao ma trận
NUM_LEDS   = MATRIX_W * MATRIX_H   # 256
FRAME_SIZE = NUM_LEDS * 3          # 768 bytes GRB
ACK_CHAR   = b'K'
TIMEOUT    = 10.0                  # Giây chờ ACK tối đa

# ══════════════════════════════════════════════════════════════════════════
#  ❷  XỬ LÝ ẢNH
# ══════════════════════════════════════════════════════════════════════════

def image_to_grb_bytes(path: str) -> bytes:
    """
    Đọc ảnh PNG/JPEG bất kỳ, resize về 16x16, chuyển sang GRB.
    Mạch thực tế hàn zigzag nên cần ánh xạ lại tọa độ X.
    """
    img = Image.open(path).convert("RGB")
    # Resize về 16×16 dùng LANCZOS (chất lượng cao nhất)
    img = img.resize((MATRIX_W, MATRIX_H), Image.LANCZOS)
    
    # Tạo mảng ảo để tính toán tọa độ
    pixels = img.load()
    grb_bytes = bytearray(FRAME_SIZE)
    
    IS_ZIGZAG = True # Bật chế độ mạch hàn Zíc Zắc giống file host.py
    
    for y in range(MATRIX_H):
        for x in range(MATRIX_W):
            # Tính tọa độ X thực tế trên phần cứng
            actual_x = x if not IS_ZIGZAG else (x if y % 2 == 0 else MATRIX_W - 1 - x)
            idx = (y * MATRIX_W + actual_x) * 3
            
            r, g, b = pixels[x, y]
            
            # Đẩy vào buffer theo thứ tự G-R-B của WS2812B
            grb_bytes[idx]     = g
            grb_bytes[idx + 1] = r
            grb_bytes[idx + 2] = b

    print(f"[IMG] {path} → resize {MATRIX_W}×{MATRIX_H} → {len(grb_bytes)} bytes GRB (ZIGZAG={IS_ZIGZAG})")
    return bytes(grb_bytes)

def preview_matrix(path: str):
    """In preview 16×16 bằng ký tự màu ANSI terminal (tuỳ chọn, đẹp)."""
    try:
        img = Image.open(path).convert("RGB").resize((MATRIX_W, MATRIX_H), Image.LANCZOS)
        print(f"\n[PREVIEW] {MATRIX_W}×{MATRIX_H} matrix:")
        for y in range(MATRIX_H):
            row = ""
            for x in range(MATRIX_W):
                r, g, b = img.getpixel((x, y))
                row += f"\x1b[48;2;{r};{g};{b}m  \x1b[0m"
            print(row)
        print()
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════
#  ❸  LỚP KẾT NỐI BLUETOOTH NATIVE
# ══════════════════════════════════════════════════════════════════════════

class BluetoothConn:
    """Kết nối trực tiếp qua Native Socket (Không cần cài PyBluez)."""
    def __init__(self, mac: str, port: int):
        self.mac  = mac
        self.port = port
        self._sock = None

    def connect(self):
        print(f"[BT] Đang kết nối tới {self.mac} (RFCOMM port {self.port})...")
        self._sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self._sock.connect((self.mac, self.port))
        self._sock.settimeout(TIMEOUT)
        print(f"[BT] Đã kết nối ✅")

    def send(self, data: bytes):
        total = len(data)
        sent  = 0
        while sent < total:
            n = self._sock.send(data[sent:])
            sent += n

    def recv(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            try:
                chunk = self._sock.recv(n - len(buf))
                if not chunk:
                    raise ConnectionError("Kết nối bị ngắt khi đọc dữ liệu.")
                buf += chunk
            except socket.timeout:
                raise TimeoutError("Chờ phản hồi quá lâu (Timeout).")
        return buf

    def close(self):
        if self._sock:
            self._sock.close()

# ══════════════════════════════════════════════════════════════════════════
#  ❹  GIAO THỨC GỬI FRAME
# ══════════════════════════════════════════════════════════════════════════

def wait_for_ack(conn, label: str = ""):
    print(f"[ACK] Đang chờ ACK{' (' + label + ')' if label else ''}...")
    start = time.time()
    while True:
        try:
            byte = conn.recv(1)
            if byte == ACK_CHAR:
                print(f"[ACK] Nhận được 'K' ✅")
                return
            elapsed = time.time() - start
            if elapsed > TIMEOUT:
                raise TimeoutError(f"Hết {TIMEOUT}s mà chưa nhận ACK.")
        except TimeoutError:
            # Nếu timeout, in ra để debug
            raise

def send_frame(conn, frame: bytes):
    """
    Gửi 1 frame 768 bytes.
    Chia nhỏ thành các chunk 64 byte để tránh tràn buffer UART của HC-05.
    """
    CHUNK = 64
    total = len(frame)
    sent  = 0

    while sent < total:
        end   = min(sent + CHUNK, total)
        chunk = frame[sent:end]
        conn.send(chunk)
        sent += len(chunk)

        # Delay nhỏ để HC-05 kịp nhả data xuống CH552T qua UART
        time.sleep(0.002)

        # Progress bar
        pct = sent / total * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"\r[TX]  [{bar}] {pct:5.1f}%  {sent}/{total} bytes", end="", flush=True)

    print()

# ══════════════════════════════════════════════════════════════════════════
#  ❺  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    # ── Chọn file ảnh ─────────────────────────────────────────────────────
    image_path = sys.argv[1] if len(sys.argv) > 1 else IMAGE_FILE
    if not os.path.isfile(image_path):
        sys.exit(f"[ERROR] Không tìm thấy file ảnh: {image_path}\n"
                 f"        Hãy chắc chắn bạn đã gõ 'cd Source' trước khi chạy script.")

    # ── Chuẩn bị dữ liệu ──────────────────────────────────────────────────
    frame_data = image_to_grb_bytes(image_path)
    preview_matrix(image_path)

    # ── Khởi tạo kết nối ──────────────────────────────────────────────────
    conn = BluetoothConn(HC05_MAC, BT_PORT)

    try:
        conn.connect()
    except Exception as e:
        sys.exit(f"[ERROR] Không kết nối được: {e}\n[!] Hãy đảm bảo board đã cắm điện và HC-05 đang nháy đèn.")

    # ── Giao thức gửi ─────────────────────────────────────────────────────
    try:
        # Bước 1: Chờ MCU sẵn sàng
        wait_for_ack(conn, "boot/ready")

        # Bước 2: Gửi frame
        t0 = time.time()
        print(f"[TX]  Đang gửi {FRAME_SIZE} bytes ({NUM_LEDS} LEDs)...")
        send_frame(conn, frame_data)
        elapsed = time.time() - t0
        print(f"[TX]  Hoàn tất trong {elapsed*1000:.1f} ms")

        # Bước 3: Chờ báo cáo đã hiển thị xong
        wait_for_ack(conn, "display done")

        print("\n[OK]  Ảnh đã hiển thị trên LED matrix! 🎉")
        print("      MCU sẵn sàng nhận lệnh tiếp theo.\n")

    except (TimeoutError, ConnectionError) as e:
        print(f"\n[ERROR] {e}")
        # CƠ CHẾ PHÁ DEADLOCK: Tự động nhồi data nếu mạch lỡ nhịp
        print("[!] Đang thử nhồi data để phá Deadlock...")
        send_frame(conn, frame_data)

    finally:
        conn.close()
        print("[BT]  Đã đóng kết nối.")

if __name__ == "__main__":
    main()