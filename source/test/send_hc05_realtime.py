#!/usr/bin/env python3
"""
send_hc05_realtime_test.py
==================================================
Realtime test: PC -> HC-05 -> CH552T -> WS2812B 16x16

Protocol khớp với file C:
    MCU -> PC: 'R'                         READY
    PC  -> MCU: A5 5A + 768 GRB + sum16    1 frame
    MCU -> PC: 'K'                         OK, đã show xong
    MCU -> PC: 'E'                         lỗi frame/checksum/timeout

Cài thư viện:
    pip install pyserial

Cách chạy Windows:
    python send_hc05_realtime_test.py --port COM7

Đổi COM7 thành COM port của HC-05 sau khi pair Bluetooth.
"""

import argparse
import math
import sys
import time

import serial


WIDTH = 16
HEIGHT = 16
NUM_LEDS = WIDTH * HEIGHT
FRAME_SIZE = NUM_LEDS * 3

SOF = bytes([0xA5, 0x5A])
ACK_READY = b"R"
ACK_OK = b"K"
ACK_ERR = b"E"


def xy_to_index(x: int, y: int) -> int:
    """
    Mapping LED 16x16.
    Mặc định: zigzag/serpentine phổ biến.

    Nếu matrix của bạn chạy sai hướng, sửa hàm này sau.
    """
    if y % 2 == 0:
        return y * WIDTH + x
    return y * WIDTH + (WIDTH - 1 - x)


def set_pixel(frame: bytearray, x: int, y: int, r: int, g: int, b: int) -> None:
    """
    WS2812B buffer theo thứ tự GRB:
        byte 0 = G
        byte 1 = R
        byte 2 = B
    """
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        return

    idx = xy_to_index(x, y) * 3
    frame[idx + 0] = max(0, min(255, g))
    frame[idx + 1] = max(0, min(255, r))
    frame[idx + 2] = max(0, min(255, b))


def solid_color(r: int, g: int, b: int) -> bytearray:
    frame = bytearray(FRAME_SIZE)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            set_pixel(frame, x, y, r, g, b)
    return frame


def moving_dot(t: int) -> bytearray:
    """
    Hiệu ứng test đơn giản:
    - nền xanh dương rất nhẹ
    - 1 chấm sáng chạy vòng quanh
    """
    frame = solid_color(0, 0, 8)

    # chấm chạy theo hàng ngang rồi xuống dòng
    pos = t % NUM_LEDS
    x = pos % WIDTH
    y = pos // WIDTH

    set_pixel(frame, x, y, 180, 0, 0)      # đỏ
    set_pixel(frame, (x - 1) % WIDTH, y, 80, 30, 0)  # đuôi vàng nhẹ
    return frame


