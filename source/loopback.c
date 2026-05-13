/**
 * UART0 Loopback Test – Pure Polling (không dùng interrupt cho TX/RX)
 * =====================================================================
 * Chập P3.1 (TXD0) → P3.0 (RXD0).
 *
 *  XANH LÁ 2s  → MCU + WS2812B sống
 *  RAINBOW      → ✅ Loopback OK, UART đúng baud, đúng wiring
 *  ĐỎ           → ❌ Không nhận được data (chưa chập dây / sai baud)
 *  XANH DƯƠNG   → ⚠ Nhận một phần rồi timeout (baud lệch / noise)
 *
 * Fix so với v1:
 *   - Bỏ tx_done flag + interrupt cho TX: interrupt TX không fire → treo mãi
 *   - Thay bằng pure polling TI + RI xen kẽ trong doLoopback()
 *   - Thêm chẩn đoán 3 màu dựa vào số byte nhận được khi timeout
 */

#include <stdint.h>

#define LED_PIN     1
#define NUM_LEDS    256
#define BUFFER_SIZE 768     // 256 LED × 3 byte GRB

__xdata uint8_t led_buffer[BUFFER_SIZE];
__data  uint16_t i;
__data  uint8_t  b, j;

// ─── Delay ───────────────────────────────────────────────────────────────────
void delay_ms(uint16_t ms) {
    uint16_t x, y;
    for (x = 0; x < ms; x++)
        for (y = 0; y < 2000; y++)
            __asm__("nop");
}

// ─── Tính byte test tại index k (rainbow GRB, 4 band màu) ───────────────────
//   pixel 0–63   : ĐỎ   (GRB: 0, 180, 0)
//   pixel 64–127 : XANH LÁ  (GRB: 180, 0, 0)
//   pixel 128–191: XANH DƯƠNG (GRB: 0, 0, 180)
//   pixel 192–255: TRẮNG mờ  (GRB: 60, 60, 60)
uint8_t testByte(uint16_t k) {
    uint8_t pixel = (uint8_t)(k / 3);
    uint8_t ch    = (uint8_t)(k % 3);     // 0=G, 1=R, 2=B
    if      (pixel < 64)  return (ch == 1) ? 180 : 0;
    else if (pixel < 128) return (ch == 0) ? 180 : 0;
    else if (pixel < 192) return (ch == 2) ? 180 : 0;
    else                  return 60;
}

// ─── UART0 Init: 115200 baud @ 24MHz 1T ──────────────────────────────────────
void UART0_Init(void) {
    T2MOD |= bTMR_CLK | bT1_CLK;   // Timer1 dùng Fsys trực tiếp (1T)
    TMOD  &= ~0xF0;
    TMOD  |=  bT1_M1;               // Timer1 Mode 2 (8-bit auto-reload)
    PCON  |=  SMOD;                 // SMOD=1 → baud × 2
    TH1    = 243; TL1 = 243;        // 256 − 13 = 243 → 115384 baud (err 0.16%)
    TF1 = 0; TR1 = 1;

    SM0 = 0; SM1 = 1;               // UART0 Mode 1
    REN = 1;                        // enable receiver
    TI  = 0; RI = 0;

    // P3.1 (TXD0) push-pull output
    P3_MOD_OC &= ~(1 << 1);
    P3_DIR_PU  |= (1 << 1);

    ES = 0;                         // polling mode: KHÔNG dùng UART interrupt
    EA = 1;
}

