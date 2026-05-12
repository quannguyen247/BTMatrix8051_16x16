#include <stdint.h>

#define LED_PIN_NUM 1
#define NUM_LEDS    256
#define BUFFER_SIZE 768

__xdata uint8_t led_buffer[BUFFER_SIZE];
__data uint16_t i;
__data uint8_t  b, j;
volatile uint16_t rx_index   = 0;
volatile uint8_t  frame_ready = 0;

void delay_ms(uint16_t ms) {
    uint16_t x, y;
    for (x = 0; x < ms; x++)
        for (y = 0; y < 2000; y++) __asm__("nop");
}

void UART0_Init(void) {
    T2MOD |= bTMR_CLK | bT1_CLK;
    SM0 = 0; SM1 = 1; REN = 1;
    TMOD &= ~0xF0; TMOD |= bT1_M1;
    PCON |= SMOD;
    TH1 = 243; TL1 = 243;
    TF1 = 0; TR1 = 1;
    TI = 0; RI = 0;
    ES = 1; EA = 1;
}

void UART0_SendByte(uint8_t dat) {
    TI = 0; SBUF = dat; while (!TI); TI = 0;
}

void UART0_ISR(void) __interrupt(INT_NO_UART0) __using(1) {
    if (RI) {
        RI = 0;
        if (!frame_ready && (rx_index < BUFFER_SIZE)) {
            led_buffer[rx_index++] = SBUF;
            if (rx_index >= BUFFER_SIZE) frame_ready = 1;
        }
    }
    if (TI) TI = 0;
}

void WS2812B_Show(void) {
    EA = 0;
    for (i = 0; i < BUFFER_SIZE; i++) {
        b = led_buffer[i];
        for (j = 0; j < 8; j++) {
            if (b & 0x80) {
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                __asm__("nop\nnop");
            } else {
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
            }
            b <<= 1;
        }
    }
    P1_1 = 0;
    delay_ms(1);
    EA = 1;
}

void setup() {
    SAFE_MOD = 0x55; SAFE_MOD = 0xAA;
    CLOCK_CFG = 0x06;
    SAFE_MOD = 0x00;

    P1_MOD_OC &= ~(1 << LED_PIN_NUM);
    P1_DIR_PU  |= (1 << LED_PIN_NUM);
    P1_1 = 0;
    delay_ms(50);

    for (i = 0; i < BUFFER_SIZE; i += 3) {
        led_buffer[i] = 0; led_buffer[i+1] = 255; led_buffer[i+2] = 0;
    }
    WS2812B_Show();
    delay_ms(2000);

    UART0_Init();
    UART0_SendByte('K');
}

void loop() {
    uint8_t r = 0, g = 0, bl = 0;

    if (frame_ready) {
        WS2812B_Show();
        EA = 0; rx_index = 0; frame_ready = 0; EA = 1;
        UART0_SendByte('K');
        return;
    }

    if      (rx_index == 0)   r  = 255;  // Đỏ: chưa nhận gì
    else if (rx_index < 256)  g  = 255;  // Xanh lá: nhận 1-255
    else                      bl = 255;  // Xanh dương: nhận 256-767

    for (i = 0; i < BUFFER_SIZE; i += 3) {
        led_buffer[i] = g; led_buffer[i+1] = r; led_buffer[i+2] = bl;
    }
    WS2812B_Show();
    delay_ms(100);
}