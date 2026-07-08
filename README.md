# BTMatrix8051

Wireless 16×16 WS2812B LED matrix controlled from a PC through an HC-05 Bluetooth module and driven by a CH552T 8051-based microcontroller.

## Overview

```text
PC / Laptop
  -> Bluetooth SPP
  -> HC-05
  -> UART 115200 8N1
  -> CH552T
  -> WS2812B 16×16
```

The PC generates 16×16 display frames and sends them over Bluetooth. The HC-05 forwards the data to the CH552T through UART. The CH552T verifies each frame and outputs the LED data to the WS2812B matrix using cycle-controlled bit-banging.

Main programs:

| File | Role |
|---|---|
| `source/ProMatrix.py` | PC host program for camera pixel-art, static image, and scrolling text |
| `source/CH552T/CH552T.ino` | Main CH552T firmware for UART receiving and WS2812B output |

## Features

- HC-05 Bluetooth SPP wireless transmission
- 16×16 WS2812B matrix, 256 RGB LEDs
- 768-byte GRB frame buffer
- UART frame protocol with header, checksum, and R/K/E handshake
- MCU repeatedly sends `R` while idle, so the PC host can reconnect without resetting the board
- Camera pixel-art realtime mode
- Static image refresh mode
- Scrolling text mode
- Standalone C demos for UART and LED testing

## Repository Structure

```text
DOANVXL/
├── CH55x/
│   ├── Datasheet/
│   │   ├── CH552DS_zh-CN.PDF
│   │   └── CH552DS1_en.PDF
│   ├── Driver/
│   │   ├── DRVSETUP64/
│   │   ├── WIN 1X/
│   │   ├── CH375W64.sys
│   │   ├── CH375WDM.CAT
│   │   ├── CH375WDM.INF
│   │   ├── CH375WDM.sys
│   │   └── SETUP.EXE
│   └── HDK/
│       ├── WeAct-CH55xCoreBoard-V10 Board Shape.pdf
│       └── WeAct-CH55xCoreBoard-V10 SchDoc.pdf
│
├── source/
│   ├── CH552T/
│   │   └── CH552T.ino
│   ├── chase.c
│   ├── loopback.c
│   ├── ProMatrix.py
│   ├── rainbow.c
│   ├── rgb.c
│   └── sample.png
│
├── .gitignore
├── HC-05 Datasheet.pdf
├── LICENSE
├── README.md
└── WS2812B-LED-datasheet.pdf
```

## Folder Notes

| Path | Description |
|---|---|
| `CH55x/Datasheet/` | CH552 datasheets |
| `CH55x/Driver/` | WCH USB driver files |
| `CH55x/HDK/` | WeAct CH55x board hardware reference files |
| `source/CH552T/CH552T.ino` | Main MCU firmware |
| `source/ProMatrix.py` | Main PC host application |
| `source/loopback.c` | UART 115200 loopback test |
| `source/rainbow.c` | WS2812B rainbow demo |
| `source/rgb.c` | RGB/GRB color test |
| `source/chase.c` | LED chase demo |
| `source/sample.png` | Sample image for static image mode |
| `HC-05 Datasheet.pdf` | HC-05 Bluetooth module datasheet |
| `WS2812B-LED-datasheet.pdf` | WS2812B RGB LED datasheet |

