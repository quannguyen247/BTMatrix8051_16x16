/**
 * ============================================================
 * WS2812B LED Controller — CH552T @ 24MHz
 * ============================================================
 * Giao thức : UART 115200 baud (Bluetooth / USB-Serial)
 * Output    : 256x WS2812B bit-bang trên P1.1
 * Compiler  : SDCC (Small Device C Compiler)
 *
 * TIMING CỦA CPU (1T mode — bắt buộc phải set):
 * 1 machine cycle  = 1 / 24,000,000 Hz = 41.67 ns
 * SETB / CLR P1.x  ≈ 2 cycles         = 83 ns
 * NOP              = 1 cycle          = 41.67 ns
 * Loop overhead    ≈ 6 cycles         = 250 ns
 *
 * CÁC LỖI ĐÃ FIX:
 * [F1] TH1 = 243 -> 115200 baud chuẩn xác cho 24MHz (1T mode)
 * [F2] TL1 = 243 -> Sync ngay lập tức tránh mất byte đầu
 * [F3] ISR __using(1) -> Tối ưu ngắt cực ngắn
 * [F4] EA=0/1 reset -> Chống race condition
 * [F5] Reset Pulse 50us -> Đảm bảo LED chốt data
 * ============================================================
 */

#include <stdint.h>

/* ============================================================
   CẤU HÌNH PHẦN CỨNG
   ============================================================ */
#define LED_PIN_NUM 1
#define NUM_LEDS 256
#define BUFFER_SIZE 768 // 256 LEDs x 3 bytes (GRB)

/* ============================================================
   BIẾN TOÀN CỤC (XRAM 8KB)
   ============================================================ */
__xdata uint8_t led_buffer[BUFFER_SIZE];
volatile uint16_t rx_index = 0;
volatile uint8_t frame_ready = 0;

/* ============================================================
   UART0_Init — CH552T @ 24MHz → 115200 baud
   ============================================================ */
void UART0_Init(void)
{
    // Bật 1T mode cho Timer 1
    T2MOD |= bTMR_CLK | bT1_CLK;

    SM0 = 0; // UART Mode 1
    SM1 = 1;
    REN = 1; // Bật nhận

    TMOD &= ~0xF0;
    TMOD |= bT1_M1; // Mode 2: 8-bit auto-reload

    PCON |= SMOD; // Nhân đôi baud rate

    // 24,000,000 / (32 * (256 - 243)) = 115,384 (~0.16% error)
    TH1 = 243;
    TL1 = 243; 

    TF1 = 0;
    TR1 = 1; // Start Timer 1

    TI = 0;
    RI = 0;

    ES = 1; // Bật ngắt UART0
    EA = 1; // Bật ngắt toàn cục
}

void UART0_SendByte(uint8_t dat)
{
    TI = 0;
    SBUF = dat;
    while(!TI);
    TI = 0;
}

void UART0_ISR(void) __interrupt(INT_NO_UART0) __using(1)
{
    if(RI) {
        RI = 0;
        if(!frame_ready && (rx_index < BUFFER_SIZE)) {
            led_buffer[rx_index++] = SBUF;
            if(rx_index >= BUFFER_SIZE) {
                frame_ready = 1;
            }
        }
    }
    if(TI) TI = 0;
}

/* ============================================================
   WS2812B_Show — Bit-bang trực tiếp ra P1.1
   ============================================================ */
void WS2812B_Show(void)
{
    uint16_t i;
    uint8_t j, b;
    uint16_t delay_latch = 200; // Delay reset pulse > 50us

    EA = 0; // Tắt ngắt bảo vệ timing

    for(i = 0; i < BUFFER_SIZE; i++) {
        b = led_buffer[i];
        for(j = 0; j < 8; j++) {
            if(b & 0x80) {
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                __asm__("nop\nnop\nnop\nnop");
            } else {
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
            }
            b <<= 1;
        }
    }

    // Reset pulse để IC chốt màu
    P1_1 = 0;
    while(delay_latch--) {
        __asm__("nop");
    }

    EA = 1; // Bật lại ngắt
}

void setup(void)
{
    // Cấu hình P1.1 Push-Pull
    P1_MOD_OC &= ~(1 << LED_PIN_NUM);
    P1_DIR_PU |= (1 << LED_PIN_NUM);
    P1_1 = 0;

    UART0_Init();
    UART0_SendByte('K'); // Handshake
}

void loop(void)
{
    if(frame_ready) {
        WS2812B_Show();

        // Reset buffer an toàn
        EA = 0;
        rx_index = 0;
        frame_ready = 0;
        EA = 1;

        UART0_SendByte('K'); // Sẵn sàng frame tiếp theo
    }
}