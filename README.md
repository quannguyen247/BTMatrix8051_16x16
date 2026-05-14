# BTMatrix8051

Wireless 16×16 WS2812B LED matrix driven by a CH552T and controlled from a PC through an HC-05 Bluetooth module.

## Overview

```text
PC / Laptop
  -> Bluetooth SPP
  -> HC-05
  -> UART 115200 8N1
  -> CH552T
  -> WS2812B 16×16
```

The PC generates a 16×16 frame, sends it over Bluetooth, and the CH552T outputs the data to the WS2812B matrix by bit-banging.

Main programs:

| File | Role |
|---|---|
| `source/ProMatrix.py` | PC host program: image, GIF, text, camera pixel-art |
| `source/CH552T/CH552T.ino` | Main CH552T firmware: UART receiver + WS2812B driver |

## Features

- HC-05 Bluetooth SPP wireless transmission
- 16×16 WS2812B matrix, 256 LEDs
- 768-byte GRB frame buffer
- UART frame protocol with header, checksum, and handshake
- Static image mode
- GIF mode
- Scrolling text mode
- Camera pixel-art realtime mode
- Separate C demos for UART and LED testing

## Repository Structure

```text
DOANVXL/
├── CH55x/
│   ├── Datasheet/
│   │   ├── CH552DS_zh-CN.PDF
│   │   └── CH552DS1_en.PDF
│   │
│   ├── Driver/
│   │   ├── DRVSETUP64/
│   │   ├── WIN 1X/
│   │   ├── CH375W64.sys
│   │   ├── CH375WDM.CAT
│   │   ├── CH375WDM.INF
│   │   ├── CH375WDM.sys
│   │   └── SETUP.EXE
│   │
│   └── HDK/
│       ├── WeAct-CH55xCoreBoard-V10 Board Shape...
│       └── WeAct-CH55xCoreBoard-V10 SchDoc.pdf
│
├── source/
│   ├── CH552T/
│   │   └── CH552T.ino
│   │
│   ├── chase.c
│   ├── loopback.c
│   ├── ProMatrix.py
│   ├── rainbow.c
│   ├── rgb.c
│   └── sample.png
│
├── .gitignore
├── LICENSE
├── README.md
└── schematic.png
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
| `source/sample.png` | Sample image for image mode |

## Hardware Connection

### HC-05 to CH552T

| HC-05 | CH552T |
|---|---|
| VCC | 5V or 3.3V, depending on HC-05 board |
| GND | GND |
| TXD | UART RXD |
| RXD | UART TXD, preferably through level shifting |

### WS2812B to CH552T

| WS2812B | CH552T |
|---|---|
| DIN | P1.1 |
| 5V | External 5V supply |
| GND | Common GND |

Notes:

- HC-05 RXD is usually 3.3V logic. Use a voltage divider from CH552T TXD to HC-05 RXD if needed.
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

The PC sends the next frame only when the MCU is ready. This prevents UART reception from interrupting WS2812B bit-banging.

## Performance at 115200 Baud

One frame contains 772 bytes including header and checksum.

```text
UART 8N1 throughput = 115200 / 10 = 11520 bytes/s
UART frame time     = 772 / 11520 ≈ 67 ms
WS2812B refresh     ≈ 7.7 ms
Best-case frame     ≈ 74.7 ms
Best-case FPS       ≈ 13.4 FPS
```

Real FPS is lower because of Bluetooth SPP latency, Python serial overhead, Windows scheduling, and handshake delay. Around 7–12 FPS is normal.

## Arduino IDE Setup for CH552T

### 1. Install WCH driver

Driver files are in:

```text
CH55x/Driver/
```

Use:

```text
32-bit Windows: run SETUP.EXE
64-bit Windows: use the 64-bit driver folder, for example DRVSETUP64/
```

### 2. Install CH55xDuino board package

Arduino IDE:

```text
File -> Preferences -> Additional Boards Manager URLs
```

Add:

```text
https://raw.githubusercontent.com/DeqingSun/ch55xduino/ch55xduino/package_ch55xduino_mcs51_index.json
```

Then:

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

Do **not** use `Default CDC` for the main firmware. Use:

```text
USER CODE w/ 0B USB ram
```

This project needs XRAM for the 768-byte LED frame buffer. CDC USB mode reserves USB RAM, so it is not recommended here.

### 4. Manual upload

Use this upload sequence:

```text
1. Unplug the CH552T board.
2. Hold the bootloader button connected to P3.6.
3. Plug the board into USB while still holding the button.
4. Click Upload in Arduino IDE quickly.
5. Release the button only after upload succeeds.
```

Some setups can be configured for automatic upload, but that reserves RAM for upload/USB configuration. For this project, manual bootloader upload with `USER CODE w/ 0B USB ram` is preferred.

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

Menu:

```text
1. ProCV Camera Pixel Art
2. Send GIF
3. Send static image
4. Scrolling text
5. Config
6. Exit
```

Use option `5. Config` to set the Bluetooth COM port.

## HC-05 COM Port

After pairing HC-05 with Windows, use the **Outgoing** Bluetooth COM port.

Example:

```text
Standard Serial over Bluetooth link (COM11)
```

If the port is not `COM11`, update it in `ProMatrix.py` option 5.

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
COM value in ProMatrix.py is correct
```

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

If your matrix is serpentine, update the Python `index(x, y)` mapping.

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
- The stable MCU role is: receive frame, verify checksum, output WS2812B, ACK.

## License

This project is licensed under the [Apache License 2.0](LICENSE).