// ─── Pure Polling Loopback ───────────────────────────────────────────────────
//  TX và RX được poll xen kẽ trong cùng 1 vòng lặp.
//  Không cần interrupt → không có race condition.
//
//  Trả về số byte RX nhận được:
//    = BUFFER_SIZE (768) → thành công
//    < 768              → timeout (bao nhiêu byte nhận được trước khi chết)
//
uint16_t doLoopback(void) {
    uint16_t tx_k   = 0;
    uint16_t rx_k   = 0;
    uint16_t guard  = 0;       // timeout counter reset mỗi lần nhận 1 byte

    TI = 0; RI = 0;

    // Kick byte đầu tiên
    SBUF = testByte(tx_k++);

    while (rx_k < BUFFER_SIZE) {

        // ── TX: gửi byte tiếp theo khi UART TX rảnh ──────────────────────
        if (tx_k < BUFFER_SIZE && TI) {
            TI = 0;
            SBUF = testByte(tx_k++);
            // Không cần delay: 115200 baud → 1 byte ≈ 87µs
            // CPU @ 24MHz xử lý vòng lặp này rất nhanh (~µs)
        }

        // ── RX: lưu byte khi UART RX có data ─────────────────────────────
        if (RI) {
            RI = 0;
            led_buffer[rx_k++] = SBUF;
            guard = 0;          // reset timeout mỗi lần nhận được byte
            continue;
        }

        // ── Timeout: nếu không nhận được byte nào quá lâu ────────────────
        // ~300 iterations ≈ vài µs; 60000 iterations ≈ vài ms
        // Sau khi TX xong, RX nên về trong <1ms; nếu >50ms → lỗi
        if (++guard > 60000U) break;
    }

    return rx_k;
}

// ─── WS2812B Bit-bang @ 24MHz 1T ─────────────────────────────────────────────
void WS2812B_Show(void) {
    EA = 0;
    for (i = 0; i < BUFFER_SIZE; i++) {
        b = led_buffer[i];
        for (j = 0; j < 8; j++) {
            if (b & 0x80) {
                // T1H ≈ 708 ns (trong range 650–950 ns) ✓
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop"
                        "\nnop\nnop\nnop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                // T1L: 6nop + ~4cy overhead ≈ 416 ns (>220 ns min) ✓
                __asm__("nop\nnop\nnop\nnop\nnop\nnop");
            } else {
                // T0H ≈ 292 ns (>220 ns min) ✓
                P1_1 = 1;
                __asm__("nop\nnop\nnop\nnop\nnop");
                P1_1 = 0;
                // T0L: 13nop + ~4cy overhead ≈ 708 ns (>580 ns min) ✓
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

// ─── Helpers ─────────────────────────────────────────────────────────────────
void fillSolid(uint8_t g, uint8_t r, uint8_t bl) {
    uint16_t k;
    for (k = 0; k < BUFFER_SIZE; k += 3) {
        led_buffer[k]   = g;
        led_buffer[k+1] = r;
        led_buffer[k+2] = bl;
    }
}

// ─── Setup ───────────────────────────────────────────────────────────────────
void setup() {
    SAFE_MOD  = 0x55;
    SAFE_MOD  = 0xAA;
    CLOCK_CFG = 0x06;           // 24 MHz
    SAFE_MOD  = 0x00;

    P1_MOD_OC &= ~(1 << LED_PIN);
    P1_DIR_PU  |= (1 << LED_PIN);
    P1_1 = 0;
    delay_ms(50);

    // XANH LÁ = WS2812B + MCU sống
    fillSolid(180, 0, 0);
    WS2812B_Show();
    delay_ms(2000);

    // Tắt trước khi test
    fillSolid(0, 0, 0);
    WS2812B_Show();
    delay_ms(300);

    UART0_Init();
}

// ─── Loop ────────────────────────────────────────────────────────────────────
void loop() {
    uint16_t received = doLoopback();

    if (received == BUFFER_SIZE) {
        // ✅ Nhận đủ 768 byte → UART loopback OK
        //    led_buffer đã có rainbow data từ loopback
        WS2812B_Show();
        delay_ms(800);

    } else if (received == 0) {
        // ❌ Không nhận được gì → chưa chập dây / UART không TX
        fillSolid(0, 180, 0);       // ĐỎ: không có loopback
        WS2812B_Show();
        delay_ms(1200);

    } else {
        // ⚠ Nhận một phần rồi timeout → baud lệch / noise
        //   Hiển thị tỉ lệ nhận được: màu XANH DƯƠNG, độ sáng theo rx_k
        uint8_t brightness = (uint8_t)((uint32_t)received * 180 / BUFFER_SIZE);
        fillSolid(0, 0, brightness); // XANH DƯƠNG mờ→sáng tùy số byte nhận
        WS2812B_Show();
        delay_ms(1200);
    }
}