#include <stdint.h>

#define NUM_LEDS 256
#define BUFFER_SIZE 768     

#define SOF1 0xA5
#define SOF2 0x5A
#define ACK_READY 'R'
#define ACK_OK 'K'
#define ACK_ERR 'E'

__xdata uint8_t led_buffer[BUFFER_SIZE];
__data  uint16_t i;
__data  uint8_t  b, j;

// Software delay
void delay_ms(uint16_t ms) {
    uint16_t x, y;
    for (x = 0; x < ms; x++)
        for (y = 0; y < 2000; y++)
            __asm__("nop");
}

// UART0 Init: 115200 baud @ 24MHz 1T 
void UART0_Init(void) {
    T2MOD |= bTMR_CLK | bT1_CLK; // Timer1 dùng Fsys trực tiếp (1T)
    TMOD &= ~0xF0;
    TMOD |= bT1_M1; // Timer1 Mode 2 (8-bit auto-reload)
    PCON |= SMOD; // SMOD=1 -> baud x 2
    TH1 = 243; TL1 = 243; // 256 - 13 = 243 -> ~115384 baud, err ~0.16%
    TF1 = 0; TR1 = 1;

    SM0 = 0; SM1 = 1; // UART0 Mode 1, 8N1
    REN = 1; 
    TI = 0; RI = 0;

    // P3.1 (TXD0) push-pull output
    P3_MOD_OC &= ~(1 << 1);
    P3_DIR_PU |= (1 << 1);

    ES = 0; // polling UART, no UART interrupt
    EA = 1;
}

// Pure polling UART helpers 
void UART0_SendByte(uint8_t v) {
    SBUF = v;
    while (!TI);
    TI = 0;
}

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

// Receive exactly one 16x16 GRB frame, 1 -> OK, 0 -> timeout/header/checksum error.
uint8_t ReceiveFrame(void) {
    uint8_t v;
    uint16_t k;
    uint16_t sum_calc = 0;
    uint16_t sum_rx;
    uint8_t lo, hi;

    // Tìm header A5 5A. Timeout dài hơn để chờ PC mở kết nối Bluetooth.
    while (1) {
        if (!UART0_ReadByteTimeout(&v, 60000U)) return 0;
        if (v == SOF1) {
            if (!UART0_ReadByteTimeout(&v, 3000U)) return 0;
            if (v == SOF2) break;
        }
    }

    // Receive 768 byte GRB, but DO NOT show yet. 
    for (k = 0; k < BUFFER_SIZE; k++) {
        if (!UART0_ReadByteTimeout(&v, 3000U)) return 0;
        led_buffer[k] = v;
        sum_calc += v;
    }

    // Checksum16 little-endian: sum(payload) & 0xFFFF
    if (!UART0_ReadByteTimeout(&lo, 3000U)) return 0;
    if (!UART0_ReadByteTimeout(&hi, 3000U)) return 0;
    sum_rx = (uint16_t)lo | ((uint16_t)hi << 8);

    return (sum_calc == sum_rx) ? 1 : 0;
}

// WS2812B Bit-banging @ 24MHz 1T 
void WS2812B_Show(void) {
    EA = 0;
    for (i = 0; i < BUFFER_SIZE; i++) {
        b = led_buffer[i];
        for (j = 0; j < 8; j++) {
            if (b & 0x80) {
                // T1H ≈ 708 ns
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop"
                        "\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                // T1L ≈ 416 ns
                __asm__("nop\nnop\nnop\nnop\nnop\nnop");
            } else {
                // T0H ≈ 292 ns
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                // T0L ≈ 708 ns
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop"
                        "\nnop\nnop\nnop\nnop\nnop");
            }
            b <<= 1;
        }
    }
    P1_1 = 0;
    delay_ms(1); // reset/latch > 50 us
    EA = 1;
}

// Helpers 
void fillSolid(uint8_t g, uint8_t r, uint8_t bl) {
    uint16_t k;
    for (k = 0; k < BUFFER_SIZE; k += 3) {
        led_buffer[k]   = g;
        led_buffer[k+1] = r;
        led_buffer[k+2] = bl;
    }
}

void setup(void) {
    SAFE_MOD  = 0x55;
    SAFE_MOD  = 0xAA;
    CLOCK_CFG = 0x06; // 24 MHz
    SAFE_MOD  = 0x00;

    P1_MOD_OC &= ~(1 << 1);
    P1_DIR_PU  |= (1 << 1);
    P1_1 = 0;
    delay_ms(50);

    // Boot test: green 1s = MCU + WS2812B alive
    fillSolid(180, 0, 0);
    WS2812B_Show();
    delay_ms(1000);

    fillSolid(0, 0, 0);
    WS2812B_Show();
    delay_ms(200);

    UART0_Init();
}

void loop(void) {
    // Ready handshake: PC only sends a new frame after receiving this byte.
    UART0_SendByte(ACK_READY);

    if (ReceiveFrame()) {
        // Received a complete frame, UART is idle -> safe to bit-bang WS2812B.
        WS2812B_Show();

        // ACK -> 'R' (ready) -> frame -> 'K' (OK) -> 'R' (ready) -> frame -> ...
        UART0_SendByte(ACK_OK);
    } else {
        // Frame error / timeout -> RED
        UART0_SendByte(ACK_ERR);
        fillSolid(0, 30, 0);
        WS2812B_Show();
        delay_ms(100);
    }
}