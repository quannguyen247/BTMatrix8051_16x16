# PC to LED Matrix Wireless Communication via HC-05 & CH552T

This project implements a high-speed wireless data transmission and multimedia display system. The system utilizes the **CH552T** microcontroller as the core processing unit, combined with an **HC-05** Bluetooth module to communicate with a computer (or other Bluetooth-enabled devices), driving a **16x16 LED Matrix (WS2812B)**.

By optimizing the data structure and utilizing specialized hardware communication techniques, the project allows for the display of various content formats ranging from static images and rainbow effects to animations (GIFs) and real-time computer vision applications like Face Detection.

## 🌟 Architecture Overview

The system's operational workflow follows this signal flow:

**Laptop (Transmitter)** ➔ `Bluetooth` ➔ **HC-05 (Receiver)** ➔ `UART (Baud: 115200)` ➔ **CH552T (Processing)** ➔ `Bit-Banging` ➔ **WS2812B LED Matrix (16x16)**

1. **Bluetooth Communication**: The laptop handles heavy computational tasks (such as Face Detection or GIF frame extraction) and streams raw data over Bluetooth to the HC-05 module.
2. **High-Speed UART**: The HC-05 module is configured with a Baud Rate of `115200` to ensure the refresh rate of all 256 pixels on the LED matrix meets performance standards, preventing bottlenecks and screen tearing.
3. **CH552T Processing**: The MCU reads the streamed data via the UART port and maps it into a local frame buffer.
4. **Bit-banging for LED Output**: Since the WS2812B integrated LED chip has strict timing protocols (requiring nanosecond-level clock cycles) and the CH552T lacks a dedicated hardware peripheral for this specific waveform, the system employs **Bit-Banging**. The source code strictly controls machine cycles to manually toggle the output pin at high frequencies, pushing the 24-bit RGB data stream to the LED Matrix with absolute precision.

## 📁 Directory Structure

- `source/`: A collection of source codes dedicated to system control. It includes various flexible hardware interaction modules and scripts: from rainbow sequences and frame parsing to testing scripts. These codes are the core of all display rendering operations.
- `CH552T/`: Contains core libraries and base configurations for the MCU. *(**Copyright/Attribution Note**: Important files in this directory are selectively extracted from the official open-source repository [WeActStudio.CH552CoreBoard](https://github.com/WeActStudio/WeActStudio.CH552CoreBoard). All original intellectual property rights for this directory belong to WeActStudio).*
- `CH55x/`: Contains MCU technical resources:
  - `Datasheet/`: Full hardware specifications and datasheets for reference.
  - `Driver/`: MCU connection drivers supporting both Windows **32-bit** and **64-bit** operating systems.
- `Schemantic.json`: The project's schematic diagram, providing a clear overview of pinouts and overall electronic design.

## 🛠 Setup & Flashing Instructions

### 1. WCH USB Driver Installation

For your computer to recognize the CH552T MCU via the USB Bootloader, you must install the WCH driver:
- Navigate to the `CH55x/Driver/` directory.
- Run the driver installer corresponding to your Windows architecture:
  - **64-bit**: Open the `WIN 1X` folder, use the compatible `CH375WDM.INF` / `DRVSETUP64` or integrated x64 setup files.
  - **32-bit**: Use the setup files supporting x86 versions located in the root Driver directory.

### 2. Adding CH552T Board to Arduino IDE

1. Open the Arduino IDE.
2. Go to **File** ➔ **Preferences** (or use the shortcut `Ctrl + ,`).
3. Copy and paste the following JSON URL into the **Additional Boards Manager URLs** field:
   ```
   https://raw.githubusercontent.com/DeqingSun/ch55xduino/ch55xduino/package_ch55xduino_mcs51_index.json
   ```
4. Navigate to **Tools** ➔ **Board** ➔ **Boards Manager...**
5. In the search bar, type `CH55xDuino` and click **Install** to download the core.
6. Once installed, go back to **Tools** ➔ **Board** and change the board type to `CH55x Boards` ➔ `CH552`.

### 3. How to Flash (Upload) Code to CH552T

The CH552T chip flashes via a USB Bootloader mechanism that requires a strict timing sequence:
1. Completely unplug the USB cable connecting the board to the computer (power off).
2. **Press and hold** the Bootloader button on the board (this button is connected to pin **P3.6**).
3. **While continuing to hold the P3.6 button**, plug the USB cable into the computer to power it on.
4. The chip will now enter bootloader mode. Click the **Upload** button in the Arduino IDE.
5. As soon as the IDE finishes compiling and the terminal displays "Uploading..." (indicating the IDE has connected and is pushing the code), **release the P3.6 button** so the flashing process can proceed smoothly.

## 🚀 Applications & Potential

By streaming remote frames via UART/Bluetooth protocol at 115200bps to the WS2812B, the project offloads computational resources from the MCU and shifts the "heavy lifting" to the PC. The system is perfectly capable of handling:
* Rendering any static image (Static Imagery) at a 16x16 resolution.
* Displaying multimedia content, including animations / GIFs (e.g., the classic *Bad Apple* sequence).
* Integrating Computer Vision pipelines (image recognition/Machine Learning) on PC, such as real-time **Face Detection**, and instantaneously outputting the tracking box to the embedded LED screen.

## 📄 License
This project is licensed under the terms of the license found in the [LICENSE](LICENSE) file located in the root directory. Please see that file for more details.