/**
 * ============================================================
 *  WS2812B Test — CH552T @ 24MHz
 *  Không có Bluetooth, chỉ test LED đơn giản
 *
 *  Chương trình chạy tuần tự:
 *    1. Sáng đỏ toàn bộ   (1 giây)
 *    2. Sáng xanh lá      (1 giây)
 *    3. Sáng xanh dương   (1 giây)
 *    4. Chạy đuổi trắng   (từng LED một)
 *    5. Tắt hết           (1 giây)
 *    → Lặp lại
 * ============================================================ */

#include <stdint.h>

#define LED_PIN_NUM  1
#define NUM_LEDS     256
#define BUFFER_SIZE  768   // 256 × 3 bytes (GRB)

__xdata uint8_t led_buffer[BUFFER_SIZE];

/* ============================================================
   DELAY — dùng vòng lặp đơn giản, không cần Timer
   Mỗi đơn vị ≈ 1ms tại 24MHz
   ============================================================ */
void delay_ms(uint16_t ms)
{
    uint16_t i, j;
    for (i = 0; i < ms; i++)
        for (j = 0; j < 2000; j++);  // ~1ms tại 24MHz 1T
}

/* ============================================================
   WS2812B_Show — Bit-bang ra P1.1
   ============================================================ */
void WS2812B_Show(void)
{
    uint16_t i;
    uint8_t  j, b;

    EA = 0;

    for (i = 0; i < BUFFER_SIZE; i++) {
        b = led_buffer[i];
        for (j = 0; j < 8; j++) {
            if (b & 0x80) {
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop"
                        "\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                __asm__("nop\nnop\nnop\nnop");
            } else {
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop"
                        "\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
            }
            b <<= 1;
        }
    }

    EA = 1;
}

/* ============================================================
   Helpers — fill màu và clear
   ============================================================ */
void fill_color(uint8_t r, uint8_t g, uint8_t b)
{
    uint16_t i;
    for (i = 0; i < BUFFER_SIZE; i += 3) {
        led_buffer[i]     = g;   // WS2812B: GRB
        led_buffer[i + 1] = r;
        led_buffer[i + 2] = b;
    }
}

void set_pixel(uint16_t idx, uint8_t r, uint8_t g, uint8_t b)
{
    uint16_t pos = idx * 3;
    led_buffer[pos]     = g;
    led_buffer[pos + 1] = r;
    led_buffer[pos + 2] = b;
}

void clear_all(void)
{
    uint16_t i;
    for (i = 0; i < BUFFER_SIZE; i++)
        led_buffer[i] = 0;
}

/* ============================================================
   SETUP
   ============================================================ */
void setup(void)
{
    P1_MOD_OC &= ~(1 << LED_PIN_NUM);
    P1_DIR_PU  |= (1 << LED_PIN_NUM);
    P1_1 = 0;

    // Reset pulse cho WS2812B khi mới bật
    delay_ms(10);
}

/* ============================================================
   LOOP
   ============================================================ */
void loop(void)
{
    uint16_t i;

    // 1. Đỏ toàn bộ
    fill_color(255, 0, 0);
    WS2812B_Show();
    delay_ms(1000);

    // 2. Xanh lá toàn bộ
    fill_color(0, 255, 0);
    WS2812B_Show();
    delay_ms(1000);

    // 3. Xanh dương toàn bộ
    fill_color(0, 0, 255);
    WS2812B_Show();
    delay_ms(1000);

    // 4. Chạy đuổi trắng — từng LED sáng lên rồi tắt
    clear_all();
    for (i = 0; i < NUM_LEDS; i++) {
        if (i > 0) set_pixel(i - 1, 0, 0, 0);   // tắt LED trước
        set_pixel(i, 128, 128, 128);              // sáng LED hiện tại (trắng 50%)
        WS2812B_Show();
        delay_ms(20);
    }

    // 5. Tắt hết
    clear_all();
    WS2812B_Show();
    delay_ms(1000);
}