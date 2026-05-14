# -*- coding: utf-8 -*-
"""
ProMatrix.py

Laptop Bluetooth -> HC-05 -> UART -> CH552T/8051 -> WS2812B 16x16

Menu:
  1. ProCV Camera Pixel Art
  2. Send GIF
  3. Send static image, refreshed continuously
  4. Run scrolling text
  5. Config
  6. Exit

Install:
  python -m pip install pyserial pillow opencv-python numpy

MCU protocol:
  MCU -> PC : 'R'
  PC  -> MCU: A5 5A + 768 GRB bytes + checksum16
  MCU -> PC : 'K' or 'E'
"""

import time
from pathlib import Path

import serial
from PIL import Image, ImageEnhance, ImageSequence

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None


W, H = 16, 16
FRAME_SIZE = W * H * 3

SOF = bytes([0xA5, 0x5A])
ACK_R, ACK_K, ACK_E = b"R", b"K", b"E"

CFG = {
    "port": "COM11",
    "baud": 115200,

    "brightness": 0.05,

    # Chỉ áp dụng cho option 1 Camera Pixel Art
    "camera_white_cap": 6,
    "camera_color_boost": 2.5,

    "fps": 7.0,
    "text_fps": 3.0,
    "text_font_size": 2,   # 3 = font 3x5 nhỏ, 5 = font 5x7 lớn
    "image_refresh": 0.5,
    "debug_window": True,
    "default_text": "YEU EM GPT :))",
    "camera_contrast": 1.25,
    "camera_saturation": 1.35,
    "camera_mirror": True,
}


FONT_3X5 = {
    " ": ["000","000","000","000","000"],

    "A": ["010","101","111","101","101"],
    "B": ["110","101","110","101","110"],
    "C": ["011","100","100","100","011"],
    "D": ["110","101","101","101","110"],
    "E": ["111","100","110","100","111"],
    "F": ["111","100","110","100","100"],
    "G": ["011","100","101","101","011"],
    "H": ["101","101","111","101","101"],
    "I": ["111","010","010","010","111"],
    "J": ["001","001","001","101","010"],
    "K": ["101","101","110","101","101"],
    "L": ["100","100","100","100","111"],
    "M": ["101","111","111","101","101"],
    "N": ["101","111","111","111","101"],
    "O": ["010","101","101","101","010"],
    "P": ["110","101","110","100","100"],
    "Q": ["010","101","101","111","011"],
    "R": ["110","101","110","101","101"],
    "S": ["011","100","010","001","110"],
    "T": ["111","010","010","010","010"],
    "U": ["101","101","101","101","111"],
    "V": ["101","101","101","101","010"],
    "W": ["101","101","111","111","101"],
    "X": ["101","101","010","101","101"],
    "Y": ["101","101","010","010","010"],
    "Z": ["111","001","010","100","111"],

    "0": ["111","101","101","101","111"],
    "1": ["010","110","010","010","111"],
    "2": ["110","001","010","100","111"],
    "3": ["110","001","010","001","110"],
    "4": ["101","101","111","001","001"],
    "5": ["111","100","110","001","110"],
    "6": ["011","100","111","101","111"],
    "7": ["111","001","010","010","010"],
    "8": ["111","101","111","101","111"],
    "9": ["111","101","111","001","110"],

    ":": ["000","010","000","010","000"],
    ";": ["000","010","000","010","100"],
    ".": ["000","000","000","000","010"],
    ",": ["000","000","000","010","100"],
    "!": ["010","010","010","000","010"],
    "?": ["110","001","010","000","010"],
    "-": ["000","000","111","000","000"],
    "_": ["000","000","000","000","111"],
    "+": ["000","010","111","010","000"],
    "=": ["000","111","000","111","000"],
    "/": ["001","001","010","100","100"],
    "\\": ["100","100","010","001","001"],
    "(": ["001","010","010","010","001"],
    ")": ["100","010","010","010","100"],
    "[": ["011","010","010","010","011"],
    "]": ["110","010","010","010","110"],
    "<": ["001","010","100","010","001"],
    ">": ["100","010","001","010","100"],
    "'": ["010","010","000","000","000"],
    '"': ["101","101","000","000","000"],
    "@": ["111","101","111","100","111"],
    "#": ["101","111","101","111","101"],
    "$": ["011","110","010","011","110"],
    "%": ["101","001","010","100","101"],
    "&": ["010","101","010","101","011"],
    "*": ["000","101","010","101","000"],
    "^": ["010","101","000","000","000"],
    "~": ["000","011","110","000","000"],
    "|": ["010","010","010","010","010"],
    "`": ["100","010","000","000","000"],
}


