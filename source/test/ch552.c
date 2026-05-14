/*
 * HC-05 Bluetooth Receiver for WS2812B 16x16 LED Matrix
 *
 * System flow:
 *   PC/Python -> Bluetooth HC-05 -> UART0 -> CH552T -> WS2812B LED Matrix
 *
 * Frame format sent from PC:
 *   A5 5A + 768 data bytes + checksum16
 *
 * Data format:
 *   16 x 16 LEDs = 256 LEDs
 *   Each LED uses 3 bytes in GRB order
 *   Total frame size = 256 * 3 = 768 bytes
 *
 * Handshake protocol:
 *   1. MCU sends 'R' to tell PC it is ready.
 *   2. PC sends exactly one complete frame.
 *   3. MCU verifies checksum.
 *   4. MCU outputs the frame to WS2812B.
 *   5. MCU sends 'K' if successful, or 'E' if an error occurs.
 *
 * Timing note:
 *   WS2812B requires strict signal timing.
 *   Therefore, UART data must not interrupt WS2812B_Show().
 *   The PC only sends a new frame after receiving 'R' or 'K'.
 */

#include <stdint.h>

#define LED_PIN      1
#define NUM_LEDS     256
#define BUFFER_SIZE  768

#define SOF1         0xA5
#define SOF2         0x5A

#define ACK_READY    'R'
#define ACK_OK       'K'
#define ACK_ERR      'E'

__xdata uint8_t led_buffer[BUFFER_SIZE];

__data uint16_t i;
__data uint8_t  b, j;


/*
 * Simple software delay.
 * This is used only for visible boot/debug effects,
 * not for UART baud generation or WS2812B bit timing.
 */
void delay_ms(uint16_t ms) {
    uint16_t x, y;

    for (x = 0; x < ms; x++) {
        for (y = 0; y < 2000; y++) {
            __asm__("nop");
        }
    }
}


/*
 * Initialize UART0 at 115200 baud using Timer1.
 *
 * The MCU clock is configured at 24 MHz.
 * Timer1 runs in 8-bit auto-reload mode.
 * TH1 = 243 gives approximately 115384 baud,
 * which is close enough to 115200 for reliable UART communication.
 *
 * UART is handled by polling instead of interrupt.
 * This prevents UART interrupt code from disturbing WS2812B timing.
 */
void UART0_Init(void) {
    T2MOD |= bTMR_CLK | bT1_CLK;

    TMOD &= ~0xF0;
    TMOD |=  bT1_M1;

    PCON |= SMOD;

    TH1 = 243;
    TL1 = 243;

    TF1 = 0;
    TR1 = 1;

    SM0 = 0;
    SM1 = 1;
    REN = 1;

    TI = 0;
    RI = 0;

    /*
     * Configure P3.1 as UART TXD0 output.
     * P3.0 is used as UART RXD0 input by the UART peripheral.
     */
    P3_MOD_OC &= ~(1 << 1);
    P3_DIR_PU |=  (1 << 1);

    ES = 0;
    EA = 1;
}


/*
 * Send one byte through UART0.
 * The function waits until the previous byte has finished transmitting.
 */
void UART0_SendByte(uint8_t v) {
    SBUF = v;

    while (!TI);

    TI = 0;
}


/*
 * Read one byte from UART0 with timeout.
 *
 * Return value:
 *   1: one byte was received successfully
 *   0: timeout occurred
 *
 * This avoids blocking forever if the Bluetooth link is disconnected
 * or the PC stops sending data in the middle of a frame.
 */
uint8_t UART0_ReadByteTimeout(uint8_t *out, uint16_t timeout_outer) {
    uint16_t t;
    uint16_t spin;

    for (t = 0; t < timeout_outer; t++) {
        for (spin = 0; spin < 250; spin++) {
            if (RI) {
                RI = 0;
                *out = SBUF;
                return 1;
            }
        }
    }

    return 0;
}


/*
 * Receive one complete 16x16 LED frame from UART.
 *
 * Expected packet:
 *   SOF1 SOF2 + 768 data bytes + checksum low byte + checksum high byte
 *
 * The checksum is:
 *   sum of all 768 data bytes, limited to 16 bits.
 *
 * Return value:
 *   1: frame received correctly
 *   0: timeout, invalid header, or checksum error
 */