def color_wipe(t: int) -> bytearray:
    """
    Quét màu đỏ -> xanh lá -> vàng -> xanh dương.
    Dễ nhìn để biết realtime có chạy không.
    """
    colors = [
        (180, 0, 0),      # đỏ
        (0, 180, 0),      # xanh lá
        (180, 120, 0),    # vàng/cam
        (0, 0, 180),      # xanh dương
    ]

    frame = solid_color(0, 0, 0)
    color = colors[(t // NUM_LEDS) % len(colors)]
    n = (t % NUM_LEDS) + 1

    for p in range(n):
        y = p // WIDTH
        x = p % WIDTH
        set_pixel(frame, x, y, *color)

    return frame


def plasma(t: int) -> bytearray:
    """
    Hiệu ứng realtime mềm hơn, giống gradient động.
    Vẫn chỉ là tính toán local trên PC rồi gửi frame xuống MCU.
    """
    frame = bytearray(FRAME_SIZE)

    for y in range(HEIGHT):
        for x in range(WIDTH):
            v1 = math.sin((x + t * 0.35) * 0.55)
            v2 = math.sin((y + t * 0.25) * 0.70)
            v3 = math.sin((x + y + t * 0.20) * 0.45)
            v = (v1 + v2 + v3 + 3.0) / 6.0

            r = int(120 * v)
            g = int(80 * (1.0 - v))
            b = int(160 * abs(math.sin(v * math.pi)))

            set_pixel(frame, x, y, r, g, b)

    return frame


def checksum16(payload: bytes) -> bytes:
    s = sum(payload) & 0xFFFF
    return bytes([s & 0xFF, (s >> 8) & 0xFF])


def send_frame(ser: serial.Serial, payload: bytes, timeout_s: float = 5.0) -> bool:
    """
    Chờ MCU gửi 'R', gửi frame, chờ 'K'.
    Không spam UART khi MCU đang WS2812B_Show().
    """
    if len(payload) != FRAME_SIZE:
        raise ValueError(f"Frame phải đúng {FRAME_SIZE} byte, hiện tại {len(payload)} byte")

    deadline = time.time() + timeout_s

    # Chờ READY từ MCU
    while time.time() < deadline:
        b = ser.read(1)
        if b == ACK_READY:
            break
        if b == ACK_ERR:
            print("[MCU] báo lỗi frame trước đó, tiếp tục chờ READY...")
    else:
        print("Timeout: không nhận được READY 'R' từ MCU")
        return False

    packet = SOF + payload + checksum16(payload)
    ser.write(packet)
    ser.flush()

    # Chờ kết quả
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        b = ser.read(1)
        if b == ACK_OK:
            return True
        if b == ACK_ERR:
            print("[MCU] frame lỗi/checksum lỗi")
            return False

    print("Timeout: không nhận được ACK 'K' từ MCU")
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, help="COM port của HC-05, ví dụ COM7")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument(
        "--effect",
        choices=["dot", "wipe", "plasma", "solid"],
        default="plasma",
        help="Hiệu ứng test",
    )
    parser.add_argument("--fps", type=float, default=10.0, help="FPS mục tiêu, nên để 10 ở baud 115200")
    parser.add_argument("--brightness", type=float, default=1.0, help="0.1 đến 1.0")
    parser.add_argument("--seconds", type=float, default=0.0, help="0 = chạy mãi")
    args = parser.parse_args()

    frame_interval = 1.0 / max(1.0, args.fps)
    brightness = max(0.05, min(1.0, args.brightness))

    print(f"Opening {args.port} @ {args.baud}...")
    print("Nhớ pair HC-05 trước, chọn đúng COM port SPP.")
    print("Ctrl+C để dừng.")

    sent = 0
    start = time.time()
    last_report = start

    with serial.Serial(args.port, args.baud, timeout=0.05, write_timeout=2.0) as ser:
        # Xóa rác cũ trong buffer khi mới mở COM.
        time.sleep(1.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        while True:
            now = time.time()
            if args.seconds > 0 and now - start >= args.seconds:
                break

            if args.effect == "dot":
                frame = moving_dot(sent)
            elif args.effect == "wipe":
                frame = color_wipe(sent * 8)
            elif args.effect == "solid":
                # nháy đỏ -> xanh lá -> vàng -> xanh dương
                colors = [(180, 0, 0), (0, 180, 0), (180, 120, 0), (0, 0, 180)]
                frame = solid_color(*colors[(sent // 10) % len(colors)])
            else:
                frame = plasma(sent)

            if brightness < 1.0:
                for i in range(len(frame)):
                    frame[i] = int(frame[i] * brightness)

            t0 = time.time()
            ok = send_frame(ser, frame)

            if not ok:
                # Đừng spam nếu lỗi, cho MCU/HC-05 thở một chút.
                time.sleep(0.2)
                continue

            sent += 1

            # Giữ tốc độ mục tiêu. Handshake vốn đã giới hạn tốc độ thực tế.
            elapsed = time.time() - t0
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

            if time.time() - last_report >= 2.0:
                real_fps = sent / (time.time() - start)
                print(f"Frames sent: {sent}, avg FPS: {real_fps:.2f}")
                last_report = time.time()

    print("Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        raise SystemExit(0)