FONT_5X7 = {
    " ": ["00000","00000","00000","00000","00000","00000","00000"],

    "A": ["01110","10001","10001","11111","10001","10001","10001"],
    "B": ["11110","10001","10001","11110","10001","10001","11110"],
    "C": ["01111","10000","10000","10000","10000","10000","01111"],
    "D": ["11110","10001","10001","10001","10001","10001","11110"],
    "E": ["11111","10000","10000","11110","10000","10000","11111"],
    "F": ["11111","10000","10000","11110","10000","10000","10000"],
    "G": ["01111","10000","10000","10011","10001","10001","01111"],
    "H": ["10001","10001","10001","11111","10001","10001","10001"],
    "I": ["11111","00100","00100","00100","00100","00100","11111"],
    "J": ["00111","00010","00010","00010","10010","10010","01100"],
    "K": ["10001","10010","10100","11000","10100","10010","10001"],
    "L": ["10000","10000","10000","10000","10000","10000","11111"],
    "M": ["10001","11011","10101","10101","10001","10001","10001"],
    "N": ["10001","11001","10101","10011","10001","10001","10001"],
    "O": ["01110","10001","10001","10001","10001","10001","01110"],
    "P": ["11110","10001","10001","11110","10000","10000","10000"],
    "Q": ["01110","10001","10001","10001","10101","10010","01101"],
    "R": ["11110","10001","10001","11110","10100","10010","10001"],
    "S": ["01111","10000","10000","01110","00001","00001","11110"],
    "T": ["11111","00100","00100","00100","00100","00100","00100"],
    "U": ["10001","10001","10001","10001","10001","10001","01110"],
    "V": ["10001","10001","10001","10001","10001","01010","00100"],
    "W": ["10001","10001","10001","10101","10101","10101","01010"],
    "X": ["10001","10001","01010","00100","01010","10001","10001"],
    "Y": ["10001","10001","01010","00100","00100","00100","00100"],
    "Z": ["11111","00001","00010","00100","01000","10000","11111"],

    "0": ["01110","10001","10011","10101","11001","10001","01110"],
    "1": ["00100","01100","00100","00100","00100","00100","01110"],
    "2": ["01110","10001","00001","00010","00100","01000","11111"],
    "3": ["11110","00001","00001","01110","00001","00001","11110"],
    "4": ["00010","00110","01010","10010","11111","00010","00010"],
    "5": ["11111","10000","10000","11110","00001","00001","11110"],
    "6": ["01111","10000","10000","11110","10001","10001","01110"],
    "7": ["11111","00001","00010","00100","01000","01000","01000"],
    "8": ["01110","10001","10001","01110","10001","10001","01110"],
    "9": ["01110","10001","10001","01111","00001","00001","11110"],

    ":": ["00000","01100","01100","00000","01100","01100","00000"],
    ";": ["00000","01100","01100","00000","01100","00100","01000"],
    ".": ["00000","00000","00000","00000","00000","01100","01100"],
    ",": ["00000","00000","00000","00000","01100","00100","01000"],
    "!": ["00100","00100","00100","00100","00100","00000","00100"],
    "?": ["01110","10001","00001","00010","00100","00000","00100"],
    "-": ["00000","00000","00000","11111","00000","00000","00000"],
    "_": ["00000","00000","00000","00000","00000","00000","11111"],
    "+": ["00000","00100","00100","11111","00100","00100","00000"],
    "=": ["00000","00000","11111","00000","11111","00000","00000"],
    "/": ["00001","00010","00010","00100","01000","01000","10000"],
    "\\": ["10000","01000","01000","00100","00010","00010","00001"],
    "(": ["00010","00100","01000","01000","01000","00100","00010"],
    ")": ["01000","00100","00010","00010","00010","00100","01000"],
    "[": ["01110","01000","01000","01000","01000","01000","01110"],
    "]": ["01110","00010","00010","00010","00010","00010","01110"],
    "{": ["00010","00100","00100","01000","00100","00100","00010"],
    "}": ["01000","00100","00100","00010","00100","00100","01000"],
    "<": ["00010","00100","01000","10000","01000","00100","00010"],
    ">": ["01000","00100","00010","00001","00010","00100","01000"],
    "'": ["00100","00100","01000","00000","00000","00000","00000"],
    '"': ["01010","01010","01010","00000","00000","00000","00000"],
    "@": ["01110","10001","10111","10101","10111","10000","01110"],
    "#": ["01010","01010","11111","01010","11111","01010","01010"],
    "$": ["00100","01111","10100","01110","00101","11110","00100"],
    "%": ["11000","11001","00010","00100","01000","10011","00011"],
    "&": ["01100","10010","10100","01000","10101","10010","01101"],
    "*": ["00000","10101","01110","11111","01110","10101","00000"],
    "^": ["00100","01010","10001","00000","00000","00000","00000"],
    "~": ["00000","00000","01001","10110","00000","00000","00000"],
    "|": ["00100","00100","00100","00100","00100","00100","00100"],
    "`": ["01000","00100","00010","00000","00000","00000","00000"],
}


