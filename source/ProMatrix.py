import time
from pathlib import Path
import serial
from PIL import Image, ImageEnhance

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

# Connection config
PORT = "COM5"
BAUD = 115200
CAMERA_ID = 0

# Main user settings
BRIGHTNESS = 0.05
DEBUG_WINDOW = True
DEFAULT_TEXT = "TEST OK"
FPS = 10.0

# Matrix/protocol config
W, H = 16, 16
FRAME_SIZE = W * H * 3

SOF = bytes([0xA5, 0x5A])
ACK_R = b"R"
ACK_K = b"K"
ACK_E = b"E"

FONT_3X5 = {
    " ": "000/000/000/000/000",

    "A": "010/101/111/101/101", "B": "110/101/110/101/110",
    "C": "011/100/100/100/011", "D": "110/101/101/101/110",
    "E": "111/100/110/100/111", "F": "111/100/110/100/100",
    "G": "011/100/101/101/011", "H": "101/101/111/101/101",
    "I": "111/010/010/010/111", "J": "001/001/001/101/010",
    "K": "101/101/110/101/101", "L": "100/100/100/100/111",
    "M": "101/111/111/101/101", "N": "101/111/111/111/101",
    "O": "010/101/101/101/010", "P": "110/101/110/100/100",
    "Q": "010/101/101/111/011", "R": "110/101/110/101/101",
    "S": "011/100/010/001/110", "T": "111/010/010/010/010",
    "U": "101/101/101/101/111", "V": "101/101/101/101/010",
    "W": "101/101/111/111/101", "X": "101/101/010/101/101",
    "Y": "101/101/010/010/010", "Z": "111/001/010/100/111",

    "0": "111/101/101/101/111", "1": "010/110/010/010/111",
    "2": "110/001/010/100/111", "3": "110/001/010/001/110",
    "4": "101/101/111/001/001", "5": "111/100/110/001/110",
    "6": "011/100/111/101/111", "7": "111/001/010/010/010",
    "8": "111/101/111/101/111", "9": "111/101/111/001/110",

    ":": "000/010/000/010/000", ";": "000/010/000/010/100",
    ".": "000/000/000/000/010", ",": "000/000/000/010/100",
    "!": "010/010/010/000/010", "?": "110/001/010/000/010",
    "-": "000/000/111/000/000", "_": "000/000/000/000/111",
    "+": "000/010/111/010/000", "=": "000/111/000/111/000",
    "/": "001/001/010/100/100", "\\": "100/100/010/001/001",
    "(": "001/010/010/010/001", ")": "100/010/010/010/100",
    "[": "011/010/010/010/011", "]": "110/010/010/010/110",
    "<": "001/010/100/010/001", ">": "100/010/001/010/100",
    "'": "010/010/000/000/000", '"': "101/101/000/000/000",
    "@": "111/101/111/100/111", "#": "101/111/101/111/101",
    "$": "011/110/010/011/110", "%": "101/001/010/100/101",
    "&": "010/101/010/101/011", "*": "000/101/010/101/000",
    "^": "010/101/000/000/000", "~": "000/011/110/000/000",
    "|": "010/010/010/010/010", "`": "100/010/000/000/000",
}

def clamp(v):
    return max(0, min(255, int(v)))

def new_frame():
    return bytearray(FRAME_SIZE)

def set_px(frame, x, y, r, g, b):
    if not (0 <= x < W and 0 <= y < H):
        return

    k = (y * W + x) * 3

    frame[k + 0] = clamp(g * BRIGHTNESS)
    frame[k + 1] = clamp(r * BRIGHTNESS)
    frame[k + 2] = clamp(b * BRIGHTNESS)

def make_packet(frame):
    checksum = sum(frame) & 0xFFFF
    return SOF + bytes(frame) + bytes([checksum & 0xFF, checksum >> 8])

def wait_for(ser, target, timeout):
    end = time.monotonic() + timeout

    while time.monotonic() < end:
        b = ser.read(1)

        if b == target:
            return True

        if b == ACK_E:
            print("[MCU] E: frame error")
            return False

    return False

def send_frame(ser, frame, first=False):
    if not wait_for(ser, ACK_R, 10.0 if first else 2.0):
        print("READY 'R' not found. Check COM/HC-05/UART.")
        return False

    ser.write(make_packet(frame))
    ser.flush()

    if not wait_for(ser, ACK_K, 3.0):
        print("ACK 'K' not found.")
        return False

    return True

def open_link():
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUD,
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

    print(f"Opened {PORT} @ {BAUD}")
    return ser

def center_crop(img):
    img = img.convert("RGB")
    w, h = img.size
    side = min(w, h)

    x0 = (w - side) // 2
    y0 = (h - side) // 2

    return img.crop((x0, y0, x0 + side, y0 + side))

def image_to_frame(img):
    img = center_crop(img)
    img = ImageEnhance.Contrast(img).enhance(1.20)
    img = ImageEnhance.Color(img).enhance(1.25)
    img = img.resize((W, H), Image.Resampling.LANCZOS)

    frame = new_frame()

    for y in range(H):
        for x in range(W):
            set_px(frame, x, y, *img.getpixel((x, y)))

    return frame

def cv_to_pil(img_bgr):
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(img_rgb)

