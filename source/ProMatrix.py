# -*- coding: utf-8 -*-
"""
send_hc05_realtime.py
Laptop Bluetooth -> HC-05 -> UART -> CH552T/8051 -> WS2812B 16x16

Menu:
  1. ProCV robot face camera
  2. Send GIF
  3. Send static image
  4. Config
  5. Exit

Install:
  python -m pip install pyserial pillow opencv-python
"""

import time
import math
from pathlib import Path

import serial
from PIL import Image, ImageEnhance, ImageSequence

try:
    import cv2
except ImportError:
    cv2 = None


W, H = 16, 16
FRAME_SIZE = W * H * 3

SOF = bytes([0xA5, 0x5A])
ACK_R, ACK_K, ACK_E = b"R", b"K", b"E"

CFG = {
    "port": "COM11",
    "baud": 115200,
    "brightness": 0.35,
    "fps": 7.0,
    "serpentine": True,
}

GIF_PATH = ""
IMG_PATH = ""

def ask(msg, default=None, cast=str):
    s = input(f"{msg}" + (f" [{default}]" if default is not None else "") + ": ").strip()
    if not s and default is not None:
        return default
    try:
        return cast(s)
    except Exception:
        return default


def clamp(v):
    return max(0, min(255, int(v)))


def index(x, y):
    if CFG["serpentine"] and y % 2:
        x = W - 1 - x
    return (y * W + x) * 3


def new_frame():
    return bytearray(FRAME_SIZE)


def set_px(f, x, y, r, g, b, br=None):
    if not (0 <= x < W and 0 <= y < H):
        return
    if br is None:
        br = CFG["brightness"]

    k = index(x, y)
    f[k + 0] = clamp(g * br)  # WS2812B GRB
    f[k + 1] = clamp(r * br)
    f[k + 2] = clamp(b * br)


def make_packet(frame):
    s = sum(frame) & 0xFFFF
    return SOF + bytes(frame) + bytes([s & 0xFF, s >> 8])