*The files in the `CH55x/` directory are sourced from the official [WeAct Studio CH552 Core Board repository](https://github.com/WeActStudio/WeActStudio.CH552CoreBoard).*

## Hardware Connection

### HC-05 to CH552T

| HC-05 | CH552T |
|---|---|
| VCC | 5V |
| GND | GND |
| TXD | UART RXD |
| RXD | UART TXD |

### WS2812B to CH552T

| WS2812B | CH552T |
|---|---|
| DIN | P1.1 |
| 5V | External 5V supply |
| GND | Common GND |

Notes:

- The LED matrix should use a separate 5V supply.
- CH552T, HC-05, and LED matrix must share GND.

## Frame Protocol

Frame format:

```text
0xA5 0x5A + 768-byte GRB payload + checksum16
```

| Field | Size | Description |
|---|---:|---|
| Header | 2 bytes | `0xA5 0x5A` |
| Payload | 768 bytes | 256 LEDs × 3 bytes, GRB order |
| Checksum | 2 bytes | `sum(payload) & 0xFFFF`, little-endian |

Handshake:

```text
MCU -> PC    'R'    ready
PC  -> MCU   frame
MCU -> PC    'K'    ok
MCU -> PC    'E'    error
```

The current firmware sends `R` repeatedly while idle and scans for the frame header `0xA5 0x5A`. When the PC sees `R`, it sends one complete frame. After receiving and checking the frame, the MCU outputs WS2812B data and replies with `K` or `E`.

This means each display frame still follows one handshake cycle:

```text
R -> frame -> K/E
```

At `FPS = 10`, the PC attempts to send 10 complete display frames per second, so there are about 10 handshake cycles per second if UART/Bluetooth timing allows it. This keeps UART reception separated from WS2812B bit-banging and allows the Python host to be stopped and started again without pressing the reset button.

## Performance at 115200 Baud

One full frame contains 772 bytes including header and checksum.

```text
UART 8N1 throughput = 115200 / 10 = 11520 bytes/s
UART frame time     = 772 / 11520 ≈ 67 ms
WS2812B refresh     ≈ 7.7 ms
Best-case frame     ≈ 74.7 ms
Best-case FPS       ≈ 13.4 FPS
```

Real FPS is usually lower because of Bluetooth SPP latency, Python serial overhead, Windows scheduling, and handshake delay. Around 7–12 FPS is normal.

## Arduino IDE Setup for CH552T

### 1. Install WCH driver

Driver files are in:

```text
CH55x/Driver/
```

Use:

```text
32-bit Windows: run SETUP.EXE
64-bit Windows: use DRVSETUP64/
```

### 2. Install CH55xDuino board package

Open Arduino IDE:

```text
File -> Preferences -> Additional Boards Manager URLs
```

Add:

```text
https://raw.githubusercontent.com/DeqingSun/ch55xduino/ch55xduino/package_ch55xduino_mcs51_index.json
```

Then install the board package:

```text
Tools -> Board -> Boards Manager...
Search: CH55xDuino
Install
```

### 3. Board settings

Use these Arduino IDE settings:

```text
Board: CH552 Board
Bootloader pin: P3.6 (D+) pull-up
Clock Source: 24 MHz (internal), 5V
Upload method: USB
USB Settings: USER CODE w/ 0B USB ram
```

Do not use `Default CDC` for the main firmware. The project uses a 768-byte LED frame buffer, so `USER CODE w/ 0B USB ram` is preferred.

### 4. Manual upload

```text
1. Unplug the CH552T board.
2. Hold the bootloader button connected to P3.6.
3. Plug the board into USB while still holding the button.
4. Click Upload in Arduino IDE quickly.
5. Release the button only after upload succeeds.
```

Automatic upload may reserve USB/XRAM resources. For this project, manual bootloader upload with `USER CODE w/ 0B USB ram` is recommended.

## Flash Main Firmware

Open:

```text
source/CH552T/CH552T.ino
```

Upload it using the Arduino IDE settings above.

## Run PC Host

Install Python dependencies:

```bash
python -m pip install pyserial pillow opencv-python numpy
```

Run from the `source/` folder:

```bash
python ProMatrix.py
```

Current menu:

```text
1. Camera Pixel Art
2. Static Image
3. Scrolling Text
4. Exit
```

Main settings are edited directly at the top of `ProMatrix.py`:

```python
PORT = "COM5"
BAUD = 115200
CAMERA_ID = 0

BRIGHTNESS = 0.05
DEBUG_WINDOW = True
DEFAULT_TEXT = "TEST OK"
FPS = 10.0
```

## HC-05 COM Port

After pairing HC-05 with Windows, use the **Outgoing** Bluetooth COM port.

Example:

```text
Standard Serial over Bluetooth link (COM5)
```

If Windows assigns another port, update `PORT` in `source/ProMatrix.py`.

## Demo Files

### `loopback.c`

Tests whether UART 115200 works correctly on the CH552T itself.

Use it before connecting the HC-05:

```text
1. Short TX0 and RX0 on the board.
2. Flash loopback.c.
3. Send UART data at 115200 baud.
4. The MCU should receive back the transmitted data.
```

This confirms the MCU UART configuration before adding Bluetooth.

### Other demos

| File | Purpose |
|---|---|
| `rgb.c` | Solid color / GRB order test |
| `rainbow.c` | WS2812B timing and animation test |
| `chase.c` | LED indexing and chase effect test |

## Troubleshooting

### Upload fails

Check:

```text
Driver installed
Board = CH552 Board
USB Settings = USER CODE w/ 0B USB ram
Bootloader pin = P3.6 (D+) pull-up
Upload method = USB
```

Then retry manual upload:

```text
Unplug -> hold P3.6 -> plug USB -> click Upload -> release after success
```

### Python cannot open COM port

Check:

```text
HC-05 is paired
Using Outgoing COM port
No other serial monitor is using the port
PORT in ProMatrix.py is correct
```

### Camera cannot be opened

Check:

```text
Camera is enabled in BIOS / Windows settings
No other app is using the camera
CAMERA_ID in ProMatrix.py is correct
```

Try:

```python
CAMERA_ID = 1
```

if `CAMERA_ID = 0` does not work.

### LED turns red

The MCU shows dim red on frame error.

Common causes:

```text
Wrong COM port
Bluetooth disconnected
Wrong baud rate
UART TX/RX wiring issue
Checksum error
PC stopped sending frames
```

### Text looks scrambled

The current mapping is linear row-major:

```text
row 0: left -> right
row 1: left -> right
row 2: left -> right
...
```

If your matrix is serpentine, update the Python pixel mapping.

### Colors are wrong

WS2812B expects GRB order, not RGB.

```text
G, R, B
```

Both the PC host and MCU firmware use GRB.

## Notes

- Keep the CH552T firmware simple.
- Do not add UART interrupts while bit-banging WS2812B.
- Do not modify the WS2812B NOP timing unless measured again.
- Add new display modes on the PC side in `ProMatrix.py`.
- The stable MCU role is: advertise READY while idle, receive one frame, verify checksum, output WS2812B, ACK.

## References & Datasheets

- **HC-05 Bluetooth Module Datasheet**: [Original PDF Link](https://components101.com/sites/default/files/component_datasheet/HC-05%20Datasheet.pdf)
- **WS2812B RGB LED Datasheet**: [Original PDF Link](https://cdn.sparkfun.com/assets/e/6/1/f/4/WS2812B-LED-datasheet.pdf)
- **WeAct Studio CH552 Core Board**: [WeActStudio/WeActStudio.CH552CoreBoard](https://github.com/WeActStudio/WeActStudio.CH552CoreBoard)

## License

This project is licensed under the [Apache License 2.0](LICENSE).