def camera_preview(img_bgr):
    pil = center_crop(cv_to_pil(img_bgr))

    small = pil.resize((W, H), Image.Resampling.LANCZOS)
    big = small.resize((320, 320), Image.Resampling.NEAREST)
    big_bgr = cv2.cvtColor(np.array(big), cv2.COLOR_RGB2BGR)

    cam = img_bgr.copy()
    h, w = cam.shape[:2]
    side = min(w, h)

    x0 = (w - side) // 2
    y0 = (h - side) // 2

    cv2.rectangle(cam, (x0, y0), (x0 + side, y0 + side), (0, 255, 0), 2)
    cam = cv2.resize(cam, (320, 320))

    cv2.putText(
        big_bgr,
        "16x16 preview | Q to stop",
        (8, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
    )

    return cv2.hconcat([cam, big_bgr])

def run_camera():
    if cv2 is None or np is None:
        print("Missing libraries. Install with: python -m pip install opencv-python numpy")
        return

    cap = cv2.VideoCapture(CAMERA_ID)

    if not cap.isOpened():
        print("Cannot open camera.")
        return

    ok_count = 0
    fail_count = 0

    print("Camera pixel art. Q or Ctrl+C to stop.")

    try:
        with open_link() as ser:
            first = True

            while True:
                t0 = time.monotonic()

                ok, img = cap.read()
                if not ok:
                    continue

                img = cv2.flip(img, 1)
                frame = image_to_frame(cv_to_pil(img))

                if send_frame(ser, frame, first):
                    ok_count += 1
                    first = False
                else:
                    fail_count += 1

                if DEBUG_WINDOW:
                    preview = camera_preview(img)

                    cv2.putText(
                        preview,
                        f"OK={ok_count} ERR={fail_count}",
                        (10, 52),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (255, 255, 255),
                        1,
                    )

                    cv2.imshow("ProMatrix Camera", preview)

                    if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                        break

                time.sleep(max(0.0, 1.0 / max(1.0, FPS) - (time.monotonic() - t0)))

    except KeyboardInterrupt:
        pass

    finally:
        cap.release()
        cv2.destroyAllWindows()

def run_image():
    raw = input("Image path [sample.png]: ").strip().strip('"')
    path = Path(raw or "sample.png")

    if not path.exists():
        print("Image not found.")
        return

    frame = image_to_frame(Image.open(path))

    ok_count = 0
    fail_count = 0

    print("Static image refresh. Ctrl+C to stop.")

    try:
        with open_link() as ser:
            first = True

            while True:
                t0 = time.monotonic()

                if send_frame(ser, frame, first):
                    ok_count += 1
                    first = False
                else:
                    fail_count += 1

                print(f"OK={ok_count} ERR={fail_count}", end="\r")
                time.sleep(max(0.0, 1.0 / max(1.0, FPS) - (time.monotonic() - t0)))

    except KeyboardInterrupt:
        print("\nStopped image.")

def make_text_bitmap(text):
    rows = [[0] * W for _ in range(5)]
    text = "".join(ch if ch in FONT_3X5 else " " for ch in text.upper())

    for ch in text:
        glyph = FONT_3X5[ch].split("/")

        for y, row in enumerate(glyph):
            rows[y].extend(1 if bit == "1" else 0 for bit in row)
            rows[y].append(0)

    for row in rows:
        row.extend([0] * W)

    return rows

def text_frame(bitmap, scroll):
    frame = new_frame()

    colors = [
        (0, 255, 60),
        (0, 180, 255),
        (255, 120, 0),
        (255, 40, 140),
    ]

    y0 = 5

    for y, row in enumerate(bitmap):
        for x in range(W):
            sx = scroll + x

            if 0 <= sx < len(row) and row[sx]:
                set_px(frame, x, y0 + y, *colors[(sx // 5) % len(colors)])

    return frame

def run_text():
    text = input(f"Text [{DEFAULT_TEXT}]: ").strip() or DEFAULT_TEXT
    bitmap = make_text_bitmap(text)

    scroll = 0
    ok_count = 0
    fail_count = 0

    print("Scrolling text. Ctrl+C to stop.")

    try:
        with open_link() as ser:
            first = True

            while True:
                t0 = time.monotonic()
                frame = text_frame(bitmap, scroll)

                if send_frame(ser, frame, first):
                    ok_count += 1
                    first = False
                    scroll = (scroll + 1) % len(bitmap[0])
                else:
                    fail_count += 1

                if ok_count % 20 == 0:
                    print(f"OK={ok_count} ERR={fail_count} scroll={scroll}", end="\r")

                time.sleep(max(0.0, 1.0 / max(1.0, FPS) - (time.monotonic() - t0)))

    except KeyboardInterrupt:
        print("\nStopped text.")

def main():
    while True:
        print("\n1. Camera Pixel Art")
        print("2. Static Image")
        print("3. Scrolling Text")
        print("4. Exit")

        choice = input("Choose: ").strip()

        if choice == "1":
            run_camera()
        elif choice == "2":
            run_image()
        elif choice == "3":
            run_text()
        elif choice == "4":
            break
        else:
            print("Please choose 1 to 4.")

if __name__ == "__main__":
    main()