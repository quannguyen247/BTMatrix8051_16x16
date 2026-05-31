#include <stdint.h>

#define NUM_LEDS    256
#define BUFFER_SIZE 768

__xdata uint8_t led_buffer[BUFFER_SIZE];
__data uint16_t i;
__data uint8_t b, j, step = 0;

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

void setRainbowPixel(uint16_t idx, uint8_t pos) {
    uint16_t p = idx * 3;
    if (p >= BUFFER_SIZE) return;

    if (pos < 85) {
        led_buffer[p]     = 0;
        led_buffer[p + 1] = 255 - pos * 3;
        led_buffer[p + 2] = pos * 3;
    } else if (pos < 170) {
        pos -= 85;
        led_buffer[p]     = pos * 3;
        led_buffer[p + 1] = 0;
        led_buffer[p + 2] = 255 - pos * 3;
    } else {
        pos -= 170;
        led_buffer[p]     = 255 - pos * 3;
        led_buffer[p + 1] = pos * 3;
        led_buffer[p + 2] = 0;
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
    for (i = 0; i < NUM_LEDS; i++) {
        setRainbowPixel(i, (uint8_t)(i + step));
    }

    WS2812B_Show();
    
    step += 2;
    delay_ms(10);
}