def ask(msg, default=None, cast=str):
    s = input(f"{msg}" + (f" [{default}]" if default is not None else "") + ": ").strip()
    if not s and default is not None:
        return default
    try:
        return cast(s)
    except Exception:
        print("Giá trị không hợp lệ, giữ mặc định.")
        return default


def clamp(v):
    return max(0, min(255, int(v)))


def index(x, y):
    return (y * W + x) * 3


def new_frame():
    return bytearray(FRAME_SIZE)


def set_px(f, x, y, r, g, b, br=None, white_cap=None, color_boost=1.0):
    if not (0 <= x < W and 0 <= y < H):
        return

    if br is None:
        br = CFG["brightness"]

    is_whiteish = r > 180 and g > 180 and b > 180

    if is_whiteish and white_cap is not None:
        rr = min(clamp(r * br), white_cap)
        gg = min(clamp(g * br), white_cap)
        bb = min(clamp(b * br), white_cap)
    else:
        rr = clamp(r * br * color_boost)
        gg = clamp(g * br * color_boost)
        bb = clamp(b * br * color_boost)

    k = index(x, y)

    # WS2812B uses GRB order.
    f[k + 0] = gg
    f[k + 1] = rr
    f[k + 2] = bb


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
            print("[MCU] E: frame trước lỗi, chờ R tiếp...")
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
    if len(frame) != FRAME_SIZE:
        raise ValueError("Frame phải đúng 768 byte")

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
    side = min(w, h)
    x0 = (w - side) // 2
    y0 = (h - side) // 2
    return img.crop((x0, y0, x0 + side, y0 + side))


def image_to_frame(img, contrast=1.15, saturation=1.20, camera_tone=False):
    img = center_crop(img)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(saturation)
    img = img.resize((W, H), Image.Resampling.LANCZOS)

    f = new_frame()

    for y in range(H):
        for x in range(W):
            r, g, b = img.getpixel((x, y))

            if camera_tone:
                set_px(
                    f, x, y, r, g, b,
                    white_cap=CFG["camera_white_cap"],
                    color_boost=CFG["camera_color_boost"],
                )
            else:
                set_px(f, x, y, r, g, b)

    return f


