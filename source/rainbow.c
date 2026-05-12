
#include <stdint.h>

#define LED_PIN_NUM 1
#define NUM_LEDS    256
#define BUFFER_SIZE 768

// Ép mảng vào xdata
__xdata uint8_t led_buffer[BUFFER_SIZE];

// Ép các biến điều khiển vào data (RAM nội - cực nhanh và không tốn xdata)
__data uint16_t i; 
__data uint8_t j, b, step = 0;

void delay_ms(uint16_t ms) {
    uint16_t x, y;
    for (x = 0; x < ms; x++)
        for (y = 0; y < 2000; y++) __asm__("nop");
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
    EA = 1;
}

void set_pixel(uint16_t idx, uint8_t r, uint8_t g, uint8_t b) {
    uint16_t pos = idx * 3;
    if (pos < BUFFER_SIZE) {
        led_buffer[pos] = g; 
        led_buffer[pos+1] = r;
        led_buffer[pos+2] = b;
    }
}

void setup() {
    // Ép xung 24MHz
    SAFE_MOD = 0x55; SAFE_MOD = 0xAA;
    CLOCK_CFG = 0x06; 
    SAFE_MOD = 0x00;

    P1_MOD_OC &= ~(1 << LED_PIN_NUM);
    P1_DIR_PU |= (1 << LED_PIN_NUM);
    P1_1 = 0;

    delay_ms(50);
}

void loop() {
    for (i = 0; i < NUM_LEDS; i++) {
        uint8_t wheel_pos = (uint8_t)(i + step);
        // Rainbow mờ để tiết kiệm nguồn và RAM
        if (wheel_pos < 85) set_pixel(i, 20, 0, 0);
        else if (wheel_pos < 170) set_pixel(i, 0, 20, 0);
        else set_pixel(i, 0, 0, 20);
    }
    
    WS2812B_Show();
    step++;
    delay_ms(10);
}