def wait_ready(ser, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        b = ser.read(1)
        if b == ACK_R:
            return True
        if b == ACK_E:
            print("[MCU] E: lỗi frame trước đó, chờ R tiếp...")
    return False


def wait_ok(ser, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        b = ser.read(1)
        if b == ACK_K:
            return True
        if b == ACK_E:
            print("[MCU] E: checksum/header/timeout lỗi")
            return False
    return False


def send_frame(ser, frame, first=False):
    if not wait_ready(ser, 10.0 if first else 2.0):
        print("Không thấy READY 'R'. Kiểm tra COM, baud, TX/RX, nguồn HC-05.")
        return False

    ser.write(make_packet(frame))
    ser.flush()

    if not wait_ok(ser, 3.0):
        print("Không thấy ACK 'K'.")
        return False

    return True


def open_link():
    print(f"Mở {CFG['port']} @ {CFG['baud']} ...")
    ser = serial.Serial(
        port=CFG["port"],
        baudrate=CFG["baud"],
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.02,
        write_timeout=2.0,
        rtscts=False,
        dsrdtr=False,
        xonxoff=False,
    )
    time.sleep(1.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser


def center_crop(img):
    img = img.convert("RGB")
    w, h = img.size
    s = min(w, h)
    x0, y0 = (w - s) // 2, (h - s) // 2
    return img.crop((x0, y0, x0 + s, y0 + s))


def image_to_frame(img):
    img = center_crop(img)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Color(img).enhance(1.20)
    img = img.resize((W, H), Image.Resampling.LANCZOS)

    f = new_frame()
    for y in range(H):
        for x in range(W):
            r, g, b = img.getpixel((x, y))
            set_px(f, x, y, r, g, b)
    return f


def option_image():
    path = Path(input("Image path, ví dụ sample.png: ").strip().strip('"'))
    if not path.exists():
        print("Không thấy file ảnh.")
        return

    frame = image_to_frame(Image.open(path))

    try:
        with open_link() as ser:
            if send_frame(ser, frame, first=True):
                print("Đã gửi ảnh 16x16 OK. WS2812B sẽ tự giữ ảnh.")
    except Exception as e:
        print("Lỗi:", e)


def option_gif():
    path = Path(input("GIF path: ").strip().strip('"'))
    if not path.exists():
        print("Không thấy file GIF.")
        return

    loops = ask("Loop count, 0 = forever", 0, int)
    gif = Image.open(path)

    frames = []
    delays = []

    for im in ImageSequence.Iterator(gif):
        frames.append(image_to_frame(im))
        delay = im.info.get("duration", int(1000 / CFG["fps"])) / 1000.0
        delays.append(max(0.03, delay))

    print(f"Loaded {len(frames)} GIF frames. Ctrl+C để dừng.")

    sent = failed = 0
    try:
        with open_link() as ser:
            first = True
            loop = 0

            while loops == 0 or loop < loops:
                for f, d in zip(frames, delays):
                    t0 = time.monotonic()

                    if send_frame(ser, f, first):
                        sent += 1
                        first = False
                    else:
                        failed += 1
                        time.sleep(0.15)

                    time.sleep(max(0.0, d - (time.monotonic() - t0)))

                loop += 1

    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print("Lỗi:", e)

    print(f"GIF done. OK={sent}, failed={failed}")


def rect(f, x0, y0, x1, y1, r, g, b):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            set_px(f, x, y, r, g, b)


def eye(f, cx, cy, active, tick):
    color = (0, 180, 255) if active else (70, 70, 100)

    if active and tick % 22 < 3:
        color = (0, 10, 25)

    for dx in (-1, 0, 1):
        set_px(f, cx + dx, cy, *color)


def robot_frame(face_x=0.5, face_y=0.5, found=False, tick=0):
    f = new_frame()

    for y in range(H):
        for x in range(W):
            v = (math.sin(x * 0.55 + tick * 0.13) + math.sin(y * 0.75 + tick * 0.09) + 2) / 4
            set_px(f, x, y, int(20 * v), int(30 * v), int(90 * v), br=1.0)

    rect(f, 2, 2, 13, 13, *(35, 110, 180) if found else (35, 45, 75))

    set_px(f, 1, 6, 180, 30, 120)
    set_px(f, 14, 6, 180, 30, 120)
    set_px(f, 7, 1, 230, 160, 0)
    set_px(f, 8, 1, 230, 160, 0)

    ox = int((face_x - 0.5) * 3)
    oy = int((face_y - 0.5) * 2)

    eye(f, 5 + ox, 6 + oy, found, tick)
    eye(f, 10 + ox, 6 + oy, found, tick)

    if found:
        if tick % 12 < 6:
            for x in range(5, 11):
                set_px(f, x, 10, 255, 90, 0)
            set_px(f, 4, 9, 255, 90, 0)
            set_px(f, 11, 9, 255, 90, 0)
        else:
            for x in range(5, 11):
                set_px(f, x, 10, 255, 200, 0)
            set_px(f, 6, 11, 255, 200, 0)
            set_px(f, 9, 11, 255, 200, 0)
    else:
        for x in range(5, 11):
            set_px(f, x, 10, 90, 90, 120)

    return f


def option_procv():
    if cv2 is None:
        print("Thiếu OpenCV. Cài: python -m pip install opencv-python")
        return

    cam_id = ask("Camera ID", 0, int)
    cap = cv2.VideoCapture(cam_id)

    if not cap.isOpened():
        print("Không mở được camera.")
        return

    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    print("ProCV robot face running. Ctrl+C để dừng.")
    print("Tip: bật đèn sáng hơn, đưa mặt gần camera nếu laptop cam mờ.")

    sent = failed = tick = 0

    try:
        with open_link() as ser:
            first = True

            while True:
                t0 = time.monotonic()
                ok, img = cap.read()
                found = False
                fx = fy = 0.5

                if ok:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    gray = cv2.equalizeHist(gray)

                    faces = detector.detectMultiScale(
                        gray,
                        scaleFactor=1.08,
                        minNeighbors=4,
                        minSize=(40, 40),
                    )

                    if len(faces):
                        x, y, w, h = max(faces, key=lambda p: p[2] * p[3])
                        ih, iw = gray.shape[:2]
                        fx = (x + w / 2) / iw
                        fy = (y + h / 2) / ih
                        found = True

                f = robot_frame(fx, fy, found, tick)

                if send_frame(ser, f, first):
                    sent += 1
                    first = False
                else:
                    failed += 1
                    time.sleep(0.15)

                tick += 1
                time.sleep(max(0.0, 1.0 / max(1.0, CFG["fps"]) - (time.monotonic() - t0)))

                if tick % 20 == 0:
                    print(f"sent={sent}, failed={failed}, face={'YES' if found else 'NO'}")

    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print("Lỗi:", e)
    finally:
        cap.release()


def option_config():
    print("\nCurrent config:")
    for k, v in CFG.items():
        print(f"  {k}: {v}")

    CFG["port"] = ask("COM port", CFG["port"], str)
    CFG["baud"] = ask("Baud", CFG["baud"], int)
    CFG["brightness"] = max(0.05, min(1.0, ask("Brightness 0.05..1.0", CFG["brightness"], float)))
    CFG["fps"] = max(1.0, ask("FPS", CFG["fps"], float))

    s = ask("Serpentine mapping? y/n", "y" if CFG["serpentine"] else "n", str).lower()
    CFG["serpentine"] = not s.startswith("n")

    print("Config updated.\n")


def main():
    print("HC-05 WS2812B Realtime Sender")
    print("Install: python -m pip install pyserial pillow opencv-python")

    while True:
        print("\n1. ProCV robot face")
        print("2. Gửi GIF")
        print("3. Gửi ảnh tĩnh")
        print("4. Cấu hình")
        print("5. Exit")

        c = input("Chọn: ").strip()

        if c == "1":
            option_procv()
        elif c == "2":
            option_gif()
        elif c == "3":
            option_image()
        elif c == "4":
            option_config()
        elif c == "5":
            print("Bye bro :3")
            break
        else:
            print("Chọn 1..5 thôi bro.")


if __name__ == "__main__":
    main()
