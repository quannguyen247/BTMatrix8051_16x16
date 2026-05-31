#include <stdint.h>

#define NUM_LEDS 256
#define BUFFER_SIZE 768

__xdata uint8_t led_buffer[BUFFER_SIZE];
__data uint16_t i;
__data uint8_t b, j;

void delay_ms(uint16_t ms) {
    uint16_t x, y;
    for (x = 0; x < ms; x++)
        for (y = 0; y < 2000; y++)
            __asm__("nop");
}

uint8_t testByte(uint16_t k) {
    uint8_t pixel = (uint8_t)(k / 3);
    uint8_t ch = (uint8_t)(k % 3);
    if (pixel < 64)       return (ch == 1) ? 180 : 0;
    else if (pixel < 128) return (ch == 0) ? 180 : 0;
    else if (pixel < 192) return (ch == 2) ? 180 : 0;
    else                  return 60;
}

void UART0_Init(void) {
    T2MOD |= bTMR_CLK | bT1_CLK;
    TMOD &= ~0xF0;
    TMOD |= bT1_M1;
    PCON |= SMOD;
    TH1 = 243; TL1 = 243;
    TF1 = 0; TR1 = 1;

    SM0 = 0; SM1 = 1;
    REN = 1;
    TI = 0; RI = 0;

    P3_MOD_OC &= ~(1 << 1);
    P3_DIR_PU |= (1 << 1);

    ES = 0;
    EA = 1;
}

uint16_t doLoopback(void) {
    uint16_t tx_k = 0;
    uint16_t rx_k = 0;
    uint16_t guard = 0;

    TI = 0; RI = 0;
    SBUF = testByte(tx_k++);

    while (rx_k < BUFFER_SIZE) {
        if (tx_k < BUFFER_SIZE && TI) {
            TI = 0;
            SBUF = testByte(tx_k++);
        }

        if (RI) {
            RI = 0;
            led_buffer[rx_k++] = SBUF;
            guard = 0;
            continue;
        }

        if (++guard > 60000U) break;
    }

    return rx_k;
}

void WS2812B_Show(void) {
    EA = 0;
    for (i = 0; i < BUFFER_SIZE; i++) {
        b = led_buffer[i];
        for (j = 0; j < 8; j++) {
            if (b & 0x80) {
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop"
                        "\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop");
            } else {
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop"
                        "\nnop\nnop\nnop\nnop\nnop");
            }
            b <<= 1;
        }
    }
    P1_1 = 0;
    delay_ms(1);
    EA = 1;
}

void fillSolid(uint8_t green, uint8_t red, uint8_t blue) {
    uint16_t k;
    for (k = 0; k < BUFFER_SIZE; k += 3) {
        led_buffer[k]   = green;
        led_buffer[k+1] = red;
        led_buffer[k+2] = blue;
    }
}

void setup(void) {
    SAFE_MOD  = 0x55;
    SAFE_MOD  = 0xAA;
    CLOCK_CFG = 0x06;
    SAFE_MOD  = 0x00;

    P1_MOD_OC &= ~(1 << 1);
    P1_DIR_PU  |= (1 << 1);
    P1_1 = 0;
    delay_ms(50);

    fillSolid(180, 0, 0);
    WS2812B_Show();
    delay_ms(2000);

    fillSolid(0, 0, 0);
    WS2812B_Show();
    delay_ms(300);

    UART0_Init();
}

void loop(void) {
    uint16_t received = doLoopback();

    if (received == BUFFER_SIZE) {
        WS2812B_Show();
        delay_ms(800);
    } else if (received == 0) {
        fillSolid(0, 180, 0);
        WS2812B_Show();
        delay_ms(1200);
    } else {
        uint8_t brightness = (uint8_t)((uint32_t)received * 180 / BUFFER_SIZE);
        fillSolid(0, 0, brightness);
        WS2812B_Show();
        delay_ms(1200);
    }
}