def cv_frame_to_pil(img_bgr):
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(img_rgb)


def pixel_art_frame_from_camera(img_bgr):
    pil_img = cv_frame_to_pil(img_bgr)

    return image_to_frame(
        pil_img,
        contrast=CFG["camera_contrast"],
        saturation=CFG["camera_saturation"],
        camera_tone=True,
    )


def draw_pixel_preview(img_bgr):
    if np is None:
        return img_bgr

    pil_img = cv_frame_to_pil(img_bgr)

    crop = center_crop(pil_img)
    crop = ImageEnhance.Contrast(crop).enhance(CFG["camera_contrast"])
    crop = ImageEnhance.Color(crop).enhance(CFG["camera_saturation"])

    small = crop.resize((W, H), Image.Resampling.LANCZOS)
    preview = small.resize((320, 320), Image.Resampling.NEAREST)
    preview_bgr = cv2.cvtColor(np.array(preview), cv2.COLOR_RGB2BGR)

    cam = img_bgr.copy()
    cam_h, cam_w = cam.shape[:2]
    side = min(cam_w, cam_h)
    x0 = (cam_w - side) // 2
    y0 = (cam_h - side) // 2

    cv2.rectangle(cam, (x0, y0), (x0 + side, y0 + side), (0, 255, 0), 2)
    cv2.putText(cam, "Crop area", (x0 + 8, y0 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cam_resized = cv2.resize(cam, (320, 320))

    cv2.putText(preview_bgr, "16x16 Pixel Art Preview", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    cv2.putText(preview_bgr, "Press Q to stop", (8, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    return cv2.hconcat([cam_resized, preview_bgr])


def option_camera_pixel_art():
    if cv2 is None:
        print("Thiếu OpenCV. Cài: python -m pip install opencv-python")
        return

    if np is None:
        print("Thiếu numpy. Cài: python -m pip install numpy")
        return

    cam_id = ask("Camera ID", 0, int)
    cap = cv2.VideoCapture(cam_id)

    if not cap.isOpened():
        print("Không mở được camera.")
        return

    print("Camera Pixel Art Realtime running.")
    print("Option 1 có giảm trắng + boost màu riêng.")
    print("Nhấn Q trong cửa sổ debug hoặc Ctrl+C để dừng.")

    sent = failed = tick = 0

    try:
        with open_link() as ser:
            first = True

            while True:
                t0 = time.monotonic()
                ok, img = cap.read()

                if not ok:
                    print("Không đọc được frame camera.")
                    time.sleep(0.1)
                    continue

                if CFG["camera_mirror"]:
                    img = cv2.flip(img, 1)

                frame = pixel_art_frame_from_camera(img)

                if send_frame(ser, frame, first):
                    sent += 1
                    first = False
                else:
                    failed += 1
                    time.sleep(0.15)

                if CFG["debug_window"]:
                    preview = draw_pixel_preview(img)
                    cv2.putText(preview, f"sent={sent} failed={failed}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
                    cv2.imshow("ProMatrix Camera Pixel Art", preview)

                    if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                        break

                tick += 1

                time.sleep(max(
                    0.0,
                    1.0 / max(1.0, CFG["fps"]) - (time.monotonic() - t0)
                ))

                if tick % 20 == 0:
                    print(f"camera frames OK={sent}, failed={failed}")

    except KeyboardInterrupt:
        print("\nStopped camera pixel art.")
    except Exception as e:
        print("Lỗi:", e)
    finally:
        cap.release()
        if cv2 is not None:
            cv2.destroyAllWindows()

    print(f"Camera done. OK={sent}, failed={failed}")


def get_font_config():
    if int(CFG["text_font_size"]) == 5:
        return FONT_5X7, 5, 7, 4
    return FONT_3X5, 3, 5, 5


def normalize_text(text, font):
    text = text.upper()
    return "".join(ch if ch in font else " " for ch in text)


def make_text_bitmap(text, pad=True):
    font, fw, fh, _ = get_font_config()
    text = normalize_text(text, font)

    rows = [[] for _ in range(fh)]

    if pad:
        for r in range(fh):
            rows[r].extend([0] * W)

    for ch in text:
        glyph = font.get(ch, font[" "])

        for r in range(fh):
            rows[r].extend(1 if bit == "1" else 0 for bit in glyph[r])
            rows[r].append(0)

    if pad:
        for r in range(fh):
            rows[r].extend([0] * W)

    return rows


def text_frame(text, color=(0, 255, 60)):
    bitmap = make_text_bitmap(text, pad=False)
    width = len(bitmap[0])
    height = len(bitmap)
    _, _, _, y0 = get_font_config()

    f = new_frame()
    x0 = max(0, (W - width) // 2)

    for gy in range(height):
        for gx in range(width):
            if bitmap[gy][gx]:
                set_px(f, x0 + gx, y0 + gy, *color)

    return f


def scroll_text_frame(bitmap, scroll):
    f = new_frame()
    width = len(bitmap[0])
    height = len(bitmap)
    _, _, _, y0 = get_font_config()

    for gy in range(height):
        sy = y0 + gy

        for x in range(W):
            sx = scroll + x

            if 0 <= sx < width and bitmap[gy][sx]:
                phase = (sx // 6) % 4

                if phase == 0:
                    color = (0, 255, 60)
                elif phase == 1:
                    color = (0, 180, 255)
                elif phase == 2:
                    color = (255, 120, 0)
                else:
                    color = (255, 40, 140)

                set_px(f, x, sy, *color)

    return f


def option_text():
    text = ask("Text muốn chạy", CFG["default_text"], str)
    CFG["default_text"] = text

    bitmap = make_text_bitmap(text, pad=True)
    scroll = 0

    sent = failed = 0

    print("Chạy chữ ngang liên tục trên LED 16x16.")
    print(f"Font bitmap {CFG['text_font_size']}x{'5' if CFG['text_font_size'] == 3 else '7'}, nền tắt hoàn toàn.")
    print("Ctrl+C để dừng.")

    try:
        with open_link() as ser:
            first = True

            while True:
                t0 = time.monotonic()
                frame = scroll_text_frame(bitmap, scroll)

                if send_frame(ser, frame, first):
                    sent += 1
                    first = False
                    scroll += 1

                    if scroll >= len(bitmap[0]):
                        scroll = 0
                else:
                    failed += 1
                    time.sleep(0.15)

                time.sleep(max(
                    0.0,
                    1.0 / max(1.0, CFG["text_fps"]) - (time.monotonic() - t0)
                ))

                if sent % 20 == 0 and sent > 0:
                    print(f"text frames OK={sent}, failed={failed}, scroll={scroll}/{len(bitmap[0])}")

    except KeyboardInterrupt:
        print("\nStopped text.")
    except Exception as e:
        print("Lỗi:", e)

    print(f"Text done. OK={sent}, failed={failed}")


def option_image():
    path = Path(input("Image path, ví dụ sample.png: ").strip().strip('"'))

    if not path.exists():
        print("Không thấy file ảnh.")
        return

    frame = image_to_frame(Image.open(path))

    print("Gửi ảnh tĩnh dạng refresh liên tục.")
    print(f"Chu kỳ refresh hiện tại: {CFG['image_refresh']}s")
    print("Ctrl+C để dừng và quay lại menu.")

    sent = failed = 0

    try:
        with open_link() as ser:
            first = True

            while True:
                if send_frame(ser, frame, first):
                    sent += 1
                    first = False
                    print(f"image refresh OK: {sent}")
                else:
                    failed += 1
                    time.sleep(0.15)

                time.sleep(max(0.05, CFG["image_refresh"]))

    except KeyboardInterrupt:
        print("\nStopped image refresh.")
    except Exception as e:
        print("Lỗi:", e)

    print(f"Image done. OK={sent}, failed={failed}")


def option_gif():
    path = Path(input("GIF path: ").strip().strip('"'))

    if not path.exists():
        print("Không thấy file GIF.")
        return

    loops = ask("Loop count, 0 = forever", 0, int)
    gif = Image.open(path)

    frames, delays = [], []

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
        print("\nStopped GIF.")
    except Exception as e:
        print("Lỗi:", e)

    print(f"GIF done. OK={sent}, failed={failed}")


def quick_test_ok():
    print("Test nhanh: hiện chữ OK, nền tắt hoàn toàn.")

    frame = text_frame("OK", color=(0, 255, 60))
    sent = failed = 0

    try:
        with open_link() as ser:
            first = True

            for _ in range(10):
                if send_frame(ser, frame, first):
                    sent += 1
                    first = False
                else:
                    failed += 1
                    time.sleep(0.15)

                time.sleep(max(0.05, CFG["image_refresh"]))

    except Exception as e:
        print("Lỗi:", e)

    print(f"Test OK done. sent={sent}, failed={failed}")


def option_config():
    print("\nCurrent config:")

    for k, v in CFG.items():
        print(f"  {k}: {v}")

    CFG["port"] = ask("COM port", CFG["port"], str)
    CFG["baud"] = ask("Baud", CFG["baud"], int)

    CFG["brightness"] = max(
        0.01,
        min(1.0, ask("Brightness 0.01..1.0", CFG["brightness"], float))
    )

    CFG["camera_white_cap"] = max(
        1,
        min(255, ask("Camera white cap 1..255", CFG["camera_white_cap"], int))
    )

    CFG["camera_color_boost"] = max(
        0.1,
        min(10.0, ask("Camera color boost", CFG["camera_color_boost"], float))
    )

    CFG["fps"] = max(
        1.0,
        ask("FPS for GIF/Camera", CFG["fps"], float)
    )

    CFG["text_fps"] = max(
        1.0,
        ask("FPS for scrolling text", CFG["text_fps"], float)
    )

    font_size = ask("Text font size 3 or 5", CFG["text_font_size"], int)
    CFG["text_font_size"] = 5 if font_size == 5 else 3

    CFG["image_refresh"] = max(
        0.05,
        ask("Static image/Test refresh seconds", CFG["image_refresh"], float)
    )

    CFG["camera_contrast"] = max(
        0.1,
        ask("Camera contrast", CFG["camera_contrast"], float)
    )

    CFG["camera_saturation"] = max(
        0.1,
        ask("Camera saturation", CFG["camera_saturation"], float)
    )

    CFG["default_text"] = ask("Default scrolling text", CFG["default_text"], str)

    d = ask(
        "OpenCV debug window? y/n",
        "y" if CFG["debug_window"] else "n",
        str
    ).lower()

    CFG["debug_window"] = not d.startswith("n")

    m = ask(
        "Mirror camera? y/n",
        "y" if CFG["camera_mirror"] else "n",
        str
    ).lower()

    CFG["camera_mirror"] = not m.startswith("n")

    t = ask("Run quick OK test now? y/n", "n", str).lower()

    if t.startswith("y"):
        quick_test_ok()

    print("Config updated.\n")


def main():
    print("ProMatrix")
    print("Install: python -m pip install pyserial pillow opencv-python numpy")

    while True:
        print("\n1. ProCV Camera Pixel Art")
        print("2. Gửi GIF")
        print("3. Gửi ảnh tĩnh")
        print("4. Chạy text")
        print("5. Cấu hình")
        print("6. Exit")

        c = input("Chọn: ").strip()

        if c == "1":
            option_camera_pixel_art()
        elif c == "2":
            option_gif()
        elif c == "3":
            option_image()
        elif c == "4":
            option_text()
        elif c == "5":
            option_config()
        elif c == "6":
            print("Bye bro :3")
            break
        else:
            print("Chọn 1..6 thôi bro.")


if __name__ == "__main__":
    main()