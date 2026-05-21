#include <stdint.h>

#define NUM_LEDS 256
#define BUFFER_SIZE 768

#define SOF1 0xA5
#define SOF2 0x5A
#define ACK_READY 'R'
#define ACK_OK 'K'
#define ACK_ERR 'E' 

__xdata uint8_t led_buffer[BUFFER_SIZE];
__data uint16_t i; // Run through 768 bytes (select byte)
__data uint8_t b, j; // Current sending byte & bit index

// Software delay
void delay_ms(uint16_t ms) {
    uint16_t x, y;
    for (x = 0; x < ms; x++)
        for (y = 0; y < 2000; y++)
            __asm__("nop");
}

// UART0 Init: 115200 baud @ 24MHz 1T 
void UART0_Init(void) {
    T2MOD |= bTMR_CLK | bT1_CLK; // 24MHz 1T Fsys
    TMOD &= ~0xF0; // Clear Timer1
    TMOD |= bT1_M1; // Timer1 Mode 2 (8-bit auto-reload)
    PCON |= SMOD; // SMOD=1 (double baud factor)
    TH1 = 243; TL1 = 243; // ~115384 baud, err ~0.16%
    TF1 = 0; TR1 = 1; // Clear overflow flag, start Timer1

    SM0 = 0; SM1 = 1; // UART0 Mode 1, 8N1
    REN = 1; // Enable UART0 receiver
    TI = 0; RI = 0; // Clear UART0 flags

    // Config P3.1 (TXD0)
    P3_MOD_OC &= ~(1 << 1);
    P3_DIR_PU |= (1 << 1);

    ES = 0; // Polling UART (no interrupt)
    EA = 1; // Enable global interrupt
}

// Send through UART0 using polling (R/K/E -> PC)
void UART0_SendByte(uint8_t v) {
    SBUF = v;
    while (!TI);
    TI = 0;
}

// Read 1 byte from UART0 with timeout: 1 -> OK, 0 -> timeout
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

// Receive 16x16 GRB frame (A5 5A + 768 byte GRB + checksum low + checksum high): 1 -> OK, 0 -> ERR
uint8_t ReceiveFrame(void) {
    uint8_t v; // Byte read from UART0
    uint16_t k; // Payload byte index
    uint16_t sum_calc = 0; // Checksum calculated from payload
    uint16_t sum_rx; // Checksum received from UART0 (PC)
    uint8_t lo, hi; // 2 byte checksum low/high

    // Find header A5 5A
    while (1) {
        if (!UART0_ReadByteTimeout(&v, 60000U)) return 0;
        if (v == SOF1) {
            if (!UART0_ReadByteTimeout(&v, 3000U)) return 0;
            if (v == SOF2) break;
        }
    }

    // Receive 768 byte GRB 
    for (k = 0; k < BUFFER_SIZE; k++) {
        if (!UART0_ReadByteTimeout(&v, 3000U)) return 0;
        led_buffer[k] = v;  
        sum_calc += v;
    }

    // Receive low/high checksum from UART0 (PC)
    if (!UART0_ReadByteTimeout(&lo, 3000U)) return 0;
    if (!UART0_ReadByteTimeout(&hi, 3000U)) return 0;
    sum_rx = (uint16_t)lo | ((uint16_t)hi << 8);

    return (sum_calc == sum_rx) ? 1 : 0;
}

// WS2812B Bit-banging @ 24MHz 1T (HIGH long, LOW short for '1', HIGH short, LOW long for '0')
void WS2812B_Show(void) {
    EA = 0; // Disable global interrupt for precise timing
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

    // Reset/latch > 50 us
    P1_1 = 0;
    delay_ms(1); 
    EA = 1; // Re-enable global interrupt
}

// Debug helper
void fillSolid(uint8_t green, uint8_t red, uint8_t blue) {
    uint16_t k;
    for (k = 0; k < BUFFER_SIZE; k += 3) {
        led_buffer[k]   = green;
        led_buffer[k+1] = red;
        led_buffer[k+2] = blue;
    }
}

void setup(void) {
    // Clock config (unlock & relock)
    SAFE_MOD  = 0x55;
    SAFE_MOD  = 0xAA;
    CLOCK_CFG = 0x06; // 24 MHz
    SAFE_MOD  = 0x00;

    // P1.1 config for WS2812B DI
    P1_MOD_OC &= ~(1 << 1);
    P1_DIR_PU |= (1 << 1);
    P1_1 = 0;
    delay_ms(50);

    // Boot test: GREEN 1s = MCU + WS2812B OK
    fillSolid(180, 0, 0);
    WS2812B_Show();
    delay_ms(1000);

    fillSolid(0, 0, 0);
    WS2812B_Show();
    delay_ms(200);

    UART0_Init(); // Init UART0 for communication
}

// Main loop
void loop(void) {
    UART0_SendByte(ACK_READY); 

    if (ReceiveFrame()) {
        // Received OK -> safe to bit-bang WS2812B.
        WS2812B_Show();
        UART0_SendByte(ACK_OK);
    } else {
        // Frame error / timeout -> RED
        UART0_SendByte(ACK_ERR);
        fillSolid(0, 30, 0);
        WS2812B_Show();
        delay_ms(100);
    }
}