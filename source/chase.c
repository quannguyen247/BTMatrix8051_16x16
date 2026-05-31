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

void setPixel(uint16_t idx, uint8_t green, uint8_t red, uint8_t blue) {
    uint16_t pos = idx * 3;
    if (pos < BUFFER_SIZE) {
        led_buffer[pos]   = green;
        led_buffer[pos+1] = red;
        led_buffer[pos+2] = blue;
    }
}

void setup(void) {
    SAFE_MOD  = 0x55;
    SAFE_MOD  = 0xAA;
    CLOCK_CFG = 0x06;
    SAFE_MOD  = 0x00;

    P1_MOD_OC &= ~(1 << 1);
    P1_DIR_PU |= (1 << 1);
    P1_1 = 0;
    delay_ms(50);
}

void loop(void) {
    uint16_t k;

    fillSolid(0, 255, 0);
    WS2812B_Show();
    delay_ms(1000);

    fillSolid(255, 0, 0);
    WS2812B_Show();
    delay_ms(1000);

    fillSolid(0, 0, 255);
    WS2812B_Show();
    delay_ms(1000);

    fillSolid(0, 0, 0);
    for (k = 0; k < NUM_LEDS; k++) {
        if (k > 0) setPixel(k - 1, 0, 0, 0);
        setPixel(k, 128, 128, 128);
        WS2812B_Show();
        delay_ms(20);
    }

    fillSolid(0, 0, 0);
    WS2812B_Show();
    delay_ms(1000);
}