uint8_t ReceiveFrame(void) {
    uint8_t v;
    uint8_t lo, hi;

    uint16_t k;
    uint16_t sum_calc = 0;
    uint16_t sum_rx;

    /*
     * Search for the start-of-frame marker A5 5A.
     * This helps the MCU recover if noise or old bytes exist in the UART buffer.
     */
    while (1) {
        if (!UART0_ReadByteTimeout(&v, 60000U)) {
            return 0;
        }

        if (v == SOF1) {
            if (!UART0_ReadByteTimeout(&v, 3000U)) {
                return 0;
            }

            if (v == SOF2) {
                break;
            }
        }
    }

    /*
     * Receive the full GRB frame into RAM.
     * The LED output is not updated here yet.
     */
    for (k = 0; k < BUFFER_SIZE; k++) {
        if (!UART0_ReadByteTimeout(&v, 3000U)) {
            return 0;
        }

        led_buffer[k] = v;
        sum_calc += v;
    }

    /*
     * Receive checksum in little-endian order:
     * low byte first, then high byte.
     */
    if (!UART0_ReadByteTimeout(&lo, 3000U)) {
        return 0;
    }

    if (!UART0_ReadByteTimeout(&hi, 3000U)) {
        return 0;
    }

    sum_rx = (uint16_t)lo | ((uint16_t)hi << 8);

    return (sum_calc == sum_rx) ? 1 : 0;
}


/*
 * Output the current frame buffer to the WS2812B LED matrix.
 *
 * WS2812B uses a one-wire protocol with strict timing.
 * Interrupts are disabled during this function to keep the waveform stable.
 *
 * Each byte is sent from MSB to LSB.
 * Data order in led_buffer is GRB, which matches WS2812B convention.
 */
void WS2812B_Show(void) {
    EA = 0;

    for (i = 0; i < BUFFER_SIZE; i++) {
        b = led_buffer[i];

        for (j = 0; j < 8; j++) {
            if (b & 0x80) {
                /*
                 * Send bit '1':
                 * high time is longer than low time.
                 */
                P1_1 = 1;
                __asm__(
                    "nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop"
                    "\nnop\nnop\nnop\nnop\nnop\nnop\nnop"
                );

                P1_1 = 0;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop");
            } else {
                /*
                 * Send bit '0':
                 * high time is shorter than low time.
                 */
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop");

                P1_1 = 0;
                __asm__(
                    "nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop"
                    "\nnop\nnop\nnop\nnop\nnop"
                );
            }

            b <<= 1;
        }
    }

    /*
     * Keep the line low for more than 50 us
     * so WS2812B latches the received frame.
     */
    P1_1 = 0;
    delay_ms(1);

    EA = 1;
}


/*
 * Fill the whole LED buffer with one solid color.
 *
 * Parameters are in GRB order because WS2812B expects:
 *   Green, Red, Blue
 */
void fillSolid(uint8_t g, uint8_t r, uint8_t bl) {
    uint16_t k;

    for (k = 0; k < BUFFER_SIZE; k += 3) {
        led_buffer[k]     = g;
        led_buffer[k + 1] = r;
        led_buffer[k + 2] = bl;
    }
}


/*
 * System initialization.
 *
 * This function:
 *   1. Sets the MCU clock to 24 MHz.
 *   2. Configures the WS2812B output pin.
 *   3. Shows a short green boot test.
 *   4. Initializes UART0 for Bluetooth communication.
 */
void setup(void) {
    SAFE_MOD  = 0x55;
    SAFE_MOD  = 0xAA;
    CLOCK_CFG = 0x06;
    SAFE_MOD  = 0x00;

    P1_MOD_OC &= ~(1 << LED_PIN);
    P1_DIR_PU |=  (1 << LED_PIN);

    P1_1 = 0;
    delay_ms(50);

    /*
     * Boot test:
     * green means the MCU and LED matrix are working.
     */
    fillSolid(180, 0, 0);
    WS2812B_Show();
    delay_ms(1000);

    fillSolid(0, 0, 0);
    WS2812B_Show();
    delay_ms(200);

    UART0_Init();
}


/*
 * Main loop.
 *
 * The MCU always waits for one complete frame before updating the LEDs.
 * This keeps UART reception and WS2812B output separated.
 */
void loop(void) {
    UART0_SendByte(ACK_READY);

    if (ReceiveFrame()) {
        WS2812B_Show();
        UART0_SendByte(ACK_OK);
    } else {
        UART0_SendByte(ACK_ERR);

        /*
         * Dim red indicates a receive error.
         * This helps debug Bluetooth or UART issues visually.
         */
        fillSolid(0, 30, 0);
        WS2812B_Show();
        delay_ms(100);
    }
}