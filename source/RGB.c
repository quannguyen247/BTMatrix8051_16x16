
#include <stdint.h>

#define LED_PIN_NUM 1
#define NUM_LEDS    256
#define BUFFER_SIZE 768

// Ép buffer vào XRAM
__xdata uint8_t led_buffer[BUFFER_SIZE];

// Dùng RAM nội (data) cho các biến chạy để tối ưu tốc độ và bộ nhớ
__data uint16_t i;
__data uint8_t b, j, step = 0;

void delay_ms(uint16_t ms) {
    uint16_t x, y;
    for (x = 0; x < ms; x++)
        for (y = 0; y < 2000; y++) __asm__("nop");
}

/* ============================================================
   WS2812B_Show: Bit-bang chuẩn 24MHz
   ============================================================ */
void WS2812B_Show(void) {
    EA = 0; 
    for (i = 0; i < BUFFER_SIZE; i++) {
        b = led_buffer[i];
        for (j = 0; j < 8; j++) {
            if (b & 0x80) {
                P1_1 = 1; // T1H
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
                P1_1 = 0; // T1L
                __asm__("nop\nnop");
            } else {
                P1_1 = 1; // T0H
                __asm__("nop\nnop\nnop\nnop\nnop");
                P1_1 = 0; // T0L
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
            }
            b <<= 1;
        }
    }
    EA = 1;
}

/* ============================================================
   Hàm phối màu RGB (Wheel)
   pos: 0-255 đại diện cho vị trí trên vòng tròn màu
   ============================================================ */
void set_rainbow_pixel(uint16_t idx, uint8_t pos) {
    uint16_t p = idx * 3;
    if (p >= BUFFER_SIZE) return;

    if (pos < 85) {
        // G - R - B
        led_buffer[p]     = 0;            // Green
        led_buffer[p + 1] = 255 - pos * 3; // Red
        led_buffer[p + 2] = pos * 3;       // Blue
    } else if (pos < 170) {
        pos -= 85;
        led_buffer[p]     = pos * 3;       // Green
        led_buffer[p + 1] = 0;             // Red
        led_buffer[p + 2] = 255 - pos * 3; // Blue
    } else {
        pos -= 170;
        led_buffer[p]     = 255 - pos * 3; // Green
        led_buffer[p + 1] = pos * 3;       // Red
        led_buffer[p + 2] = 0;             // Blue
    }
}

void setup() {
    // Ép xung nội 24MHz (Nếu menu Tools chưa ăn)
    SAFE_MOD = 0x55; SAFE_MOD = 0xAA;
    CLOCK_CFG = 0x06; 
    SAFE_MOD = 0x00;

    // P1.1 Push-Pull
    P1_MOD_OC &= ~(1 << LED_PIN_NUM);
    P1_DIR_PU |= (1 << LED_PIN_NUM);
    P1_1 = 0;

    delay_ms(50);
}

void loop() {
    // Đổ màu cầu vồng dựa trên biến step
    for (i = 0; i < NUM_LEDS; i++) {
        // (i + step) tạo hiệu ứng màu dịch chuyển dọc dải LED
        set_rainbow_pixel(i, (uint8_t)(i + step));
    }

    WS2812B_Show();
    
    step += 2;   // Tăng step để màu "chạy"
    delay_ms(10); // Tốc độ chạy màu
}